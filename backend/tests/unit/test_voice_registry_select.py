"""T24 Step2: 降级演练 — registry 按 is_configured 自动选型。"""
import pytest

from app.config import settings
from app.duplex.voice.providers.registry import ProviderRegistry


def test_dashscope_is_considered_configured():
    """未声明 is_configured 的 Provider 视为已配置。"""
    assert ProviderRegistry.is_configured("dashscope") is True


def test_local_not_configured_by_default(monkeypatch):
    monkeypatch.setattr(settings, "VOICE_LOCAL_ENABLED", False)
    assert ProviderRegistry.is_configured("local") is False


def test_local_configured_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "VOICE_LOCAL_ENABLED", True)
    assert ProviderRegistry.is_configured("local") is True


def test_select_falls_back_when_preferred_not_configured(monkeypatch):
    """首选 local 未配置 → 自动降级到 dashscope。"""
    monkeypatch.setattr(settings, "VOICE_LOCAL_ENABLED", False)
    assert ProviderRegistry.select("local") == "dashscope"


def test_select_keeps_preferred_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "VOICE_LOCAL_ENABLED", True)
    assert ProviderRegistry.select("local") == "local"


def test_select_unknown_key_returns_default():
    assert ProviderRegistry.select("__nonexistent__") == "dashscope"
