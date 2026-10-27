"""第 3 章首批新增连接器单测：gitlab / ima / rss（不打真实网络、不依赖 DB）。"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.connectors.doc_sources import DocConnResult, DocSourceError, get_doc_source
from app.connectors.doc_sources.base import BaseDocSource
from app.connectors.doc_sources.gitlab import is_supported_file, parse_projects
from app.connectors.doc_sources.rss import parse_feed, parse_headers


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
        self.last_headers = None

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


# ── GitLab: 配置解析与白名单 ──────────────────────────────────────
def test_gitlab_parse_projects_line_form():
    assert parse_projects("123:main:docs/,README.md") == [
        {"project_id": "123", "ref": "main", "paths": ["docs/", "README.md"]}
    ]
    assert parse_projects("456") == [{"project_id": "456", "ref": "", "paths": []}]


def test_gitlab_parse_projects_json_form():
    assert parse_projects('[{"project_id":"1","ref":"dev","paths":["a/"]}]') == [
        {"project_id": "1", "ref": "dev", "paths": ["a/"]}
    ]


def test_gitlab_file_whitelist():
    assert is_supported_file("docs/guide.md")
    assert is_supported_file("a/b/spec.pdf")
    assert not is_supported_file("src/main.go")
    assert not is_supported_file("logo.png")


# ── GitLab: 列举与正文 ────────────────────────────────────────────
def test_gitlab_lists_selected_projects_and_files(no_whitelist):
    src = get_doc_source("gitlab", {
        "base_url": "https://93.184.216.34",
        "access_token": "glpat-x",
        "projects": "7:main:docs/",
    })

    def handler(method, url, kwargs):
        if url.endswith("/version"):
            return {"version": "17.2.0"}
        if url.endswith("/projects/7"):
            return {"id": 7, "name_with_namespace": "team / handbook",
                    "web_url": "https://git/team/handbook"}
        if "/repository/tree" in url:
            return [
                {"type": "blob", "path": "docs/intro.md"},
                {"type": "blob", "path": "docs/logo.png"},       # 图片不在白名单
                {"type": "blob", "path": "src/main.go"},         # 代码不在白名单
                {"type": "blob", "path": "README.md"},           # 不在 paths 范围内
                {"type": "tree", "path": "docs/sub"},
            ]
        raise AssertionError(url)

    patch_http(src, handler)
    projects = run(src.list_nodes(None))
    assert projects[0].doc_id == "proj:7:main"
    files = run(src.list_nodes("proj:7:main"))
    assert [f.doc_id for f in files] == ["file:7:main:docs/intro.md"]


def test_gitlab_fetches_raw_markdown(no_whitelist):
    src = get_doc_source("gitlab", {
        "base_url": "https://93.184.216.34", "access_token": "glpat-x",
    })

    def handler(method, url, kwargs):
        if "/repository/files/" in url:
            return httpx.Response(200, content="# 手册\n\n正文".encode("utf-8"))
        raise AssertionError(url)

    patch_http(src, handler)
    doc = run(src.fetch_doc("file:7:main:docs/intro.md"))
    assert doc.markdown.startswith("# 手册")


def test_gitlab_empty_file_falls_back_to_path(no_whitelist):
    """文件被清空时以路径占位，避免旧正文滞留。"""
    src = get_doc_source("gitlab", {
        "base_url": "https://93.184.216.34", "access_token": "glpat-x",
    })

    def handler(method, url, kwargs):
        return httpx.Response(200, content=b"")

    patch_http(src, handler)
    doc = run(src.fetch_doc("file:7:main:docs/empty.md"))
    assert "docs/empty.md" in doc.markdown


def test_gitlab_missing_token_message(no_whitelist):
    src = get_doc_source("gitlab", {"base_url": "https://93.184.216.34"})
    res = run(src.test_connection())
    assert isinstance(res, DocConnResult) and not res.ok
    assert "Access Token" in res.message


# ── IMA ──────────────────────────────────────────────────────────
def test_ima_lists_kb_and_media(no_whitelist):
    src = get_doc_source("ima", {"client_id": "cid", "api_key": "key"})

    def handler(method, url, kwargs):
        if url.endswith("/get_addable_knowledge_base_list"):
            return {"code": 0, "data": {"knowledge_base_list": [
                {"knowledge_base_id": "kb1", "name": "产品知识库"},
            ]}}
        if url.endswith("/get_knowledge_list"):
            return {"code": 0, "data": {"media_list": [
                {"media_id": "m1", "title": "需求文档", "media_type": 1},
                {"media_id": "m2", "title": "AI 会话", "media_type": 12},   # 跳过
                {"media_id": "m3", "title": "视频", "media_type": 16},      # 跳过
            ], "next_cursor": ""}}
        raise AssertionError(url)

    patch_http(src, handler)
    kbs = run(src.list_nodes(None))
    assert kbs[0].doc_id == "kb1"
    medias = run(src.list_nodes("kb1"))
    assert [m.doc_id for m in medias] == ["media:m1"]


def test_ima_fetches_note_content(no_whitelist):
    src = get_doc_source("ima", {"client_id": "cid", "api_key": "key"})

    def handler(method, url, kwargs):
        if url.endswith("/get_media_info"):
            return {"code": 0, "data": {
                "title": "会议纪要",
                "notebook_ext_info": {"notebook_id": "nb1"},
            }}
        if url.endswith("/get_doc_content"):
            return {"code": 0, "data": {"content": "# 会议纪要\n\n要点一"}}
        raise AssertionError(url)

    patch_http(src, handler)
    doc = run(src.fetch_doc("media:m1"))
    assert doc.title == "会议纪要" and "# 会议纪要" in doc.markdown


def test_ima_missing_api_key(no_whitelist):
    src = get_doc_source("ima", {"client_id": "cid"})
    res = run(src.test_connection())
    assert not res.ok and "API Key" in res.message


def test_ima_platform_error_code_not_swallowed(no_whitelist):
    src = get_doc_source("ima", {"client_id": "cid", "api_key": "key"})

    def handler(method, url, kwargs):
        return {"code": 40001, "msg": "invalid apikey"}

    patch_http(src, handler)
    with pytest.raises(DocSourceError) as exc:
        run(src.list_nodes(None))
    assert "40001" in str(exc.value)


# ── RSS ──────────────────────────────────────────────────────────
def test_rss_parse_headers():
    assert parse_headers("Authorization: Bearer x\nCookie: a=b") == {
        "Authorization": "Bearer x", "Cookie": "a=b",
    }


def test_rss_parse_rss2_feed():
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>第一篇</title><link>https://a.com/1</link>
        <guid>g1</guid><pubDate>Mon, 01 Jan 2026 00:00:00 GMT</pubDate></item>
    </channel></rss>""".encode("utf-8")
    items = parse_feed(xml)
    assert items[0]["id"] == "g1" and items[0]["link"] == "https://a.com/1"


def test_rss_parse_atom_feed():
    xml = b"""<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>E1</title><link rel="alternate" href="https://b.com/e1"/>
        <id>id1</id><updated>2026-01-01T00:00:00Z</updated></entry>
    </feed>"""
    items = parse_feed(xml)
    assert items[0]["link"] == "https://b.com/e1" and items[0]["updated"].startswith("2026")


def test_rss_parse_json_feed():
    payload = b'{"items":[{"id":"j1","title":"J1","url":"https://c.com/1"}]}'
    assert parse_feed(payload)[0]["link"] == "https://c.com/1"


def test_rss_lists_feeds_and_items(no_whitelist):
    src = get_doc_source("rss", {"feed_urls": "https://93.184.216.34/feed.xml"})

    def handler(method, url, kwargs):
        if url.endswith("/feed.xml"):
            return httpx.Response(200, content="""<?xml version="1.0"?><rss version="2.0">
              <channel><item><title>条目一</title>
              <link>https://93.184.216.34/post/1</link><guid>g1</guid></item></channel></rss>"""
                                  .encode("utf-8"))
        raise AssertionError(url)

    patch_http(src, handler)
    feeds = run(src.list_nodes(None))
    assert feeds[0].doc_id == "feed::https://93.184.216.34/feed.xml"
    items = run(src.list_nodes(feeds[0].doc_id))
    assert items[0].title == "条目一"
    assert items[0].doc_id == "item::https://93.184.216.34/feed.xml::https://93.184.216.34/post/1"


def test_rss_fetch_doc_does_not_send_auth_headers(no_whitelist):
    """正文页不得携带 auth_headers（防凭据泄漏给第三方站点）。"""
    src = get_doc_source("rss", {
        "feed_urls": "https://93.184.216.34/feed.xml",
        "auth_headers": "Authorization: Bearer secret",
    })

    def handler(method, url, kwargs):
        assert "Authorization" not in (kwargs["headers"] or {}), kwargs["headers"]
        return httpx.Response(200, content=(
            "<html><head><title>文章标题</title></head>"
            "<body><h1>正文</h1></body></html>"
        ).encode("utf-8"))

    patch_http(src, handler)
    doc = run(src.fetch_doc(
        "item::https://93.184.216.34/feed.xml::https://93.184.216.34/post/1"
    ))
    assert doc.title == "文章标题" and "正文" in doc.markdown


def test_rss_missing_feed_urls(no_whitelist):
    src = get_doc_source("rss", {})
    res = run(src.test_connection())
    assert not res.ok and "订阅源" in res.message
