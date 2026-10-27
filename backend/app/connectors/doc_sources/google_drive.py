"""Google Drive 文档源（``source_type=google_drive``）。

认证：OAuth2 刷新令牌 —— ``_fetch_token()`` 向 ``https://oauth2.googleapis.com/token``
用 ``client_id`` / ``client_secret`` / ``refresh_token`` 换 access_token，基类负责惰性
获取与 TTL 缓存（一次导入会话内只换一次票）。令牌端点要求
``application/x-www-form-urlencoded``，故走 ``_request(form_body=...)``。

枚举：``GET /drive/v3/files?q=...&fields=...``（``pageToken`` 分页，共享盘需
``driveId`` + ``supportsAllDrives``）。
正文优先级：Google 原生文档 ``files/{id}/export?mimeType=text/markdown`` → 失败降级
``text/plain`` → 二进制文件 ``files/{id}?alt=media`` 下载后本地转 Markdown。
快捷方式解析 ``shortcutDetails.targetId`` 指向的真实文件。

外部授权：Google Cloud 创建 OAuth 客户端 → 取得 refresh_token；权限是**资源级**的，
目标文件/文件夹必须共享给该 OAuth 客户端对应的账号。
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
from app.connectors.doc_sources.binary import bytes_to_markdown, is_supported

logger = logging.getLogger(__name__)

HOST = "https://www.googleapis.com"
TOKEN_URL = "https://oauth2.googleapis.com/token"
FILES_PATH = "/drive/v3/files"
FILE_PATH = "/drive/v3/files/{file_id}"
EXPORT_PATH = "/drive/v3/files/{file_id}/export"

# Google 原生文档 MIME（可导出为文本）
GOOGLE_DOC_MIMES = (
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
)
FOLDER_MIME = "application/vnd.google-apps.folder"
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"
FILE_FIELDS = "nextPageToken,files(id,name,mimeType,modifiedTime,parents,shortcutDetails)"
# 分页上限
MAX_PAGES = 30
PAGE_SIZE = 200


def _encode_folder(file_id: str) -> str:
    return f"folder:{file_id}"


def _encode_native(file_id: str) -> str:
    """Google 原生文档（走 export）。"""
    return f"gdoc:{file_id}"


def _encode_binary(file_id: str, name: str) -> str:
    """上传型二进制文件（走 alt=media）。"""
    return f"bin:{file_id}:{name}"


def _decode(doc_id: str) -> Tuple[str, ...]:
    parts = (doc_id or "").split(":", 2)
    if not parts or parts[0] not in ("folder", "gdoc", "bin"):
        raise DocSourceError(f"无法解析的 Google Drive 标识：{doc_id}")
    return tuple(parts)


class GoogleDriveDocSource(BaseDocSource):
    source_type = "google_drive"
    token_in = "header"
    # Drive 只用 HTTP 状态码 + body.error.message 表达错误
    error_code_field = None
    timeout = 30.0

    # ── 令牌 ──────────────────────────────────────────────────
    async def _fetch_token(self) -> Optional[str]:
        client_id = (self.credentials.get("client_id") or "").strip()
        client_secret = (self.credentials.get("client_secret") or "").strip()
        refresh_token = (self.credentials.get("refresh_token") or "").strip()
        missing = [n for n, v in (
            ("Client ID", client_id), ("Client Secret", client_secret),
            ("Refresh Token", refresh_token),
        ) if not v]
        if missing:
            raise DocSourceError(f"缺少 {' / '.join(missing)}")
        data = await self._request_json(
            "POST", TOKEN_URL, with_token=False,
            form_body={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
            },
        )
        token = (data or {}).get("access_token") or ""
        if not token:
            raise DocSourceError(
                f"换取访问令牌失败：{(data or {}).get('error_description') or '请检查 Refresh Token 是否有效'}"
            )
        return token

    # ── 凭据 ──────────────────────────────────────────────────
    def _root_id(self) -> str:
        return (self.credentials.get("folder_id") or "").strip() or "root"

    def _drive_id(self) -> str:
        return (self.credentials.get("drive_id") or "").strip()

    # ── 实现三个抽象方法 ──────────────────────────────────────
    async def test_connection(self) -> DocConnResult:
        try:
            await self._access_token()
            data = await self._request_json(
                "GET", f"{HOST}{FILES_PATH}", params={
                    "pageSize": 1, "fields": FILE_FIELDS, **self._shared_params(),
                },
            )
            files = (data or {}).get("files") or []
            return DocConnResult(
                ok=True,
                message="连通成功：凭据有效，可访问 Drive",
                identity=f"目录 {self._root_id()} 下可列举（示例 {len(files)} 项）",
            )
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            folder_id = self._root_id() if not parent_id else _decode(parent_id)[1]
            return await self._list_folder(folder_id)
        finally:
            await self.aclose()

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            parts = _decode(doc_id)
            if parts[0] == "gdoc":
                return await self._fetch_native(parts[1])
            if parts[0] == "bin":
                name = parts[2] if len(parts) > 2 else parts[1]
                return await self._fetch_binary(parts[1], name)
            raise DocSourceError(f"{doc_id} 不是可导入的文档")
        finally:
            await self.aclose()

    # ── 私有辅助 ──────────────────────────────────────────────
    def _shared_params(self) -> Dict[str, Any]:
        """共享盘（Team Drive）需要显式声明，否则列举不到。"""
        drive_id = self._drive_id()
        if not drive_id:
            return {}
        return {
            "driveId": drive_id,
            "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true",
            "corpora": "drive",
        }

    async def _list_folder(self, folder_id: str) -> List[ExternalDocRef]:
        refs: List[ExternalDocRef] = []
        page_token: Optional[str] = None
        for _ in range(MAX_PAGES):
            params: Dict[str, Any] = {
                "q": f"'{folder_id}' in parents and trashed = false",
                "fields": FILE_FIELDS,
                "pageSize": PAGE_SIZE,
                **self._shared_params(),
            }
            if page_token:
                params["pageToken"] = page_token
            data = await self._request_json("GET", f"{HOST}{FILES_PATH}", params=params)
            for f in (data or {}).get("files") or []:
                file_id = f.get("id") or ""
                if not file_id:
                    continue
                mime = f.get("mimeType") or ""
                name = f.get("name") or "未命名"
                if mime == SHORTCUT_MIME:
                    # 快捷方式解析到目标对象，等价于目标本身
                    target = (f.get("shortcutDetails") or {}).get("targetId") or ""
                    if not target:
                        continue
                    file_id, mime = target, (f.get("shortcutDetails") or {}).get("targetMimeType") or ""
                if mime == FOLDER_MIME:
                    refs.append(
                        ExternalDocRef(
                            doc_id=_encode_folder(file_id), title=name, node_type="folder",
                            parent_id=folder_id,
                        )
                    )
                    continue
                if mime in GOOGLE_DOC_MIMES:
                    refs.append(
                        ExternalDocRef(
                            doc_id=_encode_native(file_id), title=name, node_type="doc",
                            parent_id=folder_id, updated_at=f.get("modifiedTime"),
                        )
                    )
                    continue
                if is_supported(name):
                    refs.append(
                        ExternalDocRef(
                            doc_id=_encode_binary(file_id, name), title=name,
                            node_type="doc", parent_id=folder_id,
                            updated_at=f.get("modifiedTime"),
                        )
                    )
            page_token = (data or {}).get("nextPageToken")
            if not page_token:
                break
        return refs

    async def _fetch_native(self, file_id: str) -> FetchDocResult:
        """Google 原生文档优先导出 Markdown，失败降级纯文本。"""
        for mime_type in ("text/markdown", "text/plain"):
            try:
                resp = await self._request(
                    "GET", f"{HOST}{EXPORT_PATH}".format(file_id=file_id),
                    params={"mimeType": mime_type},
                )
            except DocSourceError:
                continue
            if resp.status_code < 400:
                markdown = resp.text or ""
                if markdown.strip():
                    return FetchDocResult(
                        title=file_id, markdown=markdown, updated_at=None,
                    )
        raise DocSourceError(
            f"Google 文档 {file_id} 导出失败：请确认该文档已共享给 OAuth 客户端账号"
        )

    async def _fetch_binary(self, file_id: str, name: str) -> FetchDocResult:
        resp = await self._request(
            "GET", f"{HOST}{FILE_PATH}".format(file_id=file_id), params={"alt": "media"},
        )
        if resp.status_code >= 400:
            raise DocSourceError(self._http_error_message(resp))
        return FetchDocResult(
            title=name, markdown=bytes_to_markdown(name, resp.content), updated_at=None,
        )


register_doc_source(
    "google_drive",
    GoogleDriveDocSource,
    ProviderMeta(
        source_type="google_drive",
        name="Google Drive",
        desc="云盘文件与 Google 原生文档",
        host=HOST,
        credential_fields=(
            CredField("client_id", "OAuth Client ID", required=True,
                      placeholder="xxxxxxxx.apps.googleusercontent.com"),
            CredField("client_secret", "OAuth Client Secret", required=True, secret=True,
                      placeholder="GOCSPX-xxxxxxxx"),
            CredField("refresh_token", "Refresh Token", required=True, secret=True,
                      placeholder="1//0xxxxxxxx",
                      hint="OAuth 授权后获得的长期刷新令牌；系统自动用它换取访问令牌"),
            CredField("folder_id", "根目录 ID", placeholder="留空使用云盘根目录 root",
                      hint="打开目标文件夹，从 URL /drive/folders/<id> 复制该段"),
            CredField("drive_id", "共享盘 ID", placeholder="团队盘（Shared Drive）才需填写",
                      hint="访问共享盘时必填，否则列举不到共享盘内的文件"),
        ),
    ),
)
