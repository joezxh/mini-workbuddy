"""上传文件落盘 / 读取（支撑「重试」重新执行分段）。

``kb_document`` 早先只在内存闭包里持有文件字节，后台任务一结束字节即消失，
文档失败后无法重新走「解析 → 清洗 → 切块 → 向量化」，只能重嵌既有切片。

此处在上传时把原始字节落盘到::

    {UPLOAD_DIR}/kb/{tenant_id}/{uuid_code}/{safe_filename}

路径写入 ``kb_document.meta['file_path']``（同时记录 ``chunker_type``），
重试端点据此读回字节并重跑整条管线。落盘失败不阻塞上传，仅告警——
此时重试会提示改用「重新向量化」。
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional

from loguru import logger

from app.config import settings

# 仅保留安全字符：字母数字与常见符号、中日韩字符；其余折叠为下划线
_UNSAFE = re.compile(r"[^0-9A-Za-z._\-\u4e00-\u9fa5]+")
_MAX_NAME = 120


def _safe_filename(name: str) -> str:
    """去掉路径成分与危险字符，防止目录穿越。"""
    base = Path(name or "").name or "unnamed"
    cleaned = _UNSAFE.sub("_", base).lstrip(".")
    return (cleaned or "unnamed")[:_MAX_NAME]


def kb_upload_dir(tenant_id: int, uuid_code: str) -> Path:
    """该文档的落盘目录（不存在则调用方负责创建）。"""
    return Path(settings.UPLOAD_DIR) / "kb" / str(tenant_id) / uuid_code


def save_upload(tenant_id: int, uuid_code: str, filename: str, content: bytes) -> str:
    """落盘原始文件，返回路径字符串；失败返回空串（不阻塞上传主链路）。"""
    try:
        target = kb_upload_dir(tenant_id, uuid_code) / _safe_filename(filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return str(target)
    except Exception as exc:  # noqa: BLE001 - 落盘是增强能力，失败不得阻断上传
        logger.warning(f"[KB 上传] 原始文件落盘失败，重试将无法重跑分段: {exc}")
        return ""


def load_upload(file_path: str) -> bytes:
    """读回原始字节；文件缺失时抛 FileNotFoundError 由调用方转 400。"""
    return Path(file_path).read_bytes()


def drop_upload(file_path: Optional[str]) -> None:  # noqa: F821
    """删除文档时清理落盘目录（尽力而为，失败仅告警）。"""
    if not file_path:
        return
    try:
        shutil.rmtree(Path(file_path).parent, ignore_errors=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[KB 上传] 清理落盘文件失败 {file_path}: {exc}")
