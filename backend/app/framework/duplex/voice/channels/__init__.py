"""多渠道输出模块。

负责将 Agent 回复按用户选中的渠道与输出模式（文字/语音/文字+语音）
分发到对应即时通信渠道（微信、WhatsApp、Telegram 等）。
"""

from .registry import ChannelConfig, ChannelRegistry, OutputMode
from .dispatcher import ChannelOutputDispatcher

__all__ = [
    "ChannelConfig",
    "ChannelRegistry",
    "OutputMode",
    "ChannelOutputDispatcher",
]
