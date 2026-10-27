"""Seafile 资料库文档源（``source_type=seafile``）。

认证：``Authorization: Token <api_token>``（用户 API Token，不允许含空白字符）。
枚举：``GET /api2/repos/``（资料库列表）→ ``GET /api2/repos/{repo_id}/dir/?p=<path>``。
正文：**两步下载** —— 先 ``GET /api2/repos/{repo_id}/file/?p=<path>`` 取 fileserver 临时
下载链接，再请求该链接取字节流；**第二步不带令牌**（fileserver 是独立域名/端口，
凭链接自带的一次性凭据访问）。

资源 ID：``repo:<repo_id>:<path>``（目录）与 ``file:<repo_id>:<path>``（文件）。
加密资料库无法读取内容，列举时跳过；不支持转换的格式（图片 / 音视频等）同样跳过。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from app.connectors.doc_sources._host import resolve_host
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

API_PREFIX = "/api2"
REPOS_PATH = "/api2/repos/"
DIR_PATH = "/api2/repos/{repo_id}/dir/"
FILE_LINK_PATH = "/api2/repos/{repo_id}/file/"

# 单次目录列举上限
DIR_PAGE_LIMIT = 500


def _encode_dir(repo_id: str, path: str) -> str:
    return f"repo:{repo_id}:{path}"


def _encode_file(repo_id: str, path: str) -> str:
    return f"file:{repo_id}:{path}"


def _decode(doc_id: str) -> Tuple[str, str, str]:
    parts = (doc_id or "").split(":", 2)
    if len(parts) != 3 or parts[0] not in ("repo", "file"):
        raise DocSourceError(f"无法解析的 Seafile 资源标识：{doc_id}")
    return parts[0], parts[1], parts[2]


def _normalize_path(path: str) -> str:
    """目录路径统一为以 / 开头、无结尾斜杠（根为 ``/``）。"""
    path = (path or "").strip() or "/"
    if not path.startswith("/"):
        path = "/" + path
    if len(path) > 1:
        path = path.rstrip("/")
    return path


class SeafileDocSource(BaseDocSource):
    source_type = "seafile"
    token_in = "none"   # 自定义头 Authorization: Token <api_token>
    error_code_field = None
    timeout = 30.0

    # ── 凭据 ──────────────────────────────────────────────────
    @property
    def _host(self) -> str:
        return resolve_host(self.credentials.get("base_url") or "")

    def _auth_headers(self) -> Dict[str, str]:
        token = (self.credentials.get("api_token") or "").strip()
        if not token:
            raise DocSourceError("缺少 Seafile API Token")
        if any(ch.isspace() for ch in token):
            raise DocSourceError("Seafile API Token 不允许包含空白字符")
        return {"Authorization": f"Token {token}"}

    def _repo_id(self) -> str:
        return (self.credentials.get("repo_id") or "").strip()

    def _root_path(self) -> str:
        return _normalize_path(self.credentials.get("path") or "/")

    # ── 实现三个抽象方法 ──────────────────────────────────────
    async def test_connection(self) -> DocConnResult:
        try:
            repos = await self._list_repos()
            if not repos:
                return DocConnResult(
                    ok=False,
                    message="凭据有效，但未获取到任何资料库：请确认该 Token 所属账号对目标"
                            "资料库有读权限（加密资料库无法读取）",
                )
            return DocConnResult(
                ok=True, message="连通成功：凭据有效", identity=f"可访问资料库 {len(repos)} 个",
            )
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            if not parent_id:
                if self._repo_id():
                    # 凭据里指定了资料库：直接列其根目录
                    return await self._list_dir(self._repo_id(), self._root_path())
                return await self._list_repos()
            kind, repo_id, path = _decode(parent_id)
            if kind != "repo":
                return []
            return await self._list_dir(repo_id, path)
        finally:
            await self.aclose()

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            kind, repo_id, path = _decode(doc_id)
            if kind != "file":
                raise DocSourceError(f"{doc_id} 不是可导入的文件")
            url = await self._download_link(repo_id, path)
            # fileserver 请求不带令牌：链接本身已含一次性凭据
            resp = await self._request("GET", url, with_token=False)
            if resp.status_code >= 400:
                raise DocSourceError(self._http_error_message(resp))
            name = path.rsplit("/", 1)[-1]
            if is_supported(name):
                return FetchDocResult(
                    title=name, markdown=bytes_to_markdown(name, resp.content), updated_at=None,
                )
            text = bytes_to_text(resp.content).strip()
            if not text:
                raise DocSourceError(f"文件 {name} 未解析出任何文本")
            return FetchDocResult(title=name, markdown=text, updated_at=None)
        finally:
            await self.aclose()

    # ── 私有辅助 ──────────────────────────────────────────────
    async def _list_repos(self) -> List[ExternalDocRef]:
        data = await self._request_json(
            "GET", f"{self._host}{REPOS_PATH}", headers=self._auth_headers()
        )
        refs: List[ExternalDocRef] = []
        for repo in data or []:
            repo_id = repo.get("id") or ""
            if not repo_id:
                continue
            if repo.get("encrypted"):
                # 加密资料库服务端无法解密，读取必然失败
                logger.info("seafile 跳过加密资料库 repo_id=%s", repo_id)
                continue
            refs.append(
                ExternalDocRef(
                    doc_id=_encode_dir(repo_id, "/"),
                    title=repo.get("name") or repo_id,
                    node_type="folder",
                )
            )
        return refs

    async def _list_dir(self, repo_id: str, path: str) -> List[ExternalDocRef]:
        data = await self._request_json(
            "GET", f"{self._host}{DIR_PATH}".format(repo_id=quote(repo_id, safe="")),
            headers=self._auth_headers(),
            params={"p": path, "t": "d"},
        )
        refs: List[ExternalDocRef] = []
        for entry in data or []:
            name = entry.get("name") or ""
            if not name:
                continue
            child = f"{path.rstrip('/')}/{name}"
            if entry.get("type") == "dir":
                refs.append(
                    ExternalDocRef(
                        doc_id=_encode_dir(repo_id, child),
                        title=name,
                        node_type="folder",
                        parent_id=_encode_dir(repo_id, path),
                        updated_at=str(entry.get("mtime") or "") or None,
                    )
                )
                continue
            if not is_supported(name):
                continue
            refs.append(
                ExternalDocRef(
                    doc_id=_encode_file(repo_id, child),
                    title=name,
                    node_type="doc",
                    parent_id=_encode_dir(repo_id, path),
                    updated_at=str(entry.get("mtime") or "") or None,
                )
            )
            if len(refs) >= DIR_PAGE_LIMIT:
                break
        return refs

    async def _download_link(self, repo_id: str, path: str) -> str:
        """取 fileserver 下载链接（第一步，带令牌）。"""
        resp = await self._request(
            "GET",
            f"{self._host}{FILE_LINK_PATH}".format(repo_id=quote(repo_id, safe="")),
            headers=self._auth_headers(),
            params={"p": path, "reused": "1"},
        )
        if resp.status_code >= 400:
            raise DocSourceError(self._http_error_message(resp))
        try:
            body = resp.json()
        except ValueError:
            # 部分版本直接返回带引号的 URL 文本
            body = (resp.text or "").strip().strip('"')
        url = body if isinstance(body, str) else ""
        if not url:
            raise DocSourceError(f"未能获取文件下载链接：{path}")
        return url


register_doc_source(
    "seafile",
    SeafileDocSource,
    ProviderMeta(
        source_type="seafile",
        name="Seafile",
        desc="资料库内的文档（两步下载）",
        host="https://（按部署地址）",
        credential_fields=(
            CredField("base_url", "Seafile 地址", required=True,
                      placeholder="https://seafile.example.com",
                      hint="支持部署路径前缀；内网部署需先把域名加入 SSRF_WHITELIST"),
            CredField("api_token", "API Token", required=True, secret=True,
                      placeholder="用户设置中生成的 API Token",
                      hint="不允许包含空白字符"),
            CredField("repo_id", "资料库 ID", placeholder="留空则列出全部资料库",
                      hint="填写后直接列出该资料库根目录"),
            CredField("path", "资料库内路径", placeholder="/",
                      hint="仅在填写了资料库 ID 时生效，默认根目录 /"),
        ),
    ),
)
