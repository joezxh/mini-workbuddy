"""外部文档源单测（不打真实网络、不依赖数据库）。

用 monkeypatch 替换 ``BaseDocSource._request_json``，验证：
端点拼接、令牌只取一次、块 → Markdown、错误映射为可读中文、五平台注册完整。
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.connectors.doc_sources import (
    DocConnResult,
    ExternalDocRef,
    FetchDocResult,
    MdBlock,
    blocks_to_markdown,
    get_doc_source,
    list_providers,
    supported_source_types,
)
from app.connectors.doc_sources.base import BaseDocSource
from app.connectors.doc_sources.markdown import (
    BULLETED,
    CALLOUT,
    CODE,
    DIVIDER,
    HEADING,
    IMAGE,
    NUMBERED,
    PARAGRAPH,
    QUOTE,
    TODO,
)


def run(coro):
    """独立事件循环执行协程：避免受其它用例的 loop 状态影响。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _FakeClient:
    """替身 httpx.AsyncClient：只实现文档源用到的 request/aclose。"""

    def __init__(self, handler, calls):
        self._handler = handler
        self._calls = calls
        self.is_closed = False

    async def request(self, method, url, headers=None, params=None, json=None):
        self._calls.append((method, url, {"headers": headers, "params": params, "json": json}))
        payload = self._handler(method, url, {"headers": headers, "params": params, "json": json})
        return httpx.Response(200, json=payload)

    async def aclose(self):
        self.is_closed = True


def patch_http(src: BaseDocSource, handler):
    """替换到传输层（httpx client），使令牌获取/注入、JSON 解析、错误映射全部真实执行。

    返回调用记录 [(method, url, kwargs)]，可用于断言「令牌只取一次」。
    """
    calls: list = []
    client = _FakeClient(handler, calls)
    src._client = client
    src._client_instance = lambda: client  # type: ignore[method-assign]
    return calls


# ── Markdown 转换器 ────────────────────────────────────────────────
def test_markdown_renders_common_blocks():
    md = blocks_to_markdown([
        MdBlock(kind=HEADING, text="标题", level=2),
        MdBlock(kind=PARAGRAPH, text="正文段落"),
        MdBlock(kind=BULLETED, text="条目一"),
        MdBlock(kind=NUMBERED, text="第一步"),
        MdBlock(kind=TODO, text="待办", checked=True),
        MdBlock(kind=QUOTE, text="引用"),
        MdBlock(kind=CODE, text="print(1)", language="python"),
        MdBlock(kind=DIVIDER),
        MdBlock(kind=CALLOUT, text="提示"),
        MdBlock(kind=IMAGE, text="图", url="https://x/y.png"),
    ])
    assert "## 标题" in md
    assert "正文段落" in md
    assert "- 条目一" in md
    assert "1. 第一步" in md
    assert "- [x] 待办" in md
    assert "> 引用" in md
    assert "```python" in md and "print(1)" in md
    assert "---" in md
    assert "![图](https://x/y.png)" in md


def test_markdown_nested_list_and_table():
    child = MdBlock(kind=BULLETED, text="子项")
    md = blocks_to_markdown([
        MdBlock(kind=BULLETED, text="父项", children=[child]),
        MdBlock(kind="table", rows=[["列A", "列B"], ["1", "2"]]),
    ])
    assert "- 父项" in md and "  - 子项" in md
    assert "| 列A | 列B |" in md and "| --- | --- |" in md


def test_markdown_table_escapes_pipe():
    md = blocks_to_markdown([MdBlock(kind="table", rows=[["a|b"]])])
    assert "a\\|b" in md


# ── 注册表 / 平台元数据 ────────────────────────────────────────────
def test_all_five_providers_registered():
    assert set(supported_source_types()) == {
        "feishu", "dingtalk", "yuque", "wecom", "notion",
    }


def test_provider_metadata_has_credential_schema():
    for p in list_providers():
        assert p["name"] and p["host"].startswith("https://")
        fields = p["credential_fields"]
        assert fields, f"{p['source_type']} 缺少凭据字段定义"
        assert any(f["required"] for f in fields)


def test_get_doc_source_unknown_type_raises():
    from app.connectors.doc_sources.base import DocSourceError

    with pytest.raises(DocSourceError):
        get_doc_source("not-exist", {})


# ── 飞书 ──────────────────────────────────────────────────────────
def test_feishu_lists_spaces_and_nodes_and_fetches_markdown():
    src = get_doc_source("feishu", {"app_id": "id", "app_secret": "sec"})

    def handler(method, url, kwargs):
        if "tenant_access_token" in url:
            return {"tenant_access_token": "tok"}
        if url.endswith("/wiki/v2/spaces"):
            return {"data": {"items": [{"id": "s1", "name": "研发空间"}], "total": 1}}
        if "/nodes" in url:
            return {"data": {"items": [
                {"node_token": "n1", "obj_token": "d1", "obj_type": "docx",
                 "title": "架构说明", "has_child": False, "obj_edit_time": "2026-10-12"},
                {"node_token": "n2", "obj_type": "docx", "title": "有子文档",
                 "has_child": True},
                {"node_token": "n3", "obj_type": "sheet", "title": "表格",
                 "has_child": False},
            ], "has_more": False}}
        if "/blocks" in url:
            return {"data": {"items": [
                {"block_type": 3, "heading1": {"elements": [{"text_run": {"content": "架构"}}]}},
                {"block_type": 2, "text": {"elements": [{"text_run": {"content": "正文"}}]}},
            ], "has_more": False}}
        raise AssertionError(url)

    calls = patch_http(src, handler)

    spaces = run(src.list_nodes(None))
    assert spaces[0].doc_id == "s1" and spaces[0].node_type == "space"

    nodes = run(src.list_nodes("s1"))
    kinds = {n.title: n.node_type for n in nodes}
    assert kinds == {"架构说明": "doc", "有子文档": "folder"}  # 表格类型被跳过

    doc = run(src.fetch_doc("d1"))
    assert doc.title == "架构"
    # block_type=3 对应 heading1，渲染为一级标题
    assert "# 架构" in doc.markdown and "正文" in doc.markdown

    # 令牌只取一次：后续请求不应再访问 token 端点
    token_calls = [c for c in calls if "tenant_access_token" in c[1]]
    assert len(token_calls) == 1


def test_feishu_test_connection_ok_and_identity():
    src = get_doc_source("feishu", {"app_id": "id", "app_secret": "sec"})

    def handler(method, url, kwargs):
        if "tenant_access_token" in url:
            return {"tenant_access_token": "tok"}
        return {"data": {"items": [], "total": 3}}

    patch_http(src, handler)
    res = run(src.test_connection())
    assert isinstance(res, DocConnResult) and res.ok
    assert "3" in res.identity


def test_feishu_test_connection_bad_credential_message():
    src = get_doc_source("feishu", {"app_id": "", "app_secret": ""})
    res = run(src.test_connection())
    assert not res.ok and "App ID" in res.message


# ── 语雀 ──────────────────────────────────────────────────────────
def test_yuque_lists_repos_docs_and_returns_markdown_body():
    src = get_doc_source("yuque", {"token": "t", "namespace": ""})

    def handler(method, url, kwargs):
        if url.endswith("/api/v2/user"):
            return {"data": {"login": "joe", "name": "张三"}}
        if "/users/joe/repos" in url:
            return {"data": [{"namespace": "joe/handbook", "name": "手册"}]}
        if url.endswith("/api/v2/groups"):
            return {"data": []}
        if url.endswith("/repos/joe/handbook/docs"):
            return {"data": [
                {"slug": "intro", "title": "简介", "type": "Doc", "updated_at": "2026-10-01"},
                {"slug": "sheet", "title": "表格", "type": "Sheet"},
            ]}
        if url.endswith("/docs/intro"):
            return {"data": {"title": "简介", "body": "# 简介\n\n正文"}}
        raise AssertionError(url)

    patch_http(src, handler)

    repos = run(src.list_nodes(None))
    assert repos[0].doc_id == "joe/handbook"

    docs = run(src.list_nodes("joe/handbook"))
    assert [d.doc_id for d in docs] == ["joe/handbook/intro"]  # Sheet 被跳过

    doc = run(src.fetch_doc("joe/handbook/intro"))
    assert doc.title == "简介" and doc.markdown.startswith("# 简介")


def test_yuque_namespace_shortcut():
    src = get_doc_source("yuque", {"token": "t", "namespace": "joe/handbook"})

    def handler(method, url, kwargs):
        assert url.endswith("/repos/joe/handbook/docs"), url
        return {"data": [{"slug": "intro", "title": "简介", "type": "Doc"}]}

    patch_http(src, handler)
    docs = run(src.list_nodes(None))
    assert docs[0].doc_id == "joe/handbook/intro"


def test_yuque_missing_token_message():
    src = get_doc_source("yuque", {"token": ""})
    res = run(src.test_connection())
    assert not res.ok and "令牌" in res.message


# ── Notion ────────────────────────────────────────────────────────
def test_notion_search_and_blocks():
    src = get_doc_source("notion", {"secret": "ntn_x"})

    def handler(method, url, kwargs):
        if url.endswith("/v1/search"):
            return {"results": [
                {"object": "page", "id": "p1", "last_edited_time": "2026-10-05",
                 "properties": {"title": {"type": "title",
                                          "title": [{"plain_text": "设计文档"}]}}},
            ], "has_more": False}
        if "/blocks/" in url:
            return {"results": [
                {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "设计"}]}},
                {"type": "bulleted_list_item",
                 "bulleted_list_item": {"rich_text": [{"plain_text": "要点"}]}},
                {"type": "to_do", "to_do": {"checked": True,
                                            "rich_text": [{"plain_text": "待办"}]}},
                {"type": "code", "code": {"language": "python",
                                          "rich_text": [{"plain_text": "x=1"}]}},
            ], "has_more": False}
        raise AssertionError(url)

    patch_http(src, handler)

    pages = run(src.list_nodes(None))
    assert pages[0].title == "设计文档" and pages[0].node_type == "doc"

    doc = run(src.fetch_doc("p1"))
    assert doc.title == "设计"
    assert "# 设计" in doc.markdown
    assert "- 要点" in doc.markdown
    assert "- [x] 待办" in doc.markdown
    assert "```python" in doc.markdown


def test_notion_missing_secret_message():
    src = get_doc_source("notion", {"secret": ""})
    res = run(src.test_connection())
    assert not res.ok and "Integration Token" in res.message


# ── 钉钉 / 企业微信 ────────────────────────────────────────────────
def test_dingtalk_token_and_nodes():
    src = get_doc_source("dingtalk", {"app_key": "k", "app_secret": "s"})

    def handler(method, url, kwargs):
        if url.endswith("/gettoken"):
            return {"access_token": "tok"}
        if url.endswith("/v1.0/doc/workspaces"):
            return {"data": {"workspaces": [{"workspaceId": "w1", "name": "知识库"}]}}
        if url.endswith("/v1.0/doc/nodes/query"):
            return {"data": {"nodes": [
                {"nodeId": "n1", "nodeType": "DOC", "name": "文档一"},
                {"nodeId": "n2", "nodeType": "FOLDER", "name": "目录"},
            ]}}
        if "/content" in url:
            return {"data": {"name": "文档一", "content": "# 文档一\n\n正文"}}
        raise AssertionError(url)

    patch_http(src, handler)
    ws = run(src.list_nodes(None))
    assert ws[0].doc_id == "w1"
    nodes = run(src.list_nodes("w1"))
    assert {n.node_type for n in nodes} == {"doc", "folder"}
    doc = run(src.fetch_doc("n1"))
    assert doc.markdown.startswith("# 文档一")


def test_wecom_token_and_doc_list():
    src = get_doc_source("wecom", {"corp_id": "c", "corp_secret": "s"})

    def handler(method, url, kwargs):
        if url.endswith("/cgi-bin/gettoken"):
            return {"access_token": "tok"}
        if url.endswith("/cgi-bin/wedoc/spi_list"):
            return {"data": {"doc_list": [{"docid": "d1", "doc_name": "报销制度"}]}}
        if url.endswith("/cgi-bin/wedoc/document"):
            return {"data": {"doc_name": "报销制度", "content": "# 报销\n\n正文"}}
        raise AssertionError(url)

    patch_http(src, handler)
    docs = run(src.list_nodes(None))
    assert docs[0].doc_id == "d1" and docs[0].title == "报销制度"
    doc = run(src.fetch_doc("d1"))
    assert doc.markdown.startswith("# 报销")


# ── 错误映射 ──────────────────────────────────────────────────────
@pytest.mark.parametrize("status,keyword", [
    (401, "凭据无效"),
    (403, "凭据无效"),
    (404, "资源不存在"),
    (429, "限流"),
    (500, "服务异常"),
])
def test_http_error_message_readable(status, keyword):
    resp = httpx.Response(status, json={"msg": "平台原始错误"})
    msg = BaseDocSource._http_error_message(resp)
    assert keyword in msg and "平台原始错误" in msg


# ── 数据结构 ──────────────────────────────────────────────────────
def test_dataclass_shapes():
    ref = ExternalDocRef(doc_id="1", title="t", node_type="doc")
    assert ref.parent_id is None
    res = FetchDocResult(title="t", markdown="# t", updated_at=None)
    assert res.markdown == "# t"
