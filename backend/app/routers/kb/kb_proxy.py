"""外部知识库检索代理（对齐文档 D1 边界内、spec §10.2 proxy 形态）。

不拉数据、无内部文档管理；仅配置 CRUD + 连通性测试 + 检索转发。
SSRF 防护：仅 https、拒绝内网/环回地址段（spec §11 风险表）。
"""
from __future__ import annotations

import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.connectors.external_kb_endpoint import ExternalKbEndpoint
from app.models.sys.sys_user import SysUser
from app.services.kb.kb_permissions import KB_ADMIN, require_kb_permission

router = APIRouter(prefix="/api/v1/external-kb-endpoints", tags=["外部知识库代理"])


def validate_endpoint_url(url: str) -> str:
    """SSRF 防护：仅 https 且主机不得解析到内网/环回地址。返回规整后的 URL。"""
    parsed = urlparse(url or "")
    if parsed.scheme != "https":
        raise HTTPException(status_code=422, detail="外部端点必须使用 https")
    host = parsed.hostname or ""
    if not host:
        raise HTTPException(status_code=422, detail="缺少主机名")
    if host in ("localhost",) or host.endswith(".local"):
        raise HTTPException(status_code=422, detail="禁止内网主机")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise HTTPException(status_code=422, detail=f"主机无法解析: {exc}")
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise HTTPException(status_code=422, detail=f"禁止内网地址: {addr}")
    return url


def _tenant_id(current_user: SysUser) -> int:
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="tenant_required")
    return tenant_id


def _serialize(ep: ExternalKbEndpoint) -> dict:
    return {
        "id": ep.id,
        "name": ep.name,
        "endpoint_url": ep.endpoint_url,
        "index_name": ep.index_name,
        "metadata_mapping": ep.metadata_mapping,
        "status": ep.status,
        "error_detail": ep.error_detail,
        "allowed_callers": ep.allowed_callers,
    }


def _get(db: Session, tenant_id: int, endpoint_id: int) -> ExternalKbEndpoint:
    ep = db.execute(
        select(ExternalKbEndpoint).where(
            ExternalKbEndpoint.tenant_id == tenant_id,
            ExternalKbEndpoint.id == endpoint_id,
        )
    ).scalar_one_or_none()
    if ep is None:
        raise HTTPException(status_code=404, detail="外部端点不存在")
    return ep


class EndpointBody(BaseModel):
    name: str
    endpoint_url: str
    index_name: Optional[str] = None
    auth_key: Optional[str] = None
    metadata_mapping: Optional[str] = None


@router.post("", status_code=201)
def create_endpoint(
    body: EndpointBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    url = validate_endpoint_url(body.endpoint_url)
    ep = ExternalKbEndpoint(
        tenant_id=_tenant_id(current_user),
        name=body.name, endpoint_url=url, index_name=body.index_name,
        metadata_mapping=body.metadata_mapping,
        creator_id=getattr(current_user, "user_id", None),
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return _serialize(ep)


@router.get("")
def list_endpoints(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    rows = db.execute(
        select(ExternalKbEndpoint).where(
            ExternalKbEndpoint.tenant_id == _tenant_id(current_user)
        )
    ).scalars().all()
    return [_serialize(e) for e in rows]


@router.put("/{endpoint_id}")
def update_endpoint(
    endpoint_id: int,
    body: EndpointBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    ep = _get(db, _tenant_id(current_user), endpoint_id)
    ep.name = body.name
    ep.endpoint_url = validate_endpoint_url(body.endpoint_url)
    ep.index_name = body.index_name
    ep.metadata_mapping = body.metadata_mapping
    db.commit()
    db.refresh(ep)
    return _serialize(ep)


@router.delete("/{endpoint_id}")
def delete_endpoint(
    endpoint_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    ep = _get(db, _tenant_id(current_user), endpoint_id)
    db.delete(ep)
    db.commit()
    return {"deleted": endpoint_id}


class CallersBody(BaseModel):
    """调用方白名单（spec §10.6）；``callers=null`` 表示不限制。"""
    callers: Optional[list[str]] = None


def is_caller_allowed(ep: ExternalKbEndpoint, caller: Optional[str]) -> bool:
    """空名单=不限制；设了名单则必须命中（fail-closed）。"""
    allowed = ep.allowed_callers
    if not allowed:
        return True
    return bool(caller) and caller in allowed


@router.get("/{endpoint_id}/callers")
def list_callers(
    endpoint_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """查看该外部库授权的调用方（Agent/应用标识）。"""
    ep = _get(db, _tenant_id(current_user), endpoint_id)
    return {"endpoint_id": ep.id, "callers": ep.allowed_callers}


@router.put("/{endpoint_id}/callers")
def update_callers(
    endpoint_id: int,
    body: CallersBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    _perm=Depends(require_kb_permission(KB_ADMIN)),
):
    """设置调用方白名单；传 null 清空为不限制。"""
    ep = _get(db, _tenant_id(current_user), endpoint_id)
    ep.allowed_callers = body.callers if body.callers else None
    db.commit()
    db.refresh(ep)
    return {"endpoint_id": ep.id, "callers": ep.allowed_callers}


@router.post("/{endpoint_id}/test")
def test_endpoint(
    endpoint_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """连通性测试：HEAD 请求外部端点（10s 超时），状态/错误落库返回。"""
    import httpx

    ep = _get(db, _tenant_id(current_user), endpoint_id)
    try:
        with httpx.Client(timeout=10.0, follow_redirects=False) as client:
            resp = client.head(ep.endpoint_url)
        ep.status = "active"
        ep.error_detail = None
        result = {"ok": True, "http_status": resp.status_code}
    except Exception as exc:  # noqa: BLE001 - 连通性失败是测试结果，不是异常
        ep.status = "error"
        ep.error_detail = f"{type(exc).__name__}: {exc}"
        result = {"ok": False, "error": ep.error_detail}
    db.commit()
    return result
