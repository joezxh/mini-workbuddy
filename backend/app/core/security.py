"""共享安全工具：SSRF 防护等。

抽出供外部知识库检索代理（kb_proxy）与站点爬虫连接器
（doc_sources.web_crawler，经 doc_sources._host 转发）复用，
避免内网/环回地址拦截逻辑在多处分叉漂移。
"""
from __future__ import annotations

import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException


def is_safe_url(url: str, *, require_https: bool = False) -> str:
    """校验 URL 不指向内网/环回/保留地址。

    - ``require_https``：为 True 时仅允许 https（外部检索代理端点场景）。
    - 拒绝缺失主机、``localhost`` / ``*.local``、以及解析到私有/环回/链路本地/保留网段。

    返回规整后的原始 URL；不合法抛 ``HTTPException(422)``。
    """
    parsed = urlparse(url or "")
    if require_https and parsed.scheme != "https":
        raise HTTPException(status_code=422, detail="必须使用 https")
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=422, detail=f"不支持的协议: {parsed.scheme}")
    host = parsed.hostname or ""
    if not host:
        raise HTTPException(status_code=422, detail="缺少主机名")
    if host == "localhost" or host.endswith(".local"):
        raise HTTPException(status_code=422, detail="禁止内网主机")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise HTTPException(status_code=422, detail=f"主机无法解析: {exc}") from exc
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise HTTPException(status_code=422, detail=f"禁止内网地址: {addr}")
    return url


def is_internal_host(host: str) -> bool:
    """判断主机名解析后是否落在内网/环回/保留网段（供 web 爬虫逐跳校验）。"""
    if not host:
        return True
    if host == "localhost" or host.endswith(".local"):
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            return True
    return False
