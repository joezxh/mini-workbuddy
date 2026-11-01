"""进程内 TTL 缓存（线程安全 LRU）。

自 ``middleware/audit_logger.py`` 的私有 ``_TTLCache`` 上提，避免仓库出现第二份
内存缓存实现（``kb_cache._MemoryCache`` 含 Redis 回退，语义更重，本期不复用）。

⚠️ 安全用法：缓存脱敏后的结果时，键**必须**包含访问者角色签名
（见 :func:`make_key` 的 ``role_sig`` 部分）。否则拥有豁免角色的用户所对应的
**未脱敏**结果会命中到普通用户，等同于脱敏策略失效。
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Optional


class TTLCache:
    """简单的线程安全 TTL 缓存（LRU 淘汰）。"""

    def __init__(self, maxsize: int = 256, ttl: float = 60.0) -> None:
        self._cache: OrderedDict = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl
        self._lock = threading.Lock()

    def get(self, key: Any) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                value, ts = self._cache[key]
                if time.time() - ts < self._ttl:
                    self._cache.move_to_end(key)
                    return value
                del self._cache[key]
            return None

    def set(self, key: Any, value: Any) -> None:
        with self._lock:
            self._cache[key] = (value, time.time())
            self._cache.move_to_end(key)
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)


def make_key(*parts: Any) -> str:
    """把分散的键成分拼成稳定字符串（顺序敏感：调用方自行排序）。"""
    return "|".join(str(p) for p in parts)
