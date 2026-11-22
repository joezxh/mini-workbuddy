"""双工语音编排配置存储（进程内共享）。

提供 Agent 设计配置与输出渠道配置的统一存储，供：
- REST 路由（/api/v1/duplex/*）读写与增删改
- WebSocket 网关在创建会话时读取，过滤/排序插件与初始化渠道注册表

采用进程内单例而非数据库表，避免引入迁移；服务重启后回落到内置默认配置。
真实生产环境可平滑替换为 DB 实现（接口不变）。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.framework.duplex.voice.channels.registry import BUILTIN_CHANNELS, ChannelConfig
from app.framework.duplex.voice.plugins import BUILTIN_PLUGINS

# 前端展示元数据（图标 / 描述），与前端 AgentOrchestratorManagerPanel 对应
_AGENT_META: dict[str, dict[str, Any]] = {
    "ecommerce_sales": {"icon": "🛒", "desc": "默认活跃 Agent，推荐商品、促成交易、提升转化率", "rules": ["推荐商品", "价格咨询", "促成交易"], "priority": 1},
    "product_catalog": {"icon": "📦", "desc": "检索商品详情、规格、价格、库存", "rules": ["商品详情", "库存查询"], "priority": 2},
    "cross_border": {"icon": "🌍", "desc": "跨境物流、关税计算、清关、海外仓", "rules": ["关税", "清关", "海外仓"], "priority": 3},
    "marketing": {"icon": "🎯", "desc": "促销活动、优惠券、会员权益、积分", "rules": ["优惠", "会员"], "priority": 4},
    "dispute_resolution": {"icon": "⚖️", "desc": "AI 自动处理投诉：分类、方案、补偿、升级人工", "rules": ["投诉", "退款", "纠纷"], "priority": 5},
}


def _build_default_agents() -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    for plugin_cls in BUILTIN_PLUGINS:
        plugin = plugin_cls()
        key = plugin.key
        meta = _AGENT_META.get(key, {})
        tools = getattr(plugin, "tools", []) or []
        tool_names = [t.get("name") if isinstance(t, dict) else str(t) for t in tools]
        agents.append({
            "key": plugin.key,
            "name": plugin.display_name,
            "icon": meta.get("icon", "🤖"),
            "desc": meta.get("desc", ""),
            "enabled": plugin.key != "marketing",
            "priority": meta.get("priority", 99),
            "prompt": plugin.system_prompt,
            "rules": meta.get("rules", []),
            "tools": tool_names,
        })
    return sorted(agents, key=lambda a: a["priority"])


# 进程内单例配置
_agents: list[dict[str, Any]] = _build_default_agents()
_channels: list[dict[str, Any]] = [
    {
        "key": c.key, "name": c.name, "icon": c.icon, "desc": c.desc,
        "active": c.active, "output": c.output, "capability": c.capability,
    }
    for c in BUILTIN_CHANNELS
]


# ── Agent 配置 ──
def list_agents() -> list[dict[str, Any]]:
    return deepcopy(_agents)


def get_agent(key: str) -> dict[str, Any] | None:
    for a in _agents:
        if a["key"] == key:
            return deepcopy(a)
    return None


def upsert_agent(payload: dict[str, Any]) -> dict[str, Any]:
    key = payload.get("key")
    if not key:
        raise ValueError("key 不能为空")
    existing = next((a for a in _agents if a["key"] == key), None)
    if existing is None:
        existing = {
            "key": key, "name": key, "icon": "🤖", "desc": "", "enabled": True,
            "priority": len(_agents) + 1, "prompt": "", "rules": [], "tools": [],
        }
        _agents.append(existing)
    for field in ("name", "icon", "desc", "enabled", "priority", "prompt", "rules", "tools"):
        if field in payload:
            existing[field] = payload[field]
    _agents.sort(key=lambda a: a["priority"])
    return deepcopy(existing)


def delete_agent(key: str) -> bool:
    idx = next((i for i, a in enumerate(_agents) if a["key"] == key), None)
    if idx is None:
        return False
    _agents.pop(idx)
    return True


def enabled_agents() -> list[dict[str, Any]]:
    """返回已启用且按优先级排序的 Agent 配置（供网关注册插件）。"""
    return deepcopy([a for a in _agents if a.get("enabled", True)])


# ── 渠道配置 ──
def list_channels() -> list[dict[str, Any]]:
    return deepcopy(_channels)


def upsert_channel(payload: dict[str, Any]) -> dict[str, Any]:
    key = payload.get("key")
    if not key:
        raise ValueError("key 不能为空")
    existing = next((c for c in _channels if c["key"] == key), None)
    if existing is None:
        existing = {
            "key": key, "name": key, "icon": "🔗", "desc": "",
            "active": False, "output": "text", "capability": "pending_backend",
        }
        _channels.append(existing)
    for field in ("name", "icon", "desc", "active", "output", "capability"):
        if field in payload:
            existing[field] = payload[field]
    return deepcopy(existing)


def delete_channel(key: str) -> bool:
    idx = next((i for i, c in enumerate(_channels) if c["key"] == key), None)
    if idx is None:
        return False
    _channels.pop(idx)
    return True


def build_channel_registry() -> Any:
    """根据当前配置构造 ChannelRegistry（供网关会话初始化）。"""
    from app.framework.duplex.voice.channels.registry import ChannelRegistry
    cfgs = [
        ChannelConfig(
            key=c["key"], name=c["name"], active=c.get("active", False),
            output=c.get("output", "text"), capability=c.get("capability", "pending_backend"),
            icon=c.get("icon", "🔗"), desc=c.get("desc", ""),
        )
        for c in _channels
    ]
    return ChannelRegistry(cfgs)
