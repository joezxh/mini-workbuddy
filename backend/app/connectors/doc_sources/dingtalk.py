"""钉钉文档源。

认证：``GET https://oapi.dingtalk.com/gettoken?appkey&appsecret`` 取 access_token。
令牌注入：本文件调用的是**新版**文档 OpenAPI（``api.dingtalk.com`` /v1.0/*），
要求以请求头 ``x-acs-dingtalk-access-token: <token>`` 传递（无 Bearer 前缀），
故用 ``token_in="header_raw"``；旧版 oapi 的 ``?access_token=`` 查询参数方式不适用，
沿用会导致 400「缺少参数：x-acs-dingtalk-access-token」。
枚举：知识库（workspaces）→ 节点（nodes/query）逐层下钻。
正文：按 nodeId 取内容，优先使用平台返回的 Markdown/纯文本。

⚠️ 权限约束（2026-10 核实）：
「获取知识库列表」``GET /v1.0/doc/workspaces`` 所需权限点 ``Document.Workspace.Read``
已被钉钉官方下线，新版开发者后台不再提供该权限的申请入口（报错里的申请链接是
死循环）。「查询目录树」``POST /v1.0/doc/nodes/query`` 只需
``Document.WorkspaceDocument.Read``（知识库文档读权限，可正常开通）。
因此**新应用必须走「知识库直连」模式**：凭据中填写知识库 ID + 操作人 UnionId，
连通测试与目录浏览直接基于目录树接口，不再依赖知识库列表接口。

⚠️ 注意：钉钉文档 OpenAPI 的「列表 / 取正文」端点随版本变动较快，
本文件已把路径抽成模块级常量（见下方 *_PATH），若线上报 404/参数错误，
只需按最新官方文档校正常量即可，不必改动调用逻辑。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.connectors.doc_sources.base import (
    BaseDocSource,
    CredField,
    DocConnResult,
    DocSourceError,
    ExternalDocRef,
    FetchDocResult,
    ProviderMeta,
    register_doc_source,
)
from app.connectors.doc_sources.binary import bytes_to_markdown, is_supported

TOKEN_HOST = "https://oapi.dingtalk.com"
API_HOST = "https://api.dingtalk.com"
TOKEN_PATH = "/gettoken"
WORKSPACES_PATH = "/v1.0/doc/workspaces"
NODES_QUERY_PATH = "/v1.0/doc/nodes/query"
NODE_CONTENT_PATH = "/v1.0/doc/nodes/{node_id}/content"
# 钉盘上传文件（docx / pptx / xlsx / pdf）的下载签名 URL；需 Storage.File.Read 权限。
# 该端点随版本变动较快，若线上报 404 只需按最新官方文档校正常量。
DENTRY_DOWNLOAD_PATH = "/v1.0/storage/spaces/{space_id}/dentries/{dentry_id}/downloadInfos"

# 上传型文件标识前缀（与在线文档 nodeId 区分）
FILE_PREFIX = "file:"


def _as_bool(value: Any, *, default: bool = False) -> bool:
    """凭据里的开关字段可能是布尔 / 字符串，统一解析（未填用默认）。"""
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "on")


class DingtalkDocSource(BaseDocSource):
    source_type = "dingtalk"
    # 新版文档 OpenAPI 要求令牌走专用请求头（无 Bearer 前缀）
    token_in = "header_raw"
    token_header_name = "x-acs-dingtalk-access-token"
    # /gettoken 等旧版端点用 errcode/errmsg 表达业务成败（HTTP 仍为 200）
    error_code_field = "errcode"

    async def _fetch_token(self) -> Optional[str]:
        app_key = self.credentials.get("app_key") or ""
        app_secret = self.credentials.get("app_secret") or ""
        if not (app_key and app_secret):
            raise DocSourceError("缺少 AppKey 或 AppSecret")
        data = await self._request_json(
            "GET", f"{TOKEN_HOST}{TOKEN_PATH}",
            params={"appkey": app_key, "appsecret": app_secret},
            with_token=False,
        )
        token = (data or {}).get("access_token")
        if not token:
            raise DocSourceError(f"获取 access_token 失败：{(data or {}).get('errmsg') or '未知错误'}")
        return token

    def _operator_id(self) -> str:
        """操作人 unionId：doc 系列接口的必传参数，来自凭据表单。"""
        return (self.credentials.get("operator_id") or "").strip()

    # ── 可选能力开关（对齐 WeKnora 文档 §3.5 的 settings）────────
    def _include_uploaded_files(self) -> bool:
        """是否导入钉盘上传的附件（docx / pptx / xlsx / pdf）。

        默认关闭：附件下载会产生额外存储与 embedding 成本，且需要额外申请
        ``Storage.File.Read`` 权限。
        """
        return _as_bool(self.credentials.get("include_uploaded_files"), default=False)

    def _preserve_folder_structure(self) -> bool:
        """是否把目录结构编码进文件名（``<工作区名>/<子目录>/…/<标题>``）。

        默认关闭，保证存量数据源升级后导入结果逐字节不变。
        """
        return _as_bool(self.credentials.get("preserve_folder_structure"), default=False)

    def _space_name(self) -> str:
        return (self.credentials.get("space_name") or "").strip()

    def _op_params(self, base: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """组装查询参数并附带 operatorId；doc 接口缺 operatorId 会报 400。"""
        q = dict(base or {})
        op = self._operator_id()
        if op:
            q["operatorId"] = op
        return q

    async def test_connection(self) -> DocConnResult:
        space_id = (self.credentials.get("space_id") or "").strip()
        try:
            await self._access_token()
            if space_id:
                # 知识库直连：只依赖「查询目录树」（Document.WorkspaceDocument.Read），
                # 新应用开通不了 Document.Workspace.Read，列表接口不可用
                if not self._operator_id():
                    return DocConnResult(
                        ok=False,
                        message="请填写操作人 UnionId：钉钉目录树接口必须携带 operatorId，"
                                "可在钉钉管理后台或「查询用户详情」接口获取成员 unionId",
                    )
                refs = await self._list_nodes(space_id, None, "")
                return DocConnResult(
                    ok=True,
                    message="连通成功：凭据有效（知识库直连模式）",
                    identity=f"知识库 {space_id} 可访问，根目录 {len(refs)} 个节点",
                )
            data = await self._request_json(
                "GET", f"{API_HOST}{WORKSPACES_PATH}", params=self._op_params({"maxResults": 1})
            )
            payload = (data or {}).get("data") or data or {}
            items = payload.get("workspaces") or payload.get("list") or []
            return DocConnResult(
                ok=True,
                message="连通成功：凭据有效",
                identity=f"可访问知识库 {len(items) if items else (payload.get('total') or 0)} 个",
            )
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=self._friendly_error(str(exc)))
        finally:
            await self.aclose()

    @staticmethod
    def _friendly_error(message: str) -> str:
        """对 Document.Workspace.Read 缺权限的已知死循环报错给出可操作指引。"""
        if "Document.Workspace.Read" in message:
            return (
                f"{message}。该权限点已被钉钉官方下线，新版开发者后台无法申请；"
                "请在上方「知识库 ID」填写目标知识库的 spaceId，并将「操作人 UnionId」"
                "设为对该知识库至少有「仅可查看」权限的成员，改用知识库直连模式"
                "（仅依赖已开通的 Document.WorkspaceDocument.Read 目录树权限）"
            )
        return message

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            if not parent_id:
                space_id = (self.credentials.get("space_id") or "").strip()
                if space_id:
                    # 直连模式：顶层直接展开指定知识库的根目录
                    root = self._space_name() or space_id if self._preserve_folder_structure() else ""
                    return await self._list_nodes(space_id, None, root)
                return await self._list_workspaces()
            workspace_id, node_id, parent_path = self._split_parent(parent_id)
            return await self._list_nodes(workspace_id, node_id, parent_path)
        finally:
            await self.aclose()

    async def _list_workspaces(self) -> List[ExternalDocRef]:
        data = await self._request_json(
            "GET", f"{API_HOST}{WORKSPACES_PATH}", params=self._op_params({"maxResults": 50})
        )
        payload = (data or {}).get("data") or data or {}
        items = payload.get("workspaces") or payload.get("list") or []
        return [
            ExternalDocRef(
                doc_id=str(w.get("workspaceId") or w.get("id")),
                title=w.get("name") or "未命名知识库",
                node_type="space",
            )
            for w in items
            if w.get("workspaceId") or w.get("id")
        ]

    async def _list_nodes(
        self, workspace_id: str, node_id: Optional[str], parent_path: str = ""
    ) -> List[ExternalDocRef]:
        body: Dict[str, Any] = {"workspaceId": workspace_id, "maxResults": 50}
        if node_id:
            body["parentNodeId"] = node_id
        data = await self._request_json(
            "POST", f"{API_HOST}{NODES_QUERY_PATH}",
            params=self._op_params(), json_body=body
        )
        payload = (data or {}).get("data") or data or {}
        items = payload.get("nodes") or payload.get("list") or []
        preserve = self._preserve_folder_structure()
        refs: List[ExternalDocRef] = []
        for n in items:
            nid = n.get("nodeId") or n.get("id")
            if not nid:
                continue
            node_type = n.get("nodeType") or ""
            has_child = bool(n.get("hasChild"))
            name = n.get("name") or n.get("title") or "未命名"
            if has_child or node_type == "FOLDER":
                # 开启目录结构保留时把路径编进 doc_id：下钻请求是独立实例，
                # 进程内缓存会丢失，只能随 ID 传递
                child_path = f"{parent_path}/{name}" if preserve and parent_path else (
                    name if preserve else ""
                )
                refs.append(
                    ExternalDocRef(
                        doc_id=f"{workspace_id}::{nid}" + (f"::{child_path}" if preserve else ""),
                        title=name,
                        node_type="folder",
                        parent_id=node_id or workspace_id,
                        updated_at=n.get("updateTime") or n.get("gmtModified"),
                    )
                )
                continue
            if node_type == "SHEET":
                # 钉钉表格无公开正文导出接口，跳过
                continue
            if node_type == "FILE":
                # 钉盘上传的附件：默认不导入（需 Storage.File.Read + 下载成本）
                if not self._include_uploaded_files():
                    continue
                refs.append(
                    ExternalDocRef(
                        # 文件名随 ID 传递：下载签名接口只认 dentryId，拿不到可读名称
                        doc_id=f"{FILE_PREFIX}{workspace_id}::{nid}::{name}",
                        title=name,
                        node_type="doc",
                        parent_id=node_id or workspace_id,
                        updated_at=n.get("updateTime") or n.get("gmtModified"),
                    )
                )
                continue
            if node_type not in ("DOC", "DOCX", ""):
                continue
            refs.append(
                ExternalDocRef(
                    doc_id=str(nid),
                    title=f"{parent_path}/{name}" if preserve and parent_path else name,
                    node_type="doc",
                    parent_id=node_id or workspace_id,
                    updated_at=n.get("updateTime") or n.get("gmtModified"),
                )
            )
        return refs

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            if doc_id.startswith(FILE_PREFIX):
                return await self._fetch_uploaded(doc_id[len(FILE_PREFIX):])
            data = await self._request_json(
                "GET", f"{API_HOST}{NODE_CONTENT_PATH}".format(node_id=doc_id),
                params=self._op_params()
            )
            payload = (data or {}).get("data") or data or {}
            # 不同版本返回的字段名不一致，按顺序取第一个非空值
            content = (
                payload.get("markdown")
                or payload.get("content")
                or payload.get("text")
                or ""
            )
            if not content:
                raise DocSourceError("该文档未返回可导入的文本内容")
            return FetchDocResult(
                title=payload.get("name") or payload.get("title") or "钉钉文档",
                markdown=content if content.endswith("\n") else content + "\n",
                updated_at=payload.get("updateTime") or payload.get("gmtModified"),
            )
        finally:
            await self.aclose()

    async def _fetch_uploaded(self, ref: str) -> FetchDocResult:
        """钉盘上传附件：申请签名下载 URL → 下载字节流 → 转 Markdown。"""
        parts = (ref or "").split("::", 2)
        workspace_id = parts[0] if parts else ""
        dentry_id = parts[1] if len(parts) > 1 else ref
        # 名称可能含 "::"，故第三段整体取用，缺失时用 dentryId 兜底
        name = parts[2].strip() if len(parts) > 2 and parts[2].strip() else dentry_id
        data = await self._request_json(
            "GET",
            f"{API_HOST}{DENTRY_DOWNLOAD_PATH}".format(
                space_id=workspace_id, dentry_id=dentry_id,
            ),
            params=self._op_params(),
        )
        payload = (data or {}).get("data") or data or {}
        url = (payload.get("downloadUrl") or payload.get("url")
               or (payload.get("downloadInfo") or {}).get("resourceUrl") or "")
        if not url:
            raise DocSourceError(
                f"未能获取附件下载链接（dentry={dentry_id}）：请确认已开通 "
                "Storage.File.Read 权限"
            )
        resp = await self._request("GET", url, with_token=False)
        if resp.status_code >= 400:
            raise DocSourceError(self._http_error_message(resp))
        # 部分响应会在 header 里回显文件名；拿不到就用 dentryId 兜底
        hinted = resp.headers.get("Content-Disposition") or ""
        if "filename=" in hinted:
            name = hinted.split("filename=", 1)[1].strip().strip('"')
        if not is_supported(name):
            raise DocSourceError(
                f"附件 {name} 不是可转换的文档格式（仅支持 PDF / Word / Excel / PPT / 文本）"
            )
        return FetchDocResult(
            title=name, markdown=bytes_to_markdown(name, resp.content), updated_at=None,
        )

    @staticmethod
    def _split_parent(parent_id: str) -> tuple:
        """还原 ``workspace::node`` 或带目录路径的 ``workspace::node::path``。"""
        parts = (parent_id or "").split("::")
        if len(parts) >= 3:
            return parts[0], parts[1], parts[2]
        if len(parts) == 2:
            return parts[0], parts[1], ""
        return parent_id, None, ""


register_doc_source(
    "dingtalk",
    DingtalkDocSource,
    ProviderMeta(
        source_type="dingtalk",
        name="钉钉文档",
        desc="钉钉文档空间",
        host=API_HOST,
        credential_fields=(
            CredField("app_key", "AppKey", required=True, placeholder="dingxxxxxx"),
            CredField("app_secret", "AppSecret", required=True, secret=True,
                      placeholder="应用凭证 Secret",
                      hint="需在钉钉开放平台为应用开通「知识库文档读权限」"
                           "（权限点：Document.WorkspaceDocument.Read，含查询目录树）并发布应用。"
                           "注意：「知识库读权限 Document.Workspace.Read」已被钉钉官方下线，"
                           "新应用在权限列表中找不到、无法申请，请改用下方「知识库直连」方式。"),
            CredField("space_id", "知识库 ID",
                      placeholder="强烈建议填写（知识库直连模式）",
                      hint="新应用开通不了 Document.Workspace.Read，无法枚举知识库列表；"
                           "请填写目标知识库 URL（https://alidocs.dingtalk.com/i/spaces/<ID>/overview）"
                           "中的 ID，直连该知识库目录树。留空则尝试列表接口（仅存量已开通该权限的应用可用）。"),
            CredField("operator_id", "操作人 UnionId",
                      placeholder="对目标知识库至少有「仅可查看」权限的成员 unionId",
                      hint="钉钉目录树/正文接口必传 operatorId（unionId），"
                           "可在开发者后台 API Studio 调试台或「查询用户详情」接口获取。"),
            CredField("include_uploaded_files", "导入钉盘上传附件", placeholder="false",
                      hint="默认关闭。开启后会把知识库里的 docx / pptx / xlsx / pdf "
                           "附件一并导入（需额外开通 Storage.File.Read 权限，"
                           "并产生额外存储与向量化成本）"),
            CredField("preserve_folder_structure", "保留目录结构", placeholder="false",
                      hint="默认关闭。开启后文件名编码为「工作区名/子目录/…/标题」，"
                           "需重新导入一次才会给已入库文档归位"),
            CredField("space_name", "工作区名称", placeholder="留空则使用知识库 ID",
                      hint="仅在开启「保留目录结构」时用作路径首段，提升可读性"),
        ),
    ),
)
