"""上传文件落盘 / 读取（支撑「重试」重新执行分段）。

v2：底层委托统一文件存储服务（file_service），旧函数签名保持不变，
调用方无需改动。返回值兼容两种形态：

* ``file://<id>``  —— 新链路，经统一存储（DB/LOCAL/S3 可插拔）
* 绝对路径          —— 历史数据（改造前落盘），load/drop 继续支持

落盘失败仍不阻塞上传（保留原有失败语义），仅告警。
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import SessionLocal
from app.services.file import file_service

_UNSAFE = re.compile(r"[^0-9A-Za-z._\-一-龥]+")
_MAX_NAME = 120
_FILE_URI_PREFIX = "file://"


def _safe_filename(name: str) -> str:
    base = Path(name or "").name or "unnamed"
    cleaned = _UNSAFE.sub("_", base).lstrip(".")
    return (cleaned or "unnamed")[:_MAX_NAME]


def kb_upload_dir(tenant_id: int, uuid_code: str) -> Path:
    """历史落盘目录（仅供旧数据兼容）。"""
    return Path(settings.UPLOAD_DIR) / "kb" / str(tenant_id) / uuid_code


def save_upload(tenant_id: int, uuid_code: str, filename: str, content: bytes) -> str:
    """保存原始文件，返回 ``file://<id>``（新）或绝对路径（历史兜底）。"""
    db: Session = SessionLocal()
    try:
        record = file_service.create_file(
            db, content, filename, directory="kb", code="kms",
            tenant_id=tenant_id,
        )
        return f"{_FILE_URI_PREFIX}{record.id}"
    except Exception as exc:  # noqa: BLE001 - 落盘是增强能力，失败不得阻断上传
        logger.warning(f"[KB 上传] 统一存储写入失败，尝试历史本地落盘: {exc}")
    finally:
        db.close()
    try:
        target = kb_upload_dir(tenant_id, uuid_code) / _safe_filename(filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return str(target)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[KB 上传] 原始文件落盘失败，重试将无法重跑分段: {exc}")
        return ""


def load_upload(file_path: str, db: Optional[Session] = None) -> bytes:
    """读回原始字节；兼容 file:// 统一存储与历史磁盘路径。"""
    if file_path.startswith(_FILE_URI_PREFIX):
        file_id = int(file_path[len(_FILE_URI_PREFIX):])
        own = db is None
        session = db or SessionLocal()
        try:
            record = file_service.get_file(session, file_id)
            if not record:
                raise FileNotFoundError(file_path)
            content = file_service.get_file_content(session, record.config_id, record.path)
            if content is None:
                raise FileNotFoundError(file_path)
            return content
        finally:
            if own:
                session.close()
    return Path(file_path).read_bytes()


def drop_upload(file_path: Optional[str], db: Optional[Session] = None) -> None:
    """删除文档时清理原始文件（尽力而为）。"""
    if not file_path:
        return
    if file_path.startswith(_FILE_URI_PREFIX):
        file_id = int(file_path[len(_FILE_URI_PREFIX):])
        own = db is None
        session = db or SessionLocal()
        try:
            file_service.delete_file(session, file_id)
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[KB 上传] 统一存储删除失败 {file_path}: {exc}")
        finally:
            if own:
                session.close()
    try:
        shutil.rmtree(Path(file_path).parent, ignore_errors=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[KB 上传] 清理落盘文件失败 {file_path}: {exc}")
