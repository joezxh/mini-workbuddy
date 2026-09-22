"""网关增量：ping 回客户端、interrupt 调 provider.interrupt、
tool.confirm 上行路由、voice_config 平台匹配。"""
import json

import pytest

from app.duplex.voice.voice_config import _platform_matches


class StubProvider:
    def __init__(self):
        self.interrupted = False
        self.confirmed = []

    async def interrupt(self):
        self.interrupted = True

    async def resolve_confirm(self, confirm_id, approved):
        self.confirmed.append((confirm_id, approved))


def test_platform_matches():
    assert _platform_matches("openai", "openai") is True
    assert _platform_matches("openai", "DashScope") is False
    assert _platform_matches("dashscope", "openai") is False
    assert _platform_matches(None, "s2s") is False


@pytest.mark.asyncio
async def test_ping_replies_to_client():
    from app.duplex.voice.websocket_gateway import _handle_control_frame
    from app.duplex.voice.turn_state import TurnState

    provider = StubProvider()
    sent = []

    class FakeWs:
        async def send_text(self, raw):
            sent.append(json.loads(raw))

    await _handle_control_frame({"type": "ping"}, provider, TurnState(), "s1",
                                FakeWs())
    assert sent == [{"type": "pong"}]


@pytest.mark.asyncio
async def test_interrupt_calls_provider(monkeypatch):
    from app.duplex.voice import websocket_gateway as gw
    from app.duplex.voice.turn_state import TurnState

    # 轮次持久化走真实 DB，单测中打桩（本用例只验证仲裁与透传）
    monkeypatch.setattr(gw, "mark_interrupted", lambda *a, **k: None)
    monkeypatch.setattr(gw, "bump_generation", lambda *a, **k: None)

    provider = StubProvider()
    turn = TurnState()
    turn.turn_id = "t1"
    turn.on_speech_started()
    await gw._handle_control_frame({"type": "interrupt"}, provider, turn, "s1")
    assert provider.interrupted is True
    assert turn.generation >= 1


@pytest.mark.asyncio
async def test_tool_confirm_routed():
    from app.duplex.voice.websocket_gateway import _handle_control_frame
    from app.duplex.voice.turn_state import TurnState

    provider = StubProvider()
    await _handle_control_frame(
        {"type": "tool.confirm",
         "data": {"confirm_id": "c1", "approved": True}},
        provider, TurnState(), "s1")
    assert provider.confirmed == [("c1", True)]
