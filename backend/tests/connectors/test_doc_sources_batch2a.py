"""第 4 章首批单测：github / google_drive / onedrive（不打真实网络、不依赖 DB）。"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.connectors.doc_sources import DocConnResult, DocSourceError, get_doc_source
from app.connectors.doc_sources.base import BaseDocSource
from app.connectors.doc_sources.github import _decode, _encode_file, _encode_repo
from app.connectors.doc_sources.onedrive import _scope_of


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


@pytest.fixture
def no_whitelist(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "SSRF_WHITELIST", "")


# ── GitHub ────────────────────────────────────────────────────────
def test_github_id_roundtrip():
    assert _encode_repo("o/r", "main") == "repo:o/r:main"
    assert _encode_file("o/r", "main", "docs/a.md") == "file:o/r:main:docs/a.md"
    assert _decode("file:o/r:main:docs/a.md") == ("file", "o/r", "main", "docs/a.md")


def test_github_test_connection_identity(no_whitelist):
    src = get_doc_source("github", {"token": "ghp_x"})

    def handler(method, url, kwargs):
        assert (kwargs["headers"] or {}).get("X-GitHub-Api-Version") == "2022-11-28"
        if url.endswith("/user"):
            return {"login": "octocat"}
        raise AssertionError(url)

    patch_http(src, handler)
    res = run(src.test_connection())
    assert res.ok and "octocat" in res.identity


def test_github_lists_tree_with_whitelist_and_paths(no_whitelist):
    src = get_doc_source("github", {
        "token": "ghp_x", "owner": "o", "repo": "r", "ref": "main", "paths": "docs/",
    })

    def handler(method, url, kwargs):
        if "/git/trees/main" in url:
            return {"truncated": False, "tree": [
                {"type": "blob", "path": "docs/a.md"},
                {"type": "blob", "path": "docs/logo.png"},   # 图片不在白名单
                {"type": "blob", "path": "src/main.go"},     # 代码不在白名单
                {"type": "blob", "path": "README.md"},       # 不在 paths 范围
                {"type": "tree", "path": "docs/sub"},
            ]}
        raise AssertionError(url)

    patch_http(src, handler)
    nodes = run(src.list_nodes(None))          # 指定了 repo → 直接给出仓库节点
    assert nodes[0].doc_id == "repo:o/r:main"
    files = run(src.list_nodes("repo:o/r:main"))
    assert [f.doc_id for f in files] == ["file:o/r:main:docs/a.md"]


def test_github_fetches_raw_content(no_whitelist):
    src = get_doc_source("github", {"token": "ghp_x"})

    def handler(method, url, kwargs):
        assert (kwargs["headers"] or {}).get("Accept") == "application/vnd.github.raw"
        return httpx.Response(200, content="# 手册\n\n正文".encode("utf-8"))

    patch_http(src, handler)
    doc = run(src.fetch_doc("file:o/r:main:docs/a.md"))
    assert doc.markdown.startswith("# 手册")


def test_github_empty_file_placeholder(no_whitelist):
    src = get_doc_source("github", {"token": "ghp_x"})

    def handler(method, url, kwargs):
        return httpx.Response(200, content=b"")

    patch_http(src, handler)
    doc = run(src.fetch_doc("file:o/r:main:docs/empty.md"))
    assert "docs/empty.md" in doc.markdown


def test_github_missing_token(no_whitelist):
    src = get_doc_source("github", {})
    res = run(src.test_connection())
    assert not res.ok and "Personal Access Token" in res.message


# ── Google Drive ──────────────────────────────────────────────────
def test_google_drive_refresh_token_flow(no_whitelist):
    src = get_doc_source("google_drive", {
        "client_id": "cid", "client_secret": "sec", "refresh_token": "rt",
    })

    def handler(method, url, kwargs):
        if url == "https://oauth2.googleapis.com/token":
            assert (kwargs["data"] or {}).get("grant_type") == "refresh_token"
            assert (kwargs["data"] or {}).get("client_secret") == "sec"
            return {"access_token": "tok", "expires_in": 3600}
        if url.endswith("/drive/v3/files"):
            assert (kwargs["headers"] or {}).get("Authorization") == "Bearer tok"
            return {"files": [
                {"id": "d1", "name": "需求文档",
                 "mimeType": "application/vnd.google-apps.document"},
                {"id": "f1", "name": "子目录",
                 "mimeType": "application/vnd.google-apps.folder"},
            ]}
        raise AssertionError(url)

    patch_http(src, handler)
    assert run(src.test_connection()).ok
    nodes = run(src.list_nodes(None))
    kinds = {n.title: n.node_type for n in nodes}
    assert kinds == {"需求文档": "doc", "子目录": "folder"}


def test_google_drive_export_native_doc(no_whitelist):
    src = get_doc_source("google_drive", {
        "client_id": "cid", "client_secret": "sec", "refresh_token": "rt",
    })

    def handler(method, url, kwargs):
        if url == "https://oauth2.googleapis.com/token":
            return {"access_token": "tok"}
        if "/export" in url:
            assert (kwargs["params"] or {}).get("mimeType") == "text/markdown"
            return httpx.Response(200, text="# 需求文档\n\n正文")
        raise AssertionError(url)

    patch_http(src, handler)
    doc = run(src.fetch_doc("gdoc:d1"))
    assert doc.markdown.startswith("# 需求文档")


def test_google_drive_missing_refresh_token(no_whitelist):
    src = get_doc_source("google_drive", {"client_id": "cid", "client_secret": "sec"})
    res = run(src.test_connection())
    assert not res.ok and "Refresh Token" in res.message


def test_google_drive_shortcut_resolves_target(no_whitelist):
    src = get_doc_source("google_drive", {
        "client_id": "cid", "client_secret": "sec", "refresh_token": "rt",
    })

    def handler(method, url, kwargs):
        if url == "https://oauth2.googleapis.com/token":
            return {"access_token": "tok"}
        return {"files": [
            {"id": "s1", "name": "快捷方式",
             "mimeType": "application/vnd.google-apps.shortcut",
             "shortcutDetails": {"targetId": "t1",
                                 "targetMimeType": "application/vnd.google-apps.document"}},
        ]}

    patch_http(src, handler)
    nodes = run(src.list_nodes(None))
    assert [n.doc_id for n in nodes] == ["gdoc:t1"]


# ── OneDrive ──────────────────────────────────────────────────────
def test_onedrive_scope_selection():
    assert _scope_of({}) == "me/drive"
    assert _scope_of({"drive_id": "d1"}) == "drives/d1"
    assert _scope_of({"site_id": "s1", "drive_id": "d1"}) == "sites/s1/drive"


def test_onedrive_client_credentials_flow(no_whitelist):
    src = get_doc_source("onedrive", {
        "tenant_id": "t1", "client_id": "cid", "client_secret": "sec",
    })

    def handler(method, url, kwargs):
        if "/oauth2/v2.0/token" in url:
            assert (kwargs["data"] or {}).get("grant_type") == "client_credentials"
            assert (kwargs["data"] or {}).get("scope") == "https://graph.microsoft.com/.default"
            return {"access_token": "tok"}
        if url.endswith("/v1.0/me/drive"):
            return {"name": "个人盘"}
        if url.endswith("/items/root/children"):
            assert (kwargs["headers"] or {}).get("Authorization") == "Bearer tok"
            return {"value": [
                {"id": "i1", "name": "手册.docx", "file": {"mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}},
                {"id": "i2", "name": "子目录", "folder": {"childCount": 2}},
                {"id": "i3", "name": "logo.png"},
            ]}
        raise AssertionError(url)

    patch_http(src, handler)
    assert run(src.test_connection()).ok
    nodes = run(src.list_nodes(None))
    kinds = {n.title: n.node_type for n in nodes}
    assert kinds == {"手册.docx": "doc", "子目录": "folder"}


def test_onedrive_missing_tenant(no_whitelist):
    src = get_doc_source("onedrive", {"client_id": "cid", "client_secret": "sec"})
    res = run(src.test_connection())
    assert not res.ok and "Tenant ID" in res.message


def test_onedrive_platform_error_not_swallowed(no_whitelist):
    src = get_doc_source("onedrive", {
        "tenant_id": "t1", "client_id": "cid", "client_secret": "sec",
    })

    def handler(method, url, kwargs):
        if "/oauth2/v2.0/token" in url:
            return {"access_token": "tok"}
        return httpx.Response(403, json={"error": {"message": "insufficient privileges"}})

    patch_http(src, handler)
    res = run(src.test_connection())
    assert not res.ok and "403" in res.message
