"""P1 后端单测：SSEHandler / AgentScopeEventAdapter / EventBus→SSEHandler 转发。

不依赖 PG，验证统一 SSE 通道的核心逻辑（spec §4.4 / §5.2 / P1.1/P1.2/P1.4）。
"""
from __future__ import annotations

import json

from app.ai.events.adapter import AgentScopeEventAdapter, envelope_to_sse
from app.ai.events.bus import EventBus
from app.ai.events.sse_handler import SSEHandler, get_sse_handler
from app.schemas.agent.event_types import EventEnvelope, EventLevel, route_of


def _env(eid: str, etype: str, levels, content=None, **kw) -> EventEnvelope:
    route = route_of(etype)
    return EventEnvelope(
        execution_id=eid, event_type=etype,
        category=route.category, levels=list(levels),
        content=content or {}, **kw,
    )


def test_sse_handler_assigns_sequence_and_replays_after_seq():
    h = SSEHandler()
    eid = "exec-seq"
    e1 = _env(eid, "text_chunk", [EventLevel.STREAM], {"delta": "a"})
    e2 = _env(eid, "text_chunk", [EventLevel.STREAM], {"delta": "b"})
    h.capture(e1)
    h.capture(e2)
    assert e1.sequence == 1
    assert e2.sequence == 2

    # 断线重放：只补拉 seq > 1 的事件
    replay, q = h.subscribe(eid, last_seq=1)
    assert [e.sequence for e in replay] == [2]
    assert replay[0].content["delta"] == "b"

    # 实时推送
    e3 = _env(eid, "tool_call", [EventLevel.DB, EventLevel.STREAM, EventLevel.UI], {})
    h.capture(e3)
    got = q.get_nowait()
    assert got.sequence == 3
    h.unsubscribe(eid, q)


def test_sse_handler_replay_none_last_seq_returns_all():
    h = SSEHandler()
    eid = "exec-all"
    for i in range(3):
        h.capture(_env(eid, "progress", [EventLevel.STREAM], {"i": i}))
    replay, q = h.subscribe(eid, last_seq=None)
    assert [e.sequence for e in replay] == [1, 2, 3]
    h.unsubscribe(eid, q)


def test_envelope_to_sse_format_has_id_event_data():
    e = EventEnvelope(
        sequence=5, execution_id="x", event_type="text_chunk",
        category="text", levels=[EventLevel.STREAM], content={"delta": "hi"},
    )
    s = envelope_to_sse(e)
    assert s.startswith("id: 5\nevent: text_chunk\ndata: ")
    assert s.endswith("\n\n")
    payload = json.loads(s.split("data: ", 1)[1])
    assert payload["content"]["delta"] == "hi"
    assert payload["event_type"] == "text_chunk"


def test_envelope_to_sse_excludes_none_fields():
    e = EventEnvelope(
        sequence=1, execution_id="x", event_type="progress",
        category="runtime", levels=[EventLevel.STREAM], content={"stage": "s"},
    )
    s = envelope_to_sse(e)
    payload = json.loads(s.split("data: ", 1)[1])
    assert "reply_id" not in payload
    assert "block_id" not in payload


def test_bus_forwards_stream_envelope_to_sse_handler():
    bus = EventBus()  # 无 event_service → 仅 SSE 分发，不写 DB
    eid = "exec-bus-fwd"
    env = _env(eid, "progress", [EventLevel.STREAM, EventLevel.UI], {"stage": "x"})
    bus.publish(env)

    handler = get_sse_handler()
    replay, q = handler.subscribe(eid, last_seq=None)
    assert len(replay) == 1
    assert replay[0].event_type == "progress"
    handler.unsubscribe(eid, q)


def test_bus_does_not_forward_non_stream_envelope():
    bus = EventBus()
    eid = "exec-bus-no"
    # 仅 DB 级事件不应进入 SSE 通道
    env = _env(eid, "reply_start", [EventLevel.DB], {})
    bus.publish(env)
    handler = get_sse_handler()
    replay, q = handler.subscribe(eid, last_seq=None)
    assert replay == []
    handler.unsubscribe(eid, q)


def test_adapter_dict_event_to_envelope():
    adapter = AgentScopeEventAdapter(execution_id="exec-adapter")
    envs = adapter.to_envelopes_from_dict({
        "type": "progress", "data": {"stage": "thinking"},
    })
    assert len(envs) == 1
    env = envs[0]
    assert env.event_type == "progress"
    assert env.content == {"stage": "thinking"}
    route = route_of("progress")
    assert set(env.levels) == set(route.levels)
    assert env.ui_hint == route.ui_hint


def test_adapter_handle_publishes_to_bus():
    bus = EventBus()
    eid = "exec-adapter-bus"
    adapter = AgentScopeEventAdapter(execution_id=eid, bus=bus)
    adapter.handle({"type": "progress", "data": {"stage": "x"}})

    handler = get_sse_handler()
    replay, q = handler.subscribe(eid, last_seq=None)
    assert len(replay) == 1
    handler.unsubscribe(eid, q)
