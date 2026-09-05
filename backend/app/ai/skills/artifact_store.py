"""ArtifactStore —— 技能执行产物文件管理。

职责：
1. 为每次执行分配 run_dir（{SKILLS_BASE}/../runs/{execution_id}/）
2. 扫描 run_dir 下的产物文件
3. 提供文件下载路径

不持久化文件本身到 DB——文件在磁盘，DB 只记录元数据（通过 ARTIFACT 事件）。
"""
from __future__ import annotations

import logging
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 产物根目录：backend/data/runs/
_RUNS_BASE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "runs"


@dataclass
class ArtifactInfo:
    """产物文件元数据"""
    file_id: str          # 形如 "{execution_id}/{filename}"
    filename: str
    file_path: str        # 磁盘绝对路径
    size_bytes: int
    mime_type: str
    execution_id: str


def get_run_dir(execution_id: str) -> Path:
    """获取（或创建）指定执行的产物目录"""
    run_dir = _RUNS_BASE / execution_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def scan_artifacts(execution_id: str) -> list[ArtifactInfo]:
    """扫描 run_dir 下的所有产物文件，返回元数据列表。

    跳过空目录和隐藏文件。
    """
    run_dir = _RUNS_BASE / execution_id
    if not run_dir.exists():
        return []

    artifacts: list[ArtifactInfo] = []
    for entry in sorted(run_dir.rglob("*")):
        if not entry.is_file():
            continue
        if entry.name.startswith("."):
            continue
        rel_path = entry.relative_to(run_dir)
        file_id = f"{execution_id}/{rel_path.as_posix()}"
        mime_type = mimetypes.guess_type(entry.name)[0] or "application/octet-stream"
        artifacts.append(ArtifactInfo(
            file_id=file_id,
            filename=entry.name,
            file_path=str(entry.resolve()),
            size_bytes=entry.stat().st_size,
            mime_type=mime_type,
            execution_id=execution_id,
        ))
    return artifacts


def get_artifact_path(file_id: str) -> Optional[Path]:
    """根据 file_id 返回磁盘路径（用于 FileResponse 下载）。

    file_id 格式: {execution_id}/{relative_path}
    """
    parts = file_id.split("/", 1)
    if len(parts) != 2:
        return None
    execution_id, rel_path = parts
    # 防止路径穿越
    if ".." in rel_path or rel_path.startswith("/"):
        logger.warning("path traversal blocked: %s", file_id)
        return None
    file_path = _RUNS_BASE / execution_id / rel_path
    if file_path.exists() and file_path.is_file():
        return file_path
    return None
