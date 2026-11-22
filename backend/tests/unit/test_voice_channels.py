"""多渠道输出模块单元测试。

覆盖 ChannelRegistry 的状态管理与 ChannelOutputDispatcher 的分发逻辑。
"""
from __future__ import annotations

import pytest

from app.framework.duplex.voice.channels import (
    ChannelOutputDispatcher,
    ChannelRegistry,
)


def test_builtin_channels_defaults():
    """内置渠道默认配置：6 个渠道，默认选中 wechat+whatsapp。"""
    r = ChannelRegistry()
    all_channels = r.list_all()
    assert len(all_channels) == 6
    keys = {c.key for c in all_channels}
    assert keys == {"wechat", "whatsapp", "telegram", "messenger", "line", "sms"}
    assert r.active_count() == 2
    wechat = r.get("wechat")
    assert wechat is not None
    assert wechat.active is True
    assert wechat.output == "voice"
    whatsapp = r.get("whatsapp")
    assert whatsapp is not None
    assert whatsapp.active is True
    assert whatsapp.output == "text"


def test_set_active_and_output():
    """切换渠道选中状态与输出模式。"""
    r = ChannelRegistry()
    assert r.set_active("telegram", True) is True
    assert r.get("telegram").active is True
    assert r.active_count() == 3
    assert r.set_output("wechat", "both") is True
    assert r.get("wechat").output == "both"
    # 不存在的 key 返回 False
    assert r.set_active("unknown", True) is False
    assert r.set_output("unknown", "text") is False


def test_apply_config_from_frontend():
    """批量应用前端下发的渠道配置。"""
    r = ChannelRegistry()
    r.apply_config([
        {"key": "telegram", "active": True, "output": "text"},
        {"key": "sms", "active": True, "output": "voice"},
        {"key": "wechat", "active": False},
    ])
    assert r.get("wechat").active is False
    assert r.get("telegram").active is True
    assert r.get("telegram").output == "text"
    assert r.get("sms").active is True
    assert r.get("sms").output == "voice"


@pytest.mark.asyncio
async def test_dispatch_text_mode():
    """text 模式渠道收到文字推送。"""
    r = ChannelRegistry()
    r.apply_config([
        {"key": "wechat", "active": True, "output": "text"},
        {"key": "whatsapp", "active": True, "output": "text"},
    ])
    d = ChannelOutputDispatcher(r)
    results = await d.dispatch("hello", agent_key="ecommerce_sales")
    assert results["wechat"] == "text_sent"
    assert results["whatsapp"] == "text_sent"


@pytest.mark.asyncio
async def test_dispatch_voice_mode_requires_audio_url():
    """voice 模式无 audio_url 时跳过语音推送。"""
    r = ChannelRegistry()
    r.apply_config([{"key": "telegram", "active": True, "output": "voice"}])
    d = ChannelOutputDispatcher(r)
    results = await d.dispatch("hello")
    # 无 audio_url，voice 渠道不分发
    assert "telegram" not in results
    assert "telegram_voice" not in results


@pytest.mark.asyncio
async def test_dispatch_voice_mode_with_audio_url():
    """voice 模式有 audio_url 时推送语音。"""
    r = ChannelRegistry()
    r.apply_config([{"key": "telegram", "active": True, "output": "voice"}])
    d = ChannelOutputDispatcher(r)
    results = await d.dispatch("hello", audio_url="http://x/a.wav")
    assert results["telegram_voice"] == "voice_sent"


@pytest.mark.asyncio
async def test_dispatch_both_mode():
    """both 模式同时推送文字与语音。"""
    r = ChannelRegistry()
    r.apply_config([{"key": "wechat", "active": True, "output": "both"}])
    d = ChannelOutputDispatcher(r)
    results = await d.dispatch("hello", audio_url="http://x/a.wav")
    assert results["wechat"] == "text_sent"
    assert results["wechat_voice"] == "voice_sent"


@pytest.mark.asyncio
async def test_dispatch_no_active_channels():
    """无选中渠道时分发返回空字典。"""
    r = ChannelRegistry()
    for ch in r.list_all():
        r.set_active(ch.key, False)
    d = ChannelOutputDispatcher(r)
    results = await d.dispatch("hello")
    assert results == {}
