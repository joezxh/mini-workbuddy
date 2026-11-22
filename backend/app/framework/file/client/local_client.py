"""LOCAL 文件客户端：内容落盘到 FILE_STORAGE_DIR / basePath。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from loguru import logger

from app.config import settings
from app.framework.file.client.base import FileClient


class LocalFileClient(FileClient):
    def __init__(self, config_id: int, code: str, config: dict):
        super().__init__(config_id, code, config)
        base = config.get("basePath") or config.get("base_path")
        self.base_path = Path(base) if base else Path(settings.FILE_STORAGE_DIR)

    def _full_path(self, path: str) -> Path:
        parts = [p for p in str(path).replace("\\", "/").split("/") if p]
        if not parts:
            raise ValueError("文件路径不能为空")
        if ".." in parts:
            raise ValueError(f"文件路径含非法路径穿越段: {path}")
        clean = "/".join(p for p in parts if p != ".")
        return self.base_path / clean

    def upload(self, content: bytes, path: str, db=None, content_type: str | None = None) -> str:
        target = self._full_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return self.format_url(path)

    def delete(self, path: str, db=None) -> None:
        target = self._full_path(path)
        if target.is_file():
            target.unlink(missing_ok=True)
            # 清理空父目录（尽力而为）
            for parent in (target.parent, *target.parent.parents):
                if parent == self.base_path.resolve():
                    break
                try:
                    parent.rmdir()
                except OSError:
                    break

    def get_content(self, path: str, db=None) -> Optional[bytes]:
        target = self._full_path(path)
        if not target.is_file():
            return None
        try:
            return target.read_bytes()
        except OSError as exc:
            logger.warning(f"[LocalFileClient] 读取失败 {path}: {exc}")
            return None

    def get_files(self, prefix: str = "", db=None) -> list[dict]:
        root = self._full_path(prefix) if prefix else self.base_path
        if not root.exists():
            return []
        base = self.base_path.resolve()
        return [
            {"path": p.resolve().relative_to(base).as_posix(), "size": p.stat().st_size}
            for p in root.rglob("*") if p.is_file()
        ]
