"""OneDrive / SharePoint 文档源（``source_type=onedrive``）。

认证：Azure AD 应用的 ``client_credentials`` 流程 —— ``_fetch_token()`` 向
``https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token`` 换 Graph 访问令牌，
基类负责惰性获取与 TTL 缓存（一次导入会话内只换一次票）。应用需在 Azure 门户授予
``Files.Read.All`` / ``Sites.Read.All`` 应用权限并**完成管理员同意**。

枚举（Microsoft Graph v1.0，三选一作用域）：
- 个人盘：``/me/drive``
- 指定驱动：``/drives/{drive_id}``
- SharePoint 站点文档库：``/sites/{site_id}/drive``

子节点：``{scope}/root/children`` 或 ``{scope}/items/{id}/children``（``@odata.nextLink``
分页）。正文：``{scope}/items/{id}/content``；Office / PDF 走本地转换
（``binary.bytes_to_markdown``），纯文本类直接解码。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

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
from app.connectors.doc_sources.binary import bytes_to_markdown, bytes_to_text, is_supported

logger = logging.getLogger(__name__)

HOST = "https://graph.microsoft.com"
GRAPH_PREFIX = "/v1.0"
TOKEN_PATH = "/oauth2/v2.0/token"
DEFAULT_SCOPE = "https://graph.microsoft.com/.default"

# 分页上限，避免超大文档库无限翻页
MAX_PAGES = 30
PAGE_SIZE = 200


def _scope_of(credentials: Dict[str, Any]) -> str:
    """按凭据选择 Graph 作用域：个人盘 / 指定驱动 / SharePoint 站点文档库。"""
    drive_id = (credentials.get("drive_id") or "").strip()
    site_id = (credentials.get("site_id") or "").strip()
    if site_id:
        return f"sites/{site_id}/drive"
    if drive_id:
        return f"drives/{drive_id}"
    return "me/drive"


def _encode_folder(scope: str, item_id: str) -> str:
    return f"folder:{scope}:{item_id}"


def _encode_file(scope: str, item_id: str) -> str:
    return f"file:{scope}:{item_id}"


def _decode(doc_id: str) -> Tuple[str, str, str]:
    parts = (doc_id or "").split(":", 2)
    if len(parts) != 3 or parts[0] not in ("folder", "file"):
        raise DocSourceError(f"无法解析的 OneDrive 标识：{doc_id}")
    return parts[0], parts[1], parts[2]


class OneDriveDocSource(BaseDocSource):
    source_type = "onedrive"
    token_in = "header"
    # Graph 用 HTTP 状态码 + body.error 表达错误
    error_code_field = None
    timeout = 30.0

    # ── 令牌 ──────────────────────────────────────────────────
    async def _fetch_token(self) -> Optional[str]:
        tenant_id = (self.credentials.get("tenant_id") or "").strip()
        client_id = (self.credentials.get("client_id") or "").strip()
        client_secret = (self.credentials.get("client_secret") or "").strip()
        missing = [n for n, v in (
            ("Tenant ID", tenant_id), ("Client ID", client_id),
            ("Client Secret", client_secret),
        ) if not v]
        if missing:
            raise DocSourceError(f"缺少 {' / '.join(missing)}")
        data = await self._request_json(
            "POST", f"https://login.microsoftonline.com/{tenant_id}{TOKEN_PATH}",
            with_token=False,
            form_body={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": DEFAULT_SCOPE,
            },
        )
        token = (data or {}).get("access_token") or ""
        if not token:
            error = (data or {}).get("error_description") or "请检查应用凭据与管理员同意状态"
            raise DocSourceError(f"换取 Graph 访问令牌失败：{error}")
        return token

    # ── 凭据 ──────────────────────────────────────────────────
    @property
    def _scope(self) -> str:
        return _scope_of(self.credentials)

    def _folder_path(self) -> str:
        return (self.credentials.get("folder_path") or "").strip().strip("/")

    # ── 实现三个抽象方法 ──────────────────────────────────────
    async def test_connection(self) -> DocConnResult:
        try:
            await self._access_token()
            data = await self._request_json(
                "GET", f"{HOST}{GRAPH_PREFIX}/{self._scope}"
            )
            name = (data or {}).get("name") or self._scope
            return DocConnResult(
                ok=True, message="连通成功：凭据有效", identity=f"可访问 {name}",
            )
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            if not parent_id:
                return await self._list_children("root")
            kind, scope, item_id = _decode(parent_id)
            if kind != "folder":
                return []
            return await self._list_children(item_id, scope=scope)
        finally:
            await self.aclose()

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            kind, scope, item_id = _decode(doc_id)
            if kind != "file":
                raise DocSourceError(f"{doc_id} 不是可导入的文件")
            resp = await self._request(
                "GET", f"{HOST}{GRAPH_PREFIX}/{scope}/items/{item_id}/content"
            )
            if resp.status_code >= 400:
                raise DocSourceError(self._http_error_message(resp))
            # Graph 的 /content 不回文件名，用清单接口拿到的名字更可靠
            meta = await self._request_json(
                "GET", f"{HOST}{GRAPH_PREFIX}/{scope}/items/{item_id}",
                params={"select": "name,lastModifiedDateTime"},
            )
            name = (meta or {}).get("name") or item_id
            body = resp.content or b""
            if is_supported(name):
                return FetchDocResult(
                    title=name, markdown=bytes_to_markdown(name, body),
                    updated_at=(meta or {}).get("lastModifiedDateTime"),
                )
            text = bytes_to_text(body).strip()
            if not text:
                raise DocSourceError(f"文件 {name} 未解析出任何文本")
            return FetchDocResult(
                title=name, markdown=text,
                updated_at=(meta or {}).get("lastModifiedDateTime"),
            )
        finally:
            await self.aclose()

    # ── 私有辅助 ──────────────────────────────────────────────
    async def _list_children(
        self, item_id: str, scope: Optional[str] = None
    ) -> List[ExternalDocRef]:
        scope = scope or self._scope
        url = f"{HOST}{GRAPH_PREFIX}/{scope}/items/{item_id}/children"
        params: Dict[str, Any] = {"$top": PAGE_SIZE, "$select": "id,name,folder,file,lastModifiedDateTime"}
        refs: List[ExternalDocRef] = []
        for _ in range(MAX_PAGES):
            data = await self._request_json("GET", url, params=params)
            for item in (data or {}).get("value") or []:
                name = item.get("name") or "未命名"
                iid = item.get("id") or ""
                if not iid:
                    continue
                if item.get("folder"):
                    if not self._folder_allowed(name):
                        continue
                    refs.append(
                        ExternalDocRef(
                            doc_id=_encode_folder(scope, iid), title=name,
                            node_type="folder", parent_id=item_id,
                        )
                    )
                    continue
                if not is_supported(name):
                    continue
                refs.append(
                    ExternalDocRef(
                        doc_id=_encode_file(scope, iid), title=name, node_type="doc",
                        parent_id=item_id, updated_at=item.get("lastModifiedDateTime"),
                    )
                )
            next_link = (data or {}).get("@odata.nextLink")
            if not next_link:
                break
            url, params = next_link, {}
        return refs

    def _folder_allowed(self, name: str) -> bool:
        """未配置 folder_path 时全部可见；配置了则只下钻到该子目录层级。"""
        target = self._folder_path()
        if not target:
            return True
        return name == target.split("/")[0]


register_doc_source(
    "onedrive",
    OneDriveDocSource,
    ProviderMeta(
        source_type="onedrive",
        name="OneDrive / SharePoint",
        desc="OneDrive 与 SharePoint 文档库（Graph）",
        host=HOST,
        credential_fields=(
            CredField("tenant_id", "Tenant ID", required=True,
                      placeholder="Azure AD 目录（租户）ID"),
            CredField("client_id", "Client ID", required=True,
                      placeholder="Azure 应用（客户端）ID"),
            CredField("client_secret", "Client Secret", required=True, secret=True,
                      placeholder="应用密钥",
                      hint="需授予 Files.Read.All / Sites.Read.All 应用权限并完成管理员同意"),
            CredField("drive_id", "Drive ID", placeholder="留空使用 /me/drive（个人盘）",
                      hint="指定驱动（文档库）时填写"),
            CredField("site_id", "SharePoint 站点 ID", placeholder="留空则不使用站点文档库",
                      hint="填写后走 /sites/{id}/drive；与 drive_id 二选一，优先 site_id"),
            CredField("folder_path", "起始目录", placeholder="留空从根目录开始",
                      hint="只需填首层目录名，用于缩小列举范围"),
        ),
    ),
)
