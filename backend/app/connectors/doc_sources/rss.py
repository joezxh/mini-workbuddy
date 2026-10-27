"""RSS / Atom / JSON Feed 文档源（``source_type=rss``）。

解析用标准库（``xml.etree.ElementTree`` + ``json``），**不引入 gofeed 之类的新依赖**；
三种格式统一规约为 ``{id, title, link, updated}``。

**不支持删除同步**：feed 天然滚动淘汰旧条目，无法区分「下架」与「滚出窗口」，因此本
连接器只做新增 / 覆盖，从不产出删除动作（这是平台特性，不是实现取舍）。

**凭据隔离**：``auth_headers``（Basic / Bearer / Cookie 均可）**只附加在 feed 请求上**，
抓取文章正文页时绝不携带，避免把凭据泄漏给第三方站点。

文档 ID：``feed::<feed_url>``（订阅源，可下钻）与 ``item::<feed_url>::<link>``
（条目；带上 feed_url 防止跨源的 GUID 撞车）。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional
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

# 单个订阅源最多返回的条目数（feed 可能很长，列表不宜无限增长）
DEFAULT_MAX_ITEMS = 50
MAX_ITEMS_LIMIT = 500
# 订阅源地址分隔符（URL 含 "://" 但不含 "::"，故安全）
SEP = "::"

CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}"


def _localname(tag: str) -> str:
    """去掉 XML 命名空间前缀。"""
    return tag.split("}", 1)[1] if "}" in (tag or "") else (tag or "")


def parse_headers(raw: str) -> Dict[str, str]:
    """解析 ``Name: Value`` 多行请求头；非法行跳过（不阻断整体）。"""
    out: Dict[str, str] = {}
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        name, _, value = line.partition(":")
        name, value = name.strip(), value.strip()
        if name:
            out[name] = value
    return out


def parse_feed(payload: bytes) -> List[Dict[str, Any]]:
    """解析 RSS2.0 / Atom / JSON Feed，返回条目列表。

    条目结构：``{id, title, link, updated, summary}``；``id`` 取
    ``GUID > Link > Title`` 第一个非空值。
    """
    text = (payload or b"").decode("utf-8", errors="ignore").strip()
    if not text:
        return []
    if text.startswith("{"):
        return _parse_json_feed(text)
    return _parse_xml_feed(text)


def _parse_json_feed(text: str) -> List[Dict[str, Any]]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out: List[Dict[str, Any]] = []
    for item in (data or {}).get("items") or []:
        link = item.get("url") or item.get("external_url") or ""
        out.append({
            "id": item.get("id") or link or item.get("title") or "",
            "title": item.get("title") or "",
            "link": link,
            "updated": item.get("date_modified") or item.get("date_published") or "",
            "summary": item.get("content_text") or item.get("summary") or "",
        })
    return out


def _parse_xml_feed(text: str) -> List[Dict[str, Any]]:
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return []
    entries = []
    if _localname(root.tag) == "rss":
        channel = root.find("channel")
        entries = list(channel.findall("item")) if channel is not None else []
    else:  # Atom: <feed><entry>
        entries = [e for e in root if _localname(e.tag) == "entry"]
    out: List[Dict[str, Any]] = []
    for entry in entries:
        out.append({
            "id": _child_text(entry, "guid", "id") or _atom_link(entry) or _child_text(entry, "title"),
            "title": _child_text(entry, "title"),
            "link": _child_text(entry, "link") or _atom_link(entry),
            "updated": _child_text(entry, "pubDate", "updated", "modified", "dc:date"),
            "summary": _child_text(entry, "description", "summary", f"{CONTENT_NS}encoded"),
        })
    return out


def _child_text(entry, *names: str) -> str:
    for child in entry:
        if _localname(child.tag) in names:
            return (child.text or "").strip()
    return ""


def _atom_link(entry) -> str:
    """Atom 的链接在 ``<link href=...>`` 属性里（rel=alternate 优先）。"""
    fallback = ""
    for child in entry:
        if _localname(child.tag) != "link":
            continue
        href = (child.get("href") or "").strip()
        rel = (child.get("rel") or "alternate").strip()
        if href and rel == "alternate":
            return href
        if href and not fallback:
            fallback = href
    return fallback


def _encode_feed(url: str) -> str:
    return f"feed{SEP}{url}"


def _encode_item(feed_url: str, link: str) -> str:
    return f"item{SEP}{feed_url}{SEP}{link}"


def _decode(doc_id: str) -> tuple:
    parts = (doc_id or "").split(SEP)
    if len(parts) == 2 and parts[0] == "feed":
        return "feed", parts[1], ""
    if len(parts) == 3 and parts[0] == "item":
        return "item", parts[1], parts[2]
    raise DocSourceError(f"无法解析的订阅源标识：{doc_id}")


class RssDocSource(BaseDocSource):
    source_type = "rss"
    token_in = "none"
    # feed 站点只用 HTTP 状态表达成败，无数值业务码
    error_code_field = None
    timeout = 30.0

    # ── 凭据 ──────────────────────────────────────────────────
    def _feed_urls(self) -> List[str]:
        raw = self.credentials.get("feed_urls") or ""
        urls: List[str] = []
        seen = set()
        for chunk in re.split(r"[\n,]+", raw):
            url = chunk.strip()
            if not url:
                continue
            url = resolve_url(url)
            if url not in seen:
                seen.add(url)
                urls.append(url)
        return urls

    def _auth_headers(self) -> Dict[str, str]:
        return parse_headers(self.credentials.get("auth_headers") or "")

    def _max_items(self) -> int:
        try:
            value = int(str(self.credentials.get("max_items") or "").strip() or DEFAULT_MAX_ITEMS)
        except ValueError:
            value = DEFAULT_MAX_ITEMS
        return max(1, min(value, MAX_ITEMS_LIMIT))

    # ── 实现三个抽象方法 ──────────────────────────────────────
    async def test_connection(self) -> DocConnResult:
        urls = self._feed_urls()
        if not urls:
            return DocConnResult(ok=False, message="未配置任何订阅源地址")
        ok_count = 0
        total_items = 0
        failures: List[str] = []
        for url in urls[:10]:
            try:
                items = await self._fetch_feed(url)
                ok_count += 1
                total_items += len(items)
            except DocSourceError as exc:
                # 单个源失败不阻断：记录原因，仍按「部分可用」判定
                failures.append(f"{urlparse(url).netloc}：{exc}")
                continue
        if ok_count == 0:
            detail = "；".join(failures[:3])
            return DocConnResult(ok=False, message=f"全部订阅源均不可访问：{detail}")
        identity = f"{ok_count}/{len(urls)} 个订阅源，共 {total_items} 条"
        if failures:
            return DocConnResult(
                ok=True,
                message=f"部分订阅源不可用（{len(failures)} 个），其余可正常同步",
                identity=identity,
            )
        return DocConnResult(ok=True, message="连通成功：订阅源可访问", identity=identity)

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            if not parent_id:
                return [
                    ExternalDocRef(
                        doc_id=_encode_feed(url),
                        title=urlparse(url).netloc or url,
                        node_type="folder",
                        url=url,
                    )
                    for url in self._feed_urls()
                ]
            kind, feed_url, _link = _decode(parent_id)
            if kind != "feed":
                return []
            items = await self._fetch_feed(feed_url)
            return [
                ExternalDocRef(
                    doc_id=_encode_item(feed_url, item.get("link") or ""),
                    title=item.get("title") or item.get("link") or "未命名条目",
                    node_type="doc",
                    parent_id=_encode_feed(feed_url),
                    updated_at=item.get("updated") or None,
                    url=item.get("link") or None,
                )
                for item in items[: self._max_items()]
                if item.get("link")
            ]
        finally:
            await self.aclose()

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            kind, _feed_url, link = _decode(doc_id)
            if kind != "item" or not link:
                raise DocSourceError(f"{doc_id} 不是可导入的订阅条目")
            # 正文页不携带 auth_headers：避免凭据泄漏给第三方站点
            resp = await self._request("GET", resolve_url(link))
            if resp.status_code >= 400:
                raise DocSourceError(self._http_error_message(resp))
            html = resp.text or ""
            title = extract_title(html) or (urlparse(link).path.rstrip("/").rsplit("/", 1)[-1]
                                            or urlparse(link).netloc)
            return FetchDocResult(
                title=title, markdown=html_to_markdown(html), updated_at=None,
            )
        finally:
            await self.aclose()

    # ── 私有辅助 ──────────────────────────────────────────────
    async def _fetch_feed(self, url: str) -> List[Dict[str, Any]]:
        resp = await self._request("GET", url, headers=self._auth_headers() or None)
        if resp.status_code >= 400:
            raise DocSourceError(self._http_error_message(resp))
        items = parse_feed(resp.content)
        if not items:
            raise DocSourceError(f"订阅源未解析出任何条目：{url}")
        return items


register_doc_source(
    "rss",
    RssDocSource,
    ProviderMeta(
        source_type="rss",
        name="RSS / Atom",
        desc="订阅源文章（RSS2.0 / Atom / JSON Feed）",
        host="https://（按订阅源地址）",
        credential_fields=(
            CredField("feed_urls", "订阅源地址", required=True, multiline=True,
                      placeholder="https://blog.example.com/feed.xml",
                      hint="每行一个地址（也可用逗号分隔）；支持 RSS2.0 / Atom / "
                           "JSON Feed。内网地址需先加入 SSRF_WHITELIST"),
            CredField("auth_headers", "订阅源请求头", secret=True, multiline=True,
                      placeholder="Authorization: Bearer <token>",
                      hint="每行一条 Name: Value，用于私有订阅源；只发给订阅源，"
                           "不会发给文章正文页"),
            CredField("max_items", "每个源最多条目数", placeholder="50",
                      hint="默认 50，上限 500"),
        ),
    ),
)
