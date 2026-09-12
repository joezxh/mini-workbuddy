"""工作流管理 API"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.schemas.workflow import (
    WorkflowFlowCreate, WorkflowFlowUpdate, WorkflowFlowOut,
    WorkflowFlowListOut, WorkflowExecutionLogOut,
    WorkflowChainCreate, WorkflowChainUpdate, WorkflowChainOut,
    WorkflowTestReq, WorkflowTestResp,
    PlatformTypeEnum, FlowTypeEnum,
)
from app.services.workflow.workflow_service import WorkflowService
from app.services.workflow.gateway import WorkflowGateway

router = APIRouter(prefix="/api/v1/workflow", tags=["工作流管理"])
svc = WorkflowService()


# ── 枚举查询 ─────────────────────────────────────────────────

@router.get("/platforms/types")
def get_platform_types():
    """获取支持的平台类型和流程类型枚举"""
    return {"platform_types": PlatformTypeEnum.ALL, "flow_types": FlowTypeEnum.ALL}


# ── Flow CRUD ────────────────────────────────────────────────

@router.get("/flows", response_model=WorkflowFlowListOut)
def list_flows(
    platform_type: Optional[str] = Query(None),
    flow_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    total, items = svc.list_flows(db, tenant_id=user.tenant_id,
                                  platform_type=platform_type, flow_type=flow_type,
                                  is_active=is_active, page=page, page_size=page_size)
    return WorkflowFlowListOut(total=total, items=[WorkflowFlowOut.model_validate(i) for i in items])


@router.post("/flows", response_model=WorkflowFlowOut)
def create_flow(
    data: WorkflowFlowCreate,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    flow = svc.create_flow(db, {**data.model_dump(exclude={"api_key"}),
                                 "api_key": data.api_key,
                                 "tenant_id": user.tenant_id,
                                 "created_by": user.id})
    db.commit()
    return WorkflowFlowOut.model_validate(flow)


@router.get("/flows/{flow_id}", response_model=WorkflowFlowOut)
def get_flow(flow_id: int, db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    flow = svc.get_flow(db, flow_id)
    if not flow:
        raise HTTPException(404, "工作流不存在")
    return WorkflowFlowOut.model_validate(flow)


@router.put("/flows/{flow_id}", response_model=WorkflowFlowOut)
def update_flow(flow_id: int, data: WorkflowFlowUpdate,
                db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    flow = svc.get_flow(db, flow_id)
    if not flow:
        raise HTTPException(404, "工作流不存在")
    flow = svc.update_flow(db, flow, data.model_dump(exclude_unset=True))
    db.commit()
    return WorkflowFlowOut.model_validate(flow)


@router.delete("/flows/{flow_id}")
def delete_flow(flow_id: int, db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    flow = svc.get_flow(db, flow_id)
    if not flow:
        raise HTTPException(404, "工作流不存在")
    svc.delete_flow(db, flow)
    db.commit()
    return {"ok": True}


@router.post("/flows/{flow_id}/test", response_model=WorkflowTestResp)
async def test_flow(flow_id: int, data: WorkflowTestReq,
                    db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    flow = svc.get_flow(db, flow_id)
    if not flow:
        raise HTTPException(404, "工作流不存在")
    gateway = WorkflowGateway(db)
    result = await gateway.execute(
        flow_code=flow.flow_code, tenant_id=user.tenant_id,
        inputs=data.inputs, user_id=str(user.id), timeout=data.timeout,
    )
    return WorkflowTestResp(success=result.success, output=result.output,
                            error=result.error, latency_ms=result.latency_ms)


# ── Execution Log ────────────────────────────────────────────

@router.get("/executions")
def list_executions(
    flow_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    total, items = svc.list_executions(db, flow_id=flow_id, status=status,
                                       page=page, page_size=page_size)
    return {"total": total,
            "items": [WorkflowExecutionLogOut.model_validate(i) for i in items]}


# ── Chain CRUD ───────────────────────────────────────────────

@router.get("/chains")
def list_chains(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    total, items = svc.list_chains(db, tenant_id=user.tenant_id, page=page, page_size=page_size)
    return {"total": total, "items": [WorkflowChainOut.model_validate(i) for i in items]}


@router.post("/chains", response_model=WorkflowChainOut)
def create_chain(data: WorkflowChainCreate,
                 db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    chain = svc.create_chain(db, {**data.model_dump(), "tenant_id": user.tenant_id,
                                   "created_by": user.id})
    db.commit()
    return WorkflowChainOut.model_validate(chain)


@router.put("/chains/{chain_id}", response_model=WorkflowChainOut)
def update_chain(chain_id: int, data: WorkflowChainUpdate,
                 db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    from sqlalchemy import select
    from app.models.workflow.workflow_chain import WorkflowChain
    chain = db.scalars(select(WorkflowChain).where(
        WorkflowChain.id == chain_id, WorkflowChain.is_deleted == False)).first()
    if not chain:
        raise HTTPException(404, "链不存在")
    chain = svc.update_chain(db, chain, data.model_dump(exclude_unset=True))
    db.commit()
    return WorkflowChainOut.model_validate(chain)


@router.delete("/chains/{chain_id}")
def delete_chain(chain_id: int, db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    from sqlalchemy import select
    from app.models.workflow.workflow_chain import WorkflowChain
    chain = db.scalars(select(WorkflowChain).where(
        WorkflowChain.id == chain_id, WorkflowChain.is_deleted == False)).first()
    if not chain:
        raise HTTPException(404, "链不存在")
    svc.delete_chain(db, chain)
    db.commit()
    return {"ok": True}
