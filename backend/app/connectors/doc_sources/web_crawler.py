"""Web Crawler（Sitemap）文档源（``source_type=web_crawler``）。

**本连接器取代早期的 ``web`` 种子 URL 简易抓取实现**（``doc_sources/web.py`` 已删除）：
早期实现只能从种子页抽同域 ``<a href>`` 下钻两层，覆盖面依赖页面上的链接，既不完整也
不稳定。正式实现以 ``sitemap.xml`` 为入口，支持 ``sitemapindex`` 递归、包含 / 排除正则、
页数上限，能拿到站点**声明的完整页面清单**。

解析：``<urlset><url><loc>/<lastmod>`` 与 ``<sitemapindex><sitemap><loc>``（标准库
``xml.etree.ElementTree``，与 ``rss.py`` 共用同一套去命名空间处理）。
正文：逐页抓取 → HTML → Markdown（``html.html_to_markdown``）。

安全：每个 URL（sitemap 与页面）均经 ``_host.resolve_url`` 校验，拒绝内网 / 环回 /
保留网段；内网站点需先加入 ``SSRF_WHITELIST``。
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from xml.etree import ElementTree

from app.connectors.doc_sources._host import resolve_url
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
from app.connectors.doc_sources.html import extract_title, html_to_markdown

logger = logging.getLogger(__name__)

# sitemapindex 递归层数与解析出的页面上限（防止失控的全站抓取）
DEFAULT_MAX_DEPTH = 2
MAX_DEPTH_LIMIT = 5
DEFAULT_MAX_PAGES = 200
MAX_PAGES_LIMIT = 1000
# 单个 sitemap 最多解析的子 sitemap 数
MAX_CHILD_SITEMAPS = 50

SEP = "::"


def _localname(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in (tag or "") else (tag or "")


def _encode_sitemap(url: str) -> str:
    return f"sm{SEP}{url}"


def _encode_dir(prefix: str) -> str:
    return f"dir{SEP}{prefix}"


def _encode_page(url: str) -> str:
    return f"page{SEP}{url}"


def _decode(doc_id: str) -> Tuple[str, str]:
    parts = (doc_id or "").split(SEP, 1)
    if len(parts) != 2 or parts[0] not in ("sm", "dir", "page"):
        raise DocSourceError(f"无法解析的站点资源标识：{doc_id}")
    return parts[0], parts[1]


def parse_sitemap(payload: bytes) -> Tuple[List[str], List[Dict[str, str]]]:
    """解析 sitemap，返回 (子 sitemap 列表, 页面列表[{loc,lastmod}])。

    两种根元素：``<urlset>``（页面清单）与 ``<sitemapindex>``（子 sitemap 索引）。
    """
    text = (payload or b"").decode("utf-8", errors="ignore").strip()
    if not text:
        return [], []
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise DocSourceError(f"sitemap 解析失败：{exc}") from exc
    kind = _localname(root.tag)
    children: List[str] = []
    pages: List[Dict[str, str]] = []
    for node in root:
        if kind == "sitemapindex" and _localname(node.tag) == "sitemap":
            loc = _child_text(node, "loc")
            if loc:
                children.append(loc)
            continue
        if kind == "urlset" and _localname(node.tag) == "url":
            loc = _child_text(node, "loc")
            if loc:
                pages.append({"loc": loc, "lastmod": _child_text(node, "lastmod")})
    return children, pages


def _child_text(node, name: str) -> str:
    for child in node:
        if _localname(child.tag) == name:
            return (child.text or "").strip()
    return ""


def _path_of(url: str) -> str:
    return urlparse(url).path or "/"


class WebCrawlerDocSource(BaseDocSource):
    source_type = "web_crawler"
    token_in = "none"
    error_code_field = None
    timeout = 30.0

    def __init__(self, credentials: Dict[str, Any]) -> None:
        super().__init__(credentials)
        self._pages_cache: Optional[List[Dict[str, str]]] = None

    # ── 凭据 ──────────────────────────────────────────────────
    def _sitemaps(self) -> List[str]:
        raw = self.credentials.get("sitemap_url") or ""
        out: List[str] = []
        seen = set()
        for line in re.split(r"[\n,]+", raw):
            url = line.strip()
            if not url:
                continue
            url = resolve_url(url)
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out

    def _max_pages(self) -> int:
        try:
            value = int(str(self.credentials.get("max_pages") or "").strip()
                        or DEFAULT_MAX_PAGES)
        except ValueError:
            value = DEFAULT_MAX_PAGES
        return max(1, min(value, MAX_PAGES_LIMIT))

    def _max_depth(self) -> int:
        try:
            value = int(str(self.credentials.get("max_depth") or "").strip()
                        or DEFAULT_MAX_DEPTH)
        except ValueError:
            value = DEFAULT_MAX_DEPTH
        return max(0, min(value, MAX_DEPTH_LIMIT))

    def _include_re(self) -> Optional[re.Pattern]:
        raw = (self.credentials.get("include_patterns") or "").strip()
        return re.compile(raw) if raw else None

    def _exclude_re(self) -> Optional[re.Pattern]:
        raw = (self.credentials.get("exclude_patterns") or "").strip()
        return re.compile(raw) if raw else None

    def _kept(self, url: str) -> bool:
        include = self._include_re()
        exclude = self._exclude_re()
        if include and not include.search(url):
            return False
        if exclude and exclude.search(url):
            return False
        return True

    # ── 实现三个抽象方法 ──────────────────────────────────────
    async def test_connection(self) -> DocConnResult:
        try:
            pages = await self._load_pages()
            if not pages:
                return DocConnResult(
                    ok=False,
                    message="未从 sitemap 解析到任何页面：请检查 sitemap 地址是否可访问，"
                            "或放宽「包含 / 排除规则」",
                )
            return DocConnResult(
                ok=True, message="连通成功：sitemap 可解析",
                identity=f"可抓取页面 {len(pages)} 个",
            )
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            if not parent_id:
                return [
                    ExternalDocRef(
                        doc_id=_encode_sitemap(url),
                        title=urlparse(url).netloc or url,
                        node_type="folder", url=url,
                    )
                    for url in self._sitemaps()
                ]
            kind, value = _decode(parent_id)
            pages = await self._load_pages()
            if kind == "sm":
                return self._children_of(pages, "")
            if kind == "dir":
                return self._children_of(pages, value)
            return []
        finally:
            await self.aclose()

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            kind, url = _decode(doc_id)
            if kind != "page":
                raise DocSourceError(f"{doc_id} 不是可导入的页面")
            resp = await self._request("GET", resolve_url(url))
            if resp.status_code >= 400:
                raise DocSourceError(self._http_error_message(resp))
            html = resp.text or ""
            title = extract_title(html) or _path_of(url).rstrip("/").rsplit("/", 1)[-1] \
                or urlparse(url).netloc
            return FetchDocResult(title=title, markdown=html_to_markdown(html), updated_at=None)
        finally:
            await self.aclose()

    # ── 私有辅助 ──────────────────────────────────────────────
    async def _load_pages(self) -> List[Dict[str, str]]:
        """递归解析全部 sitemap，去重后按规则过滤（一次导入会话内只解析一次）。"""
        if self._pages_cache is not None:
            return self._pages_cache
        collected: List[Dict[str, str]] = []
        seen: set = set()

        async def walk(url: str, depth: int) -> None:
            if depth > self._max_depth() or len(collected) >= self._max_pages():
                return
            resp = await self._request("GET", resolve_url(url))
            if resp.status_code >= 400:
                raise DocSourceError(f"sitemap 不可访问：{self._http_error_message(resp)}")
            children, pages = parse_sitemap(resp.content)
            for p in pages:
                loc = p.get("loc") or ""
                if not loc or loc in seen or not self._kept(loc):
                    continue
                seen.add(loc)
                collected.append(p)
                if len(collected) >= self._max_pages():
                    break
            for child in children[:MAX_CHILD_SITEMAPS]:
                if len(collected) >= self._max_pages():
                    break
                await walk(child, depth + 1)

        try:
            for sitemap in self._sitemaps():
                await walk(sitemap, 0)
        finally:
            self._pages_cache = collected
        logger.info("web_crawler 解析到页面 %s 个", len(collected))
        return collected

    def _children_of(
        self, pages: List[Dict[str, str]], prefix: str
    ) -> List[ExternalDocRef]:
        """按 URL 路径层级生成目录 / 页面节点（懒加载，只算当前层）。

        目录前缀统一以 ``/`` 开头（与 URL path 对齐），根层级前缀为空字符串。
        """
        folders: Dict[str, str] = {}
        docs: List[ExternalDocRef] = []
        raw = (prefix or "").strip("/")
        base = f"/{raw}" if raw else ""
        for p in pages:
            path = _path_of(p.get("loc") or "")
            if base and not path.startswith(base + "/"):
                continue
            rest = path[len(base):].strip("/") if base else path.strip("/")
            if not rest:
                continue
            seg = rest.split("/")
            if len(seg) > 1:
                child = f"{base}/{seg[0]}"
                folders.setdefault(child, seg[0])
                continue
            docs.append(
                ExternalDocRef(
                    doc_id=_encode_page(p.get("loc") or ""),
                    title=seg[0] or "首页",
                    node_type="doc",
                    parent_id=_encode_dir(base) if base else None,
                    updated_at=p.get("lastmod") or None,
                    url=p.get("loc"),
                )
            )
        refs = [
            ExternalDocRef(
                doc_id=_encode_dir(folder), title=name, node_type="folder",
                parent_id=_encode_dir(base) if base else None,
            )
            for folder, name in sorted(folders.items())
        ]
        return refs + docs


register_doc_source(
    "web_crawler",
    WebCrawlerDocSource,
    ProviderMeta(
        source_type="web_crawler",
        name="Web Crawler",
        desc="按 sitemap 抓取整站页面（自动转 Markdown）",
        host="https://（按 sitemap 域名）",
        credential_fields=(
            CredField("sitemap_url", "Sitemap 地址", required=True, multiline=True,
                      placeholder="https://example.com/sitemap.xml",
                      hint="每行一个（也可用逗号分隔）；支持 sitemapindex 递归。"
                           "内网站点需先加入 SSRF_WHITELIST"),
            CredField("include_patterns", "包含规则（正则）",
                      placeholder="^https://example\\.com/docs/",
                      hint="留空表示不过滤；命中的 URL 才会被抓取"),
            CredField("exclude_patterns", "排除规则（正则）",
                      placeholder="/(tag|category)/",
                      hint="在包含规则之后再过滤一遍"),
            CredField("max_pages", "最多页面数", placeholder="200",
                      hint=f"默认 {DEFAULT_MAX_PAGES}，上限 {MAX_PAGES_LIMIT}"),
            CredField("max_depth", "sitemapindex 递归层数", placeholder="2",
                      hint=f"默认 {DEFAULT_MAX_DEPTH}，上限 {MAX_DEPTH_LIMIT}"),
        ),
    ),
)
