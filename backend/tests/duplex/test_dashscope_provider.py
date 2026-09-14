"""DashScopeProvider 单元测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.duplex.voice.providers.dashscope import DashScopeProvider


class TestDashScopeProvider:
    def test_key(self):
        p = DashScopeProvider()
        assert p.key == "dashscope"

    def test_sample_rates(self):
        p = DashScopeProvider()
        assert p.input_sample_rate == 16000
        assert p.output_sample_rate == 24000

    @pytest.mark.asyncio
    async def test_close_without_connect(self):
        """未连接时 close 不报错。"""
        p = DashScopeProvider()
        await p.close()

    @pytest.mark.asyncio
    async def test_send_audio_without_connection_raises(self):
        """未连接时 send_audio 应抛异常。"""
        p = DashScopeProvider()
        with pytest.raises(RuntimeError, match="未连接"):
            await p.send_audio(b"test")

    def test_parse_asr_event(self):
        """测试 ASR 事件解析（A.7.3：归一化为 transcript，网关映射 role=user）。"""
        p = DashScopeProvider()
        raw = {
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "你好世界",
        }
        event = p._parse_event(raw)
        assert event is not None
        assert event.type == "transcript"
        assert event.data["text"] == "你好世界"

    def test_parse_audio_event(self):
        """测试音频 delta 事件解析（A.7.2：base64 解码为原始 PCM 字节）。"""
        import base64
        p = DashScopeProvider()
        pcm = b"\x01\x02\x03\x04"
        raw = {
            "type": "response.audio.delta",
            "delta": base64.b64encode(pcm).decode("ascii"),
        }
        event = p._parse_event(raw)
        assert event is not None
        assert event.type == "audio_delta"
        assert event.data["audio"] == pcm

    def test_parse_error_event_logged_not_emitted(self):
        """服务端 error 事件仅落日志，不产出事件（A.8：session.update 被拒可观测）。"""
        p = DashScopeProvider()
        event = p._parse_event({"type": "error", "code": "invalid_session_update"})
        assert event is None

    def test_configure_session_includes_turn_detection(self):
        """A.8：session.update 默认下发 turn_detection=smart_turn，可覆盖/关闭。"""
        import json
        p = DashScopeProvider()
        sent = []

        async def fake_send(payload):
            sent.append(json.loads(payload))

        p._ws = MagicMock()
        p._ws.send = AsyncMock(side_effect=fake_send)

        import asyncio
        # 默认：smart_turn
        asyncio.run(p.configure_session(instructions="hi", voice="Cherry"))
        assert sent[0]["session"]["turn_detection"] == {"type": "smart_turn"}
        # 覆盖：server_vad
        asyncio.run(p.configure_session(turn_detection={"type": "server_vad"}))
        assert sent[1]["session"]["turn_detection"] == {"type": "server_vad"}
        # 关闭："off" 时不下发（回退服务端默认 VAD）
        asyncio.run(p.configure_session(turn_detection="off"))
        assert "turn_detection" not in sent[2]["session"]
        # 未提供 transcription 时不下发，避免无效字段导致整个 session.update 被拒
        assert "input_audio_transcription" not in sent[0]["session"]

    def test_parse_tool_call_event(self):
        """测试工具调用事件解析。"""
        import json
        p = DashScopeProvider()
        raw = {
            "type": "response.function_call_arguments.done",
            "name": "duplex_phase_advance",
            "arguments": json.dumps({"target_phase": "BACK_TO_BACK"}),
        }
        event = p._parse_event(raw)
        assert event is not None
        assert event.type == "tool_call"
        assert event.data["name"] == "duplex_phase_advance"
        assert event.data["arguments"]["target_phase"] == "BACK_TO_BACK"

    def test_parse_unknown_event_returns_none(self):
        """未知事件类型返回 None。"""
        p = DashScopeProvider()
        event = p._parse_event({"type": "unknown_type"})
        assert event is None
