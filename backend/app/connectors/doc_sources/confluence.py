"""Confluence 文档源（``source_type=confluence``）。

认证三选一（与文档 §3.11 一致）：
1. Server / Data Center **PAT**：``Authorization: Bearer <token>``（推荐，7.9+）；
2. Server / Data Center **Basic**：``username`` + ``password``；
3. Cloud **Basic**：Atlassian 账号邮箱 + ``api_token``。

枚举：``GET /rest/api/space`` → ``GET /rest/api/content?spaceKey=&expand=body.rendered``。
正文：``GET /rest/api/content/{id}?expand=body.view`` → HTML → Markdown。

地址：Cloud 基址自动补 ``/wiki``（``https://<site>.atlassian.net``）；Server/DC 由用户填写
→ 经 ``_host.resolve_host`` 校验（内网需先加入 ``SSRF_WHITELIST``）。

**与文档的一处差异**：WeKnora 的「删除保护（消失页面 ≥20 且占比 ≥80% 时整次报错）」服务于
它的定时全量同步；本工程的导入是手动幂等的，映射表只做新建 / 覆盖 / 跳过，从不删除本地
文档，因此该阈值在此不适用。版本号仍作为 ``updated_at`` 回填，便于面板展示变更。
"""
from __future__ import annotations

import logging
from base64 import b64encode
from typing import Any, Dict, List, Optional, Tuple

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
from app.connectors.doc_sources.html import html_to_markdown

logger = logging.getLogger(__name__)

EDITION_SERVER = "server"
EDITION_CLOUD = "cloud"

SPACES_PATH = "/rest/api/space"
CONTENT_PATH = "/rest/api/content"
CONTENT_ITEM_PATH = "/rest/api/content/{page_id}"

# 分页上限，避免超大空间无限翻页
MAX_PAGES = 20
PAGE_LIMIT = 50


def _encode_space(key: str) -> str:
    return f"space:{key}"


def _encode_page(page_id: str) -> str:
    return f"page:{page_id}"


def _decode(doc_id: str) -> Tuple[str, str]:
    parts = (doc_id or "").split(":", 1)
    if len(parts) != 2 or parts[0] not in ("space", "page"):
        raise DocSourceError(f"无法解析的 Confluence 标识：{doc_id}")
    return parts[0], parts[1]


class ConfluenceDocSource(BaseDocSource):
    source_type = "confluence"
    token_in = "none"   # Basic / Bearer 均由 _auth_headers 自行组装
    # Confluence 只用 HTTP 状态码表达成败
    error_code_field = None
    timeout = 30.0

    # ── 凭据 ──────────────────────────────────────────────────
    @property
    def _edition(self) -> str:
        return (self.credentials.get("edition") or EDITION_SERVER).strip().lower()

    @property
    def _host(self) -> str:
        base = resolve_host(self.credentials.get("base_url") or "")
        if self._edition == EDITION_CLOUD and not base.rstrip("/").endswith("/wiki"):
            base = base.rstrip("/") + "/wiki"
        return base

    def _auth_headers(self) -> Dict[str, str]:
        username = (self.credentials.get("username") or "").strip()
        token = (self.credentials.get("token") or "").strip()      # Server PAT
        password = (self.credentials.get("password") or "").strip()
        api_token = (self.credentials.get("api_token") or "").strip()  # Cloud
        if token:
            return {"Authorization": f"Bearer {token}"}
        if api_token:
            return _basic(username, api_token, "Cloud API Token")
        if password:
            return _basic(username, password, "密码")
        raise DocSourceError(
            "缺少凭据：请填写 Server PAT（token）或「用户名 + 密码」或 Cloud 的"
            "「邮箱 + API Token」"
        )

    # ── 实现三个抽象方法 ──────────────────────────────────────
    async def test_connection(self) -> DocConnResult:
        try:
            self._auth_headers()  # 缺凭据时给出可操作提示
            data = await self._request_json(
                "GET", f"{self._host}{SPACES_PATH}",
                headers=self._auth_headers(), params={"limit": 1},
            )
            results = (data or {}).get("results") or []
            size = (data or {}).get("size")
            total = size if isinstance(size, int) else len(results)
            if not total:
                return DocConnResult(
                    ok=False,
                    message="凭据有效，但未获取到任何空间：请确认该账号对目标空间有查看权限",
                )
            return DocConnResult(
                ok=True, message="连通成功：凭据有效", identity=f"可访问空间 {total} 个",
            )
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            if not parent_id:
                return await self._list_spaces()
            kind, key = _decode(parent_id)
            if kind != "space":
                return []
            return await self._list_pages(key)
        finally:
            await self.aclose()

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            kind, page_id = _decode(doc_id)
            if kind != "page":
                raise DocSourceError(f"{doc_id} 不是可导入的页面")
            data = await self._request_json(
                "GET", f"{self._host}{CONTENT_ITEM_PATH}".format(page_id=page_id),
                headers=self._auth_headers(),
                params={"expand": "body.view"},
            )
            title = (data or {}).get("title") or "Confluence 页面"
            body = ((data or {}).get("body") or {}).get("view") or {}
            html = body.get("value") or ""
            if not html:
                raise DocSourceError(f"页面 {title} 未返回正文（可能无查看权限）")
            version = ((data or {}).get("version") or {})
            return FetchDocResult(
                title=title,
                markdown=html_to_markdown(html),
                updated_at=str(version.get("when") or "") or None,
            )
        finally:
            await self.aclose()

    # ── 私有辅助 ──────────────────────────────────────────────
    async def _list_spaces(self) -> List[ExternalDocRef]:
        data = await self._request_json(
            "GET", f"{self._host}{SPACES_PATH}",
            headers=self._auth_headers(), params={"limit": PAGE_LIMIT},
        )
        refs: List[ExternalDocRef] = []
        for s in (data or {}).get("results") or []:
            key = s.get("key") or ""
            if not key:
                continue
            refs.append(
                ExternalDocRef(
                    doc_id=_encode_space(key),
                    title=s.get("name") or key,
                    node_type="folder",
                )
            )
        return refs

    async def _list_pages(self, space_key: str) -> List[ExternalDocRef]:
        refs: List[ExternalDocRef] = []
        start = 0
        for _ in range(MAX_PAGES):
            data = await self._request_json(
                "GET", f"{self._host}{CONTENT_PATH}",
                headers=self._auth_headers(),
                params={
                    "spaceKey": space_key,
                    "type": "page",          # 不导入附件与博客文章
                    "limit": PAGE_LIMIT,
                    "start": start,
                    "expand": "version",
                },
            )
            results = (data or {}).get("results") or []
            for p in results:
                page_id = str(p.get("id") or "")
                if not page_id:
                    continue
                version = p.get("version") or {}
                refs.append(
                    ExternalDocRef(
                        doc_id=_encode_page(page_id),
                        title=p.get("title") or "未命名页面",
                        node_type="doc",
                        parent_id=_encode_space(space_key),
                        updated_at=str(version.get("when") or "") or None,
                    )
                )
            if len(results) < PAGE_LIMIT:
                break
            start += PAGE_LIMIT
        return refs


def _basic(username: str, secret: str, label: str) -> Dict[str, str]:
    if not username:
        raise DocSourceError(f"缺少用户名（Cloud 场景填 Atlassian 账号邮箱）以配合{label}")
    raw = f"{username}:{secret}".encode("utf-8")
    return {"Authorization": f"Basic {b64encode(raw).decode('ascii')}"}


register_doc_source(
    "confluence",
    ConfluenceDocSource,
    ProviderMeta(
        source_type="confluence",
        name="Confluence",
        desc="空间下的页面（Server / Cloud）",
        host="https://（按部署地址）",
        credential_fields=(
            CredField("base_url", "Confluence 地址", required=True,
                      placeholder="https://wiki.example.com",
                      hint="Cloud 填 https://<site>.atlassian.net（自动补 /wiki）；"
                           "内网部署需先把域名加入 SSRF_WHITELIST"),
            CredField("edition", "版本", placeholder="server",
                      hint="server（Server / Data Center，默认）或 cloud"),
            CredField("username", "用户名", placeholder="Cloud 填 Atlassian 账号邮箱",
                      hint="PAT 模式可留空；Basic 模式必填"),
            CredField("token", "Personal Access Token", secret=True,
                      placeholder="Server / DC 的个人访问令牌（推荐）",
                      hint="填了它即走 Bearer 认证，不再使用密码"),
            CredField("password", "密码", secret=True, placeholder="Server / DC 登录密码",
                      hint="未填 PAT 时与用户名配合做 Basic 认证"),
            CredField("api_token", "Cloud API Token", secret=True,
                      placeholder="https://id.atlassian.com/manage-profile/security/api-tokens",
                      hint="Cloud 场景与「邮箱」配合做 Basic 认证"),
        ),
    ),
)
