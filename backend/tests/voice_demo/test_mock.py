"""Mock 生成器测试 — spec docs/superpowers/specs/2026-11-10-voice-demo-design.md §3.4。"""
import asyncio
import io
import wave

import pytest

from app.services.voice_demo import mock


def test_asr_shape():
    r = mock.mock_asr_text("auto")
    assert set(r) == {"text", "language"} and r["text"]


def test_tts_wav_parsable():
    raw = mock.mock_tts_wav_bytes()
    w = wave.open(io.BytesIO(raw), "rb")
    assert w.getframerate() == 24000 and w.getnchannels() == 1 and w.getsampwidth() == 2
    assert w.getnframes() > 0


@pytest.mark.asyncio
async def test_realtime_script_round():
    """一轮：append 累计 → speech_started/stopped → 转录 → audio deltas → response.done。"""
    sent: list = []

    async def client_events():
        # 累计 0.6s 音频（16k*2*0.6=19200B base64 分两片）触发轮次
        for i in range(2):
            yield {"type": "input_audio_buffer.append", "audio": "A" * 9600}
        yield {"type": "input_audio_buffer.commit"}  # Mock 不严格依赖 VAD，commit 兜底

    async def send(evt):
        sent.append(evt)
        await asyncio.sleep(0)

    script = mock.MockRealtimeScript()
    await script.run(send, client_events())
    types = [e["type"] for e in sent]
    assert "session.created" in types
    assert "input_audio_buffer.speech_started" in types
    assert "input_audio_buffer.speech_stopped" in types
    assert "response.audio.delta" in types
    assert types[-1] == "response.done"


@pytest.mark.asyncio
async def test_realtime_script_cancel():
    """累计不足阈值时 cancel → 仅 response.done(status=cancelled)，无响应音频。"""
    sent: list = []

    async def client_events():
        yield {"type": "input_audio_buffer.append", "audio": "A" * 9600}  # 未达 19200 触发线
        yield {"type": "response.cancel"}

    async def send(evt):
        sent.append(evt)
        await asyncio.sleep(0)

    script = mock.MockRealtimeScript()
    await script.run(send, client_events())
    types = [e["type"] for e in sent]
    assert "response.created" not in types
    assert "response.audio.delta" not in types
    done = [e for e in sent if e["type"] == "response.done"]
    assert done and done[-1]["response"]["status"] == "cancelled"
