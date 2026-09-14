"""S2SProvider（本地 Docker qwen-audio-s2s，GA Realtime 协议）单元测试。"""
import base64
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.duplex.voice.providers.registry import ProviderRegistry
from app.duplex.voice.providers.s2s import (
    DEFAULT_S2S_REALTIME_URL,
    S2SProvider,
)


class TestS2SProvider:
    def test_registry_contains_s2s(self):
        """s2s 已注册到 ProviderRegistry（get_provider 可解析）。"""
        from app.duplex.voice.providers.registry import get_provider
        assert get_provider("s2s") is S2SProvider

    def test_sample_rates(self):
        p = S2SProvider()
        assert p.input_sample_rate == 16000
        assert p.output_sample_rate == 24000

    def test_capabilities_server_vad(self):
        caps = S2SProvider().get_capabilities()
        assert caps.server_vad is True
        assert caps.supports_interrupt is True

    @pytest.mark.asyncio
    async def test_configure_session_ga_dialect(self):
        """session.update 必须是 GA 方言：session.type='realtime' + output_modalities。"""
        p = S2SProvider()
        p._ws = MagicMock()
        p._ws.send = AsyncMock()
        await p.configure_session(instructions="你好", tools=[])
        payload = json.loads(p._ws.send.await_args.args[0])
        assert payload["type"] == "session.update"
        assert payload["session"]["type"] == "realtime"
        assert payload["session"]["output_modalities"] == ["audio"]
        assert payload["session"]["audio"]["input"]["turn_detection"] == {
            "type": "server_vad", "interrupt_response": True,
        }
        assert payload["session"]["audio"]["output"]["format"]["rate"] == 24000

    @pytest.mark.asyncio
    async def test_send_audio_base64(self):
        p = S2SProvider()
        p._ws = MagicMock()
        p._ws.send = AsyncMock()
        await p.send_audio(b"\x01\x02")
        payload = json.loads(p._ws.send.await_args.args[0])
        assert payload["type"] == "input_audio_buffer.append"
        assert base64.b64decode(payload["audio"]) == b"\x01\x02"

    @pytest.mark.asyncio
    async def test_send_text_ga_response_modalities(self):
        """send_text 触发 conversation.item.create + response.create（output_modalities）。"""
        p = S2SProvider()
        p._ws = MagicMock()
        p._ws.send = AsyncMock()
        await p.send_text("你好")
        first = json.loads(p._ws.send.await_args_list[0].args[0])
        second = json.loads(p._ws.send.await_args_list[1].args[0])
        assert first["type"] == "conversation.item.create"
        assert first["item"]["content"][0] == {"type": "input_text", "text": "你好"}
        assert second["type"] == "response.create"
        assert second["response"]["output_modalities"] == ["audio"]

    def test_parse_audio_delta_decodes_base64(self):
        p = S2SProvider()
        pcm = b"\x01\x02\x03"
        event = p._parse_event({
            "type": "response.audio.delta",
            "delta": base64.b64encode(pcm).decode("ascii"),
        })
        assert event is not None
        assert event.type == "audio_delta"
        assert event.data["audio"] == pcm

    def test_parse_ga_output_text_delta(self):
        """GA 方言 response.output_text.delta 归一化为口播转写。"""
        p = S2SProvider()
        event = p._parse_event({"type": "response.output_text.delta", "delta": "你好"})
        assert event is not None
        assert event.type == "tts_transcript"
        assert event.data["text"] == "你好"

    def test_parse_asr_completed(self):
        p = S2SProvider()
        event = p._parse_event({
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "测试",
        })
        assert event is not None
        assert event.type == "transcript"

    def test_parse_error_returns_none(self):
        p = S2SProvider()
        assert p._parse_event({"type": "error", "code": "busy"}) is None

    def test_default_url(self):
        assert DEFAULT_S2S_REALTIME_URL == "ws://127.0.0.1:8765/v1/realtime"
