"""租户管理路由。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_db, require_admin
from app.models.sys.sys_user import SysUser
from app.schemas.sys.sys_tenant import (
    SysTenantCreate, SysTenantUpdate, SysTenantResp, TenantSimple, TenantPageQuery,
)
from app.services.tenant_service import TenantService
from app.core.tenant_decorators import tenant_ignore

router = APIRouter()


# ── 固定路径路由必须在 /{tenant_id} 之前定义 ─────────────────────────

@router.get("/page", response_model=dict)
def get_tenant_page(
    name: str = Query(None),
    contact_name: str = Query(None),
    contact_mobile: str = Query(None),
    status: str = Query(None),
    page_no: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    query = TenantPageQuery(
        name=name, contact_name=contact_name,
        contact_mobile=contact_mobile, status=status,
        page_no=page_no, page_size=page_size,
    )
    service = TenantService(db)
    items, total = service.get_tenant_page(query)
    return {
        "code": 0,
        "data": {
            "list": [SysTenantResp.model_validate(t).model_dump() for t in items],
            "total": total,
        },
    }


@router.get("/simple-list", response_model=list[TenantSimple])
@tenant_ignore
def get_tenant_simple_list(db: Session = Depends(get_db)):
    """获取活跃租户精简列表（下拉选择用，无需认证）"""
    service = TenantService(db)
    return [TenantSimple.model_validate(t) for t in service.get_simple_list()]


@router.get("/get-id-by-name")
@tenant_ignore
def get_tenant_id_by_name(
    name: str = Query(...),
    db: Session = Depends(get_db),
):
    """根据租户名获取租户ID"""
    from app.models.sys.sys_tenant import SysTenant
    tenant = db.query(SysTenant).filter(SysTenant.name == name).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    return {"code": 0, "data": {"tenant_id": tenant.tenant_id}}


@router.post("/create")
def create_tenant(
    req: SysTenantCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    try:
        tenant = service.create_tenant(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "data": {"tenant_id": tenant.tenant_id}}


@router.put("/update")
def update_tenant(
    req: SysTenantUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    try:
        tenant = service.update_tenant(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "data": {"tenant_id": tenant.tenant_id}}


@router.delete("/delete/{tenant_id}")
def delete_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    try:
        service.delete_tenant(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "message": "删除成功"}


@router.delete("/delete-list")
def delete_tenant_list(
    ids: list[int],
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    for tid in ids:
        try:
            service.delete_tenant(tid)
        except ValueError:
            continue
    return {"code": 0, "message": "批量删除成功"}


# ── 动态路径路由放在最后，避免拦截固定路径 ─────────────────────────

@router.get("/{tenant_id}", response_model=SysTenantResp)
def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    tenant = service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    return SysTenantResp.model_validate(tenant)
