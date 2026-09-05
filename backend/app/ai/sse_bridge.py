"""AgentScope Event → SSE 桥接层。

将 AgentScope 的 reply_stream() 事件流转换为前端可消费的 SSE 事件。
前端通过 EventSource 或 fetch + ReadableStream 消费这些事件。
"""
from __future__ import annotations
import json
from typing import AsyncGenerator, Optional


class SSEBridge:
    """将 AgentScope Event 流转换为 SSE 事件推送给前端"""

    async def stream_agent_reply(self, agent, user_msg) -> AsyncGenerator[str, None]:
        """流式获取 Agent 回复并转换为 SSE 事件

        Args:
            agent: AgentScope Agent 实例（或自定义 Agent 封装）
            user_msg: 用户消息 (agentscope.message.UserMsg)

        Yields:
            SSE 格式的事件字符串
        """
        async for event in agent.reply_stream(user_msg):
            # 自定义 Agent（ResearchAgent/SkillAgent/TeamAgent）yield dict 事件
            if isinstance(event, dict):
                event_type = event.get("type", "message")
                event_data = event.get("data", event)
                yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                continue
            # AgentScope 原生 Event 对象
            sse_event = self._convert_event(event)
            if sse_event:
                yield f"event: {sse_event['type']}\ndata: {json.dumps(sse_event['data'], ensure_ascii=False)}\n\n"

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
