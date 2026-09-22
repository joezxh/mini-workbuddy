"""AgentScope Event → SSE 桥接层。

将 AgentScope 的 reply_stream() 事件流转换为前端可消费的 SSE 事件（旧格式，前端
兼容）。同时，若传入 ``bus``/``execution_id``，则把每条事件经
``AgentScopeEventAdapter`` 归一为统一 ``EventEnvelope`` 并 publish 到 bus（spec §5.2 /
P1.1），使 chat 链路与 skill 链路在统一 SSE 通道（/stream）上事件格式一致。
"""
from __future__ import annotations
import json
from typing import Any, AsyncGenerator, Optional


class SSEBridge:
    """将 AgentScope Event 流转换为 SSE 事件推送给前端"""

    async def stream_agent_reply(
        self,
        agent,
        user_msg,
        bus: Any = None,
        execution_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """流式获取 Agent 回复并转换为 SSE 事件

        Args:
            agent: AgentScope Agent 实例（或自定义 Agent 封装）
            user_msg: 用户消息 (agentscope.message.UserMsg)
            bus: 可选 EventBus；提供后每条事件额外发布为统一信封（供 /stream 订阅）
            execution_id: 可选执行 ID；与 bus 配合用于统一通道路由
            trace_id: 可选链路追踪 ID
            source_id: 可选来源标识（如 skill_name / agent_code）

        Yields:
            SSE 格式的事件字符串（旧格式，保持前端兼容）
        """
        adapter = None
        if bus is not None and execution_id is not None:
            from app.ai.events.adapter import AgentScopeEventAdapter
            adapter = AgentScopeEventAdapter(
                execution_id=execution_id, trace_id=trace_id,
                source="agent", source_id=source_id, bus=bus,
            )

        async for event in agent.reply_stream(user_msg):
            # 自定义 Agent（ResearchAgent/SkillAgent/TeamAgent）yield dict 事件
            if isinstance(event, dict):
                event_type = event.get("type", "message")
                event_data = event.get("data", event)
                yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                if adapter is not None:
                    for env in adapter.to_envelopes_from_dict(event):
                        bus.publish(env)
                continue
            # AgentScope 原生 Event 对象
            sse_event = self._convert_event(event)
            if sse_event:
                yield f"event: {sse_event['type']}\ndata: {json.dumps(sse_event['data'], ensure_ascii=False)}\n\n"
                if adapter is not None:
                    adapter.handle(event)

    def _convert_event(self, event) -> Optional[dict]:
        """将 AgentScope Event 转换为 SSE 事件字典"""
        # 延迟导入，避免循环依赖
        from agentscope.event import (
            ReplyStartEvent, ReplyEndEvent,
            TextBlockStartEvent, TextBlockDeltaEvent, TextBlockEndEvent,
            ThinkingBlockStartEvent, ThinkingBlockDeltaEvent, ThinkingBlockEndEvent,
            ToolCallStartEvent, ToolCallEndEvent,
            ToolResultStartEvent, ToolResultTextDeltaEvent, ToolResultEndEvent,
        )

        if isinstance(event, ReplyStartEvent):
            return {
                "type": "reply_start",
                "data": {"reply_id": event.reply_id, "name": event.name}
            }
        elif isinstance(event, ReplyEndEvent):
            return {
                "type": "reply_end",
                "data": {"reply_id": event.reply_id}
            }
        elif isinstance(event, TextBlockStartEvent):
            return {
                "type": "text_start",
                "data": {"reply_id": event.reply_id, "block_id": event.block_id}
            }
        elif isinstance(event, TextBlockDeltaEvent):
            return {
                "type": "text_delta",
                "data": {
                    "reply_id": event.reply_id,
                    "block_id": event.block_id,
                    "delta": event.delta
                }
            }
        elif isinstance(event, TextBlockEndEvent):
            return {
                "type": "text_end",
                "data": {"reply_id": event.reply_id, "block_id": event.block_id}
            }
        elif isinstance(event, ThinkingBlockStartEvent):
            return {
                "type": "thinking_start",
                "data": {"reply_id": event.reply_id, "block_id": event.block_id}
            }
        elif isinstance(event, ThinkingBlockDeltaEvent):
            return {
                "type": "thinking_delta",
                "data": {
                    "reply_id": event.reply_id,
                    "block_id": event.block_id,
                    "delta": event.delta
                }
            }
        elif isinstance(event, ThinkingBlockEndEvent):
            return {
                "type": "thinking_end",
                "data": {"reply_id": event.reply_id, "block_id": event.block_id}
            }
        elif isinstance(event, ToolCallStartEvent):
            return {
                "type": "tool_call_start",
                "data": {
                    "reply_id": event.reply_id,
                    "tool_call_id": event.tool_call_id,
                    "tool_name": event.tool_name,
                }
            }
        elif isinstance(event, ToolCallEndEvent):
            return {
                "type": "tool_call_end",
                "data": {
                    "reply_id": event.reply_id,
                    "tool_call_id": event.tool_call_id,
                }
            }
        elif isinstance(event, ToolResultStartEvent):
            return {
                "type": "tool_result_start",
                "data": {
                    "reply_id": event.reply_id,
                    "tool_call_id": event.tool_call_id,
                }
            }
        elif isinstance(event, ToolResultTextDeltaEvent):
            return {
                "type": "tool_result_delta",
                "data": {
                    "reply_id": event.reply_id,
                    "tool_call_id": event.tool_call_id,
                    "delta": event.delta,
                }
            }
        elif isinstance(event, ToolResultEndEvent):
            return {
                "type": "tool_result_end",
                "data": {
                    "reply_id": event.reply_id,
                    "tool_call_id": event.tool_call_id,
                }
            }
        return None


def create_sse_response(event_type: str, data: dict) -> str:
    """创建单条 SSE 响应字符串"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def create_done_event() -> str:
    """创建 [DONE] 结束标记"""
    return "event: done\ndata: [DONE]\n\n"


def create_error_event(message: str) -> str:
    """创建错误事件"""
    return create_sse_response("error", {"message": message})
