"""AgentscopeRealtimeProvider 单测：AgentScope 事件 → ProviderEvent 映射。

用真实 agentscope 事件类构造（match 语句按类判别），RealtimeAgent 以
FakeAgent 桩替换——不连真实模型。
"""
import asyncio
import base64

import pytest

from agentscope.event import (
    DataBlockDeltaEvent,
    ReplyEndEvent,
    ReplyStartEvent,
    RequireUserConfirmEvent,
    TextBlockDeltaEvent,
)
from agentscope.message import ToolCallBlock

from app.duplex.voice.providers.agentscope import AgentscopeRealtimeProvider


class FakeModel:
    input_sample_rate = 16000
    output_sample_rate = 24000
    supports_text_input = True
    model_name = "qwen3.5-omni-flash-realtime"


class FakeAgent:
    def __init__(self, events=()):
        self.model = FakeModel()
        self._events = list(events)

    async def connect(self):
        pass

    async def close(self):
        pass

    async def reply_stream(self, transport):
        for ev in self._events:
            yield ev
        await asyncio.Event().wait()  # 保持流打开


def _reply_start(reply_id, role):
    return ReplyStartEvent(session_id="s", reply_id=reply_id, name="a", role=role)


def _reply_end(reply_id):
    return ReplyEndEvent(session_id="s", reply_id=reply_id)


def _make_provider(events):
    p = AgentscopeRealtimeProvider(key="dashscope")
    p._agent = FakeAgent(events)
    p._queue = asyncio.Queue()
    return p


async def _drain(p, n):
    got = []
    async for ev in p.events():
        got.append(ev)
        if len(got) == n:
            break
    await p.close()  # 收尾：取消泵任务，避免跨测试悬挂任务警告
    return got


@pytest.mark.asyncio
async def test_assistant_reply_mapping():
    audio = base64.b64encode(b"\x00\x00" * 100).decode()
    p = _make_provider([
        _reply_start("r1", "assistant"),
        TextBlockDeltaEvent(reply_id="r1", block_id="b1", delta="你好"),
        DataBlockDeltaEvent(reply_id="r1", block_id="b2",
                            media_type="audio/pcm;rate=24000", data=audio),
        _reply_end("r1"),
    ])
    await p._start_pump()
    got = await _drain(p, 4)
    assert [e.type for e in got] == [
        "response_started", "tts_transcript", "audio_delta", "playback.ended"]
    assert got[1].data["text"] == "你好"
    assert got[2].data["audio"] == b"\x00\x00" * 100


@pytest.mark.asyncio
async def test_user_reply_mapping():
    p = _make_provider([
        _reply_start("u1", "user"),
        TextBlockDeltaEvent(reply_id="u1", block_id="b1", delta="查询天气"),
        _reply_end("u1"),
    ])
    await p._start_pump()
    got = await _drain(p, 3)
    assert [e.type for e in got] == ["speech_started", "transcript", "speech_stopped"]


@pytest.mark.asyncio
async def test_require_confirm_mapping():
    tc = ToolCallBlock(id="call_1", name="database_query", input='{"query": "x"}')
    p = _make_provider([RequireUserConfirmEvent(reply_id="r1", tool_calls=[tc])])
    await p._start_pump()
    ev = (await _drain(p, 1))[0]
    assert ev.type == "tool.confirm_required"
    assert ev.data["confirm_id"] == "call_1"
    assert ev.data["tool_name"] == "database_query"
    assert ev.data["arguments"] == {"query": "x"}
    assert "call_1" in p._pending_confirms


@pytest.mark.asyncio
async def test_send_text_unsupported_emits_error():
    p = _make_provider([])
    p._agent.model.supports_text_input = False
    await p._start_pump()
    await p.send_text("hi")
    ev = (await _drain(p, 1))[0]
    assert ev.type == "error"
    assert "不支持文本输入" in ev.data["message"]
