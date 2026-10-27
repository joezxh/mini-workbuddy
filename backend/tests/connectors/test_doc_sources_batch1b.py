"""第 3 章第二批新增连接器单测：confluence / seafile（不打真实网络、不依赖 DB）。"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.connectors.doc_sources import DocConnResult, DocSourceError, get_doc_source
from app.connectors.doc_sources.base import BaseDocSource
from app.connectors.doc_sources.seafile import _decode, _encode_dir, _encode_file


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


@pytest.fixture
def no_whitelist(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "SSRF_WHITELIST", "")


# ── Confluence ────────────────────────────────────────────────────
def test_confluence_pat_auth_and_space_listing(no_whitelist):
    src = get_doc_source("confluence", {
        "base_url": "https://93.184.216.34", "token": "pat-xxx",
    })

    def handler(method, url, kwargs):
        assert (kwargs["headers"] or {}).get("Authorization") == "Bearer pat-xxx"
        if url.endswith("/rest/api/space"):
            return {"results": [{"key": "DEV", "name": "研发空间"}], "size": 1}
        raise AssertionError(url)

    calls = patch_http(src, handler)
    spaces = run(src.list_nodes(None))
    assert spaces[0].doc_id == "space:DEV" and spaces[0].title == "研发空间"
    # Server 版不应自动补 /wiki
    assert all("/wiki" not in c[1] for c in calls)


def test_confluence_cloud_appends_wiki_prefix(no_whitelist):
    src = get_doc_source("confluence", {
        "base_url": "https://93.184.216.34", "edition": "cloud",
        "username": "me@example.com", "api_token": "tok",
    })

    def handler(method, url, kwargs):
        assert url.startswith("https://93.184.216.34/wiki/rest/api/space"), url
        assert (kwargs["headers"] or {}).get("Authorization", "").startswith("Basic ")
        return {"results": [{"key": "CLOUD", "name": "云空间"}], "size": 1}

    patch_http(src, handler)
    assert run(src.list_nodes(None))[0].doc_id == "space:CLOUD"


def test_confluence_lists_pages_and_fetches_html_body(no_whitelist):
    src = get_doc_source("confluence", {
        "base_url": "https://93.184.216.34", "token": "pat-xxx",
    })

    def handler(method, url, kwargs):
        if url.endswith("/rest/api/content") and (kwargs["params"] or {}).get("spaceKey") == "DEV":
            return {"results": [
                {"id": "1001", "title": "架构说明", "version": {"number": 3, "when": "2026-10-01"}},
            ]}
        if url.endswith("/rest/api/content/1001"):
            return {"title": "架构说明",
                    "body": {"view": {"value": "<h1>架构</h1><p>模块划分</p>"}},
                    "version": {"number": 3, "when": "2026-10-01"}}
        raise AssertionError(url)

    patch_http(src, handler)
    pages = run(src.list_nodes("space:DEV"))
    assert pages[0].doc_id == "page:1001" and pages[0].updated_at == "2026-10-01"
    doc = run(src.fetch_doc("page:1001"))
    assert doc.title == "架构说明" and "# 架构" in doc.markdown and "模块划分" in doc.markdown


def test_confluence_pages_filter_blog_and_attachment(no_whitelist):
    """只导入 type=page：不导入附件与博客文章。"""
    src = get_doc_source("confluence", {
        "base_url": "https://93.184.216.34", "token": "pat-xxx",
    })

    def handler(method, url, kwargs):
        assert (kwargs["params"] or {}).get("type") == "page"
        return {"results": []}

    patch_http(src, handler)
    assert run(src.list_nodes("space:DEV")) == []


def test_confluence_missing_credentials(no_whitelist):
    src = get_doc_source("confluence", {"base_url": "https://93.184.216.34"})
    res = run(src.test_connection())
    assert isinstance(res, DocConnResult) and not res.ok
    assert "缺少凭据" in res.message


# ── Seafile ───────────────────────────────────────────────────────
def test_seafile_resource_id_roundtrip():
    assert _encode_dir("r1", "/docs") == "repo:r1:/docs"
    assert _encode_file("r1", "/docs/a.md") == "file:r1:/docs/a.md"
    assert _decode("file:r1:/docs/a.md") == ("file", "r1", "/docs/a.md")


def test_seafile_lists_repos_skipping_encrypted(no_whitelist):
    src = get_doc_source("seafile", {
        "base_url": "https://93.184.216.34", "api_token": "tok",
    })

    def handler(method, url, kwargs):
        assert (kwargs["headers"] or {}).get("Authorization") == "Token tok"
        if url.endswith("/api2/repos/"):
            return [
                {"id": "r1", "name": "产品资料", "encrypted": False},
                {"id": "r2", "name": "机密库", "encrypted": True},
            ]
        raise AssertionError(url)

    patch_http(src, handler)
    repos = run(src.list_nodes(None))
    assert [r.doc_id for r in repos] == ["repo:r1:/"]


def test_seafile_two_step_download_without_token(no_whitelist):
    """第一步带令牌取链接，第二步请求 fileserver 不带令牌。"""
    src = get_doc_source("seafile", {
        "base_url": "https://93.184.216.34", "api_token": "tok",
    })

    def handler(method, url, kwargs):
        if "/api2/repos/r1/file/" in url:
            assert (kwargs["headers"] or {}).get("Authorization") == "Token tok"
            return httpx.Response(200, text='"https://93.184.216.34/files/abc"')
        if url == "https://93.184.216.34/files/abc":
            assert not (kwargs["headers"] or {}), "fileserver 请求不应携带令牌"
            return httpx.Response(200, content="# 手册\n\n正文".encode("utf-8"))
        raise AssertionError(url)

    patch_http(src, handler)
    doc = run(src.fetch_doc("file:r1:/docs/手册.md"))
    assert doc.markdown.startswith("# 手册")


def test_seafile_lists_dir_and_filters_unsupported(no_whitelist):
    src = get_doc_source("seafile", {
        "base_url": "https://93.184.216.34", "api_token": "tok", "repo_id": "r1",
    })

    def handler(method, url, kwargs):
        if "/api2/repos/r1/dir/" in url:
            return [
                {"type": "dir", "name": "sub", "mtime": 1700000000},
                {"type": "file", "name": "guide.md", "mtime": 1700000001},
                {"type": "file", "name": "logo.png", "mtime": 1700000002},
            ]
        raise AssertionError(url)

    patch_http(src, handler)
    nodes = run(src.list_nodes(None))
    kinds = {n.title: n.node_type for n in nodes}
    assert kinds == {"sub": "folder", "guide.md": "doc"}


def test_seafile_token_with_whitespace_rejected(no_whitelist):
    """含空白字符的 Token 直接判不通过（test_connection 不得抛异常）。"""
    src = get_doc_source("seafile", {
        "base_url": "https://93.184.216.34", "api_token": "tok en",
    })
    res = run(src.test_connection())
    assert isinstance(res, DocConnResult) and not res.ok
    assert "空白" in res.message
