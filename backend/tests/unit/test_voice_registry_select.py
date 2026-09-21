"""降级演练 — registry 按 is_configured 自动选型（AgentScope 内核语义）。

is_configured 现由 resolve_voice_config（DB 语音模型解析）驱动，测试以
monkeypatch 模拟平台模型行的配置状态，不依赖真实数据库。
"""
import pytest

from app.duplex.voice.providers.registry import ProviderRegistry


@pytest.fixture
def patch_resolve(monkeypatch):
    """按 provider key 返回预设的 resolve_voice_config 结果。"""
    def _patch(configured_map):
        def fake_resolve(provider_key=None, model_id=None):
            return {"configured": configured_map.get(provider_key, False)}
        monkeypatch.setattr(
            "app.duplex.voice.voice_config.resolve_voice_config", fake_resolve)
    return _patch


def test_dashscope_configured_when_model_row_exists(patch_resolve):
    patch_resolve({"dashscope": True})
    assert ProviderRegistry.is_configured("dashscope") is True


def test_dashscope_not_configured_without_model_row(patch_resolve):
    patch_resolve({})
    assert ProviderRegistry.is_configured("dashscope") is False


def test_openai_not_configured_by_default(patch_resolve):
    patch_resolve({})
    assert ProviderRegistry.is_configured("openai") is False


def test_select_falls_back_when_preferred_not_configured(patch_resolve):
    """首选 openai 未配置 → 自动降级到默认 dashscope（已配置）。"""
    patch_resolve({"dashscope": True})
    assert ProviderRegistry.select("openai") == "dashscope"


def test_select_keeps_preferred_when_configured(patch_resolve):
    patch_resolve({"dashscope": True, "openai": True})
    assert ProviderRegistry.select("openai") == "openai"
    assert ProviderRegistry.select("dashscope") == "dashscope"


def test_select_unknown_key_returns_default(patch_resolve):
    patch_resolve({"dashscope": True})
    assert ProviderRegistry.select("__nonexistent__") == "dashscope"
