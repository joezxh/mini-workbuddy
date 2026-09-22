"""AgentRunRegistry —— 运行中执行注册表（Agent 与 Skill 共用，spec §5.3/§5.5）。

InterruptManager 的 cancel 职责 P0 并入本模块；P1 若需独立
超时调度器再拆 app/ai/events/interrupt.py。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class RunHandle:
    """一次执行的可触达句柄（cancel / HITL 恢复的入口）。"""
    execution_id: str
    task: asyncio.Task
    out_q: Optional[asyncio.Queue] = None
    agent: Any = None
    handler: Any = None
    reply_id: Optional[str] = None
    status: str = "running"          # running | waiting_hitl | done
    interrupt_reason: Optional[str] = None
    user_id: Optional[int] = None
    started_at: float = field(default_factory=time.monotonic)


class AgentRunRegistry:
    """execution_id → RunHandle。进程内单例，TTL 兜底由 P1 对账任务补充。"""

    def __init__(self) -> None:
        self._handles: dict[str, RunHandle] = {}

    def register(self, execution_id: str, task: asyncio.Task, *,
                 out_q: Optional[asyncio.Queue] = None, agent: Any = None,
                 handler: Any = None, user_id: Optional[int] = None) -> RunHandle:
        handle = RunHandle(execution_id=execution_id, task=task, out_q=out_q,
                           agent=agent, handler=handler, user_id=user_id)
        self._handles[execution_id] = handle
        return handle

    def get(self, execution_id: str) -> Optional[RunHandle]:
        return self._handles.get(execution_id)

    def unregister(self, execution_id: str) -> None:
        self._handles.pop(execution_id, None)

    # ── InterruptManager（P0 合并实现）─────────────────────────────────

    def cancel(self, execution_id: str, reason: str = "user_cancel") -> bool:
        """强制终止运行中的执行。

        running 态：task.cancel() → asyncio.CancelledError。
        waiting_hitl 态：原 consumer 已结束，task.cancel 是 no-op——
        置 cancelling 状态并投递哨兵唤醒阻塞在 out_q.get() 上的主循环，
        主循环据 handle.interrupt_reason 走 user_cancel 收尾（终审 BLK-01）。
        """
        handle = self._handles.get(execution_id)
        if handle is None or handle.status == "done":
            return False
        handle.interrupt_reason = reason
        if handle.status == "waiting_hitl":
            handle.status = "cancelling"
            if handle.out_q is not None:
                try:
                    handle.out_q.put_nowait(None)
                except Exception:
                    pass
            logger.info("execution {} cancelled during HITL: {}",
                        execution_id[:8], reason)
            return True
        handle.task.cancel()
        logger.info("execution {} cancelled: {}", execution_id[:8], reason)
        return True

    def mark_waiting_hitl(self, execution_id: str,
                          reply_id: Optional[str] = None) -> None:
        handle = self._handles.get(execution_id)
        if handle is None:
            return
        handle.status = "waiting_hitl"
        if reply_id:
            handle.reply_id = reply_id

    def mark_running(self, execution_id: str) -> None:
        handle = self._handles.get(execution_id)
        if handle is not None:
            handle.status = "running"


_REGISTRY = AgentRunRegistry()


def get_run_registry() -> AgentRunRegistry:
    return _REGISTRY
