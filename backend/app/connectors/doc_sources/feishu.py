"""飞书文档源：Wiki 空间节点树 + 云文档正文。

认证：tenant_access_token（内部应用），基类负责缓存与注入 Bearer 头。
枚举：先列 Wiki 空间，再按空间列节点（分页 + 逐层下钻）。
正文：docx blocks 分页拉取 → 中间块 → Markdown。

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
    PARAGRAPH,
    QUOTE,
    TODO,
    blocks_to_markdown,
)

HOST = "https://open.feishu.cn"
TOKEN_PATH = "/open-apis/auth/v3/tenant_access_token/internal"
SPACES_PATH = "/open-apis/wiki/v2/spaces"
NODES_PATH = "/open-apis/wiki/v2/spaces/{space_id}/nodes"
BLOCKS_PATH = "/open-apis/docx/v1/documents/{document_id}/blocks"

# block_type → (块类型, 标题层级)；未列出的类型降级为段落
_BLOCK_KINDS: Dict[int, tuple] = {
    2: (PARAGRAPH, 0),
    3: (HEADING, 1), 4: (HEADING, 2), 5: (HEADING, 3),
    6: (HEADING, 4), 7: (HEADING, 5), 8: (HEADING, 6),
    9: (HEADING, 6), 10: (HEADING, 6), 11: (HEADING, 6),
    12: (CODE, 0),
    14: (DIVIDER, 0),
    17: (TODO, 0),
    19: (CALLOUT, 0),
    22: (QUOTE, 0),
    23: (BULLETED, 0),   # 无序列表项
    24: (TODO, 0),       # 有序列表项在部分版本为 24，按待办降级处理不丢内容
    25: (BULLETED, 0),
}


def _elements_text(elements: Optional[List[Dict[str, Any]]]) -> str:
    """把 text_run / mention / equation 等行内元素拼成纯文本（链接保留为 MD）。"""
    parts: List[str] = []
    for el in elements or []:
        run = el.get("text_run")
        if run:
            content = run.get("content") or ""
            url = (run.get("text_element_style") or {}).get("link", {}).get("url")
            parts.append(f"[{content}]({url})" if url else content)
            continue
        mention = el.get("mention")
        if mention:
            parts.append(mention.get("name") or mention.get("text") or "")
            continue
        equation = el.get("equation")
        if equation:
            parts.append(equation.get("content") or "")
    return "".join(parts)


def _block_body(block: Dict[str, Any]) -> Dict[str, Any]:
    """取块体内与 block_type 对应的子对象（heading1/text/code/...）。"""
    for key, value in block.items():
        if isinstance(value, dict) and ("elements" in value or "style" in value):
            return value
    return {}


class FeishuDocSource(BaseDocSource):
    source_type = "feishu"
    token_in = "header"

    async def _fetch_token(self) -> Optional[str]:
        app_id = self.credentials.get("app_id") or ""
        app_secret = self.credentials.get("app_secret") or ""
        if not (app_id and app_secret):
            raise DocSourceError("缺少 App ID 或 App Secret")
        data = await self._request_json(
            "POST", f"{HOST}{TOKEN_PATH}",
            json_body={"app_id": app_id, "app_secret": app_secret},
            with_token=False,
        )
        token = (data or {}).get("tenant_access_token")
        if not token:
            raise DocSourceError(f"获取访问令牌失败：{(data or {}).get('msg') or '未知错误'}")
        return token

    async def test_connection(self) -> DocConnResult:
        try:
            await self._access_token()
            data = await self._request_json("GET", f"{HOST}{SPACES_PATH}",
                                            params={"page_size": 1})
            items = ((data or {}).get("data") or {}).get("items") or []
            total = ((data or {}).get("data") or {}).get("total") or len(items)
            return DocConnResult(
                ok=True,
                message="连通成功：凭据有效",
                identity=f"可访问知识空间 {total} 个",
            )
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            if not parent_id:
                return await self._list_spaces()
            space_id, node_token = self._split_parent(parent_id)
            return await self._list_space_nodes(space_id, node_token)
        finally:
            await self.aclose()

    async def _list_spaces(self) -> List[ExternalDocRef]:
        data = await self._request_json("GET", f"{HOST}{SPACES_PATH}",
                                        params={"page_size": 50})
        items = ((data or {}).get("data") or {}).get("items") or []
        return [
            ExternalDocRef(
                doc_id=str(s.get("id")),
                title=s.get("name") or "未命名空间",
                node_type="space",
                url=f"{HOST}/wiki/{s.get('id')}",
            )
            for s in items
        ]

    async def _list_space_nodes(
        self, space_id: str, node_token: Optional[str]
    ) -> List[ExternalDocRef]:
        refs: List[ExternalDocRef] = []
        page_token: Optional[str] = None
        for _ in range(20):  # 上限保护，避免异常数据导致死循环
            params: Dict[str, Any] = {"page_size": 50}
            if node_token:
                params["parent_node_token"] = node_token
            if page_token:
                params["page_token"] = page_token
            data = await self._request_json(
                "GET", f"{HOST}{NODES_PATH}".format(space_id=space_id), params=params
            )
            payload = (data or {}).get("data") or {}
            for n in payload.get("items") or []:
                obj_type = n.get("obj_type") or ""
                has_child = bool(n.get("has_child"))
                node_key = n.get("node_token") or ""
                if has_child:
                    # 目录节点：doc_id 编码 space 与 node，供下钻时还原
                    doc_id = f"{space_id}::{node_key}"
                    kind = "folder"
                elif obj_type == "docx":
                    doc_id = n.get("obj_token") or ""
                    kind = "doc"
                else:
                    # 表格/多维表格等暂不支持导入，跳过以免导入失败
                    continue
                if not doc_id:
                    continue
                refs.append(
                    ExternalDocRef(
                        doc_id=doc_id,
                        title=n.get("title") or "未命名",
                        node_type=kind,
                        parent_id=node_token or space_id,
                        updated_at=n.get("obj_edit_time") or n.get("obj_create_time"),
                        url=f"{HOST}/wiki/{node_key}",
                    )
                )
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token")
            if not page_token:
                break
        return refs

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            blocks: List[Dict[str, Any]] = []
            page_token: Optional[str] = None
            for _ in range(50):
                params: Dict[str, Any] = {
                    "page_size": 500,
                    "document_revision_id": -1,
                }
                if page_token:
                    params["page_token"] = page_token
                data = await self._request_json(
                    "GET",
                    f"{HOST}{BLOCKS_PATH}".format(document_id=doc_id),
                    params=params,
                )
                payload = (data or {}).get("data") or {}
                blocks += payload.get("items") or []
                if not payload.get("has_more"):
                    break
                page_token = payload.get("page_token")
                if not page_token:
                    break
            title = self._first_heading(blocks) or "飞书文档"
            return FetchDocResult(
                title=title,
                markdown=blocks_to_markdown(self._to_md_blocks(blocks)),
                updated_at=None,
            )
        finally:
            await self.aclose()

    def _to_md_blocks(self, blocks: List[Dict[str, Any]]) -> List[MdBlock]:
        md_blocks: List[MdBlock] = []
        for block in blocks:
            btype = block.get("block_type")
            if btype == 27:  # 图片
                token = (block.get("image") or {}).get("token") or ""
                if token:
                    md_blocks.append(
                        MdBlock(
                            kind=IMAGE,
                            text="图片",
                            url=f"{HOST}/open-apis/drive/v1/medias/{token}/download",
                        )
                    )
                continue
            if btype == 31:  # 表格：单元格在独立块中，此处降级为占位
                md_blocks.append(MdBlock(kind=PARAGRAPH, text="[表格]"))
                continue
            kind, level = _BLOCK_KINDS.get(btype, (PARAGRAPH, 0))
            body = _block_body(block)
            text = _elements_text(body.get("elements"))
            if kind == DIVIDER:
                md_blocks.append(MdBlock(kind=DIVIDER))
                continue
            if kind == TODO:
                done = ((body.get("style") or {}).get("done")) is True
                md_blocks.append(MdBlock(kind=TODO, text=text, checked=done))
                continue
            if kind == CODE:
                lang = (body.get("style") or {}).get("language") or ""
                md_blocks.append(MdBlock(kind=CODE, text=text, language=lang))
                continue
            if kind == HEADING:
                md_blocks.append(MdBlock(kind=HEADING, text=text, level=level or 1))
                continue
            if not text:
                continue
            md_blocks.append(MdBlock(kind=kind, text=text))
        return md_blocks

    @staticmethod
    def _first_heading(blocks: List[Dict[str, Any]]) -> str:
        for block in blocks:
            if block.get("block_type") in (3, 4, 5, 6, 7, 8):
                body = _block_body(block)
                text = _elements_text(body.get("elements")).strip()
                if text:
                    return text
        return ""

    @staticmethod
    def _split_parent(parent_id: str) -> tuple:
        """目录节点 doc_id 形如 ``space_id::node_token``。"""
        if "::" in parent_id:
            space_id, node_token = parent_id.split("::", 1)
            return space_id, node_token
        return parent_id, None


register_doc_source(
    "feishu",
    FeishuDocSource,
    ProviderMeta(
        source_type="feishu",
        name="飞书",
        desc="云文档 / 知识库节点",
        host=HOST,
        credential_fields=(
            CredField("app_id", "App ID", required=True, placeholder="cli_a1b2c3d4"),
            CredField("app_secret", "App Secret", required=True, secret=True,
                      placeholder="应用凭证 Secret"),
            CredField("space_id", "知识空间 ID", placeholder="留空则列出全部空间",
                      hint="填写后仅在导入向导中作为默认入口，仍可浏览其它空间"),
        ),
    ),
)
