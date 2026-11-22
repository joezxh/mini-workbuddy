"""多 Agent 编排核心。

VoiceAgentOrchestrator 负责：
1. 维护活跃 Agent，支持意图触发 + 状态触发切换
2. 跨 Agent 上下文同步（ContextSync）
3. 将 Active Plugin 的 system_prompt/tools 热更新到 RealtimeProvider
"""
from __future__ import annotations

import asyncio
from typing import Optional

from loguru import logger

from .channels.dispatcher import ChannelOutputDispatcher
from .context.sync import ContextSync
from .intent.router import IntentRouter
from .plugins.base import AgentContext, PluginDecision, VoiceAgentPlugin
from .plugins.registry import PluginRegistry


class VoiceAgentOrchestrator:
    """多 Agent 编排器。

    在 RealtimeProvider 之上增加多 Agent 编排能力。
    事件流经过编排器分发，根据意图或 Agent 决策热切换活跃 Agent，
    并将新 Agent 的 system_prompt 和 tools 注入 Provider。
    """

    def __init__(self, registry: PluginRegistry, provider,
                 channel_dispatcher: Optional[ChannelOutputDispatcher] = None) -> None:
        self._registry = registry
        self._provider = provider
        self._intent_router = IntentRouter()
        self._context_sync = ContextSync()
        self._active_key: str = "ecommerce_sales"
        self._context = AgentContext()
        self._switch_lock = asyncio.Lock()
        self._channel_dispatcher = channel_dispatcher
        # 最近一次切换的原因与来源，供 agent_switched 帧下发给前端展示细粒度激活徽章
        self._last_switch_reason: str = "default"
        self._last_switch_from: Optional[str] = None

    @property
    def active_agent(self) -> Optional[VoiceAgentPlugin]:
        """当前活跃的 Agent 插件。"""
        return self._registry.get(self._active_key)

    @property
    def active_key(self) -> str:
        """当前活跃 Agent 的 key。"""
        return self._active_key

    @property
    def context(self) -> AgentContext:
        """当前上下文快照。"""
        return self._context

    @property
    def last_switch_reason(self) -> str:
        """最近一次 Agent 切换原因（intent/voice/text/state_yield/manual/default）。"""
        return self._last_switch_reason

    @property
    def last_switch_from(self) -> Optional[str]:
        """最近一次切换的来源 Agent key。"""
        return self._last_switch_from

    def list_agents(self) -> list[dict]:
        """列出已注册 Agent 的展示快照（供 REST 暴露给前端编排器面板）。"""
        result: list[dict] = []
        for key in self._registry.list_keys():
            plugin = self._registry.get(key)
            if plugin is None:
                continue
            result.append({
                "key": key,
                "name": plugin.display_name,
                "system_prompt": plugin.system_prompt,
                "tools": getattr(plugin, "tools", []),
                "priority": getattr(plugin, "priority", 0),
                "enabled": getattr(plugin, "enabled", True),
                "active": key == self._active_key,
            })
        return result

    def set_channel_dispatcher(self, dispatcher: ChannelOutputDispatcher) -> None:
        """注入多渠道输出分发器（gateway 创建后调用）。"""
        self._channel_dispatcher = dispatcher

    async def start(self, default_key: str = "ecommerce_sales") -> None:
        """启动编排器，激活默认 Agent。"""
        self._active_key = default_key
        self._context.active_agent = default_key
        plugin = self.active_agent
        if plugin:
            await plugin.on_activate(self._context)
            await self._apply_plugin_to_provider(plugin)
            logger.info(f"[Orchestrator] 启动，默认 Agent: {default_key}")
        else:
            logger.warning(f"[Orchestrator] 默认 Agent {default_key} 未注册")

    async def on_user_speech_started(self, partial_text: str) -> None:
        """流式 STT 中间结果回调（边说边理解）。

        调用当前活跃 Agent 的 on_user_turn_start，
        若 Agent 决定让权则切换。
        """
        plugin = self.active_agent
        if not plugin:
            return
        try:
            decision = await plugin.on_user_turn_start(self._context, partial_text)
            await self._handle_decision(decision)
        except Exception as e:  # noqa: BLE001
            logger.error(f"[Orchestrator] on_user_turn_start 异常: {e}")

    async def on_user_speech_ended(self, final_text: str) -> None:
        """用户语音结束回调。

        先尝试意图路由，若命中则切换到目标 Agent；
        否则调用当前 Agent 的 on_user_turn_end。
        """
        # 意图路由
        try:
            intended_key = await self._intent_router.route(final_text, self._context)
        except Exception as e:  # noqa: BLE001
            logger.error(f"[Orchestrator] 意图路由异常: {e}")
            intended_key = None

        if intended_key and intended_key != self._active_key:
            await self.switch_to(intended_key, reason="intent")
            return

        plugin = self.active_agent
        if plugin:
            try:
                decision = await plugin.on_user_turn_end(self._context, final_text)
                await self._handle_decision(decision)
            except Exception as e:  # noqa: BLE001
                logger.error(f"[Orchestrator] on_user_turn_end 异常: {e}")

    async def on_assistant_response_end(self, text: str) -> None:
        """Agent 回复结束回调（状态触发切换 + 多渠道分发）。"""
        plugin = self.active_agent
        if plugin:
            try:
                decision = await plugin.on_assistant_turn_end(self._context, text)
                await self._handle_decision(decision)
            except Exception as e:  # noqa: BLE001
                logger.error(f"[Orchestrator] on_assistant_turn_end 异常: {e}")

        # 多渠道输出分发（结构化结果供 WS output.dispatched 与 extra_data 落库）
        self._last_dispatch = []
        if self._channel_dispatcher:
            try:
                self._last_dispatch = await self._channel_dispatcher.dispatch_detailed(
                    text=text, agent_key=self._active_key
                )
            except Exception as e:  # noqa: BLE001
                logger.error(f"[Orchestrator] 渠道分发异常: {e}")

    @property
    def last_dispatch(self) -> list[dict]:
        """最近一次回复的多渠道结构化分发结果。"""
        return getattr(self, "_last_dispatch", [])

    async def on_tool_call(self, tool_name: str, arguments: dict) -> Optional[dict]:
        """工具调用钩子，转发给当前活跃 Agent。"""
        plugin = self.active_agent
        if plugin:
            try:
                return await plugin.on_tool_call(self._context, tool_name, arguments)
            except Exception as e:  # noqa: BLE001
                logger.error(f"[Orchestrator] on_tool_call 异常: {e}")
        return None

    async def switch_to(self, key: str, reason: str = "manual") -> bool:
        """热切换到指定 Agent。

        流程：停用当前 Agent → 同步上下文 → 激活新 Agent → 注入 Provider。
        切换过程加锁，防止并发切换冲突。
        """
        async with self._switch_lock:
            if key == self._active_key:
                return True
            target = self._registry.get(key)
            if target is None:
                logger.warning(f"[Orchestrator] 未知 Agent: {key}")
                return False

            current = self.active_agent
            current_key = self._active_key

            # 1. 停用当前 Agent
            if current:
                try:
                    await current.on_deactivate(self._context)
                except Exception as e:  # noqa: BLE001
                    logger.error(f"[Orchestrator] on_deactivate 异常: {e}")

            # 2. 同步上下文
            try:
                self._context = await self._context_sync.sync(
                    self._context, from_agent=current_key, to_agent=key)
            except Exception as e:  # noqa: BLE001
                logger.error(f"[Orchestrator] ContextSync 异常: {e}")

            # 3. 激活新 Agent
            self._active_key = key
            self._context.active_agent = key
            self._last_switch_reason = reason
            self._last_switch_from = current_key
            try:
                await target.on_activate(self._context)
            except Exception as e:  # noqa: BLE001
                logger.error(f"[Orchestrator] on_activate 异常: {e}")

            # 4. 注入到 Provider（热更新 system_prompt + tools）
            try:
                await self._apply_plugin_to_provider(target)
            except Exception as e:  # noqa: BLE001
                logger.error(f"[Orchestrator] apply_plugin_to_provider 异常: {e}")

            logger.info(
                f"[Orchestrator] Agent 切换: {current_key} → {key} (reason={reason})")
            return True

    async def _handle_decision(self, decision: PluginDecision) -> None:
        """处理 Agent 的决策，若需要让权则切换。"""
        if decision.should_yield and decision.next_agent_hint:
            await self.switch_to(
                decision.next_agent_hint,
                reason=decision.yield_reason or "state_yield")

    async def _apply_plugin_to_provider(self, plugin: VoiceAgentPlugin) -> None:
        """将 Plugin 的 system_prompt + tools 热更新到 RealtimeProvider。"""
        await self._provider.update_session(
            instructions=plugin.system_prompt,
            mcp_tools=plugin.tools,
        )
