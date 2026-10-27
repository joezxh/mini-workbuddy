"""私有化部署地址的 SSRF 统一校验通道。

``doc_sources`` 的既有约束是「平台域名写成模块级常量 ``HOST``，不接受调用方传入
任意 base_url」，从根上消除 SSRF（见 ``base.py`` 模块 docstring）。但自托管平台的
地址只能由用户填写——GitLab / Confluence / Seafile 可能是内网部署，IMAP 邮箱服务器
更是纯主机名。本模块因此成为这套约束的**唯一例外通道**，所有「用户填写的地址」
必须经此放行：

1. 命中 ``settings.SSRF_WHITELIST``（逗号分隔域名 / IP，大小写不敏感）→ 放行，
   用于接入内网私有化部署；
2. 否则必须过 ``app.core.security.is_safe_url`` / ``is_internal_host``
   （拒绝内网 / 环回 / 链路本地 / 保留网段）。

非法地址一律转成 ``DocSourceError``，**不把 ``HTTPException(422)`` 泄漏到连接器层**
（连接器层的错误契约只有 ``DocSourceError``，其 message 直接回显前端）。

新增连接器时：公共 SaaS 平台继续写 ``HOST`` 常量，**不要**用本模块；只有确需用户
填地址的私有化平台才调用 ``resolve_host`` / ``resolve_url`` / ``resolve_hostname``。
"""
from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException

from app.connectors.doc_sources.base import DocSourceError
from app.core.security import is_internal_host, is_safe_url

logger = logging.getLogger(__name__)


def _settings():
    """惰性读取配置：避免在模块导入期强绑 ``app.config``（降低循环导入风险）。"""
    from app.config import settings

    return settings


def whitelist_hosts() -> tuple[str, ...]:
    """当前 SSRF 白名单（小写主机名 / IP）。"""
    try:
        hosts = getattr(_settings(), "ssrf_whitelist_hosts", None)
        if hosts:
            return tuple(str(h).strip().lower() for h in hosts if str(h).strip())
        raw = getattr(_settings(), "SSRF_WHITELIST", "") or ""
    except Exception:  # noqa: BLE001 - 配置不可用时按「无白名单」处理，退化为严格校验
        logger.warning("读取 SSRF_WHITELIST 失败，按无白名单处理")
        return ()
    return tuple(h.strip().lower() for h in str(raw).split(",") if h.strip())


def host_in_whitelist(host: str) -> bool:
    host = (host or "").strip().lower()
    return bool(host) and host in whitelist_hosts()


def _ensure_scheme(raw: str) -> str:
    """补全协议（缺省 https）并去掉结尾斜杠，便于拼接业务路径。"""
    raw = (raw or "").strip().rstrip("/")
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw


def _hostname_of(url: str) -> str:
    return (urlparse(url).hostname or "").strip().lower()


def resolve_url(raw: str, *, require_https: bool = False) -> str:
    """校验一个完整 URL（订阅源 / sitemap / 文章页），返回补全协议后的 URL。

    :raises DocSourceError: 地址为空或命中 SSRF 拦截。
    """
    url = _ensure_scheme(raw)
    if not url:
        raise DocSourceError("缺少 URL")
    if require_https and not url.startswith("https://"):
        raise DocSourceError("URL 必须使用 https")
    host = _hostname_of(url)
    if host_in_whitelist(host):
        return url
    try:
        is_safe_url(url, require_https=require_https)
    except HTTPException as exc:
        raise DocSourceError(
            f"URL 不合法（{exc.detail}）；若为内网私有化部署，请先把域名加入 SSRF_WHITELIST"
        ) from exc
    return url


def resolve_host(raw: str, *, default: Optional[str] = None, require_https: bool = False) -> str:
    """校验平台基址（GitLab / Confluence / Seafile / GitHub 的 base_url）。

    ``default`` 是平台的官方 SaaS 地址常量：用户留空时**直接采用，不再做 SSRF 校验**
    ——它是模块级常量，与「HOST 必须硬编码」这条约束同源，本就属于可信地址；只有用户
    填写的地址才需要过 ``resolve_url``。这样也避免内网 DNS 劫持等环境噪声把官方域名
    误判成内网地址。
    """
    base = _ensure_scheme(raw)
    if not base:
        if not default:
            raise DocSourceError("缺少平台地址")
        return _ensure_scheme(default)
    return resolve_url(base, require_https=require_https)


def resolve_hostname(raw: str) -> str:
    """校验并返回裸主机名（IMAP 等直接连主机、不拼 URL 的场景）。"""
    host = (raw or "").strip()
    if not host:
        raise DocSourceError("缺少主机地址")
    # 允许以 host:port 形式填写，只取主机部分参与校验，端口由调用方单独解析
    candidate = host
    if "://" in candidate:
        candidate = _hostname_of(candidate)
    elif ":" in candidate and not candidate.startswith("["):
        candidate = candidate.rsplit(":", 1)[0]
    candidate = candidate.strip().strip("/").lower()
    if not candidate:
        raise DocSourceError("主机地址无法解析")
    if host_in_whitelist(candidate):
        return candidate
    if is_internal_host(candidate):
        raise DocSourceError(
            f"主机 {candidate} 命中内网/保留地址拦截；若为内网邮箱服务器，"
            "请先把该域名加入 SSRF_WHITELIST"
        )
    return candidate
