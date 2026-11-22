"""ArtifactStore —— 技能执行产物文件管理（统一文件存储版）。

职责：
1. 为每次执行分配 run_dir（历史磁盘产物仍可扫描）
2. 新产物经 file_service 写入统一存储（DB/LOCAL/S3 可插拔），file_id = ``file://<id>``
3. 提供产物元数据列表与下载路径

历史磁盘产物（file_id = ``{execution_id}/{filename}``）继续支持，平滑兼容。
"""
from __future__ import annotations

import logging
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 历史产物根目录：backend/data/runs/（新产物不再写此处，仅用于读取历史数据）
_RUNS_BASE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "runs"
_FILE_URI_PREFIX = "file://"


@dataclass
class ArtifactInfo:
    """产物文件元数据"""
    file_id: str          # file://<id>（新）或 {execution_id}/{filename}（历史）
    filename: str
    file_path: str
    size_bytes: int
    mime_type: str
    execution_id: str


def get_run_dir(execution_id: str) -> Path:
    """获取（或创建）指定执行的产物目录（历史磁盘产物兼容）。"""
    run_dir = _RUNS_BASE / execution_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save_artifact(execution_id: str, filename: str, content: bytes, db=None) -> ArtifactInfo:
    """写入产物到统一文件存储，返回元数据（file_id = file://<id>）。"""
    from app.db.database import SessionLocal
    from app.services.file import file_service

    own = db is None
    session = db or SessionLocal()
    try:
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        record = file_service.create_file(
            session, content, filename, directory=f"artifacts/{execution_id}",
            code="other", mime=mime, tenant_id=None,
        )
        return ArtifactInfo(
            file_id=f"{_FILE_URI_PREFIX}{record.id}", filename=filename,
            file_path=record.path, size_bytes=len(content),
            mime_type=record.type or mime, execution_id=execution_id,
        )
    finally:
        if own:
            session.close()


def scan_artifacts(execution_id: str, db=None) -> list[ArtifactInfo]:
    """扫描产物：统一存储记录 + 历史磁盘文件。"""
    artifacts: list[ArtifactInfo] = []
    if db is not None:
        from sqlalchemy import select
        from app.models.sys.sys_infra_file import SysInfraFile as _F
        for r in db.execute(
            select(_F).where(
                _F.path.like(f"artifacts/{execution_id}/%"), _F.deleted == "0",
            )
        ).scalars().all():
            artifacts.append(ArtifactInfo(
                file_id=f"{_FILE_URI_PREFIX}{r.id}", filename=r.name or r.path.split("/")[-1],
                file_path=r.path, size_bytes=r.size or 0,
                mime_type=r.type or "application/octet-stream", execution_id=execution_id,
            ))
    return artifacts + _scan_disk_artifacts(execution_id)


def _scan_disk_artifacts(execution_id: str) -> list[ArtifactInfo]:
    """历史磁盘产物扫描（新产物不使用）。"""
    run_dir = _RUNS_BASE / execution_id
    if not run_dir.exists():
        return []
    artifacts: list[ArtifactInfo] = []
    for entry in sorted(run_dir.rglob("*")):
        if not entry.is_file() or entry.name.startswith("."):
            continue
        rel_path = entry.relative_to(run_dir)
        artifacts.append(ArtifactInfo(
            file_id=f"{execution_id}/{rel_path.as_posix()}", filename=entry.name,
            file_path=str(entry.resolve()), size_bytes=entry.stat().st_size,
            mime_type=mimetypes.guess_type(entry.name)[0] or "application/octet-stream",
            execution_id=execution_id,
        ))
    return artifacts


def get_artifact_path(file_id: str) -> Optional[Path]:
    """历史磁盘产物的路径解析（新 file:// 产物请用 file_service）。"""
    if file_id.startswith(_FILE_URI_PREFIX):
        return None
    parts = file_id.split("/", 1)
    if len(parts) != 2:
        return None
    execution_id, rel_path = parts
    if ".." in rel_path or rel_path.startswith("/"):
        logger.warning("path traversal blocked: %s", file_id)
        return None
    file_path = _RUNS_BASE / execution_id / rel_path
    if file_path.exists() and file_path.is_file():
        return file_path
    return None
