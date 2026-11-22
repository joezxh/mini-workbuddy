"""文件存储配置服务：CRUD / 设主 / 测试 / 统计 / 按 code 取客户端。

租户隔离约定（与 file_service 一致）：
- 创建：普通租户配置落本人租户；超管(tenant_id=0)创建平台共享配置(tenant_id=NULL)。
- 检索（管理界面）：超管看全部；普通租户可见「本租户 + 平台共享(NULL)」。
- 变更（update/delete/set_master/test）：超管或配置属主可操作。
- 注意：get_config / get_config_by_code / get_master_config 为内部选客户端使用，
  不做租户过滤（存储客户端是平台级资源）。
"""
from __future__ import annotations

from typing import Optional

from loguru import logger
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.framework.file.client.base import FileClient
from app.framework.file.client.factory import FileClientFactory
from app.framework.file.enums import MASTER_CODE, FileStorageEnum
from app.models.sys.sys_infra_file import SysInfraFile
from app.models.sys.sys_infra_file_config import SysInfraFileConfig

SUPER_TENANT_ID = 0


def _tenant_scope(tenant_id: int | None):
    """管理界面配置列表过滤条件；超管返回 None（不过滤）。"""
    if tenant_id is None or tenant_id == SUPER_TENANT_ID:
        return None
    return or_(SysInfraFileConfig.tenant_id == tenant_id, SysInfraFileConfig.tenant_id.is_(None))


def _check_owner(config: SysInfraFileConfig, tenant_id: int | None) -> None:
    """变更操作归属校验：超管放行；平台共享配置(NULL)仅超管可改。"""
    if tenant_id is None or tenant_id == SUPER_TENANT_ID:
        return
    if config.tenant_id is None or config.tenant_id != tenant_id:
        raise ValueError("无权操作该存储配置")


def get_config(db: Session, config_id: int) -> Optional[SysInfraFileConfig]:
    return db.execute(
        select(SysInfraFileConfig).where(
            SysInfraFileConfig.id == config_id, SysInfraFileConfig.deleted == "0",
        )
    ).scalars().first()


def get_config_by_code(db: Session, code: str) -> Optional[SysInfraFileConfig]:
    return db.execute(
        select(SysInfraFileConfig).where(
            SysInfraFileConfig.code == code, SysInfraFileConfig.deleted == "0",
        )
    ).scalars().first()


def get_master_config(db: Session) -> SysInfraFileConfig:
    config = db.execute(
        select(SysInfraFileConfig).where(
            SysInfraFileConfig.is_master.is_(True), SysInfraFileConfig.deleted == "0",
        )
    ).scalars().first()
    if config is None:
        config = get_config_by_code(db, MASTER_CODE)
    if config is None:
        raise ValueError("未配置文件存储主配置，请先在「文件管理 → 存储配置」中创建")
    return config


def get_file_client(db: Session, code: Optional[str] = None) -> tuple[SysInfraFileConfig, FileClient]:
    """按 code 取客户端；code 为空或 master 走主配置。"""
    if not code or code == MASTER_CODE:
        config = get_master_config(db)
    else:
        config = get_config_by_code(db, code) or get_master_config(db)
    return config, FileClientFactory.get_client(config, code)


def get_client_by_config_id(db: Session, config_id: int) -> FileClient:
    config = get_config(db, config_id)
    if config is None:
        raise ValueError(f"文件存储配置 {config_id} 不存在")
    return FileClientFactory.get_client(config)


def create_config(
    db: Session, data: dict, creator: str | None = None, tenant_id: int | None = None,
) -> SysInfraFileConfig:
    storage = int(data["storage"])
    if not FileStorageEnum.is_supported(storage):
        raise ValueError(f"存储类型 {storage} 本期未实现（支持 DB/LOCAL/S3）")
    if get_config_by_code(db, data["code"]):
        raise ValueError(f"存储配置 code 已存在: {data['code']}")
    # 租户归属：超管(tenant_id=0)创建平台共享配置(NULL)，普通租户落本人租户
    owner_tenant = None if (tenant_id is None or tenant_id == SUPER_TENANT_ID) else tenant_id
    config = SysInfraFileConfig(
        name=data["name"], code=data["code"], storage=storage,
        config=data.get("config") or {}, remark=data.get("remark"),
        is_master=False, creator=creator, tenant_id=owner_tenant, deleted="0",
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    logger.info(f"[文件存储] 创建配置 id={config.id} code={config.code} storage={storage}")
    return config


def update_config(db: Session, config_id: int, data: dict, tenant_id: int | None = None) -> SysInfraFileConfig:
    config = get_config(db, config_id)
    if config is None:
        raise ValueError(f"文件存储配置 {config_id} 不存在")
    _check_owner(config, tenant_id)
    storage = int(data.get("storage", config.storage))
    if not FileStorageEnum.is_supported(storage):
        raise ValueError(f"存储类型 {storage} 本期未实现")
    config.name = data.get("name", config.name)
    config.code = data.get("code", config.code)
    config.storage = storage
    config.config = data.get("config", config.config)
    config.remark = data.get("remark", config.remark)
    db.commit()
    db.refresh(config)
    FileClientFactory.invalidate(config_id=config.id)
    FileClientFactory.invalidate(code=config.code)
    return config


def set_master(db: Session, config_id: int, tenant_id: int | None = None) -> None:
    config = get_config(db, config_id)
    if config is None:
        raise ValueError(f"文件存储配置 {config_id} 不存在")
    _check_owner(config, tenant_id)
    for row in db.execute(select(SysInfraFileConfig).where(SysInfraFileConfig.deleted == "0")).scalars().all():
        row.is_master = row.id == config_id
    db.commit()
    FileClientFactory.invalidate()


def delete_config(db: Session, config_id: int, tenant_id: int | None = None) -> None:
    config = get_config(db, config_id)
    if config is None:
        return
    _check_owner(config, tenant_id)
    if config.is_master:
        raise ValueError("主配置禁止删除")
    used = db.execute(
        select(func.count()).select_from(SysInfraFile).where(
            SysInfraFile.config_id == config_id, SysInfraFile.deleted == "0",
        )
    ).scalar()
    if used:
        raise ValueError(f"该配置下仍有 {used} 个文件，禁止删除")
    config.deleted = "1"
    db.commit()
    FileClientFactory.invalidate(code=config.code)
    FileClientFactory.invalidate(config_id=config.id)


def test_config(db: Session, config_id: int, tenant_id: int | None = None) -> str:
    config = get_config(db, config_id)
    if config is None:
        raise ValueError("配置不存在")
    _check_owner(config, tenant_id)
    client = FileClientFactory.get_client(config)
    test_fn = getattr(client, "test", None)
    if callable(test_fn):
        return test_fn()
    # DB/LOCAL：写入一个探针文件后删除，验证真实可用
    from app.framework.file.utils import generate_path
    path = generate_path(b"minworkbuddy-file-storage-probe", "probe.txt", "file-config-test")
    client.upload(b"minworkbuddy-file-storage-probe", path, db)
    db.commit()
    client.delete(path, db)
    db.commit()
    return client.format_url(path)


def ensure_default_config(db: Session) -> None:
    """启动期幂等播种：无配置时创建默认 LOCAL 主存储（code=master）。"""
    from app.config import settings

    if db.execute(select(SysInfraFileConfig.id).limit(1)).scalar() is not None:
        return
    config = SysInfraFileConfig(
        name="默认本地存储", code="master", storage=int(FileStorageEnum.LOCAL),
        config={"basePath": str(settings.FILE_STORAGE_DIR), "domain": ""},
        remark="系统默认主存储（ LOCAL ）", is_master=True, deleted="0",
    )
    db.add(config)
    db.commit()
    logger.info(f"[文件存储] 已播种默认主配置 LOCAL basePath={settings.FILE_STORAGE_DIR}")


def get_statistics(db: Session, tenant_id: int | None = None) -> list[dict]:
    cfg_stmt = select(SysInfraFileConfig).where(SysInfraFileConfig.deleted == "0")
    scope = _tenant_scope(tenant_id)
    if scope is not None:
        cfg_stmt = cfg_stmt.where(scope)
    configs = db.execute(cfg_stmt.order_by(SysInfraFileConfig.id)).scalars().all()

    file_stmt = (
        select(SysInfraFile.config_id, func.count(SysInfraFile.id), func.coalesce(func.sum(SysInfraFile.size), 0))
        .where(SysInfraFile.deleted == "0")
        .group_by(SysInfraFile.config_id)
    )
    file_scope = or_(SysInfraFile.tenant_id == tenant_id, SysInfraFile.tenant_id.is_(None)) \
        if tenant_id not in (None, SUPER_TENANT_ID) else None
    if file_scope is not None:
        file_stmt = file_stmt.where(file_scope)
    rows = db.execute(file_stmt).all()
    stats = {r[0]: (r[1], r[2]) for r in rows}
    return [
        {
            "configId": c.id, "configName": c.name, "storageType": c.storage,
            "fileCount": stats.get(c.id, (0, 0))[0], "totalSize": int(stats.get(c.id, (0, 0))[1]),
            "storage": c.storage,
        }
        for c in configs
    ]
