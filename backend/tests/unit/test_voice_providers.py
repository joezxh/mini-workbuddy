from app.duplex.voice.providers.registry import get_provider, register_provider
from app.duplex.voice.providers.base import RealtimeProvider
from app.duplex.voice.providers.dashscope import DashScopeProvider
from app.duplex.voice.capabilities import ProviderCapabilities


def test_registry_returns_dashscope():
    assert get_provider("dashscope") is DashScopeProvider


def test_dashscope_capabilities():
    cap = DashScopeProvider().get_capabilities()
    assert isinstance(cap, ProviderCapabilities)
    assert cap.supports_interrupt is True
