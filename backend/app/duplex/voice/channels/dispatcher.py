"""多渠道输出分发器。

Agent 回复结束后，按各选中渠道的输出模式（text/voice/both）将回复
分发到对应即时通信渠道。实际渠道推送（微信/WhatsApp API 等）由各
渠道适配器实现，当前阶段以日志 + 事件帧形式模拟，后续可接入真实 SDK。
"""
from __future__ import annotations

from typing import Optional

from loguru import logger

from .registry import ChannelConfig, ChannelRegistry


class ChannelOutputDispatcher:
    """Agent 回复分发器。

    在 orchestrator.on_assistant_response_end 之后调用，
    遍历所有选中渠道，按输出模式推送文字/语音。
    """

    def __init__(self, registry: ChannelRegistry) -> None:
        self._registry = registry

    async def dispatch(
        self,
        text: str,
        audio_url: Optional[str] = None,
        agent_key: str = "",
    ) -> dict[str, str]:
        """向所有选中渠道分发回复。

        Args:
            text: Agent 回复文本
            audio_url: TTS 音频 URL（voice/both 模式使用）
            agent_key: 产生回复的 Agent key（用于日志/事件）

        Returns:
            各渠道的分发结果 {channel_key: status}
        """
        active_channels = self._registry.list_active()
        if not active_channels:
            logger.debug("[ChannelDispatcher] 无选中渠道，跳过分发")
            return {}

        results: dict[str, str] = {}
        for ch in active_channels:
            try:
                if ch.output in ("text", "both"):
                    results[ch.key] = await self._push_text(ch, text, agent_key)
                if ch.output in ("voice", "both"):
                    if audio_url:
                        results[f"{ch.key}_voice"] = await self._push_voice(
                            ch, audio_url, agent_key
                        )
                    else:
                        logger.debug(
                            f"[ChannelDispatcher] {ch.name} 语音模式但无 audio_url，跳过语音推送"
                        )
            except Exception as e:  # noqa: BLE001
                logger.error(f"[ChannelDispatcher] {ch.name} 分发失败: {e}")
                results[ch.key] = f"error: {e}"

        logger.info(
            f"[ChannelDispatcher] 分发完成: agent={agent_key}, "
            f"channels={len(active_channels)}, results={results}"
        )
        return results

    async def _push_text(
        self, ch: ChannelConfig, text: str, agent_key: str
    ) -> str:
        """推送文字消息到渠道。

        TODO: 接入真实渠道 SDK（微信客服消息 API / WhatsApp Business API /
        Telegram Bot API 等）。当前阶段记录日志模拟。
        """
        logger.info(
            f"[ChannelDispatcher] → {ch.name} [文字] (agent={agent_key}): "
            f"{text[:30]}..."
        )
        return "text_sent"

    async def _push_voice(
        self, ch: ChannelConfig, audio_url: str, agent_key: str
    ) -> str:
        """推送语音消息到渠道。

        TODO: 接入真实渠道 SDK，将 TTS 音频转换为渠道支持的格式并推送。
        """
        logger.info(
            f"[ChannelDispatcher] → {ch.name} [语音] (agent={agent_key}): "
            f"audio={audio_url}"
        )
        return "voice_sent"
