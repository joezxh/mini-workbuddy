"""AgentScopeEventAdapter —— 合并双 SSE 通道的**唯一转换源**（spec §5.2 / P1.1）。

此前 Skill 链路（``SkillEventHandler``）与 Chat 链路（``sse_bridge.SSEBridge``）各自
把 AgentScope 事件映射成不同的 SSE 字典（``text`` vs ``text_delta``、``tool_call`` vs
``tool_call_end`` …），格式不一致。本适配器把两种链路的转换逻辑收敛到**唯一入口**：

- ``to_envelopes(event)``：AgentScope 原生事件对象 → ``EventEnvelope`` 列表；
- ``to_envelopes_from_dict(d)``：Research/ReAct/Team 等 dict 事件 → 信封；
- ``envelope_to_sse(env)``：信封 → 标准 SSE 字符串（``id: <seq>`` + ``event:`` + ``data:``）。

信封的 ``category`` / ``levels`` / ``ui_hint`` 全部由 ``route_of(event_type)`` 决定，
保证两链路落到 bus 后格式完全一致。调用方（bus）再按 levels 分发到 DB / SSE / UI。
"""
from __future__ import annotations

import json
from typing import Any, Optional

from app.schemas.agent.event_types import (
    EventEnvelope,
    route_of,
)


def envelope_to_sse(env: EventEnvelope) -> str:
    """信封 → 标准 SSE 字符串（带 Last-Event-ID 用的 seq）。"""
    data = env.model_dump(mode="json", exclude_none=True)
    seq = env.sequence if env.sequence is not None else 0
    return (
        f"id: {seq}\n"
        f"event: {env.event_type}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )


class AgentScopeEventAdapter:
    """AgentScope 事件 → EventEnvelope 的权威转换器。

    用法（chat 链路）：
        adapter = AgentScopeEventAdapter(execution_id, trace_id, bus=bus)
        async for ev in agent.reply_stream(user_msg):
            for env in adapter.handle(ev):
                yield envelope_to_sse(env)          # 兼容旧 SSE 客户端
        # 同时 bus 已把 STREAM 级信封分发到订阅的 /stream 连接

    用法（skill 链路）：``SkillExecutionService`` 内部复用同一映射构建信封。
    """

    def __init__(
        self,
        execution_id: str,
        trace_id: Optional[str] = None,
        source: str = "agent",
        source_id: Optional[str] = None,
        bus: Any = None,
    ) -> None:
        self.execution_id = execution_id
        self.trace_id = trace_id
        self.source = source
        self.source_id = source_id
        self.bus = bus

    # ── 公共入口 ─────────────────────────────────────────────────────────────

    def handle(self, event: Any) -> list[EventEnvelope]:
        """处理一条 AgentScope 事件（对象或 dict），返回信封列表并发布到 bus。"""
        if isinstance(event, dict):
            envs = self.to_envelopes_from_dict(event)
        else:
            envs = self.to_envelopes(event)
        for env in envs:
            if self.bus is not None:
                self.bus.publish(env)
        return envs

    # ── AgentScope 原生事件对象 ───────────────────────────────────────────────

    def to_envelopes(self, event: Any) -> list[EventEnvelope]:
        from agentscope.event import (
            ReplyStartEvent, ReplyEndEvent,
            TextBlockStartEvent, TextBlockDeltaEvent, TextBlockEndEvent,
            ThinkingBlockStartEvent, ThinkingBlockDeltaEvent, ThinkingBlockEndEvent,
            ToolCallStartEvent, ToolCallEndEvent,
            ToolResultStartEvent, ToolResultTextDeltaEvent,
            ToolResultDataDeltaEvent, ToolResultEndEvent,
            ModelCallEndEvent, ExceedMaxItersEvent,
            RequireUserConfirmEvent, RequireExternalExecutionEvent,
            UserConfirmResultEvent, UserInterruptEvent,
        )

        etype: Optional[str] = None
        content: dict = {}
        reply_id = getattr(event, "reply_id", None)
        block_id = getattr(event, "block_id", None)
        tool_call_id = getattr(event, "tool_call_id", None)
        metadata: dict = {}

        if isinstance(event, ReplyStartEvent):
            etype = "reply_start"
            content = {"reply_id": reply_id, "name": getattr(event, "name", "")}
        elif isinstance(event, TextBlockStartEvent):
            etype = "text_chunk"
            content = {"reply_id": reply_id, "block_id": block_id, "phase": "start"}
        elif isinstance(event, TextBlockDeltaEvent):
            etype = "text_chunk"
            content = {"reply_id": reply_id, "block_id": block_id,
                       "delta": getattr(event, "delta", "") or ""}
        elif isinstance(event, TextBlockEndEvent):
            etype = "text_done"
            content = {"reply_id": reply_id, "block_id": block_id,
                       "text": getattr(event, "text", "") or ""}
        elif isinstance(event, ThinkingBlockStartEvent):
            etype = "thinking_chunk"
            content = {"reply_id": reply_id, "block_id": block_id, "phase": "start"}
        elif isinstance(event, ThinkingBlockDeltaEvent):
            etype = "thinking_chunk"
            content = {"reply_id": reply_id, "block_id": block_id,
                       "delta": getattr(event, "delta", "") or ""}
        elif isinstance(event, ThinkingBlockEndEvent):
            etype = "thinking_done"
            content = {"reply_id": reply_id, "block_id": block_id,
                       "thinking": getattr(event, "thinking", "") or ""}
        elif isinstance(event, ToolCallStartEvent):
            etype = "tool_call"
            content = {"reply_id": reply_id, "tool_call_id": tool_call_id,
                       "tool_name": getattr(event, "tool_name", ""), "state": "asking"}
        elif isinstance(event, ToolCallEndEvent):
            etype = "tool_call"
            content = {"reply_id": reply_id, "tool_call_id": tool_call_id,
                       "tool_name": getattr(event, "tool_call_name", "") or "",
                       "input": getattr(event, "tool_args", {}) or {}, "state": "submitted"}
        elif isinstance(event, ToolResultStartEvent):
            etype = "tool_result"
            content = {"reply_id": reply_id, "tool_call_id": tool_call_id, "state": "running"}
        elif isinstance(event, (ToolResultTextDeltaEvent, ToolResultDataDeltaEvent)):
            etype = "tool_result"
            if isinstance(event, ToolResultTextDeltaEvent):
                content = {"reply_id": reply_id, "tool_call_id": tool_call_id,
                           "delta": getattr(event, "delta", "") or "", "state": "running"}
            else:
                data_b64 = getattr(event, "data", None)
                content = {"reply_id": reply_id, "tool_call_id": tool_call_id,
                           "media_type": getattr(event, "media_type", ""),
                           "data_size": len(data_b64) if data_b64 else 0,
                           "binary": True, "state": "running"}
        elif isinstance(event, ToolResultEndEvent):
            etype = "tool_result"
            content = {"reply_id": reply_id, "tool_call_id": tool_call_id,
                       "state": str(getattr(event, "state", "success") or "success").lower()}
        elif isinstance(event, ModelCallEndEvent):
            etype = "model_call"
            metadata = {
                "model_name": getattr(event, "model_name", ""),
                "input_tokens": int(getattr(event, "input_tokens", 0) or 0),
                "output_tokens": int(getattr(event, "output_tokens", 0) or 0),
            }
        elif isinstance(event, ExceedMaxItersEvent):
            etype = "iteration_limit"
            content = {"iterations": getattr(event, "max_iters", None)}
        elif isinstance(event, (RequireUserConfirmEvent, RequireExternalExecutionEvent)):
            etype = "hitl_pause"
            tool_calls = [
                {"id": getattr(tc, "id", ""), "name": getattr(tc, "name", ""),
                 "input": getattr(tc, "input", "{}"),
                 "suggested_rules": [str(r) for r in (getattr(tc, "suggested_rules", None) or [])]}
                for tc in (getattr(event, "tool_calls", None) or [])
            ]
            content = {"reply_id": reply_id, "tool_calls": tool_calls}
        elif isinstance(event, UserConfirmResultEvent):
            etype = "hitl_resume"
            content = {"reply_id": reply_id,
                       "action": "approve" if getattr(event, "confirmed", False) else "reject"}
        elif isinstance(event, UserInterruptEvent):
            etype = "interrupt_requested"
            content = {"reply_id": reply_id, "reason": "user_interrupt"}
        else:
            # 未知事件：保守按 runtime 落库（bus 兜底路由）
            return []

        return [self._make(etype, content, reply_id, block_id, tool_call_id, metadata)]

    # ── 非 AgentScope 编排器（dict 事件）──────────────────────────────────────

    def to_envelopes_from_dict(self, d: dict) -> list[EventEnvelope]:
        """Research / ReAct / Team 等 yield 的 dict 事件 → 信封。"""
        raw_type = str(d.get("type", "progress"))
        etype = raw_type
        content = d.get("data", d)
        if not isinstance(content, dict):
            content = {"value": str(content)}
        reply_id = d.get("reply_id")
        block_id = d.get("block_id")
        tool_call_id = d.get("tool_call_id")
        return [self._make(etype, content, reply_id, block_id, tool_call_id, {})]

    # ── 构造辅助 ─────────────────────────────────────────────────────────────

    def _make(
        self, event_type: str, content: dict, reply_id, block_id, tool_call_id, metadata
    ) -> EventEnvelope:
        route = route_of(event_type)
        return EventEnvelope(
            execution_id=self.execution_id,
            trace_id=self.trace_id,
            event_type=event_type,
            category=route.category,
            levels=list(route.levels),
            content=content,
            source=self.source,
            source_id=self.source_id,
            reply_id=reply_id,
            block_id=block_id,
            tool_call_id=tool_call_id,
            ui_hint=route.ui_hint,
            metadata=metadata,
        )
