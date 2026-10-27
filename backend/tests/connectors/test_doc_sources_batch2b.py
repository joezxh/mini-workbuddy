"""第 4 章第二批单测：web_crawler / slack / imap（不打真实网络、不依赖 DB）。"""
from __future__ import annotations

import asyncio
import email as email_lib

import httpx
import pytest

from app.connectors.doc_sources import DocConnResult, DocSourceError, get_doc_source
from app.connectors.doc_sources.base import BaseDocSource
from app.connectors.doc_sources.imap import decode_subject, _encode_message, _encode_mailbox
from app.connectors.doc_sources.slack import _encode_thread, render_thread
from app.connectors.doc_sources.web_crawler import _encode_page, parse_sitemap


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


# ── Web Crawler ───────────────────────────────────────────────────
SITEMAP = """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://93.184.216.34/docs/a</loc><lastmod>2026-10-01</lastmod></url>
  <url><loc>https://93.184.216.34/docs/sub/b</loc></url>
  <url><loc>https://93.184.216.34/blog/c</loc></url>
</urlset>"""


def test_web_crawler_parse_sitemap():
    children, pages = parse_sitemap(SITEMAP.encode("utf-8"))
    assert children == []
    assert [p["loc"].rsplit("/", 1)[-1] for p in pages] == ["a", "b", "c"]
    assert pages[0]["lastmod"] == "2026-10-01"


def test_web_crawler_parse_sitemap_index():
    index = """<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://93.184.216.34/s1.xml</loc></sitemap></sitemapindex>"""
    children, pages = parse_sitemap(index.encode("utf-8"))
    assert children == ["https://93.184.216.34/s1.xml"] and pages == []


def test_web_crawler_lists_tree_and_respects_rules(no_whitelist):
    src = get_doc_source("web_crawler", {
        "sitemap_url": "https://93.184.216.34/sitemap.xml",
        "exclude_patterns": "/blog/",
    })

    def handler(method, url, kwargs):
        if url.endswith("/sitemap.xml"):
            return httpx.Response(200, content=SITEMAP.encode("utf-8"))
        raise AssertionError(url)

    patch_http(src, handler)
    roots = run(src.list_nodes(None))
    assert roots[0].doc_id == "sm::https://93.184.216.34/sitemap.xml"
    top = run(src.list_nodes(roots[0].doc_id))
    # 顶层按路径首段给出目录；/blog/ 被排除规则过滤
    assert {n.title: n.node_type for n in top} == {"docs": "folder"}
    sub = run(src.list_nodes("dir::/docs"))
    assert {n.title: n.node_type for n in sub} == {"a": "doc", "sub": "folder"}


def test_web_crawler_fetches_page(no_whitelist):
    src = get_doc_source("web_crawler", {
        "sitemap_url": "https://93.184.216.34/sitemap.xml",
    })

    def handler(method, url, kwargs):
        if url.endswith("/sitemap.xml"):
            return httpx.Response(200, content=SITEMAP.encode("utf-8"))
        return httpx.Response(200, content=(
            "<html><head><title>页面标题</title></head><body><h1>正文</h1></body></html>"
        ).encode("utf-8"))

    patch_http(src, handler)
    doc = run(src.fetch_doc(_encode_page("https://93.184.216.34/docs/a")))
    assert doc.title == "页面标题" and "正文" in doc.markdown


def test_web_crawler_missing_sitemap(no_whitelist):
    src = get_doc_source("web_crawler", {})
    res = run(src.test_connection())
    assert not res.ok and "sitemap" in res.message.lower()


# ── Slack ─────────────────────────────────────────────────────────
def test_slack_test_connection_identity(no_whitelist):
    src = get_doc_source("slack", {"token": "xoxb-1"})

    def handler(method, url, kwargs):
        if url.endswith("/api/auth.test"):
            return {"ok": True, "team": "天阙", "user": "kb-bot"}
        raise AssertionError(url)

    patch_http(src, handler)
    res = run(src.test_connection())
    assert res.ok and "天阙" in res.identity


def test_slack_ok_false_is_error_not_swallowed(no_whitelist):
    """Slack 用 HTTP 200 + ok:false 表达失败，必须转成 DocSourceError。"""
    src = get_doc_source("slack", {"token": "xoxb-1"})

    def handler(method, url, kwargs):
        return {"ok": False, "error": "invalid_auth"}

    patch_http(src, handler)
    res = run(src.test_connection())
    assert not res.ok and "invalid_auth" in res.message


def test_slack_lists_channels_and_only_threads(no_whitelist):
    src = get_doc_source("slack", {"token": "xoxb-1"})

    def handler(method, url, kwargs):
        if url.endswith("/api/conversations.list"):
            return {"ok": True, "channels": [{"id": "C1", "name": "知识库"}],
                    "response_metadata": {"next_cursor": ""}}
        if url.endswith("/api/conversations.history"):
            return {"ok": True, "messages": [
                {"ts": "1700000000.000100", "text": "有回复的讨论\n第二行",
                 "reply_count": 2},
                {"ts": "1700000001.000100", "text": "孤立消息"},   # 无回复 → 不作为文档
            ]}
        raise AssertionError(url)

    patch_http(src, handler)
    channels = run(src.list_nodes(None))
    assert channels[0].doc_id == "ch:C1"
    threads = run(src.list_nodes("ch:C1"))
    assert [t.doc_id for t in threads] == [_encode_thread("C1", "1700000000.000100")]
    assert threads[0].title == "有回复的讨论"


def test_slack_renders_thread_markdown():
    md = render_thread([
        {"user": "U1", "ts": "1700000000.000100", "text": "问题？"},
        {"user": "U2", "ts": "1700000005.000100", "text": "答复"},
    ], "C1")
    assert "**U1**" in md and "问题？" in md and "**U2**" in md


def test_slack_missing_token(no_whitelist):
    src = get_doc_source("slack", {})
    res = run(src.test_connection())
    assert not res.ok and "Slack Token" in res.message


# ── IMAP ──────────────────────────────────────────────────────────
def test_imap_subject_decoding():
    assert decode_subject("=?UTF-8?B?5omL5YaM?=") == "手册"
    assert decode_subject("plain") == "plain"
    assert decode_subject(None) == ""


def test_imap_doc_id_encoding():
    assert _encode_mailbox("INBOX") == "mbox:INBOX"
    assert _encode_message("INBOX", "42", "7") == "msg:INBOX:42:7"


def test_imap_missing_credentials(no_whitelist):
    src = get_doc_source("imap", {"host": "93.184.216.34"})
    res = run(src.test_connection())
    assert isinstance(res, DocConnResult) and not res.ok
    assert "用户名" in res.message


def test_imap_internal_host_rejected(no_whitelist):
    src = get_doc_source("imap", {
        "host": "127.0.0.1", "username": "u", "password": "p",
    })
    res = run(src.test_connection())
    assert not res.ok and "SSRF_WHITELIST" in res.message


def test_imap_body_extraction_prefers_plain_text():
    """multipart 场景下优先取 text/plain；HTML 仅作兜底。"""
    from app.connectors.doc_sources.imap import _body_of

    raw = (
        "Subject: t\nContent-Type: multipart/alternative; boundary=b\n\n"
        "--b\nContent-Type: text/plain; charset=utf-8\n\n纯文本正文\n"
        "--b\nContent-Type: text/html; charset=utf-8\n\n<h1>HTML</h1>\n--b--\n"
    ).encode("utf-8")
    assert _body_of(email_lib.message_from_bytes(raw)) == "纯文本正文"


def test_imap_html_body_converted_to_markdown():
    from app.connectors.doc_sources.imap import _body_of

    raw = (
        "Subject: t\nContent-Type: text/html; charset=utf-8\n\n"
        "<h1>标题</h1><p>段落</p>\n"
    ).encode("utf-8")
    assert "# 标题" in _body_of(email_lib.message_from_bytes(raw))
