"""飞书 / Lark 文档源共享核心（区域常量 + 令牌 + Wiki / 云盘两套 ops）。

飞书与 Lark 是**两朵隔离云**：``open.feishu.cn`` 创建的应用读不到 Lark 租户的数据，
凭据不通用，因此二者是独立的 ``source_type``（``feishu`` / ``lark``，云盘同理）。
但 API 路径与返回结构完全一致，故抽出本核心承载：

- 区域常量表 ``REGIONS``（**模块级常量，不接受用户输入**，沿用「HOST 必须硬编码」的
  SSRF 约束）；
- ``tenant_access_token`` 换取（复用基类 ``_fetch_token()`` + TTL 缓存）；
- 云文档块 → Markdown 转换（Wiki 的 docx 与云盘的 docx 共用）；
- ``FeishuWikiSource`` / ``FeishuDriveSource`` 两套 ops。

``feishu.py`` / ``lark.py`` / ``feishu_drive.py`` / ``lark_drive.py`` 只声明区域与形态
组合并注册，不重复实现逻辑。
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from app.connectors.doc_sources.base import (
    BaseDocSource,
    DocConnResult,
    DocSourceError,
    ExternalDocRef,
    FetchDocResult,
)
from app.connectors.doc_sources.binary import bytes_to_markdown, is_supported
from app.connectors.doc_sources.markdown import (
    BULLETED,
    CALLOUT,
    CODE,
    DIVIDER,
    HEADING,
    IMAGE,
    MdBlock,
    NUMBERED,
    PARAGRAPH,
    QUOTE,
    TODO,
    blocks_to_markdown,
)

# 区域 → 开放平台域名（常量表，非用户输入）
REGION_FEISHU = "feishu"
REGION_LARK = "lark"
REGIONS: Dict[str, str] = {
    REGION_FEISHU: "https://open.feishu.cn",
    REGION_LARK: "https://open.larksuite.com",
}

TOKEN_PATH = "/open-apis/auth/v3/tenant_access_token/internal"
SPACES_PATH = "/open-apis/wiki/v2/spaces"
NODES_PATH = "/open-apis/wiki/v2/spaces/{space_id}/nodes"
BLOCKS_PATH = "/open-apis/docx/v1/documents/{document_id}/blocks"
DRIVE_FILES_PATH = "/open-apis/drive/v1/files"
DRIVE_META_PATH = "/open-apis/drive/v1/files/{token}/meta"
DRIVE_DOWNLOAD_PATH = "/open-apis/drive/v1/files/{token}/download"
EXPORT_TASK_PATH = "/open-apis/drive/v1/export_tasks"
EXPORT_TASK_RESULT_PATH = "/open-apis/drive/v1/export_tasks/{ticket}"
EXPORT_FILE_DOWNLOAD_PATH = "/open-apis/drive/v1/export_tasks/file/{file_token}/download"

# 导出任务轮询：sheet / bitable 的导出是异步的，最多等 10 轮
EXPORT_MAX_POLLS = 10
EXPORT_POLL_INTERVAL = 1.0
# 导出目标格式（按 obj_type 选）
EXPORT_EXTENSIONS: Dict[str, str] = {"sheet": "xlsx", "bitable": "xlsx", "docx": "docx"}
# 云盘支持导入的类型；其余（slides / mindnote 等无公开内容 API）在列举时跳过
DRIVE_DOC_TYPES = ("docx", "sheet", "bitable", "file")

# block_type → (块类型, 标题层级)；未列出的类型降级为段落
_BLOCK_KINDS: Dict[int, Tuple[str, int]] = {
    1: (PARAGRAPH, 0),      # 页面
    2: (PARAGRAPH, 0),      # 文本
    3: (HEADING, 1),
    4: (HEADING, 2),
    5: (HEADING, 3),
    6: (HEADING, 4),
    7: (HEADING, 5),
    8: (HEADING, 6),
    9: (BULLETED, 0),
    10: (NUMBERED, 0),
    12: (CODE, 0),
    13: (QUOTE, 0),
    14: (DIVIDER, 0),
    15: (TODO, 0),
    17: (TODO, 0),
    19: (CALLOUT, 0),
    22: (QUOTE, 0),
    23: (BULLETED, 0),      # 无序列表项
    24: (TODO, 0),          # 有序列表项在部分版本为 24，按待办降级处理不丢内容
    25: (BULLETED, 0),
}


def _elements_text(elements: Optional[List[Dict[str, Any]]]) -> str:
    """把 text_run / mention / equation 等行内元素拼成纯文本（链接保留为 MD）。"""
    parts: List[str] = []
    for el in elements or []:
        run = el.get("text_run") or {}
        text = run.get("content") or ""
        url = (run.get("text_element_style") or {}).get("link", {}).get("url")
        parts.append(f"[{text}]({url})" if url else text)
    return "".join(parts)


def _block_body(block: Dict[str, Any]) -> Dict[str, Any]:
    """取块体内与 block_type 对应的子对象（heading1/text/code/...）。"""
    for key, value in block.items():
        if isinstance(value, dict) and ("elements" in value or "style" in value):
            return value
    return {}


class FeishuBaseDocSource(BaseDocSource):
    """飞书 / Lark 公共基类：区域化 HOST + 令牌换取 + 块转 Markdown。"""

    region: str = REGION_FEISHU
    token_in = "header"
    # 飞书「权限不足 / 应用未加入知识空间 / 参数错误」一律返回 HTTP 200 + code!=0，
    # 不校验业务码会被静默解析成空列表（表现为测试通过但选不到文档）
    error_code_field = "code"

    @property
    def HOST(self) -> str:
        domain = REGIONS.get(self.region)
        if not domain:
            raise DocSourceError(f"未定义的飞书区域：{self.region}")
        return domain

    # ── 凭据读取 ──────────────────────────────────────────────
    def _space_id(self) -> str:
        """凭据里填写的知识空间 ID；填写后走直连模式，不再依赖空间列表接口。"""
        return (self.credentials.get("space_id") or "").strip()

    def _folder_token(self) -> str:
        """云盘根目录 folder_token（必填：云盘没有「列出根空间」的接口）。"""
        return (self.credentials.get("folder_token") or "").strip()

    # ── 令牌 ─────────────────────────────────────────────────
    async def _fetch_token(self) -> Optional[str]:
        app_id = self.credentials.get("app_id") or ""
        app_secret = self.credentials.get("app_secret") or ""
        if not (app_id and app_secret):
            raise DocSourceError("缺少 App ID 或 App Secret")
        data = await self._request_json(
            "POST", f"{self.HOST}{TOKEN_PATH}",
            json_body={"app_id": app_id, "app_secret": app_secret},
            with_token=False,
        )
        token = (data or {}).get("tenant_access_token") or ""
        if not token:
            raise DocSourceError(f"获取访问令牌失败：{(data or {}).get('msg') or '未知错误'}")
        return token

    # ── 云文档块 → Markdown ──────────────────────────────────
    async def _fetch_docx_markdown(self, document_id: str) -> Tuple[str, str]:
        """拉取 docx 全部块，返回 (标题, Markdown)。"""
        blocks: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        for _ in range(50):
            params: Dict[str, Any] = {"page_size": 500, "document_revision_id": -1}
            if page_token:
                params["page_token"] = page_token
            data = await self._request_json(
                "GET", f"{self.HOST}{BLOCKS_PATH}".format(document_id=document_id),
                params=params,
            )
            payload = (data or {}).get("data") or {}
            blocks += payload.get("items") or []
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token")
            if not page_token:
                break
        title = self._first_heading(blocks) or "飞书文档"
        return title, blocks_to_markdown(self._to_md_blocks(blocks))

    def _to_md_blocks(self, blocks: List[Dict[str, Any]]) -> List[MdBlock]:
        md_blocks: List[MdBlock] = []
        for block in blocks:
            btype = block.get("block_type")
            if btype == 27:  # 图片
                token = (block.get("image") or {}).get("token") or ""
                if token:
                    md_blocks.append(
                        MdBlock(
                            kind=IMAGE,
                            text="图片",
                            url=f"{self.HOST}/open-apis/drive/v1/medias/{token}/download",
                        )
                    )
                continue
            if btype == 31:  # 表格：单元格在独立块中，此处降级为占位
                md_blocks.append(MdBlock(kind=PARAGRAPH, text="[表格]"))
                continue
            kind, level = _BLOCK_KINDS.get(btype, (PARAGRAPH, 0))
            body = _block_body(block)
            text = _elements_text(body.get("elements"))
            if kind == DIVIDER:
                md_blocks.append(MdBlock(kind=DIVIDER))
                continue
            if kind == TODO:
                done = ((body.get("style") or {}).get("done")) is True
                md_blocks.append(MdBlock(kind=TODO, text=text, checked=done))
                continue
            if kind == CODE:
                lang = (body.get("style") or {}).get("language") or ""
                md_blocks.append(MdBlock(kind=CODE, text=text, language=lang))
                continue
            if kind == HEADING:
                md_blocks.append(MdBlock(kind=HEADING, text=text, level=level or 1))
                continue
            if not text:
                continue
            md_blocks.append(MdBlock(kind=kind, text=text))
        return md_blocks

    @staticmethod
    def _first_heading(blocks: List[Dict[str, Any]]) -> str:
        for block in blocks:
            if block.get("block_type") in (3, 4, 5, 6, 7, 8):
                body = _block_body(block)
                text = _elements_text(body.get("elements")).strip()
                if text:
                    return text
        return ""

    @staticmethod
    def _split_parent(parent_id: str) -> Tuple[str, Optional[str]]:
        """目录节点 doc_id 形如 ``space_id::node_token``。"""
        if "::" in parent_id:
            space_id, node_token = parent_id.split("::", 1)
            return space_id, node_token
        return parent_id, None


class FeishuWikiSource(FeishuBaseDocSource):
    """飞书 / Lark 知识库（Wiki）：空间 → 节点树 → docx 正文。"""

    async def test_connection(self) -> DocConnResult:
        try:
            await self._access_token()
            space_id = self._space_id()
            if space_id:
                # 直连模式：只依赖「获取知识空间节点」，应用未加入空间时列表接口不可用
                refs = await self._list_space_nodes(space_id, None)
                return DocConnResult(
                    ok=True,
                    message="连通成功：凭据有效（知识空间直连）",
                    identity=f"知识空间 {space_id} 下 {len(refs)} 个节点",
                )
            data = await self._request_json("GET", f"{self.HOST}{SPACES_PATH}",
                                            params={"page_size": 50})
            items = ((data or {}).get("data") or {}).get("items") or []
            total = ((data or {}).get("data") or {}).get("total") or len(items)
            if not total:
                # 凭据有效但看不到任何空间：多数是应用没被加进知识空间，给出可操作指引
                return DocConnResult(
                    ok=False,
                    message="凭据有效，但未获取到任何知识空间：请为应用开通 wiki 权限"
                            "（wiki:wiki:readonly 或 wiki:wiki），并在知识空间「设置 → 成员」"
                            "中把该应用加入；也可在凭据中填写「知识空间 ID」走直连模式。",
                )
            return DocConnResult(
                ok=True,
                message="连通成功：凭据有效",
                identity=f"可访问知识空间 {total} 个",
            )
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            if not parent_id:
                space_id = self._space_id()
                # 填了知识空间 ID 则直连列出该空间节点，跳过空间列表
                if space_id:
                    return await self._list_space_nodes(space_id, None)
                spaces = await self._list_spaces()
                # 飞书「应用未加进空间 / 仅有 wiki:node 无 wiki:wiki 权限」时，
                # 空间列表会静默返回空（HTTP 200 + 空 items），导致前端树一片空白。
                # 这里显式抛出可操作错误，把「空白」变成「看得懂的报错」。
                if not spaces:
                    raise DocSourceError(
                        "未获取到任何知识空间：请为应用开通 wiki:wiki:readonly 权限，"
                        "或在凭据中填写「知识空间 ID」走直连模式（推荐，无需空间列表权限）。"
                    )
                return spaces
            space_id, node_token = self._split_parent(parent_id)
            return await self._list_space_nodes(space_id, node_token)
        finally:
            await self.aclose()

    async def _list_spaces(self) -> List[ExternalDocRef]:
        data = await self._request_json("GET", f"{self.HOST}{SPACES_PATH}",
                                        params={"page_size": 50})
        items = ((data or {}).get("data") or {}).get("items") or []
        refs: List[ExternalDocRef] = []
        for s in items:
            # 飞书 wiki/v2/spaces 返回的主键字段是 space_id（不是 id）；
            # 取错字段会让 doc_id 变成 None，导致下钻请求 /wiki/v2/spaces/None/nodes
            # 失败、文档列表为空。用 space_id 优先、id 兜底以兼容旧/变体响应。
            space_id = s.get("space_id") or s.get("id") or ""
            if not space_id:
                continue
            refs.append(
                ExternalDocRef(
                    doc_id=str(space_id),
                    title=s.get("name") or "未命名空间",
                    node_type="space",
                    url=f"{self.HOST}/wiki/{space_id}",
                )
            )
        return refs

    async def _list_space_nodes(
        self, space_id: str, node_token: Optional[str]
    ) -> List[ExternalDocRef]:
        refs: List[ExternalDocRef] = []
        page_token: Optional[str] = None
        for _ in range(20):  # 上限保护，避免异常数据导致死循环
            params: Dict[str, Any] = {"page_size": 50}
            if node_token:
                params["parent_node_token"] = node_token
            if page_token:
                params["page_token"] = page_token
            data = await self._request_json(
                "GET", f"{self.HOST}{NODES_PATH}".format(space_id=space_id), params=params
            )
            payload = (data or {}).get("data") or {}
            for n in payload.get("items") or []:
                obj_type = n.get("obj_type") or ""
                has_child = bool(n.get("has_child"))
                node_key = n.get("node_token") or ""
                if has_child:
                    # 目录节点：doc_id 编码 space 与 node，供下钻时还原
                    doc_id = f"{space_id}::{node_key}"
                    kind = "folder"
                elif obj_type == "docx":
                    doc_id = n.get("obj_token") or ""
                    kind = "doc"
                else:
                    # 表格/多维表格等暂不支持导入，跳过以免导入失败
                    continue
                if not doc_id:
                    continue
                refs.append(
                    ExternalDocRef(
                        doc_id=doc_id,
                        title=n.get("title") or "未命名",
                        node_type=kind,
                        parent_id=node_token or space_id,
                        updated_at=n.get("obj_edit_time") or n.get("obj_create_time"),
                        url=f"{self.HOST}/wiki/{node_key}",
                    )
                )
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token")
            if not page_token:
                break
        return refs

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            title, markdown = await self._fetch_docx_markdown(doc_id)
            return FetchDocResult(title=title, markdown=markdown, updated_at=None)
        finally:
            await self.aclose()


# ── 云盘 doc_id 编解码 ───────────────────────────────────────────
def encode_drive_doc(obj_type: str, token: str) -> str:
    """云盘文档 doc_id：``file:<obj_type>:<token>``（类型随行，拉取正文时无需再查元数据）。"""
    return f"file:{obj_type}:{token}"


def encode_drive_folder(token: str) -> str:
    """云盘目录 doc_id：``folder:<token>``。"""
    return f"folder:{token}"


def decode_drive_id(doc_id: str) -> Tuple[str, str, str]:
    """还原 (kind, obj_type, token)；非法 doc_id 抛 DocSourceError。

    两种形态：``file:<obj_type>:<token>``（文档，三段）与 ``folder:<token>``（目录，两段）。
    """
    parts = (doc_id or "").split(":")
    if len(parts) == 3 and parts[0] == "file":
        return "file", parts[1], parts[2]
    if len(parts) == 2 and parts[0] == "folder":
        return "folder", "", parts[1]
    raise DocSourceError(f"无法解析的云盘资源标识：{doc_id}")


class FeishuDriveSource(FeishuBaseDocSource):
    """飞书 / Lark 云盘：以 ``folder_token`` 为根目录，逐层列举文件。

    云盘没有「列出根空间」的接口，**根目录必须由用户给出 folder_token**（对齐 WeKnora
    ``drive/connector.go`` 的硬性约束），留空直接报错而不是回退到云空间根目录。
    """

    async def test_connection(self) -> DocConnResult:
        try:
            token = self._folder_token()
            if not token:
                return DocConnResult(
                    ok=False,
                    message="缺少云盘文件夹 token：请在云盘打开目标文件夹，"
                            "从 URL（/drive/folder/<token>）复制该段填入",
                )
            await self._access_token()
            refs = await self._list_folder(token)
            return DocConnResult(
                ok=True,
                message="连通成功：凭据有效，可读取该云盘文件夹",
                identity=f"文件夹下 {len(refs)} 个条目",
            )
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            token = self._folder_token()
            if not token:
                raise DocSourceError(
                    "缺少云盘文件夹 token：请在凭据中填写目标文件夹的 folder_token"
                )
            if not parent_id:
                # 顶层：根目录本身作为唯一可下钻节点
                return [
                    ExternalDocRef(
                        doc_id=encode_drive_folder(token),
                        title=await self._folder_name(token) or f"文件夹 {token}",
                        node_type="folder",
                        url=f"{self.HOST}/drive/folder/{token}",
                    )
                ]
            kind, _obj_type, folder_token = decode_drive_id(parent_id)
            if kind != "folder":
                return []
            return await self._list_folder(folder_token)
        finally:
            await self.aclose()

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            kind, obj_type, token = decode_drive_id(doc_id)
            if kind != "file":
                raise DocSourceError(f"{doc_id} 不是文档节点")
            if obj_type == "docx":
                title, markdown = await self._fetch_docx_markdown(token)
                return FetchDocResult(title=title, markdown=markdown, updated_at=None)
            if obj_type in ("sheet", "bitable"):
                return await self._fetch_exported(token, obj_type)
            if obj_type == "file":
                return await self._fetch_uploaded(token)
            raise DocSourceError(f"暂不支持导入的云盘类型：{obj_type}")
        finally:
            await self.aclose()

    # ── 私有辅助 ─────────────────────────────────────────────
    async def _folder_name(self, token: str) -> str:
        """回显文件夹名称；该接口失败不影响主流程（回退到 token）。"""
        try:
            data = await self._request_json(
                "GET", f"{self.HOST}{DRIVE_META_PATH}".format(token=token)
            )
        except DocSourceError:
            return ""
        return ((data or {}).get("data") or {}).get("name") or ""

    async def _list_folder(self, folder_token: str) -> List[ExternalDocRef]:
        refs: List[ExternalDocRef] = []
        page_token: Optional[str] = None
        for _ in range(20):  # 上限保护
            params: Dict[str, Any] = {"folder_token": folder_token, "page_size": 200}
            if page_token:
                params["page_token"] = page_token
            data = await self._request_json(
                "GET", f"{self.HOST}{DRIVE_FILES_PATH}", params=params
            )
            payload = (data or {}).get("data") or {}
            for f in payload.get("files") or []:
                obj_type = f.get("type") or ""
                token = f.get("token") or ""
                name = f.get("name") or "未命名"
                if not token:
                    continue
                if obj_type == "folder":
                    refs.append(
                        ExternalDocRef(
                            doc_id=encode_drive_folder(token),
                            title=name,
                            node_type="folder",
                            parent_id=folder_token,
                            url=f"{self.HOST}/drive/folder/{token}",
                        )
                    )
                    continue
                if obj_type not in DRIVE_DOC_TYPES:
                    # slides / mindnote 等无公开内容 API，跳过以免导入必然失败
                    continue
                if obj_type == "file" and not is_supported(name):
                    # 上传型文件只有可转换格式才有意义（pdf/word/ppt/excel/txt/md）
                    continue
                refs.append(
                    ExternalDocRef(
                        doc_id=encode_drive_doc(obj_type, token),
                        title=name,
                        node_type="doc",
                        parent_id=folder_token,
                        updated_at=f.get("latest_modify_time") or f.get("created_time"),
                        url=f"{self.HOST}/drive/file/{token}",
                    )
                )
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token")
            if not page_token:
                break
        return refs

    async def _fetch_uploaded(self, token: str) -> FetchDocResult:
        """云盘上传型文件：下载字节流后转 Markdown。"""
        resp = await self._request("GET", f"{self.HOST}{DRIVE_DOWNLOAD_PATH}".format(token=token))
        if resp.status_code >= 400:
            raise DocSourceError(self._http_error_message(resp))
        filename = resp.headers.get("Content-Disposition") or "file"
        # 文件名不可靠时用 token 兜底；转换只看扩展名，故至少要保证有后缀
        if not is_supported(filename):
            filename = f"{token}.bin" if not is_supported(filename) else filename
        # 无扩展名时按内容无法判定，直接给出可操作提示
        if not is_supported(filename):
            raise DocSourceError("云盘文件缺少可识别的扩展名，无法转换为 Markdown")
        return FetchDocResult(
            title=token,
            markdown=bytes_to_markdown(filename, resp.content),
            updated_at=None,
        )

    async def _fetch_exported(self, token: str, obj_type: str) -> FetchDocResult:
        """表格 / 多维表格：创建导出任务 → 轮询 → 下载导出文件 → 转 Markdown。"""
        extension = EXPORT_EXTENSIONS.get(obj_type, "xlsx")
        data = await self._request_json(
            "POST", f"{self.HOST}{EXPORT_TASK_PATH}",
            json_body={"file_extension": extension, "token": token, "type": obj_type},
        )
        ticket = ((data or {}).get("data") or {}).get("ticket") or ""
        if not ticket:
            raise DocSourceError("创建导出任务失败：平台未返回 ticket")
        file_token = ""
        for _ in range(EXPORT_MAX_POLLS):
            result = await self._request_json(
                "GET", f"{self.HOST}{EXPORT_TASK_RESULT_PATH}".format(ticket=ticket)
            )
            payload = (result or {}).get("data") or {}
            status = payload.get("job_status")
            if status == 0:  # 0=成功
                file_token = (payload.get("result") or {}).get("file_token") or ""
                break
            if status in (2, 3):  # 2=处理中 3=排队中
                await asyncio.sleep(EXPORT_POLL_INTERVAL)
                continue
            raise DocSourceError(f"导出任务失败（job_status={status}）")
        if not file_token:
            raise DocSourceError("导出任务超时：请稍后重试或减少单次导入的文件数")
        resp = await self._request(
            "GET", f"{self.HOST}{EXPORT_FILE_DOWNLOAD_PATH}".format(file_token=file_token)
        )
        if resp.status_code >= 400:
            raise DocSourceError(self._http_error_message(resp))
        markdown = bytes_to_markdown(f"{token}.{extension}", resp.content)
        return FetchDocResult(title=token, markdown=markdown, updated_at=None)
