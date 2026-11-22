"""文件存储配置路由（对齐 Java /system/file-config）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.deps import get_current_user
from app.models.sys.sys_user import SysUser
from app.services.file import file_config_service

router = APIRouter(prefix="/system/file-config", tags=["文件存储配置"])


def _ok(data=None, message="success"):
    return {"code": 0, "message": message, "data": data}


def _config_resp(config) -> dict:
    return {
        "id": config.id, "name": config.name, "code": config.code,
        "storage": config.storage, "master": bool(config.is_master),
        "config": config.config or {}, "remark": config.remark,
        "createTime": config.create_time.isoformat() if config.create_time else None,
    }


def _tenant_id(user: SysUser | None) -> int | None:
    return getattr(user, "tenant_id", None) if user else None


@router.post("/create")
def create_config(payload: dict, db: Session = Depends(get_db),
                  current_user: SysUser = Depends(get_current_user)):
    try:
        config = file_config_service.create_config(
            db, payload, getattr(current_user, "username", None),
            tenant_id=_tenant_id(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ok(config.id)


@router.put("/update")
def update_config(payload: dict, db: Session = Depends(get_db),
                  current_user: SysUser = Depends(get_current_user)):
    try:
        config = file_config_service.update_config(
            db, int(payload["id"]), payload, tenant_id=_tenant_id(current_user),
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ok(True)


@router.put("/update-master")
def set_master(id: int = Query(...), db: Session = Depends(get_db),
               current_user: SysUser = Depends(get_current_user)):
    try:
        file_config_service.set_master(db, id, tenant_id=_tenant_id(current_user))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ok(True)


@router.delete("/delete")
def delete_config(id: int = Query(...), db: Session = Depends(get_db),
                  current_user: SysUser = Depends(get_current_user)):
    try:
        file_config_service.delete_config(db, id, tenant_id=_tenant_id(current_user))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ok(True)


@router.delete("/delete-list")
def delete_config_list(ids: str = Query(...), db: Session = Depends(get_db),
                       current_user: SysUser = Depends(get_current_user)):
    try:
        for cid in [int(i) for i in ids.split(",") if i.strip()]:
            file_config_service.delete_config(db, cid, tenant_id=_tenant_id(current_user))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ok(True)


@router.get("/get")
def get_config(id: int = Query(...), db: Session = Depends(get_db),
               current_user: SysUser = Depends(get_current_user)):
    config = file_config_service.get_config(db, id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return _ok(_config_resp(config))


@router.get("/page")
def get_config_page(
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
    name: str = Query(""), code: str = Query(""), storage: int | None = Query(None),
    db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user),
):
    from sqlalchemy import func, or_, select
    from app.models.sys.sys_infra_file_config import SysInfraFileConfig

    stmt = select(SysInfraFileConfig).where(SysInfraFileConfig.deleted == "0")
    tenant_id = _tenant_id(current_user)
    if tenant_id not in (None, 0):
        # 普通租户：本租户 + 平台共享(NULL)；超管(tenant_id=0)看全部
        stmt = stmt.where(or_(
            SysInfraFileConfig.tenant_id == tenant_id,
            SysInfraFileConfig.tenant_id.is_(None),
        ))
    if name:
        stmt = stmt.where(SysInfraFileConfig.name.like(f"%{name}%"))
    if code:
        stmt = stmt.where(SysInfraFileConfig.code.like(f"%{code}%"))
    if storage is not None:
        stmt = stmt.where(SysInfraFileConfig.storage == storage)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar()
    rows = db.execute(
        stmt.order_by(SysInfraFileConfig.id).offset((page - 1) * pageSize).limit(pageSize)
    ).scalars().all()
    return _ok({"data": [_config_resp(r) for r in rows], "total": total,
                "page": page, "pageSize": pageSize})


@router.get("/test")
def test_config(id: int = Query(...), db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)):
    try:
        return _ok(file_config_service.test_config(db, id, tenant_id=_tenant_id(current_user)))
    except Exception as exc:  # noqa: BLE001 - 测试接口需把底层错误回传前端
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/statistics")
def get_statistics(db: Session = Depends(get_db),
                   current_user: SysUser = Depends(get_current_user)):
    return _ok(file_config_service.get_statistics(db, tenant_id=_tenant_id(current_user)))


@router.get("/export")
def export_configs(db: Session = Depends(get_db),
                   current_user: SysUser = Depends(get_current_user)):
    """导出配置为 JSON（敏感凭据明文，仅管理员使用；按租户范围导出）。"""
    from sqlalchemy import or_, select
    from app.models.sys.sys_infra_file_config import SysInfraFileConfig

    stmt = select(SysInfraFileConfig).where(SysInfraFileConfig.deleted == "0")
    tenant_id = _tenant_id(current_user)
    if tenant_id not in (None, 0):
        stmt = stmt.where(or_(
            SysInfraFileConfig.tenant_id == tenant_id,
            SysInfraFileConfig.tenant_id.is_(None),
        ))
    configs = db.execute(stmt).scalars().all()
    return _ok([_config_resp(c) for c in configs])


@router.post("/import")
def import_configs(payload: list[dict], db: Session = Depends(get_db),
                   current_user: SysUser = Depends(get_current_user)):
    created = []
    try:
        for item in payload:
            if file_config_service.get_config_by_code(db, item.get("code", "")):
                continue
            created.append(file_config_service.create_config(
                db, item, getattr(current_user, "username", None),
                tenant_id=_tenant_id(current_user),
            ).id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ok(created)
