"""T24: LocalProvider 本地管线（四 stage 编排）测试。

注意：M2 中 LocalProvider 为 mock 回显；M4 重写为真实四 stage 编排，
范式由「回显」改为「VAD→STT→Agent→TTS」，故本测试同步更新。
"""
import asyncio
import struct

import pytest

from app.config import settings
from app.duplex.voice.agent_adapter import AgentRegistry
from app.duplex.voice.providers.local import LocalProvider
from app.duplex.voice.providers.registry import get_provider


class FakeLocalAgent:
    """测试用 Agent：避免真实联网调用。"""

    agent_id = "fake-local-agent"
    engine_code = "fake"

    async def run_voice_turn(self, audio_b64=None, text=None, history=None, tools=None):
        return {"text": f"收到：{text}", "audio_b64": None, "tool_calls": []}

    async def call_tool(self, name, args):
        return {"name": name}


@pytest.fixture
def local_enabled(monkeypatch):
    monkeypatch.setattr(settings, "VOICE_LOCAL_ENABLED", True)
    yield


@pytest.fixture
def fake_agent():
    AgentRegistry.register(FakeLocalAgent())
    AgentRegistry.set_default("fake-local-agent")
    yield
    AgentRegistry.set_default(None)


def test_local_provider_registered():
    assert get_provider("local") is LocalProvider


def test_local_provider_capabilities_are_client_vad():
    """本地管线：客户端 VAD 主导、无原生转录。"""
    caps = LocalProvider().get_capabilities()
    assert caps.server_vad is False
    assert caps.manual_vad_only is True
    assert caps.native_transcription is False
    assert caps.barge_in_mode == "client"
    assert caps.supports_interrupt is True


def test_not_configured_raises_on_connect():
    """未启用本地管线 → connect 直接抛出，交由上层降级到云端。"""
    assert LocalProvider().is_configured() is False  # 默认关闭

    async def run():
        p = LocalProvider()
        with pytest.raises(RuntimeError):
            await p.connect({})

    asyncio.run(run())


def test_local_provider_emits_speech_started(local_enabled):
    """响亮音频 → VAD 判定说话开始（能量法兜底，无需模型）。"""
    async def run():
        p = LocalProvider()
        await p.connect({"instructions": "x"})
        try:
            task = asyncio.create_task(p.events().__anext__())
            loud = struct.pack("<1000h", *([20000] * 1000))
            await p.send_audio(loud)
            ev = await asyncio.wait_for(task, 2.0)
            return ev
        finally:
            await p.close()

    ev = asyncio.run(run())
    assert ev.type == "speech_started"


def test_local_provider_text_path_produces_audio(local_enabled, fake_agent):
    """文本 → Agent → TTS：产出 response_started 与 audio_delta。"""
    async def run():
        p = LocalProvider()
        await p.connect({"instructions": "x"})
        try:
            await p.send_text("你好")
            types = []
            for _ in range(2):
                ev = await asyncio.wait_for(p.events().__anext__(), 5.0)
                types.append(ev.type)
            return types
        finally:
            await p.close()

    types = asyncio.run(run())
    assert "response_started" in types
    assert "audio_delta" in types


def test_vad_loop_pipeline_emits_transcript(local_enabled, fake_agent):
    """完整链路：音频段结束 → STT 转写 → Agent → TTS 音频。"""
    async def run():
        p = LocalProvider()
        await p.connect({"instructions": "x"})
        try:
            # 1) 说话开始
            loud = struct.pack("<1000h", *([20000] * 1000))
            await p.send_audio(loud)
            assert (await asyncio.wait_for(p.events().__anext__(), 2.0)).type == "speech_started"

            # 2) 持续静音触发结束（min_silence_ms=300，每块 31.25ms）
            quiet = struct.pack("<1000h", *([0] * 1000))
            for _ in range(12):
                await p.send_audio(quiet)

            seen = []
            for _ in range(4):
                ev = await asyncio.wait_for(p.events().__anext__(), 5.0)
                seen.append(ev.type)
            return seen
        finally:
            await p.close()

    seen = asyncio.run(run())
    assert "speech_stopped" in seen
    assert "transcript_final" in seen
