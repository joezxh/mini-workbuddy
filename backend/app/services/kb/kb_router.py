"""kb_ref REST 端点（挂载于 /agentscope/knowledge_bases）。

本路由暴露 kb_ref 的增删查列接口，是 MWB 侧「知识库登记」对外的 HTTP 面。
所有接口强制携带租户标识（``X-Tenant-Id`` 头或 ``tenant_id`` 查询参数），
缺失即 400（纵深防御，P1 Task 6）；数据访问统一经 ``KbRefService`` 并按 tenant_id 过滤。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.kb.kb_ref import KbRef
from app.services.kb.kb_ref_service import KbRefService


router = APIRouter(prefix="/kb", tags=["kb"])


def get_db():
    """每个请求一个独立会话（与生产 app 的 get_db 解耦，便于挂载/独立部署）。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_tenant_id(
    x_tenant_id: Optional[int] = Header(None, alias="X-Tenant-Id"),
    tenant_id: Optional[int] = Query(None),
) -> int:
    """从请求中提取并校验租户标识（缺失即拒绝）。"""
    tid = x_tenant_id if x_tenant_id is not None else tenant_id
    if tid is None:
        raise HTTPException(status_code=400, detail="缺少租户标识 X-Tenant-Id")
    return tid


class KbRefCreate(BaseModel):
    name: str
    description: Optional[str] = None
    creator_id: Optional[int] = None


class KbRefOut(BaseModel):
    id: int
    kb_id: str
    name: str
    description: Optional[str] = None
    as_user_id: str
    doc_count: int
    segment_count: int
    creator_id: Optional[int] = None

    @classmethod
    def from_model(cls, m: KbRef) -> "KbRefOut":
        return cls(
            id=m.id,
            kb_id=m.kb_id,
            name=m.name,
            description=m.description,
            as_user_id=m.as_user_id,
            doc_count=m.doc_count,
            segment_count=m.segment_count,
            creator_id=m.creator_id,
        )


@router.post("", response_model=KbRefOut, status_code=201)
def create_kb(
    body: KbRefCreate,
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> KbRefOut:
    svc = KbRefService(db, tenant_id)
    ref = svc.create_kb_ref(body.name, body.description, body.creator_id)
    db.commit()
    return KbRefOut.from_model(ref)


@router.get("", response_model=List[KbRefOut])
def list_kb(
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> List[KbRefOut]:
    svc = KbRefService(db, tenant_id)
    return [KbRefOut.from_model(r) for r in svc.list_kb_refs()]


@router.get("/{kb_id}", response_model=KbRefOut)
def get_kb(
    kb_id: str,
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> KbRefOut:
    svc = KbRefService(db, tenant_id)
    ref = svc.get_kb_ref(kb_id)
    if ref is None:
        raise HTTPException(status_code=404, detail="kb 不存在")
    return KbRefOut.from_model(ref)


@router.delete("/{kb_id}")
def delete_kb(
    kb_id: str,
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> Response:
    svc = KbRefService(db, tenant_id)
    if not svc.delete_kb_ref(kb_id):
        raise HTTPException(status_code=404, detail="kb 不存在")
    db.commit()
    return Response(status_code=204)
