"""租户套餐管理路由。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_db, require_admin
from app.models.sys.sys_user import SysUser
from app.schemas.sys.sys_tenant import (
    SysTenantPackageCreate, SysTenantPackageUpdate, SysTenantPackageResp, SysTenantPackageSimple,
)
from app.services.tenant_service import TenantService

router = APIRouter()


# ── 固定路径路由必须在 /{package_id} 之前定义 ─────────────────────────

@router.get("/page")
def get_package_page(
    name: str = Query(None),
    status: str = Query(None),
    page_no: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    items, total = service.get_package_page(name, status, page_no, page_size)
    return {
        "code": 0,
        "data": {
            "list": [SysTenantPackageResp.model_validate(p).model_dump() for p in items],
            "total": total,
        },
    }


@router.get("/simple-list", response_model=list[SysTenantPackageSimple])
def get_package_simple_list(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    """获取活跃套餐精简列表（租户表单下拉用）"""
    service = TenantService(db)
    return [SysTenantPackageSimple.model_validate(p) for p in service.get_package_simple_list()]


@router.post("/create")
def create_package(
    req: SysTenantPackageCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    try:
        package = service.create_package(
            name=req.name, status=req.status,
            remark=req.remark, menu_ids=req.menu_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "data": {"package_id": package.package_id}}


@router.put("/update")
def update_package(
    req: SysTenantPackageUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    try:
        update_data = req.model_dump(exclude_unset=True, exclude={"package_id"})
        package = service.update_package(req.package_id, **update_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "data": {"package_id": package.package_id}}


@router.delete("/delete/{package_id}")
def delete_package(
    package_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    try:
        service.delete_package(package_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "message": "删除成功"}


@router.delete("/delete-list")
def delete_package_list(
    ids: list[int],
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    for pid in ids:
        try:
            service.delete_package(pid)
        except ValueError:
            continue
    return {"code": 0, "message": "批量删除成功"}


# ── 动态路径路由放在最后，避免拦截固定路径 ─────────────────────────

@router.get("/{package_id}", response_model=SysTenantPackageResp)
def get_package(
    package_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    service = TenantService(db)
    package = service.get_package(package_id)
    if not package:
        raise HTTPException(status_code=404, detail="套餐不存在")
    return SysTenantPackageResp.model_validate(package)
