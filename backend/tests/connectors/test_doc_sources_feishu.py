"""飞书系四个来源单测：feishu / lark（知识库）与 feishu_drive / lark_drive（云盘）。

沿用「不打真实网络」的替身方式：本文件自带可返回原始字节的 httpx 替身，用于覆盖
云盘的下载 / 导出链路（不仅限 JSON 响应）。
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from app.connectors.doc_sources import DocConnResult, DocSourceError, get_doc_source
from app.connectors.doc_sources.base import BaseDocSource
from app.connectors.doc_sources.feishu_core import (
    decode_drive_id,
    encode_drive_doc,
    encode_drive_folder,
)


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _FakeClient:
    """httpx.AsyncClient 替身：handler 可返回 dict（JSON）或 httpx.Response（原始字节）。"""

    def __init__(self, handler, calls):
        self._handler = handler
        self._calls = calls
        self.is_closed = False

    async def request(self, method, url, headers=None, params=None, json=None, data=None):
        self._calls.append((method, url, {"headers": headers, "params": params, "json": json}))
        out = self._handler(method, url, {"headers": headers, "params": params, "json": json})
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


def token_handler(extra):
    """统一处理 tenant_access_token，其余交给 extra(method, url, kwargs)。"""

    def handler(method, url, kwargs):
        if "tenant_access_token" in url:
            return {"tenant_access_token": "tok"}
        return extra(method, url, kwargs)

    return handler


# ── doc_id 编解码 ─────────────────────────────────────────────────
def test_drive_doc_id_roundtrip():
    assert encode_drive_doc("docx", "d1") == "file:docx:d1"
    assert encode_drive_folder("f1") == "folder:f1"
    assert decode_drive_id("file:docx:d1") == ("file", "docx", "d1")
    assert decode_drive_id("folder:f1") == ("folder", "", "f1")


def test_drive_doc_id_invalid():
    with pytest.raises(DocSourceError):
        decode_drive_id("oops")


# ── 区域隔离：lark 走 open.larksuite.com ──────────────────────────
def test_lark_wiki_uses_larksuite_domain():
    src = get_doc_source("lark", {"app_id": "id", "app_secret": "sec"})

    def extra(method, url, kwargs):
        if url.endswith("/wiki/v2/spaces"):
            # 飞书/ Lark 空间列表的真实主键字段是 space_id（不是 id）
            return {"data": {"items": [{"space_id": "s1", "name": "Lark 空间"}], "total": 1}}
        raise AssertionError(url)

    calls = patch_http(src, token_handler(extra))
    spaces = run(src.list_nodes(None))
    assert spaces[0].title == "Lark 空间"
    # 关键回归：doc_id 必须是真实 space_id，否则下钻会请求 /spaces/None/nodes 而取空
    assert spaces[0].doc_id == "s1"
    assert all(c[1].startswith("https://open.larksuite.com") for c in calls)


def test_feishu_wiki_space_drilldown_uses_real_space_id():
    """回归：选空间下钻时，节点请求必须带真实 space_id（曾因取 id=None 而取空）。"""
    src = get_doc_source("feishu", {"app_id": "id", "app_secret": "sec"})

    def extra(method, url, kwargs):
        if url.endswith("/wiki/v2/spaces"):
            return {"data": {"items": [{"space_id": "sp1", "name": "知识库 A"}], "total": 1}}
        if url.endswith("/wiki/v2/spaces/sp1/nodes"):
            return {"data": {"items": [
                {"node_token": "n1", "obj_token": "d1", "obj_type": "docx",
                 "title": "文档一", "has_child": False},
            ], "has_more": False}}
        raise AssertionError(url)

    patch_http(src, token_handler(extra))
    spaces = run(src.list_nodes(None))
    assert spaces[0].doc_id == "sp1"
    docs = run(src.list_nodes("sp1"))
    assert [d.doc_id for d in docs] == ["d1"]


def test_lark_drive_uses_larksuite_domain():
    src = get_doc_source("lark_drive", {
        "app_id": "id", "app_secret": "sec", "folder_token": "fld1",
    })

    def extra(method, url, kwargs):
        if "/files/" in url and url.endswith("/meta"):
            return {"data": {"name": "Lark 根目录"}}
        raise AssertionError(url)

    calls = patch_http(src, token_handler(extra))
    nodes = run(src.list_nodes(None))
    assert nodes[0].title == "Lark 根目录"
    assert all(c[1].startswith("https://open.larksuite.com") for c in calls)


# ── 云盘：folder_token 必填 ───────────────────────────────────────
def test_feishu_drive_missing_folder_token():
    src = get_doc_source("feishu_drive", {"app_id": "id", "app_secret": "sec"})
    res = run(src.test_connection())
    assert isinstance(res, DocConnResult) and not res.ok
    assert "文件夹 token" in res.message


# ── 云盘：列举 + 跳过不支持类型 ───────────────────────────────────
def test_feishu_drive_lists_folder_and_skips_unsupported():
    src = get_doc_source("feishu_drive", {
        "app_id": "id", "app_secret": "sec", "folder_token": "fld1",
    })

    def extra(method, url, kwargs):
        if "/drive/v1/files" in url and "folder_token" in (kwargs["params"] or {}):
            return {"data": {"files": [
                {"type": "folder", "token": "sub1", "name": "子目录"},
                {"type": "docx", "token": "d1", "name": "说明文档",
                 "latest_modify_time": "2026-10-01"},
                {"type": "slides", "token": "s1", "name": "幻灯片"},
                {"type": "file", "token": "u1", "name": "附件.exe"},
            ], "has_more": False}}
        if url.endswith("/meta"):
            return {"data": {"name": "产品资料"}}
        raise AssertionError(url)

    patch_http(src, token_handler(extra))
    nodes = run(src.list_nodes("folder:fld1"))
    kinds = {n.title: n.node_type for n in nodes}
    # 子目录 + docx 入选；slides 无公开内容 API、.exe 无法转 Markdown，均跳过
    assert kinds == {"子目录": "folder", "说明文档": "doc"}
    assert nodes[-1].doc_id == "file:docx:d1"


# ── 云盘：docx 正文走 blocks ──────────────────────────────────────
def test_feishu_drive_fetches_docx_via_blocks():
    src = get_doc_source("feishu_drive", {
        "app_id": "id", "app_secret": "sec", "folder_token": "fld1",
    })

    def extra(method, url, kwargs):
        if "/blocks" in url:
            return {"data": {"items": [
                {"block_type": 3, "heading1": {"elements": [{"text_run": {"content": "标题"}}]}},
                {"block_type": 2, "text": {"elements": [{"text_run": {"content": "正文"}}]}},
            ], "has_more": False}}
        raise AssertionError(url)

    patch_http(src, token_handler(extra))
    doc = run(src.fetch_doc("file:docx:d1"))
    assert doc.title == "标题" and "# 标题" in doc.markdown and "正文" in doc.markdown


# ── 云盘：上传型文件下载转 Markdown ───────────────────────────────
def test_feishu_drive_fetches_uploaded_file():
    src = get_doc_source("feishu_drive", {
        "app_id": "id", "app_secret": "sec", "folder_token": "fld1",
    })

    def extra(method, url, kwargs):
        if "/download" in url:
            return httpx.Response(200, content="# 附件说明\n\n来自云盘附件".encode("utf-8"),
                                  headers={"Content-Disposition": "attachment; filename=notes.md"})
        raise AssertionError(url)

    patch_http(src, token_handler(extra))
    doc = run(src.fetch_doc("file:file:u1"))
    assert "附件说明" in doc.markdown


# ── 云盘：sheet 导出任务流程 ──────────────────────────────────────
def test_feishu_drive_fetches_sheet_via_export(tmp_path):
    src_patch = get_doc_source("feishu_drive", {
        "app_id": "id", "app_secret": "sec", "folder_token": "fld1",
    })

    xlsx_bytes = _make_xlsx()

    def extra(method, url, kwargs):
        if url.endswith("/export_tasks") and kwargs.get("json"):
            assert kwargs["json"]["type"] == "sheet"
            return {"data": {"ticket": "t1"}}
        if url.endswith("/export_tasks/t1"):
            return {"data": {"job_status": 0, "result": {"file_token": "f1"}}}
        if url.endswith("/export_tasks/file/f1/download"):
            return httpx.Response(200, content=xlsx_bytes)
        raise AssertionError(url)

    patch_http(src_patch, token_handler(extra))
    doc = run(src_patch.fetch_doc("file:sheet:sh1"))
    assert "列A" in doc.markdown


def _make_xlsx() -> bytes:
    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["列A", "列B"])
    ws.append(["1", "2"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── 平台业务码不被吞（云盘同样适用）───────────────────────────────
def test_feishu_drive_platform_error_not_swallowed():
    src = get_doc_source("feishu_drive", {
        "app_id": "id", "app_secret": "sec", "folder_token": "fld1",
    })

    def handler(method, url, kwargs):
        if "tenant_access_token" in url:
            return {"tenant_access_token": "tok"}
        return {"code": 1063001, "msg": "file not authorized"}

    patch_http(src, handler)
    with pytest.raises(DocSourceError) as exc:
        run(src.list_nodes("folder:fld1"))
    assert "1063001" in str(exc.value)
