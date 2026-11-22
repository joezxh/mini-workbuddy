"""FileClient 抽象基类：三种后端统一契约。

所有方法统一接收可选 SQLAlchemy Session（DB 后端在同一事务内写内容与元数据；
LOCAL/S3 忽略该参数），由 Service 层注入，避免连接泄漏。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy.orm import Session

from app.framework.file.utils import format_file_url


class FileClient(ABC):
    def __init__(self, config_id: int, code: str, config: dict):
        self.config_id = config_id
        self.code = code
        self.config = config or {}

    @property
    def domain(self) -> str:
        return (self.config.get("domain") or "").rstrip("/")

    @abstractmethod
    def upload(self, content: bytes, path: str, db: Session | None = None,
               content_type: str | None = None) -> str:
        """写入内容并返回可访问 URL；content_type 用于对象存储正确落 Content-Type。"""

    @abstractmethod
    def delete(self, path: str, db: Session | None = None) -> None:
        """删除内容（幂等）。"""

    @abstractmethod
    def get_content(self, path: str, db: Session | None = None) -> Optional[bytes]:
        """读取内容；不存在返回 None。"""

    def presign_put_url(self, path: str, expires: int = 3600) -> str:
        raise NotImplementedError(f"{type(self).__name__} 不支持上传预签名")

    def presign_get_url(self, path: str, expires: int = 3600) -> str:
        raise NotImplementedError(f"{type(self).__name__} 不支持下载预签名")

    def rename(self, path: str, new_name: str, db: Session | None = None) -> str | None:
        """物理重命名；不支持返回 None（业务层仅改展示名）。"""
        return None

    def get_files(self, prefix: str = "", db: Session | None = None) -> list[dict]:
        """列举文件；不支持返回空列表。"""
        return []

    def format_url(self, path: str) -> str:
        return format_file_url(self.domain, self.config_id, path)
