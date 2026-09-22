"""SSEHandler（Level 2）—— EventBus 的 STREAM 级分发器（spec §4.1/§4.4）。

职责：
- 按 execution_id 维护每个执行的**环形缓冲**（最近 N 条 envelope），供断线后
  Last-Event-ID / after_seq 补拉；
- 维护每个执行的**订阅者队列**，实时把 envelope 推给所有 SSE 连接；
- envelope.sequence 在 capture 时按 execution_id 自增分配（实时通道的连续序号，
  与 DB 落库的 sequence 解耦，但同样单调）。

设计要点：
- capture / subscribe 都在同一事件循环内调用（执行协程与 SSE 端点协程同属主循环），
  因此 asyncio.Queue 直接 put/get 安全，无需跨线程调度；
- 订阅者断开（端点返回 / 异常）由调用方负责 unsubscribe，避免队列泄漏。
"""
from __future__ import annotations

import asyncio
from collections import deque
from typing import Optional

from app.schemas.agent.event_types import EventEnvelope

_RING_SIZE = 1000


class SSEHandler:
    """STREAM 级事件分发器：环形缓冲 + 订阅广播。"""

    def __init__(self, ring_size: int = _RING_SIZE) -> None:
        self._ring: dict[str, deque] = {}
        self._subs: dict[str, list] = {}
        self._counters: dict[str, int] = {}
        self._ring_size = ring_size

    # ── 写入侧（由 EventBus.publish 调用）────────────────────────────────────

    def capture(self, envelope: EventEnvelope) -> None:
        """捕获一条 STREAM 级 envelope：分配序号、入环、广播给订阅者。"""
        if envelope.sequence is None:
            envelope.sequence = self._next_seq(envelope.execution_id)
        ring = self._ring.setdefault(
            envelope.execution_id, deque(maxlen=self._ring_size)
        )
        ring.append(envelope)
        for q in self._subs.get(envelope.execution_id, []):
            q.put_nowait(envelope)

    # ── 读取侧（由 SSE 端点调用）────────────────────────────────────────────

    def subscribe(
        self, execution_id: str, last_seq: Optional[int] = None
    ):
        """订阅某执行。

        返回 ``(replay, queue)``：
        - replay：ring 中 seq > last_seq 的历史 envelope 列表（断线补拉）；
        - queue：后续实时 envelope 的 asyncio.Queue。
        """
        ring = self._ring.get(execution_id, deque())
        replay = [
            e for e in ring if last_seq is None or e.sequence > last_seq
        ]
        q: asyncio.Queue = asyncio.Queue()
        self._subs.setdefault(execution_id, []).append(q)
        return replay, q

    def unsubscribe(self, execution_id: str, q) -> None:
        """移除订阅队列。"""
        subs = self._subs.get(execution_id)
        if subs and q in subs:
            subs.remove(q)
            if not subs:
                self._subs.pop(execution_id, None)

    # ── 内部 ───────────────────────────────────────────────────────────────

    def _next_seq(self, execution_id: str) -> int:
        n = self._counters.get(execution_id, 0) + 1
        self._counters[execution_id] = n
        return n


_singleton = SSEHandler()


def get_sse_handler() -> SSEHandler:
    """全局唯一 SSEHandler（所有 EventBus 共享，按 execution_id 隔离）。"""
    return _singleton
