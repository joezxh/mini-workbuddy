"""外部知识库连接器 REST 端点（P3，prefix /api/v1/connectors）。

安全约定（与 DataOps 一致）：
- 所有端点要求登录且用户有租户（400 tenant_required）；
- 数据访问按租户隔离，跨租户即 404；
- 同步开关仅更新标志位并落一条同步日志；真实「外部拉取 runner」属后续工作
  （见设计文档 §9），当前不实际拉取外部数据。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.connectors.connector_record import ConnectorInstance, ConnectorSyncLog
from app.models.sys.sys_user import SysUser

router = APIRouter(prefix="/api/v1/connectors", tags=["外部知识库连接器"])

TENANT_REQUIRED_DETAIL = "tenant_required"


def _require_tenant_id(current_user: SysUser) -> int:
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail=TENANT_REQUIRED_DETAIL)
    return tenant_id


# 声明式表单 schema：前端 getCreateParamsConfig() 返回 options 据此动态渲染表单。
CONNECTOR_PARAMS_CONFIG: Dict[str, List[Dict[str, Any]]] = {
    "notion": [
        {"key": "token", "label": "Integration Token", "type": "password", "required": True},
        {"key": "database_ids", "label": "Database IDs", "type": "text"},
    ],
    "confluence": [
        {"key": "base_url", "label": "Base URL", "type": "text", "required": True},
        {"key": "username", "label": "用户名", "type": "text"},
        {"key": "token", "label": "API Token", "type": "password", "required": True},
        {"key": "space_key", "label": "Space Key", "type": "text"},
    ],
    "web": [
        {"key": "base_url", "label": "站点 URL", "type": "text", "required": True},
        {"key": "selector", "label": "内容选择器", "type": "text"},
    ],
    "s3": [
        {"key": "bucket", "label": "Bucket", "type": "text", "required": True},
        {"key": "region", "label": "Region", "type": "text"},
        {"key": "access_key", "label": "Access Key", "type": "text"},
        {"key": "secret_key", "label": "Secret Key", "type": "password"},
    ],
}

_KNOWN_SCALARS = {"name", "connector_type", "sync_enabled", "kb_dataset", "sync_interval_min"}


# ── 请求体 ────────────────────────────────────────────────────────────────
class ConnectorCreate(BaseModel):
    name: str = Field(..., description="实例显示名")
    connector_type: str = Field(..., description="notion | confluence | web | s3")
    sync_enabled: bool = False
    kb_dataset: Optional[str] = None
    sync_interval_min: int = 60
    model_config = ConfigDict(extra="allow")  # 类型相关凭据（token 等）收入 config

    def config_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if k not in _KNOWN_SCALARS}


class ConnectorUpdate(BaseModel):
    name: Optional[str] = None
    connector_type: Optional[str] = None
    sync_enabled: Optional[bool] = None
    kb_dataset: Optional[str] = None
    sync_interval_min: Optional[int] = None
    model_config = ConfigDict(extra="allow")

    def config_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.model_dump(exclude_unset=True).items() if k not in _KNOWN_SCALARS}


class SyncToggle(BaseModel):
    enabled: bool = True


# ── 序列化 ────────────────────────────────────────────────────────────────
def _serialize_instance(row: ConnectorInstance) -> Dict[str, Any]:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "connector_type": row.connector_type,
        "sync_enabled": bool(row.sync_enabled),
        "kb_dataset": row.kb_dataset,
        "sync_interval_min": row.sync_interval_min,
        "status": row.status,
        "last_sync_at": row.last_sync_at.isoformat() if row.last_sync_at else None,
        "error_detail": row.error_detail,
    }


# ── 端点 ──────────────────────────────────────────────────────────────────
@router.get("")
def list_instances(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    tenant_id = _require_tenant_id(current_user)
    rows = db.execute(
        select(ConnectorInstance).where(ConnectorInstance.tenant_id == tenant_id)
    ).scalars().all()
    return [_serialize_instance(r) for r in rows]


@router.get("/params-config")
def get_params_config(type: str = "") -> Dict[str, Any]:
    """返回某类型的声明式表单 schema（options），前端据此动态渲染连接参数表单。"""
    return {"type": type, "options": CONNECTOR_PARAMS_CONFIG.get(type, [])}


@router.post("", status_code=201)
def create_instance(
    body: ConnectorCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _require_tenant_id(current_user)
    code = f"{body.connector_type}-{body.name}".lower().replace(" ", "-")
    inst = ConnectorInstance(
        tenant_id=tenant_id,
        code=code,
        name=body.name,
        connector_type=body.connector_type,
        config=body.config_dict(),
        sync_enabled=body.sync_enabled,
        kb_dataset=body.kb_dataset,
        sync_interval_min=body.sync_interval_min,
        status="active",
        creator_id=current_user.user_id,
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return _serialize_instance(inst)


@router.put("/{instance_id}")
def update_instance(
    instance_id: int,
    body: ConnectorUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _require_tenant_id(current_user)
    inst = db.get(ConnectorInstance, instance_id)
    if inst is None or inst.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="connector_not_found")
    if body.name is not None:
        inst.name = body.name
    if body.connector_type is not None:
        inst.connector_type = body.connector_type
    if body.sync_enabled is not None:
        inst.sync_enabled = body.sync_enabled
    if body.kb_dataset is not None:
        inst.kb_dataset = body.kb_dataset
    if body.sync_interval_min is not None:
        inst.sync_interval_min = body.sync_interval_min
    extra = body.config_dict()
    if extra:
        merged = dict(inst.config or {})
        merged.update(extra)
        inst.config = merged
    inst.updater_id = current_user.user_id
    db.commit()
    db.refresh(inst)
    return _serialize_instance(inst)


@router.delete("/{instance_id}")
def delete_instance(
    instance_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _require_tenant_id(current_user)
    inst = db.get(ConnectorInstance, instance_id)
    if inst is None or inst.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="connector_not_found")
    db.query(ConnectorSyncLog).filter(
        ConnectorSyncLog.tenant_id == tenant_id,
        ConnectorSyncLog.instance_id == instance_id,
    ).delete(synchronize_session=False)
    db.delete(inst)
    db.commit()
    return {"deleted": instance_id}


@router.post("/{instance_id}/sync")
def set_sync(
    instance_id: int,
    body: SyncToggle,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """切换同步开关。启用时落一条同步日志（当前不实际拉取外部数据，runner 待后续接入）。"""
    tenant_id = _require_tenant_id(current_user)
    inst = db.get(ConnectorInstance, instance_id)
    if inst is None or inst.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="connector_not_found")
    inst.sync_enabled = body.enabled
    from datetime import datetime
    now = datetime.utcnow()
    inst.last_sync_at = now
    if not body.enabled:
        inst.status = "active"
        inst.error_detail = None
    log = ConnectorSyncLog(
        tenant_id=tenant_id,
        instance_id=instance_id,
        connector_type=inst.connector_type,
        status="success" if body.enabled else "disabled",
        added=0,
        updated=0,
        deleted=0,
        error_detail=(
            "连接器已启用；外部拉取 runner 尚未接入（设计文档 §9），本次仅记录启用事件。"
            if body.enabled else None
        ),
        started_at=now,
        finished_at=now,
        creator_id=current_user.user_id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return {"instance_id": instance_id, "sync_enabled": bool(inst.sync_enabled), "job_id": log.id}


@router.get("/sync-jobs")
def list_sync_jobs(
    instance_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    tenant_id = _require_tenant_id(current_user)
    stmt = select(ConnectorSyncLog).where(ConnectorSyncLog.tenant_id == tenant_id)
    if instance_id is not None:
        stmt = stmt.where(ConnectorSyncLog.instance_id == instance_id)
    logs = db.execute(stmt).scalars().all()
    names = {
        r.id: r.name
        for r in db.execute(
            select(ConnectorInstance).where(ConnectorInstance.tenant_id == tenant_id)
        ).scalars().all()
    }
    return [
        {
            "id": log.id,
            "instance_id": log.instance_id,
            "instance_name": names.get(log.instance_id, str(log.instance_id)),
            "status": log.status,
            "added": log.added,
            "updated": log.updated,
            "deleted": log.deleted,
            "duration_ms": log.duration_ms,
            "error_detail": log.error_detail,
            "started_at": log.started_at.isoformat() if log.started_at else None,
            "finished_at": log.finished_at.isoformat() if log.finished_at else None,
        }
        for log in logs
    ]
