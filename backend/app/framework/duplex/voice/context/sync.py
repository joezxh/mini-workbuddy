"""Agent 切换时的上下文同步器。

策略：完整传递对话历史、工具调用结果、检索缓存、购物车状态、会话元数据，
确保跨 Agent 的多轮连贯性。后续可按目标 Agent 做上下文裁剪。
"""
from __future__ import annotations

from ..plugins.base import AgentContext


class ContextSync:
    """上下文同步器。

    在 Agent 热切换时，将当前上下文快照同步给新激活的 Agent。
    默认实现为浅拷贝，保持所有状态完整传递。
    """

    async def sync(self, ctx: AgentContext,
                   from_agent: str, to_agent: str) -> AgentContext:
        """同步上下文到目标 Agent。

        Args:
            ctx: 当前上下文快照
            from_agent: 源 Agent key
            to_agent: 目标 Agent key

        Returns:
            同步后的新 AgentContext 实例
        """
        return AgentContext(
            conversation_history=list(ctx.conversation_history),
            tool_call_results=dict(ctx.tool_call_results),
            kb_retrieval_cache=dict(ctx.kb_retrieval_cache),
            cart_state=dict(ctx.cart_state),
            session_metadata=dict(ctx.session_metadata),
            active_agent=to_agent,
        )
