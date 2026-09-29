"""SOP 运行器 —— 注册运行并支持 HITL 挂起/恢复的流式驱动。

spec: docs/design/sop-assistant-mode-design.md §4.8 / §4.9 / §5.1

为什么需要独立运行器
--------------------
聊天链路（``ai_agent.chat_stream`` → ``SSEBridge``）**不注册运行**，
因此人工验收命中后 ``/api/v1/agent/executions/{id}/confirm`` 找不到句柄，
``resume_hitl`` 无从重驱动。本模块为 SOP 补齐三件事：

1. 注册 ``execution_id → RunHandle``（agent + handler + out_q），
   使现有 confirm 端点与 ``resume_hitl`` 可直接复用；
2. 命中 ``hitl_pause`` 时 ``mark_waiting_hitl`` + ``record_pause`` 落库；
3. 首段执行完毕后**不关闭 SSE**，继续消费 out_q 直到哨兵——
   用户答复后恢复产生的后续事件仍在同一条流上推送给前端。

同时在每次段末附带 ``sop_run`` 事件（含 ``runStateJson``），
供前端写入消息 ``extra_data`` 实现刷新/重入恢复（§4.8）。
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Optional

from loguru import logger

from .agent import SOPAgent

# 与 hitl.PAUSE_TIMEOUT_MINUTES 对齐：等待人工验收的总时长上限
_STREAM_TIMEOUT_SECONDS = 30 * 60


class _SSEFeeder:
    """把 SOP 事件转成 SSE 字符串投递到 out_q，并发布统一信封到 bus。

    形态与 ``SSEBridge`` 对 dict 事件的处理保持一致，保证前端分发逻辑零改动。
    """

    def __init__(self, out_q: asyncio.Queue, adapter: Any = None,
                 bus: Any = None) -> None:
        self.out_q = out_q
        self.adapter = adapter
        self.bus = bus

    async def handle(self, event: Any) -> None:
        if isinstance(event, dict):
            event_type = event.get("type", "message")
            data = event.get("data", event)
        else:  # 兜底：非 dict 事件不阻断流
            event_type = "message"
            data = {"raw": str(event)}

        self.out_q.put_nowait(
            f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        )
        if self.adapter is not None and isinstance(event, dict):
            for env in self.adapter.to_envelopes_from_dict(event):
                self.bus.publish(env)


async def stream_sop_reply(
    agent: SOPAgent,
    user_msg: Any,
    *,
    execution_id: str,
    bus: Any = None,
    user_id: Optional[int] = None,
    db: Any = None,
) -> AsyncGenerator[str, None]:
    """驱动 SOP 执行并 yield SSE 字符串，支持人工验收挂起与恢复。"""
    from app.ai.events.adapter import AgentScopeEventAdapter
    from app.ai.events.hitl import record_pause
    from app.ai.events.registry import get_run_registry

    adapter = None
    if bus is not None:
        adapter = AgentScopeEventAdapter(
            execution_id=execution_id, trace_id=None,
            source="agent", source_id=agent.name, bus=bus,
        )

    out_q: asyncio.Queue = asyncio.Queue()
    feeder = _SSEFeeder(out_q, adapter, bus)
    registry = get_run_registry()
    handle = registry.register(
        execution_id, asyncio.current_task(), out_q=out_q,
        agent=agent, handler=feeder, user_id=user_id,
    )

    async def _drive(resume: Optional[dict] = None) -> None:
        try:
            async for event in agent.reply_stream(
                user_msg, execution_id=execution_id, resume=resume
            ):
                await feeder.handle(event)
                if isinstance(event, dict) and event.get("type") == "hitl_pause":
                    # 挂起：置 waiting_hitl 并落库，等待 /confirm 驱动恢复
                    registry.mark_waiting_hitl(execution_id)
                    if db is not None:
                        try:
                            record_pause(db, execution_id=execution_id, tool_calls=[])
                        except Exception as exc:  # noqa: BLE001 - 落库失败不阻断挂起
                            logger.warning(f"[SOP] HITL 暂停记录失败: {exc}")
            # 段末快照：供前端持久化 sopRun（含 runStateJson）
            state = agent.run_state
            if state is not None:
                await feeder.handle({
                    "type": "sop_run",
                    "data": {**state, "execution_id": execution_id},
                })
        except Exception as exc:  # noqa: BLE001 - 执行异常统一收敛为 error 事件
            logger.exception(f"[SOP] 执行异常: {exc}")
            await feeder.handle({"type": "error", "data": {"message": str(exc)}})
        finally:
            out_q.put_nowait(None)  # 哨兵：唤醒主循环判定本段结束

    handle.task = asyncio.create_task(_drive())

    deadline = time.monotonic() + _STREAM_TIMEOUT_SECONDS
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.warning(f"[SOP] 执行流超时退出: {execution_id}")
                break
            try:
                item = await asyncio.wait_for(out_q.get(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            if item is None:
                # 本段结束：仍在等待人工验收 → 继续等 resume 后的新段
                if handle.status == "waiting_hitl":
                    continue
                break
            yield item
    finally:
        registry.unregister(execution_id)
