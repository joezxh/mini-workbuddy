"""HTTP Source —— 接收前端/API POST 的 Trigger（内存队列 → poll 取出）。

Task 3.7：外部 HTTP handler 把 SourceTrigger.submit() 进来，
poll 循环取出后由 SourceRegistry 转交 engine.receive_trigger()。
"""
from __future__ import annotations

from collections import deque
from datetime import datetime

from loguru import logger

from .base import HealthStatus, SourceKind, SourceKindProtocol, SourceTrigger


class HTTPSource(SourceKindProtocol):
    """HTTP Source —— 极简实现：内存队列 + 空转 poll。"""

    kind: SourceKind = "http"

    def __init__(self, poll_seconds: int = 60):
        self.poll_seconds = max(5, poll_seconds)
        self._queue: deque[SourceTrigger] = deque()
        self._failures = 0
        self._last_error: str | None = None

    def is_enabled(self) -> bool:
        return True

    def submit(self, trigger: SourceTrigger) -> None:
        """外部 HTTP handler 调用 —— Trigger 入队待 poll。"""
        self._queue.append(trigger)
        logger.info(f"HTTPSource.submit · ref={trigger.ref_id} · kind={trigger.kind}")

    async def poll_once(self, workspace_id: int, last_cursor: str | None = None
                        ) -> tuple[list[SourceTrigger], str | None]:
        """取出内存队列中的 Trigger（无外部请求）。"""
        triggers: list[SourceTrigger] = []
        while self._queue:
            t = self._queue.popleft()
            if not t.workspace_id:
                t.workspace_id = workspace_id
            triggers.append(t)
        self._failures = 0
        self._last_error = None
        return triggers, datetime.utcnow().isoformat()

    def health(self) -> dict:
        return HealthStatus(
            kind=self.kind, status="healthy", failures=self._failures,
            last_error=self._last_error,
        ).to_dict()
