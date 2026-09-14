"""T15: ToolCallHandler + VoiceOwnership 测试。"""
import asyncio

import pytest

from app.duplex.voice.tool_call_handler import ToolCallHandler
from app.duplex.voice.voice_ownership import VoiceOwnership


class FakeAgent:
    async def call_tool(self, name: str, args):
        return {"echo": name, "args": args}


def test_handle_success():
    handler = ToolCallHandler()
    res = asyncio.run(handler.handle("search_law", {"q": "合同法"}, agent=FakeAgent()))
    assert res["ok"] is True
    assert res["name"] == "search_law"
    assert res["result"] == {"echo": "search_law", "args": {"q": "合同法"}}


def test_handle_no_agent_fails_gracefully():
    handler = ToolCallHandler()
    res = asyncio.run(handler.handle("x", {}))
    assert res["ok"] is False
    assert res["error"] == "no agent bound"


def test_replay_reruns_failed_calls():
    handler = ToolCallHandler(agent=FakeAgent())
    failed = [{"name": "x", "arguments": {"a": 1}}]
    res = handler.replay(failed)
    assert res[0]["ok"] is True
    assert res[0]["name"] == "x"


def test_ownership_grant_and_current():
    ow = VoiceOwnership()
    ow.grant("party_a", turn_id="t1")
    assert ow.current() == "party_a"
    ow.grant("party_b", turn_id="t2")
    assert ow.current() == "party_b"


def test_ownership_revoke_non_holder_returns_false():
    ow = VoiceOwnership()
    ow.grant("party_a", turn_id="t1")
    ow.grant("party_b", turn_id="t2")
    assert ow.revoke("party_a") is False
    assert ow.current() == "party_b"


def test_ownership_revoke_holder_clears():
    ow = VoiceOwnership()
    ow.grant("party_a", turn_id="t1")
    ow.grant("party_b", turn_id="t2")
    assert ow.revoke("party_b") is True
    assert ow.current() is None
    assert ow.is_granted("party_b") is False
