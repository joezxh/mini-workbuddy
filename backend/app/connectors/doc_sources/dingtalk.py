"""钉钉文档源。

认证：``GET /gettoken?appkey&appsecret`` 取 access_token，以查询参数注入
（沿用既有 ``app/connectors/types/dingtalk.py`` 的 token_in=query 约定）。
枚举：知识库（workspaces）→ 节点（nodes/query）逐层下钻。
正文：按 nodeId 取内容，优先使用平台返回的 Markdown/纯文本。

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

TOKEN_HOST = "https://oapi.dingtalk.com"
API_HOST = "https://api.dingtalk.com"
TOKEN_PATH = "/gettoken"
WORKSPACES_PATH = "/v1.0/doc/workspaces"
NODES_QUERY_PATH = "/v1.0/doc/nodes/query"
NODE_CONTENT_PATH = "/v1.0/doc/nodes/{node_id}/content"


class DingtalkDocSource(BaseDocSource):
    source_type = "dingtalk"
    token_in = "query"
    token_query_name = "access_token"

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

    async def test_connection(self) -> DocConnResult:
        try:
            await self._access_token()
            data = await self._request_json(
                "GET", f"{API_HOST}{WORKSPACES_PATH}", params={"maxResults": 1}
            )
            payload = (data or {}).get("data") or data or {}
            items = payload.get("workspaces") or payload.get("list") or []
            return DocConnResult(
                ok=True,
                message="连通成功：凭据有效",
                identity=f"可访问知识库 {len(items) if items else (payload.get('total') or 0)} 个",
            )
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            if not parent_id:
                return await self._list_workspaces()
            workspace_id, node_id = self._split_parent(parent_id)
            return await self._list_nodes(workspace_id, node_id)
        finally:
            await self.aclose()

    async def _list_workspaces(self) -> List[ExternalDocRef]:
        data = await self._request_json(
            "GET", f"{API_HOST}{WORKSPACES_PATH}", params={"maxResults": 50}
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
        self, workspace_id: str, node_id: Optional[str]
    ) -> List[ExternalDocRef]:
        body: Dict[str, Any] = {"workspaceId": workspace_id, "maxResults": 50}
        if node_id:
            body["parentNodeId"] = node_id
        data = await self._request_json(
            "POST", f"{API_HOST}{NODES_QUERY_PATH}", json_body=body
        )
        payload = (data or {}).get("data") or data or {}
        items = payload.get("nodes") or payload.get("list") or []
        refs: List[ExternalDocRef] = []
        for n in items:
            nid = n.get("nodeId") or n.get("id")
            if not nid:
                continue
            node_type = n.get("nodeType") or ""
            has_child = bool(n.get("hasChild"))
            if has_child or node_type == "FOLDER":
                kind = "folder"
                doc_id = f"{workspace_id}::{nid}"
            elif node_type in ("DOC", "DOCX", "FILE", ""):
                kind = "doc"
                doc_id = str(nid)
            else:
                continue
            refs.append(
                ExternalDocRef(
                    doc_id=doc_id,
                    title=n.get("name") or n.get("title") or "未命名",
                    node_type=kind,
                    parent_id=node_id or workspace_id,
                    updated_at=n.get("updateTime") or n.get("gmtModified"),
                )
            )
        return refs

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            data = await self._request_json(
                "GET", f"{API_HOST}{NODE_CONTENT_PATH}".format(node_id=doc_id)
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

    @staticmethod
    def _split_parent(parent_id: str) -> tuple:
        if "::" in parent_id:
            workspace_id, node_id = parent_id.split("::", 1)
            return workspace_id, node_id
        return parent_id, None


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
                      placeholder="应用凭证 Secret"),
            CredField("space_id", "知识库 ID", placeholder="留空则列出全部知识库"),
        ),
    ),
)
