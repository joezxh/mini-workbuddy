"""既有平台能力补齐单测：Notion Database / 语雀 folder_mode+toc_only / 钉钉两个开关。"""
from __future__ import annotations

import asyncio

import httpx

from app.connectors.doc_sources import get_doc_source
from app.connectors.doc_sources.base import BaseDocSource
from app.connectors.doc_sources.yuque import build_toc_paths


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _FakeClient:
    def __init__(self, handler, calls):
        self._handler = handler
        self._calls = calls
        self.is_closed = False

    async def request(self, method, url, headers=None, params=None, json=None, data=None):
        self._calls.append((method, url, {
            "headers": headers, "params": params, "json": json, "data": data,
        }))
        out = self._handler(method, url, {
            "headers": headers, "params": params, "json": json, "data": data,
        })
        if isinstance(out, httpx.Response):
            return out
        return httpx.Response(200, json=out)

    async def aclose(self):
        self.is_closed = True


def patch_http(src: BaseDocSource, handler) -> list:
    calls: list = []
    client = _FakeClient(handler, calls)
    src._client = client
    src._client_instance = lambda: client  # type: ignore[method-assign]
    return calls


# ── Notion: Database ──────────────────────────────────────────────
def test_notion_lists_database_node():
    src = get_doc_source("notion", {"secret": "ntn_x"})

    def handler(method, url, kwargs):
        if url.endswith("/v1/search"):
            return {"results": [
                {"object": "page", "id": "p1",
                 "properties": {"title": {"type": "title",
                                          "title": [{"plain_text": "设计文档"}]}}},
                {"object": "database", "id": "db1", "title": [{"plain_text": "需求池"}]},
            ], "has_more": False}
        raise AssertionError(url)

    patch_http(src, handler)
    nodes = run(src.list_nodes(None))
    assert [n.doc_id for n in nodes] == ["p1", "db:db1"]
    assert nodes[1].title == "需求池"


def test_notion_database_rendered_as_markdown_table():
    src = get_doc_source("notion", {"secret": "ntn_x"})

    def handler(method, url, kwargs):
        if url.endswith("/query"):
            return {"results": [
                {"last_edited_time": "2026-10-05", "properties": {
                    "名称": {"type": "title", "title": [{"plain_text": "登录"}]},
                    "状态": {"type": "select", "select": {"name": "进行中"}},
                    "完成": {"type": "checkbox", "checkbox": False},
                }},
            ], "has_more": False}
        raise AssertionError(url)

    patch_http(src, handler)
    doc = run(src.fetch_doc("db:db1"))
    assert "| 名称 | 状态 | 完成 |" in doc.markdown
    assert "| 登录 | 进行中 | 否 |" in doc.markdown
    assert doc.updated_at == "2026-10-05"


def test_notion_databases_can_be_excluded():
    src = get_doc_source("notion", {"secret": "ntn_x", "include_databases": "false"})

    def handler(method, url, kwargs):
        return {"results": [{"object": "database", "id": "db1"}], "has_more": False}

    patch_http(src, handler)
    assert run(src.list_nodes(None)) == []


# ── 语雀: 目录模式 ────────────────────────────────────────────────
def test_yuque_toc_paths_built_from_flat_list():
    items = [
        {"type": "TITLE", "title": "入门", "depth": 0},
        {"type": "DOC", "title": "安装", "slug": "install", "depth": 1},
        {"type": "DOC", "title": "散篇", "slug": "misc", "depth": 0},
    ]
    paths = build_toc_paths(items)
    assert paths["install"] == ["入门", "安装"]
    assert paths["misc"] == ["散篇"]


def test_yuque_folder_mode_toc_uses_path_as_title():
    src = get_doc_source("yuque", {
        "token": "t", "namespace": "joe/handbook", "folder_mode": "toc",
    })

    def handler(method, url, kwargs):
        if url.endswith("/toc"):
            return {"data": [
                {"type": "TITLE", "title": "入门", "depth": 0},
                {"type": "DOC", "title": "安装", "slug": "install", "depth": 1},
            ]}
        if url.endswith("/docs"):
            return {"data": [
                {"slug": "install", "title": "安装", "type": "Doc"},
                {"slug": "draft", "title": "未入目录", "type": "Doc"},
            ]}
        raise AssertionError(url)

    patch_http(src, handler)
    docs = run(src.list_nodes(None))
    assert [d.title for d in docs] == ["入门/安装", "未入目录"]


def test_yuque_toc_only_filters_docs_outside_toc():
    src = get_doc_source("yuque", {
        "token": "t", "namespace": "joe/handbook",
        "folder_mode": "toc", "toc_only": "true",
    })

    def handler(method, url, kwargs):
        if url.endswith("/toc"):
            return {"data": [{"type": "DOC", "title": "安装", "slug": "install", "depth": 0}]}
        if url.endswith("/docs"):
            return {"data": [
                {"slug": "install", "title": "安装", "type": "Doc"},
                {"slug": "draft", "title": "未入目录", "type": "Doc"},
            ]}
        raise AssertionError(url)

    patch_http(src, handler)
    docs = run(src.list_nodes(None))
    assert [d.doc_id for d in docs] == ["joe/handbook/install"]


def test_yuque_toc_only_ignored_without_toc_mode():
    """toc_only 仅在 folder_mode=toc 时生效。"""
    src = get_doc_source("yuque", {
        "token": "t", "namespace": "joe/handbook", "toc_only": "true",
    })

    def handler(method, url, kwargs):
        assert not url.endswith("/toc"), "未开启 toc 模式不应请求目录接口"
        return {"data": [{"slug": "draft", "title": "未入目录", "type": "Doc"}]}

    patch_http(src, handler)
    assert len(run(src.list_nodes(None))) == 1


# ── 钉钉: 两个开关 ────────────────────────────────────────────────
def test_dingtalk_uploaded_files_skipped_by_default():
    src = get_doc_source("dingtalk", {
        "app_key": "k", "app_secret": "s", "space_id": "w9", "operator_id": "u1",
    })

    def handler(method, url, kwargs):
        if url.endswith("/gettoken"):
            return {"access_token": "tok"}
        if url.endswith("/v1.0/doc/nodes/query"):
            return {"data": {"nodes": [
                {"nodeId": "n1", "nodeType": "DOC", "name": "文档一"},
                {"nodeId": "f1", "nodeType": "FILE", "name": "附件.docx"},
                {"nodeId": "s1", "nodeType": "SHEET", "name": "表格"},
            ]}}
        raise AssertionError(url)

    patch_http(src, handler)
    nodes = run(src.list_nodes("w9"))
    # 默认不导入钉盘附件；钉钉表格无正文接口，始终跳过
    assert [n.doc_id for n in nodes] == ["n1"]


def test_dingtalk_uploaded_files_included_when_enabled():
    src = get_doc_source("dingtalk", {
        "app_key": "k", "app_secret": "s", "space_id": "w9", "operator_id": "u1",
        "include_uploaded_files": "true",
    })

    def handler(method, url, kwargs):
        if url.endswith("/gettoken"):
            return {"access_token": "tok"}
        if url.endswith("/v1.0/doc/nodes/query"):
            return {"data": {"nodes": [
                {"nodeId": "f1", "nodeType": "FILE", "name": "附件.md"},
            ]}}
        if "downloadInfos" in url:
            return {"data": {"downloadUrl": "https://93.184.216.34/file"}}
        if url == "https://93.184.216.34/file":
            return httpx.Response(200, content="# 附件\n\n正文".encode("utf-8"))
        raise AssertionError(url)

    patch_http(src, handler)
    nodes = run(src.list_nodes("w9"))
    assert nodes[0].doc_id == "file:w9::f1::附件.md"
    doc = run(src.fetch_doc("file:w9::f1::附件.md"))
    assert "附件" in doc.markdown


def test_dingtalk_preserve_folder_structure_encodes_path():
    src = get_doc_source("dingtalk", {
        "app_key": "k", "app_secret": "s", "space_id": "w9", "operator_id": "u1",
        "preserve_folder_structure": "true", "space_name": "产品知识库",
    })

    def handler(method, url, kwargs):
        if url.endswith("/gettoken"):
            return {"access_token": "tok"}
        if url.endswith("/v1.0/doc/nodes/query"):
            body = kwargs["json"] or {}
            if not body.get("parentNodeId"):
                return {"data": {"nodes": [
                    {"nodeId": "d1", "nodeType": "FOLDER", "name": "子目录"},
                ]}}
            return {"data": {"nodes": [
                {"nodeId": "n1", "nodeType": "DOC", "name": "文档一"},
            ]}}
        raise AssertionError(url)

    patch_http(src, handler)
    top = run(src.list_nodes(None))
    # 目录节点的 doc_id 带上路径，供下一次（独立实例）下钻时还原
    assert top[0].doc_id == "w9::d1::产品知识库/子目录"
    docs = run(src.list_nodes(top[0].doc_id))
    assert docs[0].title == "产品知识库/子目录/文档一"
