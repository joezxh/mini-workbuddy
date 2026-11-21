"""双工编排管理单元测试：Agent 编排 reason、配置存储 CRUD、渠道快照与统计。"""
from __future__ import annotations

import pytest

from app.duplex.voice import orchestration_store as store
from app.duplex.voice.channels.registry import (
    BUILTIN_CHANNELS,
    ChannelConfig,
    ChannelRegistry,
)
from app.duplex.voice.constants import EventType


# ── 渠道新增能力 ──
def test_channel_snapshot_serializable():
    r = ChannelRegistry()
    snap = r.snapshot()
    assert len(snap) == 6
    wechat = next(c for c in snap if c["key"] == "wechat")
    assert wechat["name"] == "微信"
    assert wechat["capability"] == "pending_backend"
    assert wechat["stats"]["dispatched"] == 0
    assert wechat["stats"]["successRate"] == "—"


def test_channel_record_dispatch_stats():
    r = ChannelRegistry()
    r.record_dispatch("wechat", succeeded=True)
    r.record_dispatch("wechat", succeeded=True)
    r.record_dispatch("wechat", succeeded=False)
    c = r.get("wechat")
    assert c.stats.dispatched == 3
    assert c.stats.succeeded == 2
    assert c.stats.success_rate == "66.7%"


def test_channel_apply_config_creates_and_updates():
    r = ChannelRegistry()
    result = r.apply_config([
        {"key": "wechat", "active": False, "output": "text"},
        {"key": "custom_ch", "name": "自定义", "active": True, "output": "voice", "capability": "configured"},
    ])
    assert "wechat" in result["applied"]
    assert "custom_ch" in result["created"]
    assert r.get("wechat").active is False
    custom = r.get("custom_ch")
    assert custom is not None and custom.active is True and custom.output == "voice"
    assert custom.capability == "configured"


def test_channel_apply_config_ignores_invalid_output():
    r = ChannelRegistry()
    r.apply_config([{"key": "wechat", "active": True, "output": "off"}])
    # off 不在合法输出中，应保留原 output=voice（前端已映射为 active=False）
    assert r.get("wechat").output == "voice"


def test_channel_unregister():
    r = ChannelRegistry()
    assert r.unregister("sms") is True
    assert r.unregister("sms") is False
    assert r.get("sms") is None


# ── 事件常量 ──
def test_new_event_constants():
    assert EventType.AGENT_SWITCHED.value == "agent_switched"
    assert EventType.CHANNEL_CONFIG_ACK.value == "channel_config_ack"
    assert EventType.OUTPUT_DISPATCHED.value == "output.dispatched"


# ── 配置存储 CRUD ──
def test_store_agents_default_and_crud():
    agents = store.list_agents()
    assert len(agents) >= 5
    keys = {a["key"] for a in agents}
    assert {"ecommerce_sales", "product_catalog", "cross_border", "marketing", "dispute_resolution"} <= keys

    created = store.upsert_agent({
        "key": "test_agent", "name": "测试 Agent", "enabled": True,
        "priority": 99, "prompt": "hi", "rules": ["r1"], "tools": ["t1"],
    })
    assert created["name"] == "测试 Agent"
    assert store.get_agent("test_agent")["priority"] == 99
    assert store.delete_agent("test_agent") is True
    assert store.get_agent("test_agent") is None


def test_store_channels_default_and_crud():
    channels = store.list_channels()
    assert len(channels) >= 6
    store.upsert_channel({"key": "test_ch", "name": "测试渠道", "active": True, "output": "voice"})
    ch = next(c for c in store.list_channels() if c["key"] == "test_ch")
    assert ch["name"] == "测试渠道" and ch["output"] == "voice"
    assert store.delete_channel("test_ch") is True


def test_store_build_channel_registry():
    r = store.build_channel_registry()
    assert isinstance(r, ChannelRegistry)
    assert len(r.list_all()) >= 6
