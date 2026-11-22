"""压缩包异步解压服务：zip/7z 上传→任务→逐条入库→进度轮询/取消。

对齐 Java ArchiveExtractServiceImpl + ArchiveExtractTaskRunner：
- 任务状态存 Redis（不可用时回退内存），TTL 30 分钟
- 状态 0 等待 / 1 解压中 / 2 完成 / 3 部分完成 / 4 失败 / 5 已取消
- 安全过滤：路径穿越、隐藏系统文件、目录/软链、加密包
- 限额：条目数、单条大小、总量、压缩比、超时
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
import uuid
import zipfile
from pathlib import Path

from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.core.job_runner import run_in_background
from app.db.database import SessionLocal
from app.services.file import file_service

SUPPORTED_FORMATS = {"zip", "7z"}
_IGNORED_NAMES = {"__macosx", ".ds_store", "thumbs.db"}
_IGNORED_PREFIXES = ("~$",)

# 状态常量
PENDING, PROCESSING, SUCCESS, PARTIAL, FAILED, CANCELED = 0, 1, 2, 3, 4, 5
_TERMINAL = {SUCCESS, PARTIAL, FAILED, CANCELED}

_PREFIX = "archive_task:"


class _ArchiveTaskStore:
    """任务存储：Redis 优先，内存回退（沿用 task_progress 范式）。"""

    def __init__(self) -> None:
        self._memory: dict[str, tuple[float, dict]] = {}
        self._lock = threading.RLock()
        self._redis = None
        try:
            import redis
            if settings.REDIS_HOST:
                self._redis = redis.from_url(settings.REDIS_URL)
                self._redis.ping()
        except Exception:  # noqa: BLE001 - Redis 不可用时回退内存
            self._redis = None

    def get(self, task_id: str) -> dict | None:
        try:
            if self._redis:
                raw = self._redis.get(_PREFIX + task_id)
                return json.loads(raw) if raw else None
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[压缩包] Redis 读取失败，回退内存: {exc}")
        with self._lock:
            entry = self._memory.get(task_id)
            if not entry:
                return None
            if entry[0] < time.time():
                self._memory.pop(task_id, None)
                return None
            return entry[1]

    def set(self, task_id: str, task: dict) -> None:
        ttl = int(getattr(settings, "FILE_ARCHIVE_TASK_TTL_MINUTES", 30)) * 60
        try:
            if self._redis:
                self._redis.set(_PREFIX + task_id, json.dumps(task, ensure_ascii=False), ex=ttl)
                return
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[压缩包] Redis 写入失败，回退内存: {exc}")
        with self._lock:
            self._memory[task_id] = (time.time() + ttl, task)


_store = _ArchiveTaskStore()


def _is_ignored(name: str) -> bool:
    lower = name.lower()
    return (lower in _IGNORED_NAMES or lower.startswith(_IGNORED_PREFIXES)
            or any(seg.lower() in _IGNORED_NAMES for seg in name.replace("\\", "/").split("/")))


def _safe_rel_path(name: str) -> str | None:
    normalized = name.replace("\\", "/").lstrip("/")
    raw_parts = [p for p in normalized.split("/") if p]
    if not raw_parts or ".." in raw_parts:
        return None
    parts = [p for p in raw_parts if p != "."]
    return "/".join(parts) if parts else None


def create_archive_task(
    db: Session, content: bytes, archive_name: str,
    directory: str | None = None, code: str | None = None, user_id: int | None = None,
    tenant_id: int | None = None, creator: str | None = None,
) -> dict:
    """落盘临时区→建任务→提交后台解压，立即返回 taskId。"""
    ext = Path(archive_name).suffix.lstrip(".").lower()
    if ext not in SUPPORTED_FORMATS:
        raise ValueError(f"不支持的压缩包格式 {ext!r}，仅支持 zip / 7z")
    if len(content) > int(getattr(settings, "FILE_ARCHIVE_MAX_TOTAL_SIZE", 200 * 1024 * 1024)):
        raise ValueError("压缩包超过总量上限")

    task_id = uuid.uuid4().hex
    temp_root = Path(getattr(settings, "FILE_ARCHIVE_TASK_TEMP_DIR", "") or tempfile.gettempdir())
    temp_dir = temp_root / "mediation-archive" / task_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    archive_path = temp_dir / f"archive.{ext}"
    archive_path.write_bytes(content)

    total = _count_entries(archive_path, ext)
    task = {
        "taskId": task_id, "archiveName": archive_name, "status": PENDING,
        "total": total, "done": 0, "list": [], "failed": [], "message": "",
        "directory": directory or "", "code": code or "", "userId": user_id,
        "tenantId": tenant_id, "creator": creator,
        "createTime": time.time(), "archivePath": str(archive_path), "tempDir": str(temp_dir),
    }
    _store.set(task_id, task)
    run_in_background(_run_task, task_id, name=f"archive-{task_id}")
    return {"taskId": task_id, "archiveName": archive_name, "total": total}


def _count_entries(archive_path: Path, ext: str) -> int:
    try:
        if ext == "zip":
            with zipfile.ZipFile(archive_path) as zf:
                return len([i for i in zf.infolist() if not i.is_dir()])
        import py7zr
        with py7zr.SevenZipFile(archive_path, "r") as zf:
            return len([n for n in zf.getnames() if not n.endswith("/")])
    except Exception as exc:  # noqa: BLE001 - 损坏包在后台任务中记录失败
        logger.warning(f"[压缩包] 读取条目失败 {archive_path.name}: {exc}")
        return 0


def get_archive_task(task_id: str) -> dict | None:
    task = _store.get(task_id)
    if not task:
        return None
    return {
        "taskId": task["taskId"], "archiveName": task["archiveName"],
        "status": task["status"], "total": task["total"], "done": task["done"],
        "list": task["list"], "failed": task["failed"], "message": task.get("message", ""),
    }


def cancel_archive_task(task_id: str) -> bool:
    task = _store.get(task_id)
    if not task or task["status"] in _TERMINAL:
        return False
    task["status"] = CANCELED
    task["message"] = "任务已取消"
    _store.set(task_id, task)
    return True


def _iter_entries(archive_path: Path, ext: str, target_dir: Path):
    """解压条目到临时目录，逐条 yield (safe_rel_path, disk_path)。"""
    max_entries = int(getattr(settings, "FILE_ARCHIVE_MAX_ENTRIES", 100))
    max_entry = int(getattr(settings, "FILE_ARCHIVE_MAX_ENTRY_SIZE", 50 * 1024 * 1024))
    max_total = int(getattr(settings, "FILE_ARCHIVE_MAX_TOTAL_SIZE", 200 * 1024 * 1024))
    max_ratio = int(getattr(settings, "FILE_ARCHIVE_MAX_RATIO", 200))
    count, total_size = 0, 0

    if ext == "zip":
        with zipfile.ZipFile(archive_path) as zf:
            for info in zf.infolist():
                if count >= max_entries or total_size >= max_total:
                    raise ValueError("超过条目数或总量限额")
                if info.is_dir() or info.flag_bits & 0x1:
                    continue
                rel = _safe_rel_path(info.filename)
                if not rel or _is_ignored(rel):
                    continue
                if info.file_size > max_entry:
                    raise ValueError(f"单文件超过 {max_entry // 1024 // 1024}MB 限额: {rel}")
                if info.compress_size and info.file_size / info.compress_size > max_ratio:
                    raise ValueError(f"压缩比异常: {rel}")
                target = target_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                count += 1
                total_size += info.file_size
                yield rel, target
    else:
        import py7zr
        with py7zr.SevenZipFile(archive_path, "r") as zf:
            for name in zf.getnames():
                if count >= max_entries or total_size >= max_total:
                    raise ValueError("超过条目数或总量限额")
                rel = _safe_rel_path(name)
                if not rel or _is_ignored(rel) or name.endswith("/"):
                    continue
                zf.extract(target_dir, path=name)
                target = target_dir / name
                if not target.is_file():
                    continue
                if target.stat().st_size > max_entry:
                    raise ValueError(f"单文件超过 {max_entry // 1024 // 1024}MB 限额: {rel}")
                count += 1
                total_size += target.stat().st_size
                yield rel, target


def _run_task(task_id: str) -> None:
    task = _store.get(task_id)
    if not task:
        return
    task["status"] = PROCESSING
    _store.set(task_id, task)
    started = time.time()
    timeout = int(getattr(settings, "FILE_ARCHIVE_TASK_TIMEOUT_MINUTES", 5)) * 60

    try:
        ext = Path(task["archiveName"]).suffix.lstrip(".").lower()
        archive_path = Path(task["archivePath"])
        temp_dir = Path(task["tempDir"])
        extract_dir = temp_dir / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)

        for rel, disk_path in _iter_entries(archive_path, ext, extract_dir):
            current = _store.get(task_id)
            if not current or current["status"] == CANCELED:
                return
            if time.time() - started > timeout:
                raise TimeoutError("解压任务超时")
            try:
                db = SessionLocal()
                try:
                    record = file_service.create_file(
                        db, disk_path.read_bytes(), disk_path.name,
                        directory=task.get("directory") or "", code=task.get("code") or None,
                        creator=task.get("creator"), tenant_id=task.get("tenantId"),
                    )
                    current["list"].append({
                        "name": rel, "url": record.url or f"/api/v1/system/file/{record.id}",
                        "size": record.size,
                    })
                finally:
                    db.close()
            except Exception as exc:  # noqa: BLE001 - 逐条失败记录原因后继续
                current["failed"].append({"name": rel, "reason": str(exc)[:200]})
            current["done"] = len(current["list"]) + len(current["failed"])
            _store.set(task_id, current)

        final = _store.get(task_id) or task
        if not final["list"]:
            final["status"] = FAILED
            final["message"] = "没有可上传的文件"
        elif final["failed"]:
            final["status"] = PARTIAL
            final["message"] = f"成功 {len(final['list'])} 个，失败 {len(final['failed'])} 个"
        else:
            final["status"] = SUCCESS
            final["message"] = f"全部 {len(final['list'])} 个文件上传成功"
        _store.set(task_id, final)
    except Exception as exc:  # noqa: BLE001
        final = _store.get(task_id) or task
        final["status"] = FAILED
        final["message"] = str(exc)[:300]
        _store.set(task_id, final)
        logger.warning(f"[压缩包] 任务失败 {task_id}: {exc}")
    finally:
        shutil.rmtree(task.get("tempDir", ""), ignore_errors=True)
