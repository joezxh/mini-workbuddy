"""外部知识库连接器 REST 端点（P3，prefix /api/v1/connectors）。

安全约定（与 DataOps 一致）：
- 所有端点要求登录且用户有租户（400 tenant_required）；
- 数据访问按租户隔离，跨租户即 404；
- 敏感配置（token/secret）经 DataOps crypto 惯例加密后落库，响应不回显。

2026-09-27 统一化（spec §3.4 / §3.5）：
- 实例层落表 ``kms_connector_instance``、作业日志落 ``kms_connector_sync_log``；
- ``connector_type`` 以 ``app/connectors/registry.py`` 四类（http/dingtalk/feishu/wecom）
  为唯一事实源，notion/confluence/web/s3 仅作**声明式表单别名**，提交时映射为 registry 类型；
- ``POST /{id}/sync`` 真实调用 ``app.connectors.runner.run_connector``，日志状态反映真实结果。
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.connectors.connector_record import (
    ConnectorInstance,
    ConnectorSyncLog,
    ConnectorSyncState,
)
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

# 别名 → registry 枚举 + 配置适配（spec §3.4）：表单按外部产品语义渲染，落库恒为 registry 类型
_ALIAS_MAP: Dict[str, Tuple[str, Dict[str, str]]] = {
    # alias: (registry_type, {外部表单字段 → ConnectorConfig 字段})
    "notion": ("http", {"base_url": "https://api.notion.com/v1", "token": "auth_token"}),
    "confluence": ("http", {"base_url": "base_url", "token": "auth_token"}),
    "web": ("http", {"base_url": "base_url"}),
    "s3": ("http", {}),
}

_REGISTRY_TYPES = {"http", "dingtalk", "feishu", "wecom"}

# 敏感字段：落库前加密、响应前剔除
_SECRET_KEYS = {"token", "auth_token", "secret_key", "access_key", "client_secret", "password"}

_KNOWN_SCALARS = {"name", "connector_type", "sync_enabled", "kb_dataset", "sync_interval_min"}


def _encrypt_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """敏感字段加密（沿用 DataOps crypto 惯例）；无 crypto 依赖时原样透传。"""
    try:
        from app.services.dataops.crypto import encrypt_value  # type: ignore
    except Exception:  # noqa: BLE001 - 降级：不阻断创建
        return config
    out = dict(config or {})
    for key in list(out):
        if key in _SECRET_KEYS and isinstance(out[key], str) and out[key]:
            try:
                out[key] = encrypt_value(out[key])
            except Exception:  # noqa: BLE001
                continue
    return out


def _mask_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """响应前剔除敏感字段值（仅回显是否存在）。"""
    out: Dict[str, Any] = {}
    for key, value in (config or {}).items():
        out[key] = "***" if key in _SECRET_KEYS else value
    return out


def _resolve_registry_type(connector_type: str, config: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """把声明式别名解析为 registry 枚举类型 + 适配后的配置。

    :raises HTTPException: 既非 registry 类型也非已知别名
    """
    ctype = (connector_type or "").lower().strip()
    if ctype in _REGISTRY_TYPES:
        return ctype, dict(config or {})
    alias = _ALIAS_MAP.get(ctype)
    if alias is None:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的连接器类型 {connector_type!r}；registry 支持：{', '.join(sorted(_REGISTRY_TYPES))}",
        )
    registry_type, field_map = alias
    merged = dict(config or {})
    for target, source in field_map.items():
        # 值为常量（如 notion 的固定 base_url）时直接采用，否则取表单同名值
        value = source if source.startswith("http") or "/" in source else merged.pop(source, None)
        if value is not None:
            merged[target] = value
    return registry_type, merged


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
    """序列化实例。

    API 字段名沿用前端契约 ``kb_dataset``（= 模型列 target_collection → kb_collection.name），
    config 中的敏感字段只回显掩码。
    """
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "connector_type": row.connector_type,
        "sync_enabled": bool(row.sync_enabled),
        "kb_dataset": row.target_collection,
        "sync_interval_min": row.sync_interval_min,
        "status": row.status,
        "config": _mask_config(row.config),
        "knowledge_id": row.knowledge_id,
        "last_sync_at": row.last_sync_at.isoformat() if row.last_sync_at else None,
        "error_detail": row.error_detail,
    }


def _last_cursor(db: Session, tenant_id: int, connector_type: str) -> Optional[str]:
    """取该租户+类型最近落库的增量游标（供日志留痕）。"""
    row = db.execute(
        select(ConnectorSyncState).where(
            ConnectorSyncState.tenant_id == tenant_id,
            ConnectorSyncState.connector_type == connector_type,
        )
    ).scalar_one_or_none()
    return row.last_cursor if row else None


def _run_sync(inst: ConnectorInstance, tenant_id: int, db: Session):
    """真实执行一次连接器拉取落库（runner 为协程，此处在同步上下文中驱动）。

    :raises ValueError: 连接器类型未注册或配置不合法
    """
    from app.connectors.base import ConnectorConfig
    from app.connectors.runner import run_connector

    raw = dict(inst.config or {})
    # 加密字段需解密后才能用于真实请求（未加密时原样透传）
    try:
        from app.services.dataops.crypto import decrypt_value  # type: ignore

        for key in list(raw):
            if key in _SECRET_KEYS and isinstance(raw[key], str) and raw[key]:
                try:
                    raw[key] = decrypt_value(raw[key])
                except Exception:  # noqa: BLE001 - 解密失败按原值处理
                    continue
    except Exception:  # noqa: BLE001
        pass

    base_url = raw.pop("base_url", None) or ""
    if not base_url:
        raise ValueError("缺少 base_url，无法执行同步（请先在实例配置中填写连接地址）")
    config = ConnectorConfig(base_url=base_url, **{
        k: v for k, v in raw.items() if k in ConnectorConfig.model_fields
    })
    return asyncio.run(run_connector(inst.connector_type, config, db, tenant_id))


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
    raw_config = body.config_dict()
    registry_type, adapted = _resolve_registry_type(body.connector_type, raw_config)
    code = f"{body.connector_type}-{body.name}".lower().replace(" ", "-")
    inst = ConnectorInstance(
        tenant_id=tenant_id,
        code=code,
        name=body.name,
        connector_type=registry_type,
        config=_encrypt_config(adapted),
        sync_enabled=body.sync_enabled,
        target_collection=body.kb_dataset,
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
        inst.connector_type, _ = _resolve_registry_type(body.connector_type, {})
    if body.sync_enabled is not None:
        inst.sync_enabled = body.sync_enabled
    if body.kb_dataset is not None:
        inst.target_collection = body.kb_dataset
    if body.sync_interval_min is not None:
        inst.sync_interval_min = body.sync_interval_min
    extra = body.config_dict()
    if extra:
        merged = dict(inst.config or {})
        merged.update(_encrypt_config(extra))
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
    """切换同步开关；启用时**真实执行一次拉取**（spec §3.5），日志状态反映真实结果。

    状态约定：
    - 关闭开关：只改标志位，不落作业日志；
    - 开启开关：落一条 pending 日志 → 调 runner → 回填 success/failed 与条数/耗时。
    """
    tenant_id = _require_tenant_id(current_user)
    inst = db.get(ConnectorInstance, instance_id)
    if inst is None or inst.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="connector_not_found")

    inst.sync_enabled = body.enabled
    if not body.enabled:
        inst.status = "active"
        inst.error_detail = None
        db.commit()
        return {"instance_id": instance_id, "sync_enabled": False, "job_id": None}

    started = datetime.utcnow()
    log = ConnectorSyncLog(
        tenant_id=tenant_id,
        instance_id=instance_id,
        connector_type=inst.connector_type,
        status="running",
        started_at=started,
        creator_id=current_user.user_id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    try:
        result = _run_sync(inst, tenant_id, db)
    except Exception as exc:  # noqa: BLE001 - 同步失败需落 failed 而非 500
        result = None
        error = str(exc)
    else:
        error = None

    finished = datetime.utcnow()
    log.finished_at = finished
    log.duration_ms = int((finished - started).total_seconds() * 1000)
    if error is not None:
        log.status = "failed"
        log.error_detail = error
        inst.status = "error"
        inst.error_detail = error
    else:
        written = int(getattr(result, "written", 0) or 0)
        log.status = "success"
        log.added = written
        log.cursor_value = _last_cursor(db, tenant_id, inst.connector_type)
        inst.status = "active"
        inst.error_detail = None
    inst.last_sync_at = finished
    db.commit()
    db.refresh(log)

    return {
        "instance_id": instance_id,
        "sync_enabled": True,
        "job_id": log.id,
        "status": log.status,
        "added": log.added,
        "error_detail": log.error_detail,
    }


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
