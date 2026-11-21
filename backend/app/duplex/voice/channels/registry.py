"""输出渠道注册表。

维护当前会话的输出渠道配置（哪些渠道被选中、各渠道的输出模式）。
渠道配置由前端编排器下发，后端据此进行回复分发。

渠道能力状态（capability）如实表达真实外发成熟度：
- enabled: 后端已具备真实外发能力
- configured: 已配置凭据但真实外发待后端启用
- pending_backend: 已配置、当前以模拟分发运行（日志 + 事件帧）
- unsupported: 后端未接入该渠道（如短信），启用后仅记录日志
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

OutputMode = Literal["text", "voice", "both"]
ChannelCapability = Literal["enabled", "configured", "pending_backend", "unsupported"]

VALID_OUTPUTS = ("text", "voice", "both")


@dataclass
class ChannelStats:
    """渠道分发统计（会话内累计）。"""
    dispatched: int = 0
    succeeded: int = 0

    @property
    def success_rate(self) -> str:
        if self.dispatched == 0:
            return "—"
        return f"{self.succeeded / self.dispatched * 100:.1f}%"


@dataclass
class ChannelConfig:
    """单个输出渠道的配置。

    Attributes:
        key: 渠道唯一标识（wechat/whatsapp/telegram/messenger/line/sms）
        name: 渠道展示名称
        active: 是否选中（选中 = Agent 向该渠道输出）
        output: 输出模式（text/voice/both）
        capability: 真实外发成熟度（如实标注，不伪造发送成功）
        icon: 前端展示图标
        desc: 渠道说明
        stats: 分发统计
    """
    key: str
    name: str
    active: bool = False
    output: OutputMode = "text"
    capability: ChannelCapability = "pending_backend"
    icon: str = "🔗"
    desc: str = ""
    stats: ChannelStats = field(default_factory=ChannelStats)


# 内置支持的渠道清单（与前端原型、设计文档 11.2 节对齐）
BUILTIN_CHANNELS: list[ChannelConfig] = [
    ChannelConfig(key="wechat", name="微信", active=True, output="voice", capability="pending_backend", icon="💬", desc="国内主流即时通信"),
    ChannelConfig(key="whatsapp", name="WhatsApp", active=True, output="text", capability="pending_backend", icon="🟢", desc="全球 180+ 国家"),
    ChannelConfig(key="telegram", name="Telegram", active=False, output="voice", capability="configured", icon="✈️", desc="海外加密即时通信"),
    ChannelConfig(key="messenger", name="Messenger", active=False, output="text", capability="configured", icon="💙", desc="Meta 旗下即时通信"),
    ChannelConfig(key="line", name="LINE", active=False, output="text", capability="configured", icon="🟢", desc="日韩/东南亚主流"),
    ChannelConfig(key="sms", name="短信", active=False, output="text", capability="unsupported", icon="📱", desc="全球短信触达"),
]


class ChannelRegistry:
    """输出渠道注册表。

    运行时维护当前会话的渠道配置，支持前端动态切换选中态与输出模式、
    新增/删除渠道、能力状态与分发统计。
    线程安全（asyncio 单线程模型下无需加锁，但保留接口一致性）。
    """

    def __init__(self, channels: Optional[list[ChannelConfig]] = None) -> None:
        self._channels: dict[str, ChannelConfig] = {}
        # 深拷贝：避免多个注册表实例共享并修改模块级 BUILTIN_CHANNELS 对象
        for cfg in (channels or BUILTIN_CHANNELS):
            copied = deepcopy(cfg)
            self._channels[copied.key] = copied

    def register(self, cfg: ChannelConfig) -> None:
        """注册或覆盖一个渠道配置。"""
        self._channels[cfg.key] = cfg

    def unregister(self, key: str) -> bool:
        """注销一个渠道。key 不存在返回 False。"""
        return self._channels.pop(key, None) is not None

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

    def apply_config(self, configs: list[dict]) -> dict[str, Any]:
        """批量应用前端下发的渠道配置。

        Args:
            configs: 前端下发的渠道配置列表，每项含 key/active/output/capability 等。

        Returns:
            结构化结果 {"applied": [...], "created": [...], "errors": [...]}，供 ACK 回执使用。

        注意：未知 key 默认忽略（保持存量行为）；仅当 allow_new=True 时才按配置新建渠道。
        前端「关闭/不发送」会在下发前映射为 active=False + 合法 output，后端不做 off 校验。
        """
        applied: list[str] = []
        created: list[str] = []
        errors: list[str] = []
        for item in configs:
            key = item.get("key")
            if not key:
                errors.append("missing key")
                continue
            cfg = self._channels.get(key)
            if cfg is None:
                created.append(key)
                cfg = ChannelConfig(
                    key=key,
                    name=str(item.get("name") or key),
                    icon=str(item.get("icon") or "🔗"),
                    desc=str(item.get("desc") or ""),
                )
                self._channels[key] = cfg
            if "active" in item:
                cfg.active = bool(item["active"])
            output = item.get("output")
            if output in VALID_OUTPUTS:
                cfg.output = output
            capability = item.get("capability")
            if capability in ("enabled", "configured", "pending_backend", "unsupported"):
                cfg.capability = capability
            applied.append(key)
        return {"applied": applied, "created": created, "errors": errors}

    def record_dispatch(self, key: str, succeeded: bool = True) -> None:
        """记录一次渠道分发结果，更新统计。"""
        cfg = self._channels.get(key)
        if cfg is None:
            return
        cfg.stats.dispatched += 1
        if succeeded:
            cfg.stats.succeeded += 1

    def snapshot(self) -> list[dict[str, Any]]:
        """导出可序列化的渠道配置快照（供 REST 与 ACK 回执）。"""
        return [
            {
                "key": c.key,
                "name": c.name,
                "icon": c.icon,
                "desc": c.desc,
                "active": c.active,
                "output": c.output,
                "capability": c.capability,
                "stats": {
                    "dispatched": c.stats.dispatched,
                    "succeeded": c.stats.succeeded,
                    "successRate": c.stats.success_rate,
                },
            }
            for c in self._channels.values()
        ]

    def active_count(self) -> int:
        """当前选中渠道数量。"""
        return sum(1 for c in self._channels.values() if c.active)
