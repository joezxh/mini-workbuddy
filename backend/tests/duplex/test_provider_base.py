"""RealtimeProvider + ProviderRegistry 单元测试。"""
import pytest
from app.duplex.voice.providers.base import ProviderEvent, RealtimeProvider
from app.duplex.voice.providers.registry import ProviderRegistry


class TestProviderEvent:
    def test_creation(self):
        e = ProviderEvent(type="asr_completed", data={"text": "你好"})
        assert e.type == "asr_completed"
        assert e.data["text"] == "你好"

    def test_defaults(self):
        e = ProviderEvent(type="audio_delta")
        assert e.data == {}


class TestProviderRegistry:
    def test_resolve_unknown_raises(self):
        with pytest.raises(ValueError, match="未知"):
            ProviderRegistry.resolve("nonexistent")

    def test_register_and_resolve(self):
        class FakeProvider(RealtimeProvider):
            key = "fake"
            input_sample_rate = 16000
            output_sample_rate = 24000
            async def connect(self, session_config): pass
            async def send_audio(self, pcm_data): pass
            async def configure_session(self, **kwargs): pass
            async def events(self):
                yield ProviderEvent(type="test")
            async def close(self): pass

        ProviderRegistry.register(FakeProvider)
        provider = ProviderRegistry.resolve("fake")
        assert isinstance(provider, FakeProvider)
        # cleanup
        ProviderRegistry._providers.pop("fake", None)

    def test_resolve_default(self):
        """无参数时返回默认 provider。"""
        ProviderRegistry._providers.clear()
        with pytest.raises(ValueError):
            ProviderRegistry.resolve()
