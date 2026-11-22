"""文件服务：上传（后端/预签名）、下载、分页、目录树、删除、统计。

租户隔离约定：
- 写入：tenant_id 必填（路由层取当前登录用户租户），超管(tenant_id=0)写 None 表示平台级。
- 检索：超管看全部；普通租户仅可见「本租户 + 平台共享(tenant_id IS NULL)」。
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import unquote

from loguru import logger
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.framework.file.enums import MASTER_CODE
from app.framework.file.utils import (
    detect_mime, format_file_url, generate_path, generate_upload_path, normalize_dir, strip_query,
)
from app.models.sys.sys_infra_file import SysInfraFile
from app.services.file import file_config_service

SUPER_TENANT_ID = 0


def _tenant_filter(model, tenant_id: int | None):
    """非超管租户检索条件：本租户 + 平台共享(NULL)。tenant_id=0(超管) 返回 None 不过滤。"""
    if tenant_id is None or tenant_id == SUPER_TENANT_ID:
        return None
    return or_(model.tenant_id == tenant_id, model.tenant_id.is_(None))


def create_file(
    db: Session,
    content: bytes,
    filename: str,
    directory: str | None = None,
    code: str | None = None,
    mime: str | None = None,
    creator: str | None = None,
    tenant_id: int | None = None,
) -> SysInfraFile:
    """后端上传：内容寻址路径 + 按 code 选存储 + 写元数据（与 Java createFileDO 对齐）。"""
    config, client = file_config_service.get_file_client(db, code)
    path = generate_path(content, filename, directory)
    mime_type = detect_mime(content, filename, mime)
    # 先推断 MIME 再上传：S3 对象需带 ContentType，否则浏览器预览/内嵌展示退化为下载
    url = client.upload(content, path, db, content_type=mime_type)
    record = SysInfraFile(
        config_id=config.id, name=filename or "unnamed", path=path, url=url,
        type=mime_type, size=len(content), creator=creator, tenant_id=tenant_id, deleted="0",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def create_file_declared(db: Session, data: dict, tenant_id: int | None = None) -> SysInfraFile:
    """预签名直传后落元数据（Java createFile(FileCreateReqVO) 等价）。"""
    config_id = data.get("configId")
    if config_id is None:
        config = file_config_service.get_master_config(db)
        config_id = config.id
    record = SysInfraFile(
        config_id=config_id, path=data["path"], name=data.get("name") or data["path"].split("/")[-1],
        url=strip_query(data.get("url")), type=data.get("type"), size=int(data.get("size") or 0),
        tenant_id=tenant_id, deleted="0",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def presign_put_url(db: Session, name: str, directory: str | None = None, code: str | None = None) -> dict:
    """生成上传路径与预签名 URL；不落库，上传完成后调用 create_file_declared 登记。"""
    config, client = file_config_service.get_file_client(db, code)
    path = generate_upload_path(name, directory)
    upload_url = client.presign_put_url(path)
    return {
        "configId": config.id, "path": path,
        "uploadUrl": upload_url, "url": client.format_url(path),
    }


def get_file(db: Session, file_id: int, tenant_id: int | None = None) -> Optional[SysInfraFile]:
    stmt = select(SysInfraFile).where(SysInfraFile.id == file_id, SysInfraFile.deleted == "0")
    scope = _tenant_filter(SysInfraFile, tenant_id)
    if scope is not None:
        stmt = stmt.where(scope)
    return db.execute(stmt).scalars().first()


def get_file_content(db: Session, config_id: int, path: str) -> Optional[bytes]:
    """按 configId + path 读内容；仅 DB 有记录的路径放行（防伪造穿越）。"""
    exists = db.execute(
        select(SysInfraFile.id).where(
            SysInfraFile.config_id == config_id, SysInfraFile.path == path, SysInfraFile.deleted == "0",
        ).limit(1)
    ).scalar()
    if exists is None:
        return None
    return file_config_service.get_client_by_config_id(db, config_id).get_content(path, db)


def delete_file(db: Session, file_id: int, tenant_id: int | None = None) -> bool:
    record = get_file(db, file_id, tenant_id)
    if record is None:
        return False
    try:
        client = file_config_service.get_client_by_config_id(db, record.config_id)
        client.delete(record.path, db)
    except Exception as exc:  # noqa: BLE001 - 物理删除失败不阻断元数据清理
        logger.warning(f"[文件存储] 物理删除失败 file_id={file_id}: {exc}")
    record.deleted = "1"
    db.commit()
    return True


def delete_file_list(db: Session, file_ids: list[int], tenant_id: int | None = None) -> int:
    count = 0
    for fid in file_ids:
        if delete_file(db, fid, tenant_id):
            count += 1
    return count


def get_file_page(
    db: Session, page: int, page_size: int, config_id: Optional[int] = None,
    path: Optional[str] = None, type_: Optional[str] = None,
    tenant_id: int | None = None,
) -> dict:
    stmt = select(SysInfraFile).where(SysInfraFile.deleted == "0")
    scope = _tenant_filter(SysInfraFile, tenant_id)
    if scope is not None:
        stmt = stmt.where(scope)
    if config_id is not None:
        stmt = stmt.where(SysInfraFile.config_id == config_id)
    if path:
        stmt = stmt.where(SysInfraFile.path.like(f"{normalize_dir(path)}%"))
    if type_:
        stmt = stmt.where(SysInfraFile.type.like(f"%{type_}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar()
    rows = db.execute(
        stmt.order_by(SysInfraFile.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return {
        "data": [_serialize(r) for r in rows], "total": total, "page": page, "pageSize": page_size,
    }


def _serialize(r: SysInfraFile) -> dict:
    return {
        "id": r.id, "configId": r.config_id, "path": r.path, "name": r.name,
        "url": r.url, "type": r.type, "size": r.size or 0,
        "createTime": r.create_time.isoformat() if r.create_time else None,
    }


def get_directories(db: Session, tenant_id: int | None = None) -> list[dict]:
    """基于文件 path 逐层切分构建目录树（与 Java getDirectories 一致）。"""
    stmt = select(SysInfraFile.path).where(SysInfraFile.deleted == "0")
    scope = _tenant_filter(SysInfraFile, tenant_id)
    if scope is not None:
        stmt = stmt.where(scope)
    paths = db.execute(stmt).scalars().all()
    root: dict = {"dirs": {}, "files": 0}
    for path in paths:
        parts = [p for p in str(path).split("/") if p]
        cursor = root
        for part in parts[:-1]:
            cursor = cursor["dirs"].setdefault(part, {"dirs": {}, "files": 0})
        cursor["files"] += 1

    def build(node: dict, prefix: str) -> list[dict]:
        # node 必须是含 "dirs" 键的节点字典；子节点 child 同样是节点字典，直接递归传入。
        return [
            {
                "name": name,
                "path": f"{prefix}/{name}" if prefix else name,
                "hasChildren": bool(child["dirs"]),
                "children": build(child, f"{prefix}/{name}" if prefix else name),
            }
            for name, child in sorted(node["dirs"].items())
        ]

    return build(root, "")


def get_statistics(db: Session, tenant_id: int | None = None) -> list[dict]:
    return file_config_service.get_statistics(db, tenant_id)
