"""语雀文档源（新建）。

认证：``X-Auth-Token`` 请求头（个人访问令牌），无 access_token 换取流程。
枚举：第一层为知识库（repos），第二层为该库的文档（docs）。
正文：``GET /api/v2/repos/{ns}/docs/{slug}`` 的 ``body`` 本身就是 Markdown，
      无需块转换，直接返回。

域名硬编码，不接受外部传入 base_url（防 SSRF）。
"""
from __future__ import annotations

import logging
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

HOST = "https://www.yuque.com"
USER_PATH = "/api/v2/user"
GROUPS_PATH = "/api/v2/groups"
USER_REPOS_PATH = "/api/v2/users/{login}/repos"
GROUP_REPOS_PATH = "/api/v2/groups/{login}/repos"
DOCS_PATH = "/api/v2/repos/{ns}/docs"
DOC_PATH = "/api/v2/repos/{ns}/docs/{slug}"
TOC_PATH = "/api/v2/repos/{ns}/toc"

MAX_PAGES = 20

# 目录模式：none=平铺（默认）｜toc=按语雀目录层级拼文件名
FOLDER_MODE_NONE = "none"
FOLDER_MODE_TOC = "toc"

logger = logging.getLogger(__name__)


def build_toc_paths(items: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """把语雀目录（``/api/v2/repos/{ns}/toc``）展平成 ``slug → 路径``。

    目录项是**带 depth 的扁平列表**：用栈按 depth 还原层级，``TITLE`` 类型的条目
    只作为分组（不对应文档），``DOC`` 条目才写入结果。
    """
    stack: List[str] = []
    paths: Dict[str, List[str]] = {}
    for item in items or []:
        try:
            depth = int(item.get("depth") or 0)
        except ValueError:
            depth = 0
        title = (item.get("title") or "").strip()
        stack = stack[:depth] + [title]
        if (item.get("type") or "").upper() == "DOC" and item.get("slug"):
            paths[str(item["slug"])] = [t for t in stack if t]
    return paths


class YuqueDocSource(BaseDocSource):
    source_type = "yuque"
    token_in = "none"   # 用静态令牌，走 X-Auth-Token 头

    def _auth_headers(self) -> Dict[str, str]:
        token = self.credentials.get("token") or ""
        if not token:
            raise DocSourceError("缺少个人访问令牌（X-Auth-Token）")
        return {"X-Auth-Token": token}

    @property
    def _namespace(self) -> str:
        return (self.credentials.get("namespace") or "").strip()

    # ── 目录模式（对齐 WeKnora 文档 §3.4 的 settings）───────────
    def _folder_mode(self) -> str:
        """``none`` 平铺（默认）｜``toc`` 按语雀目录层级拼文件名。"""
        mode = (self.credentials.get("folder_mode") or FOLDER_MODE_NONE).strip().lower()
        return FOLDER_MODE_TOC if mode == FOLDER_MODE_TOC else FOLDER_MODE_NONE

    def _toc_only(self) -> bool:
        """仅导入目录中出现的文档；**只在 folder_mode=toc 时生效**。"""
        if self._folder_mode() != FOLDER_MODE_TOC:
            return False
        raw = str(self.credentials.get("toc_only") or "").strip().lower()
        return raw in ("true", "1", "yes", "on")

    async def test_connection(self) -> DocConnResult:
        try:
            data = await self._request_json(
                "GET", f"{HOST}{USER_PATH}", headers=self._auth_headers()
            )
            user = (data or {}).get("data") or {}
            name = user.get("name") or user.get("login") or ""
            ns = self._namespace
            suffix = f"（默认仓库 {ns}）" if ns else ""
            return DocConnResult(
                ok=True, message="连通成功：令牌有效", identity=f"语雀用户 {name}{suffix}",
            )
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            headers = self._auth_headers()
            # 凭据里指定了仓库时，直接进入该仓库的文档列表
            if not parent_id and self._namespace:
                return await self._list_docs(self._namespace, headers)
            if not parent_id:
                return await self._list_repos(headers)
            return await self._list_docs(parent_id, headers)
        finally:
            await self.aclose()

    async def _list_repos(self, headers: Dict[str, str]) -> List[ExternalDocRef]:
        refs: List[ExternalDocRef] = []
        user = (await self._request_json("GET", f"{HOST}{USER_PATH}", headers=headers)
                or {}).get("data") or {}
        login = user.get("login")
        if login:
            data = await self._request_json(
                "GET", f"{HOST}{USER_REPOS_PATH}".format(login=login), headers=headers
            )
            refs += self._repos_to_refs((data or {}).get("data") or [])
        # 团队知识库：数量可能较多，取前若干个避免列表过长
        groups = (await self._request_json("GET", f"{HOST}{GROUPS_PATH}", headers=headers)
                  or {}).get("data") or []
        for g in groups[:10]:
            g_login = g.get("login")
            if not g_login:
                continue
            try:
                data = await self._request_json(
                    "GET", f"{HOST}{GROUP_REPOS_PATH}".format(login=g_login),
                    headers=headers,
                )
            except DocSourceError:
                continue  # 单个团队无权限不影响其它仓库
            refs += self._repos_to_refs((data or {}).get("data") or [])
        return refs

    @staticmethod
    def _repos_to_refs(repos: List[Dict[str, Any]]) -> List[ExternalDocRef]:
        refs: List[ExternalDocRef] = []
        for r in repos:
            ns = r.get("namespace") or r.get("slug")
            if not ns:
                continue
            refs.append(
                ExternalDocRef(
                    doc_id=str(ns),
                    title=r.get("name") or str(ns),
                    node_type="space",
                    url=f"{HOST}/{ns}",
                )
            )
        return refs

    async def _list_docs(
        self, namespace: str, headers: Dict[str, str]
    ) -> List[ExternalDocRef]:
        data = await self._request_json(
            "GET", f"{HOST}{DOCS_PATH}".format(ns=namespace), headers=headers
        )
        toc_paths: Dict[str, List[str]] = {}
        toc_mode = self._folder_mode() == FOLDER_MODE_TOC
        if toc_mode:
            toc_paths = await self._load_toc(namespace, headers)
        refs: List[ExternalDocRef] = []
        for d in (data or {}).get("data") or []:
            slug = d.get("slug")
            if not slug:
                continue
            # 语雀的 Sheet/Table 类型不是 Markdown 正文，跳过避免导入空文档
            if (d.get("type") or "Doc") != "Doc":
                continue
            path = toc_paths.get(slug)
            if toc_mode and not path and self._toc_only():
                # toc_only 是「准入过滤器」：目录外的文档不入库
                continue
            title = "/".join(path) if path else (d.get("title") or slug)
            refs.append(
                ExternalDocRef(
                    doc_id=f"{namespace}/{slug}",
                    title=title,
                    node_type="doc",
                    parent_id=namespace,
                    updated_at=d.get("updated_at") or d.get("content_updated_at"),
                    url=f"{HOST}/{namespace}/{slug}",
                )
            )
        return refs

    async def _load_toc(
        self, namespace: str, headers: Dict[str, str]
    ) -> Dict[str, List[str]]:
        """读取语雀目录，返回 ``slug → [分组…, 标题]``；失败时降级为平铺。"""
        try:
            data = await self._request_json(
                "GET", f"{HOST}{TOC_PATH}".format(ns=namespace), headers=headers
            )
        except DocSourceError:
            logger.warning("语雀目录读取失败，按平铺模式列举 ns=%s", namespace)
            return {}
        return build_toc_paths((data or {}).get("data") or [])

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            if "/" not in doc_id:
                raise DocSourceError(f"文档标识格式不正确：{doc_id}")
            # namespace 本身含斜杠（用户/仓库 或 团队/仓库），故从右侧切分
            ns, slug = doc_id.rsplit("/", 1)
            data = await self._request_json(
                "GET", f"{HOST}{DOC_PATH}".format(ns=ns, slug=slug),
                headers=self._auth_headers(),
            )
            doc = (data or {}).get("data") or {}
            body = doc.get("body") or ""
            return FetchDocResult(
                title=doc.get("title") or slug,
                markdown=body if body.endswith("\n") else body + "\n",
                updated_at=doc.get("updated_at") or doc.get("content_updated_at"),
            )
        finally:
            await self.aclose()


register_doc_source(
    "yuque",
    YuqueDocSource,
    ProviderMeta(
        source_type="yuque",
        name="语雀",
        desc="仓库文档（X-Auth-Token）",
        host=HOST,
        credential_fields=(
            CredField("token", "个人访问令牌", required=True, secret=True,
                      placeholder="X-Auth-Token"),
            CredField("namespace", "仓库 Namespace", required=True,
                      placeholder="joezxh/handbook",
                      hint="形如 用户/仓库 或 团队/仓库；填写后默认进入该仓库"),
            CredField("folder_mode", "目录模式", placeholder="none",
                      hint="none=平铺（默认）；toc=按语雀目录层级拼文件名"
                           "（书名/分组/标题）。切换后需重新导入一次才会归位"),
            CredField("toc_only", "仅导入目录内文档", placeholder="false",
                      hint="仅在 folder_mode=toc 时生效；属于准入过滤器，"
                           "已导入的副本不会因取消勾选而删除"),
        ),
    ),
)
