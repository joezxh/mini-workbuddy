"""输出渠道注册表。

维护当前会话的输出渠道配置（哪些渠道被选中、各渠道的输出模式）。
渠道配置由前端编排器下发，后端据此进行回复分发。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

OutputMode = Literal["text", "voice", "both"]


@dataclass
class ChannelConfig:
    """单个输出渠道的配置。

    Attributes:
        key: 渠道唯一标识（wechat/whatsapp/telegram/messenger/line/sms）
        name: 渠道展示名称
        active: 是否选中（选中 = Agent 向该渠道输出）
        output: 输出模式（text/voice/both）
    """
    key: str
    name: str
    active: bool = False
    output: OutputMode = "text"


# 内置支持的渠道清单（与前端原型、设计文档 11.2 节对齐）
BUILTIN_CHANNELS: list[ChannelConfig] = [
    ChannelConfig(key="wechat", name="微信", active=True, output="voice"),
    ChannelConfig(key="whatsapp", name="WhatsApp", active=True, output="text"),
    ChannelConfig(key="telegram", name="Telegram", active=False, output="voice"),
    ChannelConfig(key="messenger", name="Messenger", active=False, output="text"),
    ChannelConfig(key="line", name="LINE", active=False, output="text"),
    ChannelConfig(key="sms", name="短信", active=False, output="text"),
]


class ChannelRegistry:
    """输出渠道注册表。

    运行时维护当前会话的渠道配置，支持前端动态切换选中态与输出模式。
    线程安全（asyncio 单线程模型下无需加锁，但保留接口一致性）。
    """

    def __init__(self, channels: Optional[list[ChannelConfig]] = None) -> None:
        self._channels: dict[str, ChannelConfig] = {}
        for cfg in (channels or BUILTIN_CHANNELS):
            self._channels[cfg.key] = cfg

    def register(self, cfg: ChannelConfig) -> None:
        """注册或覆盖一个渠道配置。"""
        self._channels[cfg.key] = cfg

    def get(self, key: str) -> Optional[ChannelConfig]:
        """按 key 获取渠道配置。"""
        return self._channels.get(key)

    def list_all(self) -> list[ChannelConfig]:
        """列出所有已注册渠道。"""
        return list(self._channels.values())

    def list_active(self) -> list[ChannelConfig]:
        """列出所有选中（active=True）的渠道。"""
        return [c for c in self._channels.values() if c.active]

    def set_active(self, key: str, active: bool) -> bool:
        """设置渠道选中状态。返回是否成功（key 不存在返回 False）。"""
        cfg = self._channels.get(key)
        if cfg is None:
            return False
        cfg.active = active
        return True

    def set_output(self, key: str, output: OutputMode) -> bool:
        """设置渠道输出模式。返回是否成功。"""
        cfg = self._channels.get(key)
        if cfg is None:
            return False
        cfg.output = output
        return True

    def apply_config(self, configs: list[dict]) -> None:
        """批量应用前端下发的渠道配置。

        Args:
            configs: 前端下发的渠道配置列表，每项含 key/active/output。
        """
        for item in configs:
            key = item.get("key")
            if not key or key not in self._channels:
                continue
            cfg = self._channels[key]
            if "active" in item:
                cfg.active = bool(item["active"])
            if "output" in item and item["output"] in ("text", "voice", "both"):
                cfg.output = item["output"]

    def active_count(self) -> int:
        """当前选中渠道数量。"""
        return sum(1 for c in self._channels.values() if c.active)
