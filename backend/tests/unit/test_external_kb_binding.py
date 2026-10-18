"""外部知识库平台绑定（external_type）与 web 连接器单元自测。

不依赖数据库 / 网络：聚焦纯函数与连接器辅助方法。
"""
import pytest
from fastapi import HTTPException

from app.services.kb.kb_format import validate_external_type
from app.connectors.doc_sources.web import WebDocSource
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
    assert validate_external_type(3, "connector", "web") == "web"
    # 必填
    with pytest.raises(HTTPException):
        validate_external_type(3, "connector", None)
    # 非法平台
    with pytest.raises(HTTPException):
        validate_external_type(3, "connector", "not_a_platform")


def test_non_connector_returns_none():
    assert validate_external_type(3, "proxy", None) is None


# ── WebDocSource 辅助方法（纯逻辑，无需网络） ──────────────────────────────────
def test_seed_urls_normalize_and_dedup():
    src = WebDocSource({"seed_urls": "example.com\nhttps://a.com\n\nhttps://a.com/"})
    urls = src._seed_urls()
    assert urls == ["https://example.com", "https://a.com", "https://a.com/"]


def test_crawl_depth_clamped():
    assert WebDocSource({"crawl_depth": "0"})._crawl_depth() == 0
    assert WebDocSource({"crawl_depth": "5"})._crawl_depth() == 2  # 上限
    assert WebDocSource({"crawl_depth": "bad"})._crawl_depth() == 1  # 兜底


def test_title_from_url():
    assert WebDocSource({})._title_from_url("https://x.com/docs/intro") == "intro"
    assert WebDocSource({})._title_from_url("https://x.com") == "x.com"


def test_extract_title():
    html = "<html><head><title>  Hello   World </title></head><body>x</body></html>"
    assert WebDocSource({})._extract_title(html) == "Hello World"


def test_html_to_markdown_fallback():
    # 不依赖 markdownify：去标签纯文本兜底
    md = WebDocSource({})._html_to_markdown("<p>Hello <b>World</b></p>")
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
