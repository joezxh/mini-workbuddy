"""P1.2 / P1.4 集成测试：/stream（SSE + Last-Event-ID 重连）与 /events（DB 回放）。

直接经 EventBus 发布统一信封（STREAM 级 → SSEHandler 环形缓冲）验证 /stream；
直接落库 AgentExecutionEvent 行验证 /events 回放与流式格式一致（spec §4.4 / §6.3）。
"""
from __future__ import annotations

from app.ai.events.bus import EventBus
from app.models.agent.agent_execution_event import AgentExecutionEvent
from app.schemas.agent.event_types import EventEnvelope, route_of


def _publish(eid: str, etype: str, content: dict) -> None:
    route = route_of(etype)
    # 用独立 EventBus（无 event_service）→ 仅走 SSE 分发，不写 DB，隔离测试
    EventBus().publish(
        EventEnvelope(
            execution_id=eid,
            event_type=etype,
            category=route.category,
            levels=list(route.levels),
            content=content,
        )
    )


def _count_events(lines) -> int:
    return sum(1 for ln in lines if ln.startswith("event:"))


def test_stream_delivers_unified_envelopes(client):
    eid = "it-stream-1"
    _publish(eid, "text_chunk", {"delta": "你好"})
    _publish(eid, "tool_call", {"name": "search"})

    with client.stream("GET", f"/api/v1/agents/executions/{eid}/stream?replay_only=1") as resp:
        assert resp.status_code == 200
        # replay_only 回放后即关闭连接，iter_lines 自然结束，无需手动 break
        seen = [line for line in resp.iter_lines()]
    body = "\n".join(seen)
    assert "event: text_chunk" in body
    assert "event: tool_call" in body
    assert "id: 1" in body
    assert "id: 2" in body
    # data 为统一信封 JSON，含 event_type / levels / content
    assert '"event_type": "text_chunk"' in body or '"event_type":"text_chunk"' in body


def test_stream_respects_after_seq_replay(client):
    eid = "it-stream-replay"
    _publish(eid, "text_chunk", {"delta": "AAA"})  # seq 1
    _publish(eid, "text_chunk", {"delta": "BBB"})  # seq 2

    # after_seq=1 → 仅补拉 seq 2
    with client.stream(
        "GET", f"/api/v1/agents/executions/{eid}/stream?after_seq=1&replay_only=1"
    ) as resp:
        seen = [line for line in resp.iter_lines()]
    body = "\n".join(seen)
    assert "BBB" in body
    assert "AAA" not in body


def test_stream_last_event_id_header_reconnect(client):
    eid = "it-stream-lei"
    _publish(eid, "text_chunk", {"delta": "FIRST"})

    # 携带 Last-Event-ID: 1 → 重连时不重复已收到的 seq 1
    with client.stream(
        "GET", f"/api/v1/agents/executions/{eid}/stream?replay_only=1",
        headers={"Last-Event-ID": "1"},
    ) as resp:
        seen = [line for line in resp.iter_lines()]
    body = "\n".join(seen)
    assert "FIRST" not in body


def test_events_replay_from_db_matches_stream_format(client, db):
    eid = "it-events-1"
    db.add(AgentExecutionEvent(
        execution_id=eid, sequence=1, event_type="text_chunk",
        category="text", level=2, content={"delta": "a"}, ui_hint="markdown",
    ))
    db.add(AgentExecutionEvent(
        execution_id=eid, sequence=2, event_type="tool_call",
        category="tool", level=1, content={"name": "x"}, ui_hint="timeline",
    ))
    db.commit()

    resp = client.get(f"/api/v1/agents/executions/{eid}/events")
    assert resp.status_code == 200
    data = resp.json()
    assert data["execution_id"] == eid
    assert len(data["events"]) == 2

    ev0 = data["events"][0]
    assert ev0["sequence"] == 1
    assert ev0["event_type"] == "text_chunk"
    # levels 由 event_type 经 route_of 还原，与流式一致
    assert ev0["levels"] == sorted(route_of("text_chunk").levels)
    assert ev0["ui_hint"] == "markdown"
    assert ev0["content"] == {"delta": "a"}

    ev1 = data["events"][1]
    assert ev1["event_type"] == "tool_call"
    assert ev1["levels"] == sorted(route_of("tool_call").levels)


def test_events_after_seq_filters(db, client):
    eid = "it-events-after"
    for seq in (1, 2, 3):
        db.add(AgentExecutionEvent(
            execution_id=eid, sequence=seq, event_type="progress",
            category="runtime", level=2, content={"i": seq}, ui_hint="timeline",
        ))
    db.commit()

    resp = client.get(f"/api/v1/agents/executions/{eid}/events?after_seq=1")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert [e["sequence"] for e in events] == [2, 3]
