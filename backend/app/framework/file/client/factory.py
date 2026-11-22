"""FileClientFactory：按 code 的 TTL 缓存工厂（修复 Java 端 id/code 键不一致缺陷）。"""
from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from app.config import settings
from app.framework.file.client.base import FileClient
from app.framework.file.client.db_client import DBFileClient
from app.framework.file.client.local_client import LocalFileClient
from app.framework.file.client.s3_client import S3FileClient
from app.framework.file.enums import FileStorageEnum

if TYPE_CHECKING:
    from app.models.sys.sys_infra_file_config import SysInfraFileConfig

_CLIENT_CLASSES = {
    FileStorageEnum.DB: DBFileClient,
    FileStorageEnum.LOCAL: LocalFileClient,
    FileStorageEnum.S3: S3FileClient,
}


class FileClientFactory:
    """code -> (client, expire_at) 缓存；配置变更后显式失效，避免陈旧客户端。"""

    _lock = threading.RLock()
    _cache: dict[str, tuple[FileClient, float]] = {}

    @classmethod
    def get_client(cls, config: "SysInfraFileConfig", code: str | None = None) -> FileClient:
        key = code or config.code
        now = time.monotonic()
        with cls._lock:
            cached = cls._cache.get(key)
            ttl = getattr(settings, "FILE_CLIENT_CACHE_TTL_SECONDS", 10)
            if cached and cached[1] > now and cached[0].config_id == config.id:
                return cached[0]
            client = cls._build(config, key)
            cls._cache[key] = (client, now + ttl)
            return client

    @classmethod
    def _build(cls, config: "SysInfraFileConfig", code: str) -> FileClient:
        try:
            storage = FileStorageEnum(int(config.storage))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"未知的文件存储类型: {config.storage}") from exc
        client_cls = _CLIENT_CLASSES.get(storage)
        if client_cls is None:
            raise ValueError(f"存储类型 {storage.name} 本期未实现")
        return client_cls(config.id, code, dict(config.config or {}))

    @classmethod
    def invalidate(cls, code: str | None = None, config_id: int | None = None) -> None:
        with cls._lock:
            if code is not None:
                cls._cache.pop(code, None)
                return
            if config_id is not None:
                for key, (client, _) in list(cls._cache.items()):
                    if client.config_id == config_id:
                        cls._cache.pop(key, None)
                return
            cls._cache.clear()
