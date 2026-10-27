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
    TABLE,
    TODO,
    blocks_to_markdown,
)

HOST = "https://api.notion.com"
# 固定 API 版本：本实现基于 2022-06-28（search / blocks / databases.query 均稳定可用）。
NOTION_VERSION = "2022-06-28"
SEARCH_PATH = "/v1/search"
BLOCKS_PATH = "/v1/blocks/{id}/children"
DATABASE_QUERY_PATH = "/v1/databases/{id}/query"

# 数据库节点标识前缀（与页面 ID 区分）
DB_PREFIX = "db:"
# 单个数据库最多拉取的记录数（Notion 单次 query 上限 100 条，分页累加到此为止）
MAX_DB_ROWS = 1000
DB_PAGE_SIZE = 100

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


def property_to_text(prop: Any) -> str:
    """把 Notion 属性值渲染成纯文本（覆盖常见属性类型，未知类型降级为字符串）。

    表格单元格里只需要可读文本，富文本的花哨样式（颜色 / 公式）一律丢弃。
    """
    if not isinstance(prop, dict):
        return "" if prop is None else str(prop)
    ptype = prop.get("type") or ""
    data = prop.get(ptype)
    if isinstance(data, list):
        if all(isinstance(x, dict) and "plain_text" in x for x in data):
            return "".join(x.get("plain_text") or "" for x in data)
        if all(isinstance(x, dict) and "name" in x for x in data):
            return "，".join(str(x.get("name") or "") for x in data)
        return "，".join(str(x) for x in data)
    if isinstance(data, dict):
        if "name" in data:
            return str(data.get("name") or "")
        if "start" in data:
            end = data.get("end")
            return f"{data.get('start') or ''} → {end}" if end else str(data.get("start") or "")
        # formula / rollup 等嵌套结构按类型递归一层
        nested = data.get("type")
        if nested:
            return property_to_text({"type": nested, nested: data.get(nested)})
        return ""
    if isinstance(data, bool):
        return "是" if data else "否"
    return "" if data is None else str(data)


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

    def _include_databases(self) -> bool:
        """是否把 Notion 数据库作为可导入节点（默认开启）。"""
        raw = self.credentials.get("include_databases")
        if raw is None or raw == "":
            return True
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("true", "1", "yes", "on")

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
            want_dbs = self._include_databases()
            for _ in range(10):
                body: Dict[str, Any] = {"page_size": 50}
                if cursor:
                    body["start_cursor"] = cursor
                data = await self._request_json(
                    "POST", f"{HOST}{SEARCH_PATH}", headers=headers, json_body=body
                )
                for r in (data or {}).get("results") or []:
                    obj = r.get("object")
                    pid = r.get("id")
                    if not pid:
                        continue
                    if obj == "database":
                        if not want_dbs:
                            continue
                        # 数据库作为一个整体导入：整表渲染成 Markdown 表格
                        refs.append(
                            ExternalDocRef(
                                doc_id=f"{DB_PREFIX}{pid}",
                                title=self._database_title(r) or "未命名数据库",
                                node_type="doc",
                                updated_at=r.get("last_edited_time"),
                                url=r.get("url"),
                            )
                        )
                        continue
                    if obj != "page":
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

    async def _fetch_database(self, database_id: str) -> FetchDocResult:
        """查询数据库全部记录，渲染成 Markdown 表格。

        数据库任一记录变更即整表重建，故 ``updated_at`` 取最近编辑时间（用于面板展示）。
        """
        rows: List[List[str]] = []
        headers: List[str] = []
        latest = ""
        cursor: Optional[str] = None
        title = "Notion 数据库"
        for _ in range(MAX_DB_ROWS // DB_PAGE_SIZE + 1):
            body: Dict[str, Any] = {"page_size": DB_PAGE_SIZE}
            if cursor:
                body["start_cursor"] = cursor
            data = await self._request_json(
                "POST", f"{HOST}{DATABASE_QUERY_PATH}".format(id=database_id),
                headers=self._auth_headers(), json_body=body,
            )
            for r in (data or {}).get("results") or []:
                props = r.get("properties") or {}
                if not headers:
                    headers = list(props.keys()) or ["标题"]
                rows.append([property_to_text(v) for v in props.values()])
                edited = r.get("last_edited_time") or ""
                if edited > latest:
                    latest = edited
            if len(rows) >= MAX_DB_ROWS or not (data or {}).get("has_more"):
                break
            cursor = (data or {}).get("next_cursor")
            if not cursor:
                break
        if not rows:
            raise DocSourceError("该数据库没有可导入的记录（请确认已 Share 给 Integration）")
        return FetchDocResult(
            title=title,
            markdown=blocks_to_markdown([MdBlock(kind=TABLE, rows=[headers] + rows)]),
            updated_at=latest or None,
        )

    @staticmethod
    def _database_title(db: Dict[str, Any]) -> str:
        raw = db.get("title")
        if isinstance(raw, list):
            return "".join(p.get("plain_text") or "" for p in raw)
        return ""

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
            if doc_id.startswith(DB_PREFIX):
                return await self._fetch_database(doc_id[len(DB_PREFIX):])
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
            CredField("include_databases", "导入数据库", placeholder="true",
                      hint="默认开启：Notion 数据库会整表渲染成 Markdown 表格导入；"
                           "任一记录变更即整表重建。填 false 则只列页面"),
        ),
    ),
)
