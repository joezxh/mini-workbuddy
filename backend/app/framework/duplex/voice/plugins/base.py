"""可插拔语音 Agent 插件接口定义。

每个 Agent 以 VoiceAgentPlugin 的形式接入编排器，通过 5 个生命周期钩子
参与语音对话流程。编排器负责在合适的时机调用这些钩子，并根据
PluginDecision 决定是否切换到其他 Agent。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AgentContext:
    """跨 Agent 共享的上下文快照。

    Agent 切换时由 ContextSync 同步给新 Agent，确保多轮对话连贯性。
    包含对话历史、工具调用结果缓存、知识库检索缓存、购物车状态、
    会话元数据等。
    """
    conversation_history: list[dict] = field(default_factory=list)
    tool_call_results: dict[str, Any] = field(default_factory=dict)
    kb_retrieval_cache: dict[str, list] = field(default_factory=dict)
    cart_state: dict[str, Any] = field(default_factory=dict)
    session_metadata: dict[str, Any] = field(default_factory=dict)
    active_agent: str = "ecommerce_sales"


@dataclass
class PluginDecision:
    """Agent 对下一步的决策。

    Agent 在各个生命周期钩子中返回此对象，编排器根据 should_yield
    判断是否需要切换到 next_agent_hint 指定的 Agent。
    """
    should_yield: bool = False
    next_agent_hint: Optional[str] = None
    yield_reason: Optional[str] = None


class VoiceAgentPlugin(ABC):
    """可插拔语音 Agent 插件接口。

    所有可插拔 Agent 必须继承此类并实现 5 个抽象方法。
    tools 属性可覆写以声明该 Agent 可用的 MCP 工具 schema。
    """

    @property
    @abstractmethod
    def key(self) -> str:
        """唯一标识，如 'ecommerce_sales' / 'product_catalog'。"""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """前端展示名称。"""

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """该 Agent 的系统提示词。"""

    @property
    def tools(self) -> list[dict]:
        """该 Agent 可用的 MCP 工具 schema 列表（默认空）。"""
        return []

    @abstractmethod
    async def on_activate(self, ctx: AgentContext) -> None:
        """Agent 被激活时调用（热切换入口）。"""

    @abstractmethod
    async def on_deactivate(self, ctx: AgentContext) -> None:
        """Agent 被切走时调用。"""

    @abstractmethod
    async def on_user_turn_start(self, ctx: AgentContext,
                                  partial_transcript: str) -> PluginDecision:
        """用户语音开始（流式 STT 中间结果，边说边理解）。"""

    @abstractmethod
    async def on_user_turn_end(self, ctx: AgentContext,
                                final_transcript: str) -> PluginDecision:
        """用户语音结束（最终 STT 结果）。"""

    async def on_tool_call(self, ctx: AgentContext,
                            tool_name: str,
                            arguments: dict) -> Optional[dict]:
        """工具调用钩子（可拦截/增强/缓存）。默认不拦截。"""
        return None

    async def on_assistant_turn_end(self, ctx: AgentContext,
                                     assistant_text: str) -> PluginDecision:
        """Agent 回复结束。可决定是否让出控制权。默认不让权。"""
        return PluginDecision()
