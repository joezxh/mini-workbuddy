"""Manual Source —— 前端手动创建 Trigger（跳过 Eval 的场景）。

Task 3.7：极简实现 —— 内存队列 + pass-through poll。
当前 POST /super-agent/tickets 直接 create_ticket（不经过 intake），
本 Source 保留为后续手动 Trigger 走 intake 全流程的入口。
"""
from __future__ import annotations

from collections import deque
from datetime import datetime

from loguru import logger

from .base import HealthStatus, SourceKind, SourceKindProtocol, SourceTrigger


class ManualSource(SourceKindProtocol):
    """Manual Source —— 极简实现：内存队列 + 空转 poll。"""

    kind: SourceKind = "manual"

    def __init__(self, poll_seconds: int = 60):
        self.poll_seconds = max(5, poll_seconds)
        self._queue: deque[SourceTrigger] = deque()
        self._failures = 0
        self._last_error: str | None = None

    def is_enabled(self) -> bool:
        return True

    def submit(self, trigger: SourceTrigger) -> None:
        """手动 Trigger 入队待 poll。"""
        self._queue.append(trigger)
        logger.info(f"ManualSource.submit · ref={trigger.ref_id} · kind={trigger.kind}")

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
