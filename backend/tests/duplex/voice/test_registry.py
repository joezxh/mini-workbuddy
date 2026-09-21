"""Registry 更新后：默认注册 dashscope/openai，local/s2s 移除。"""
from app.duplex.voice.providers.registry import ProviderRegistry


def test_default_keys_registered():
    ProviderRegistry._ensure_defaults()
    keys = ProviderRegistry.list_available()
    assert "dashscope" in keys
    assert "openai" in keys
    assert "local" not in keys
    assert "s2s" not in keys


def test_resolve_backup_mutual():
    assert ProviderRegistry.resolve_backup("dashscope") == "openai"
    assert ProviderRegistry.resolve_backup("openai") == "dashscope"
    assert ProviderRegistry.resolve_backup("unknown") is None
