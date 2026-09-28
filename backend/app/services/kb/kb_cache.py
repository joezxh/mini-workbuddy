"""KB 读取缓存（Phase 3 T2）：分类树 / 知识库列表。

沿用 ``app.core.task_progress`` 的既有范式：配置 REDIS_HOST 即走 Redis，
否则回退进程内 TTL 缓存（单机开发）。**缓存失效必须显式调用**，禁止依赖
隐式过期保证一致性：写操作后按 key 前缀失效。

缓存未命中/Redis 不可用时一律回源，缓存层不参与正确性判断（非授权边界）。
"""
from __future__ import annotations

import json
import threading
import time
from functools import wraps
from typing import Callable, Optional

from app.config import settings

DEFAULT_TTL = 3600  # 1 小时（spec §4.4.2）

_PREFIX = "kms"


def _redis_client():
    try:
        import redis

        return redis.from_url(settings.REDIS_URL)
    except Exception:  # noqa: BLE001 - Redis 不可用时回退内存缓存
        return None


class _MemoryCache:
    """进程内 TTL 缓存（Redis 不可用时的回退）。"""

    def __init__(self) -> None:
        self._data: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            hit = self._data.get(key)
            if not hit:
                return None
            expire_at, value = hit
            if expire_at < time.time():
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: str, ttl: int) -> None:
        with self._lock:
            self._data[key] = (time.time() + ttl, value)

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            for key in list(self._data):
                if key.startswith(prefix):
                    self._data.pop(key, None)


_memory = _MemoryCache()


def cache_key(*parts) -> str:
    return f"{_PREFIX}:" + ":".join(str(p) for p in parts)


def cached(ttl: int = DEFAULT_TTL, key_builder: Callable | None = None):
    """同步函数结果缓存装饰器；命中直接返回，未命中回源并写入。"""

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = key_builder(*args, **kwargs) if key_builder else cache_key(
                func.__name__, *args, *sorted(kwargs.items())
            )
            raw = _cache_get(key)
            if raw is not None:
                try:
                    return json.loads(raw)
                except (TypeError, ValueError):
                    pass  # 缓存损坏 → 回源
            result = func(*args, **kwargs)
            try:
                _cache_set(key, json.dumps(result, default=str), ttl)
            except (TypeError, ValueError):
                pass  # 结果不可序列化 → 不缓存
            return result

        return wrapper

    return decorator


def invalidate(prefix: str) -> None:
    """按 key 前缀失效（写操作后调用）。"""
    client = _redis_client()
    if client is not None:
        try:
            for key in client.scan_iter(match=f"{prefix}*"):
                client.delete(key)
            return
        except Exception:  # noqa: BLE001
            pass
    _memory.delete_prefix(prefix)


def _cache_get(key: str) -> Optional[str]:
    client = _redis_client()
    if client is not None:
        try:
            value = client.get(key)
            return value.decode() if isinstance(value, bytes) else value
        except Exception:  # noqa: BLE001
            pass
    return _memory.get(key)


def _cache_set(key: str, value: str, ttl: int) -> None:
    client = _redis_client()
    if client is not None:
        try:
            client.setex(key, ttl, value)
            return
        except Exception:  # noqa: BLE001
            pass
    _memory.set(key, value, ttl)
