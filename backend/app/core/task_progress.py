"""任务进度存储抽象。

此前进度直接写在 router 的 module-level 可变 dict（如
event_processing_router._task_progress / risk_persons._person_task_progress /
risk_entities._entity_task_progress），在 uvicorn 多 worker / reload 下会：
  - 数据错乱（多个进程各自持有 dict）
  - 进程重启即丢进度
  - 非线程安全

现统一通过本模块读写，默认实现基于 Redis；无 Redis 时回退内存实现（单机开发）。
所有 router 的后台任务与 SSE 接口都应通过本模块访问进度，禁止持有全局可变状态。
"""
from __future__ import annotations

import json
import threading
from typing import Optional, Protocol

from app.config import settings


class TaskProgressStore(Protocol):
    def get(self, task_id: str) -> Optional[dict]: ...
    def set(self, task_id: str, progress: dict) -> None: ...
    def append_log(self, task_id: str, log: dict) -> None: ...


class InMemoryProgressStore:
    """单机开发回退实现（线程安全）。生产环境请勿使用。"""

    def __init__(self) -> None:
        self._data: dict[str, dict] = {}
        self._lock = threading.Lock()

    def get(self, task_id: str) -> Optional[dict]:
        with self._lock:
            return self._data.get(task_id)

    def set(self, task_id: str, progress: dict) -> None:
        with self._lock:
            self._data[task_id] = progress

    def append_log(self, task_id: str, log: dict) -> None:
        with self._lock:
            prog = self._data.setdefault(task_id, {"logs": []})
            prog.setdefault("logs", []).append(log)
            self._data[task_id] = prog


class RedisProgressStore:
    """生产实现：进度持久化到 Redis，跨进程/重启安全，带 TTL。"""

    def __init__(self, url: str | None = None, ttl: int = 3600) -> None:
        import redis

        self._r = redis.from_url(url or settings.REDIS_URL)
        self._ttl = ttl

    def get(self, task_id: str) -> Optional[dict]:
        raw = self._r.get(f"task_progress:{task_id}")
        return json.loads(raw) if raw else None

    def set(self, task_id: str, progress: dict) -> None:
        self._r.set(
            f"task_progress:{task_id}",
            json.dumps(progress, ensure_ascii=False),
            ex=self._ttl,
        )

    def append_log(self, task_id: str, log: dict) -> None:
        prog = self.get(task_id) or {}
        prog.setdefault("logs", []).append(log)
        self.set(task_id, prog)


# 按环境选择实现：配置了 REDIS_HOST 即视为可用生产 Redis
try:
    _has_redis = bool(settings.REDIS_HOST) and not settings.DEBUG
except Exception:
    _has_redis = False

progress_store: TaskProgressStore = (
    RedisProgressStore() if _has_redis else InMemoryProgressStore()
)


def create_progress(task_id: str, total: int) -> dict:
    """初始化一个任务的进度对象（统一结构，避免各 router 各自构造）。"""
    progress = {
        "status": "running",
        "total": total,
        "done": 0,
        "success": 0,
        "failed": 0,
        "logs": [],
    }
    progress_store.set(task_id, progress)
    return progress
