"""外部知识库平台绑定（external_type）与 web_crawler 连接器单元自测。

不依赖数据库 / 网络：聚焦纯函数与连接器辅助方法。
原 ``web`` 种子 URL 连接器已被 ``web_crawler``（sitemap 驱动）取代，相关用例同步迁移。
"""
import pytest
from fastapi import HTTPException

from app.services.kb.kb_format import validate_external_type
from app.connectors.doc_sources.web_crawler import (
    WebCrawlerDocSource,
    _encode_page,
    parse_sitemap,
)
from app.connectors.doc_sources.html import extract_title, html_to_markdown
from app.core.security import is_safe_url


# ── validate_external_type ────────────────────────────────────────────────────
def test_non_external_kb_rejects_external_type():
    with pytest.raises(HTTPException):
        validate_external_type(1, None, "feishu")
    with pytest.raises(HTTPException):
        validate_external_type(2, "document", "feishu")


def test_proxy_must_not_have_external_type():
    with pytest.raises(HTTPException):
        validate_external_type(3, "proxy", "feishu")


def test_connector_requires_valid_external_type():
    # 合法平台
    assert validate_external_type(3, "connector", "feishu") == "feishu"
    assert validate_external_type(3, "connector", "web_crawler") == "web_crawler"
    # 必填
    with pytest.raises(HTTPException):
        validate_external_type(3, "connector", None)
    # 非法平台
    with pytest.raises(HTTPException):
        validate_external_type(3, "connector", "not_a_platform")


def test_legacy_web_type_no_longer_accepted():
    """web 已由 web_crawler 取代，不再作为合法平台（存量数据需迁移）。"""
    with pytest.raises(HTTPException):
        validate_external_type(3, "connector", "web")


def test_non_connector_returns_none():
    assert validate_external_type(3, "proxy", None) is None


# ── WebCrawlerDocSource 辅助方法（纯逻辑，无需网络） ───────────────────────────
def test_sitemap_urls_normalize_and_dedup(monkeypatch):
    src = WebCrawlerDocSource({
        "sitemap_url": "93.184.216.34/sitemap.xml\n"
                       "https://93.184.216.34/sitemap.xml",
    })
    assert src._sitemaps() == ["https://93.184.216.34/sitemap.xml"]


def test_limits_are_clamped():
    assert WebCrawlerDocSource({"max_pages": "0"})._max_pages() == 1      # 下限
    assert WebCrawlerDocSource({"max_pages": "9999"})._max_pages() == 1000  # 上限
    assert WebCrawlerDocSource({"max_pages": "bad"})._max_pages() == 200   # 兜底
    assert WebCrawlerDocSource({"max_depth": "9"})._max_depth() == 5


def test_include_exclude_rules():
    src = WebCrawlerDocSource({
        "include_patterns": "^https://a\\.com/docs/",
        "exclude_patterns": "/tag/",
    })
    assert src._kept("https://a.com/docs/intro")
    assert not src._kept("https://a.com/blog/x")     # 未命中包含规则
    assert not src._kept("https://a.com/docs/tag/x")  # 命中排除规则


def test_parse_sitemap_and_page_encoding():
    payload = (
        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://a.com/docs/x</loc><lastmod>2026-01-01</lastmod></url>"
        "</urlset>"
    ).encode("utf-8")
    children, pages = parse_sitemap(payload)
    assert children == [] and pages[0]["lastmod"] == "2026-01-01"
    assert _encode_page("https://a.com/docs/x") == "page::https://a.com/docs/x"


def test_extract_title():
    html = "<html><head><title>  Hello   World </title></head><body>x</body></html>"
    assert extract_title(html) == "Hello World"


def test_html_to_markdown_fallback():
    # 不依赖 markdownify 的具体实现：只要标签被去掉、正文保留
    md = html_to_markdown("<p>Hello <b>World</b></p>")
    assert "Hello" in md and "World" in md


# ── SSRF 防护 ──────────────────────────────────────────────────────────────────
def test_ssrf_blocks_internal():
    with pytest.raises(HTTPException):
        is_safe_url("http://127.0.0.1:8080/x")
    with pytest.raises(HTTPException):
        is_safe_url("http://localhost/x")
    with pytest.raises(HTTPException):
        is_safe_url("ftp://example.com/x")


def test_ssrf_allows_public():
    # 仅做格式/解析校验，不做真实网络请求
    assert is_safe_url("https://www.yuque.com/x") == "https://www.yuque.com/x"
