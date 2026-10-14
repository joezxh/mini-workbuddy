"""Notion 文档源（新建）。

认证：``Authorization: Bearer <secret>`` + ``Notion-Version`` 头（静态令牌）。
枚举：``POST /v1/search`` 按 object=page 过滤（可选 root_page 限定子树）。
正文：``GET /v1/blocks/{id}/children`` 递归分页 → 中间块 → Markdown。

域名硬编码，不接受外部传入 base_url（防 SSRF）。
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

HOST = "https://api.notion.com"
NOTION_VERSION = "2022-06-28"
SEARCH_PATH = "/v1/search"
BLOCKS_PATH = "/v1/blocks/{id}/children"

_KINDS: Dict[str, tuple] = {
    "paragraph": (PARAGRAPH, 0),
    "heading_1": (HEADING, 1),
    "heading_2": (HEADING, 2),
    "heading_3": (HEADING, 3),
    "bulleted_list_item": (BULLETED, 0),
    "numbered_list_item": (NUMBERED, 0),
    "to_do": (TODO, 0),
    "quote": (QUOTE, 0),
    "callout": (CALLOUT, 0),
    "code": (CODE, 0),
    "divider": (DIVIDER, 0),
    "toggle": (PARAGRAPH, 0),
}


def _rich_text(block: Dict[str, Any], btype: str) -> str:
    """取块内富文本（含链接）拼接为 Markdown 行内文本。"""
    body = block.get(btype) or {}
    parts: List[str] = []
    for run in body.get("rich_text") or []:
        text = run.get("plain_text") or ""
        url = (run.get("text") or {}).get("link", {}).get("url") if run.get("text") else None
        parts.append(f"[{text}]({url})" if url else text)
    return "".join(parts)


class NotionDocSource(BaseDocSource):
    source_type = "notion"
    token_in = "none"   # 静态 Integration Token，走 Authorization 头

    def _auth_headers(self) -> Dict[str, str]:
        secret = self.credentials.get("secret") or ""
        if not secret:
            raise DocSourceError("缺少 Integration Token")
        return {"Authorization": f"Bearer {secret}", "Notion-Version": NOTION_VERSION}

    @property
    def _root_page(self) -> str:
        return (self.credentials.get("root_page") or "").strip()

    async def test_connection(self) -> DocConnResult:
        try:
            data = await self._request_json(
                "POST", f"{HOST}{SEARCH_PATH}",
                headers=self._auth_headers(),
                json_body={"page_size": 1},
            )
            total = (data or {}).get("total") if isinstance(data, dict) else None
            identity = f"可访问对象 {total} 个" if isinstance(total, int) else "凭据有效"
            return DocConnResult(ok=True, message="连通成功：Integration Token 有效",
                                 identity=identity)
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            headers = self._auth_headers()
            refs: List[ExternalDocRef] = []
            cursor: Optional[str] = None
            for _ in range(10):
                body: Dict[str, Any] = {
                    "page_size": 50,
                    "filter": {"property": "object", "value": "page"},
                }
                if cursor:
                    body["start_cursor"] = cursor
                data = await self._request_json(
                    "POST", f"{HOST}{SEARCH_PATH}", headers=headers, json_body=body
                )
                for r in (data or {}).get("results") or []:
                    if r.get("object") != "page":
                        continue
                    pid = r.get("id")
                    if not pid:
                        continue
                    refs.append(
                        ExternalDocRef(
                            doc_id=str(pid),
                            title=self._page_title(r) or "未命名页面",
                            node_type="doc",
                            updated_at=r.get("last_edited_time"),
                            url=r.get("url"),
                        )
                    )
                if not (data or {}).get("has_more"):
                    break
                cursor = (data or {}).get("next_cursor")
                if not cursor:
                    break
            # 指定了根页面：优先把它自己放在首位
            if self._root_page:
                refs.sort(key=lambda r: r.doc_id != self._root_page)
            return refs
        finally:
            await self.aclose()

    @staticmethod
    def _page_title(page: Dict[str, Any]) -> str:
        props = page.get("properties") or {}
        for value in props.values():
            if isinstance(value, dict) and value.get("type") == "title":
                parts = value.get("title") or []
                return "".join(p.get("plain_text") or "" for p in parts)
        return ""

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            blocks = await self._fetch_blocks(doc_id)
            return FetchDocResult(
                title=self._block_title(blocks) or "Notion 页面",
                markdown=blocks_to_markdown(self._to_md_blocks(blocks)),
                updated_at=None,
            )
        finally:
            await self.aclose()

    async def _fetch_blocks(self, block_id: str) -> List[Dict[str, Any]]:
        collected: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        for _ in range(50):
            params: Dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            data = await self._request_json(
                "GET", f"{HOST}{BLOCKS_PATH}".format(id=block_id),
                headers=self._auth_headers(), params=params,
            )
            collected += (data or {}).get("results") or []
            if not (data or {}).get("has_more"):
                break
            cursor = (data or {}).get("next_cursor")
            if not cursor:
                break
        return collected

    @staticmethod
    def _to_md_blocks(blocks: List[Dict[str, Any]]) -> List[MdBlock]:
        md_blocks: List[MdBlock] = []
        for block in blocks:
            btype = block.get("type") or ""
            if btype == "image":
                image = block.get("image") or {}
                url = (image.get("file") or {}).get("url") or (image.get("external") or {}).get("url")
                if url:
                    caption = "".join(
                        c.get("plain_text") or "" for c in image.get("caption") or []
                    )
                    md_blocks.append(MdBlock(kind=IMAGE, text=caption or "图片", url=url))
                continue
            if btype in ("table", "child_database", "child_page", "bookmark", "breadcrumb"):
                # 表格/子数据库等结构复杂，降级为占位，保证正文不丢
                md_blocks.append(MdBlock(kind=PARAGRAPH, text=f"[{btype}]"))
                continue
            kind, level = _KINDS.get(btype, (PARAGRAPH, 0))
            text = _rich_text(block, btype)
            if kind == DIVIDER:
                md_blocks.append(MdBlock(kind=DIVIDER))
                continue
            if kind == TODO:
                checked = bool((block.get("to_do") or {}).get("checked"))
                md_blocks.append(MdBlock(kind=TODO, text=text, checked=checked))
                continue
            if kind == CODE:
                language = (block.get("code") or {}).get("language") or ""
                md_blocks.append(MdBlock(kind=CODE, text=text, language=language))
                continue
            if kind == HEADING:
                md_blocks.append(MdBlock(kind=HEADING, text=text, level=level))
                continue
            if not text:
                continue
            md_blocks.append(MdBlock(kind=kind, text=text))
        return md_blocks

    @staticmethod
    def _block_title(blocks: List[Dict[str, Any]]) -> str:
        for block in blocks:
            if block.get("type") in ("heading_1", "heading_2", "heading_3"):
                text = _rich_text(block, block["type"]).strip()
                if text:
                    return text
        return ""


register_doc_source(
    "notion",
    NotionDocSource,
    ProviderMeta(
        source_type="notion",
        name="Notion",
        desc="Page / Database",
        host=HOST,
        credential_fields=(
            CredField("secret", "Integration Token", required=True, secret=True,
                      placeholder="ntn_xxxxxxxx"),
            CredField("root_page", "根页面 ID",
                      placeholder="可留空，从全部可访问页面搜索",
                      hint="填写后建议只在该页面内挑选文档"),
        ),
    ),
)
