"""doc_sources 共用基础层单测：SSRF 通道 / HTML→Markdown / 二进制转 Markdown。

不打真实网络：SSRF 用例一律用 IP 字面量（``socket.getaddrinfo`` 对 IP 不做 DNS 查询）。
"""
from __future__ import annotations

import pytest

from app.connectors.doc_sources._host import (
    host_in_whitelist,
    resolve_host,
    resolve_hostname,
    resolve_url,
    whitelist_hosts,
)
from app.connectors.doc_sources.base import DocSourceError
from app.connectors.doc_sources.binary import (
    bytes_to_markdown,
    bytes_to_text,
    ext_of,
    is_supported,
)
from app.connectors.doc_sources.html import extract_title, html_to_markdown


@pytest.fixture
def no_whitelist(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "SSRF_WHITELIST", "")
    return settings


def _whitelist(monkeypatch, value: str):
    from app.config import settings

    monkeypatch.setattr(settings, "SSRF_WHITELIST", value)
    return settings


# ── SSRF 白名单 ───────────────────────────────────────────────────
def test_whitelist_hosts_parsed_and_lowercased(monkeypatch):
    _whitelist(monkeypatch, " wiki.corp.local , 192.168.1.10 ")
    assert whitelist_hosts() == ("wiki.corp.local", "192.168.1.10")
    assert host_in_whitelist("WIKI.CORP.LOCAL")
    assert not host_in_whitelist("other.local")


def test_whitelist_empty_by_default(no_whitelist):
    assert whitelist_hosts() == ()


# ── resolve_url ───────────────────────────────────────────────────
def test_resolve_url_completes_https_scheme(no_whitelist):
    # 93.184.216.34 为 example.com 的 IP 字面量，getaddrinfo 不会发起 DNS 查询
    assert resolve_url("93.184.216.34/docs") == "https://93.184.216.34/docs"


def test_resolve_url_rejects_empty(no_whitelist):
    with pytest.raises(DocSourceError) as exc:
        resolve_url("   ")
    assert "缺少 URL" in str(exc.value)


def test_resolve_url_rejects_private_ip(no_whitelist):
    with pytest.raises(DocSourceError) as exc:
        resolve_url("http://192.168.1.10/feed.xml")
    assert "SSRF_WHITELIST" in str(exc.value)


def test_resolve_url_whitelisted_private_ip_passes(monkeypatch):
    _whitelist(monkeypatch, "192.168.1.10")
    assert resolve_url("http://192.168.1.10/feed.xml") == "http://192.168.1.10/feed.xml"


def test_resolve_url_require_https(no_whitelist):
    with pytest.raises(DocSourceError) as exc:
        resolve_url("http://93.184.216.34", require_https=True)
    assert "https" in str(exc.value)


# ── resolve_host ──────────────────────────────────────────────────
def test_resolve_host_falls_back_to_default(no_whitelist):
    # 用 IP 字面量：本环境 DNS 会把 example.com 解析到保留网段，真实域名会被 SSRF 误判
    assert resolve_host("", default="https://93.184.216.34") == "https://93.184.216.34"


def test_resolve_host_strips_trailing_slash(no_whitelist):
    assert resolve_host("https://93.184.216.34/", default="") == "https://93.184.216.34"


def test_resolve_host_missing_both_raises(no_whitelist):
    with pytest.raises(DocSourceError) as exc:
        resolve_host("", default="")
    assert "缺少平台地址" in str(exc.value)


# ── resolve_hostname ──────────────────────────────────────────────
def test_resolve_hostname_bare_host(no_whitelist):
    assert resolve_hostname("93.184.216.34") == "93.184.216.34"


def test_resolve_hostname_strips_port(no_whitelist):
    assert resolve_hostname("93.184.216.34:993") == "93.184.216.34"


def test_resolve_hostname_rejects_loopback(no_whitelist):
    with pytest.raises(DocSourceError) as exc:
        resolve_hostname("127.0.0.1")
    assert "SSRF_WHITELIST" in str(exc.value)


def test_resolve_hostname_whitelist_passes(monkeypatch):
    _whitelist(monkeypatch, "mail.corp.local")
    assert resolve_hostname("mail.corp.local") == "mail.corp.local"


def test_resolve_hostname_empty(no_whitelist):
    with pytest.raises(DocSourceError) as exc:
        resolve_hostname("")
    assert "缺少主机地址" in str(exc.value)


# ── HTML → Markdown ───────────────────────────────────────────────
def test_html_to_markdown_heading_and_link():
    md = html_to_markdown(
        "<h1>标题</h1><p>正文 <a href='https://x.com'>链接</a></p>"
    )
    assert "# 标题" in md
    assert "正文" in md and "链接" in md


def test_html_to_markdown_drops_script():
    md = html_to_markdown("<script>alert(1)</script><p>正文</p>")
    assert "alert" not in md and "正文" in md


def test_html_to_markdown_empty():
    assert html_to_markdown("") == ""


def test_extract_title():
    assert extract_title("<html><head><title> 我的 文档 </title></head></html>") == "我的 文档"
    assert extract_title("<p>无标题</p>") is None


# ── 二进制 → Markdown ─────────────────────────────────────────────
def test_bytes_to_markdown_markdown_file():
    md = bytes_to_markdown("手册.md", "# 手册\n\n正文内容".encode("utf-8"))
    assert "# 手册" in md


def test_bytes_to_markdown_unsupported_ext():
    with pytest.raises(DocSourceError) as exc:
        bytes_to_markdown("a.exe", b"MZ")
    assert "不支持" in str(exc.value)


def test_bytes_to_markdown_empty():
    with pytest.raises(DocSourceError) as exc:
        bytes_to_markdown("a.pdf", b"")
    assert "内容为空" in str(exc.value)


def test_bytes_to_text_strips_bom():
    assert bytes_to_text(b"\xef\xbb\xbfhello") == "hello"


def test_ext_helpers():
    assert is_supported("a.DOCX")
    assert not is_supported("a.exe")
    assert ext_of("dir/a.pdf") == ".pdf"
