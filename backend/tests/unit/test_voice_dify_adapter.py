"""T20: DifyAdapter 真实接入测试（不联网，mock DifyModelWrapper）。"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.duplex.voice.agent_adapter import (
    AgentRegistry,
    DifyAdapter,
)


def test_dify_adapter_registered_at_import():
    """import 即注册，agent_id 默认 'dify'。"""
    assert AgentRegistry.exists("dify")
    assert AgentRegistry.get("dify").agent_id == "dify"


def test_dify_adapter_implements_protocol():
    a = DifyAdapter(flow_code="f1")
    assert hasattr(a, "run_voice_turn")
    assert hasattr(a, "call_tool")
    assert a.engine_code == "dify"


def test_dify_adapter_blocking_response():
    """阻塞模式：直接取 ChatResponse.content。"""
    class FakeResponse:
        content = "调解建议文本"

    async def run():
        adapter = DifyAdapter(flow_code="f1")

        async def client(messages):
            return FakeResponse()

        with patch.object(adapter, "_ensure_client", return_value=client):
            return await adapter.run_voice_turn(text="你好")

    out = asyncio.run(run())
    assert out["text"] == "调解建议文本"
    assert out["audio_b64"] is None


def test_dify_adapter_streaming_response():
    """流式模式：聚合 async generator 的每个 chunk。"""
    async def run():
        adapter = DifyAdapter(flow_code="f1", stream=True)

        async def fake_stream():
            for tok in ("你好", "，请问", "有什么纠纷"):
                chunk = MagicMock()
                chunk.content = tok
                yield chunk

        async def client(messages):
            return fake_stream()

        with patch.object(adapter, "_ensure_client", return_value=client):
            return await adapter.run_voice_turn(text="hi")

    out = asyncio.run(run())
    assert out["text"] == "你好，请问有什么纠纷"


def test_dify_adapter_history_becomes_messages():
    """history + 当前文本被组装为 Msg 列表（最后一条为 user）。"""
    captured = {}

    async def run():
        adapter = DifyAdapter(flow_code="f1")
        fake_resp = MagicMock()
        fake_resp.content = "ok"

        async def client(messages):
            captured["messages"] = messages
            return fake_resp

        with patch.object(adapter, "_ensure_client", return_value=client):
            return await adapter.run_voice_turn(
                text="当前问题",
                history=[{"role": "user", "content": "上一轮"}, {"role": "assistant", "content": "上轮回答"}],
            )

    asyncio.run(run())
    msgs = captured["messages"]
    assert len(msgs) == 3
    # agentscope 2.0：content 为 list[ContentBlock]
    assert msgs[-1].content[0].text == "当前问题"
    assert msgs[0].content[0].text == "上一轮"
    assert msgs[-1].role == "user"
