"""ExecutionEventService 分级写入单测：delta 不入库、envelope 新列、别名归一。"""
import asyncio

from app.schemas.agent.event_types import EventCategory, EventEnvelope, EventLevel
from app.ai.services.execution_event_service import ExecutionEventService


def _env(event_type: str, category: str, levels, content=None, **kw) -> EventEnvelope:
    return EventEnvelope(
        execution_id="exec-1", trace_id="t-1", event_type=event_type,
        category=category, levels=list(levels), content=content or {},
        source="test", **kw,
    )


def test_record_envelope_skips_db_for_stream_only():
    """delta 类（仅 STREAM）不入队列。"""
    async def main():
        svc = ExecutionEventService(execution_id="exec-1", trace_id="t-1")
        svc.record_envelope(_env("text_chunk", EventCategory.TEXT, [EventLevel.STREAM],
                                 {"delta": "hi"}))
        assert svc._queue.empty()
    asyncio.run(main())


def test_record_envelope_enqueues_db_level_with_new_columns():
    async def main():
        svc = ExecutionEventService(execution_id="exec-1", trace_id="t-1")
        svc.record_envelope(_env(
            "tool_call", EventCategory.TOOL, [EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
            {"tool_name": "Bash"}, reply_id="r1", tool_call_id="tc1", ui_hint="timeline",
        ))
        assert svc._queue.qsize() == 1
        row = svc._queue.get_nowait()
        assert row["event_type"] == "tool_call"
        assert row["level"] == EventLevel.DB
        assert row["category"] == "tool"
        assert row["reply_id"] == "r1"
        assert row["tool_call_id"] == "tc1"
        assert row["ui_hint"] == "timeline"
        assert row["event_version"] == 1
        assert row["sequence"] == 0
    asyncio.run(main())


def test_legacy_record_normalizes_and_filters():
    """旧 record('text') 归一化为 text_chunk → 仅 STREAM → 不落库。"""
    async def main():
        svc = ExecutionEventService(execution_id="exec-1", trace_id="t-1")
        svc.record(event_type="text", content={"delta": "x"})
        assert svc._queue.empty()
        # team_start 仍落库（存量行为保留）
        svc.record(event_type="team_start", content={"team_code": "t"})
        assert svc._queue.qsize() == 1
        row = svc._queue.get_nowait()
        assert row["event_type"] == "team_start"
        assert row["category"] == "team"
        assert EventLevel.DB in row["levels"]
    asyncio.run(main())


def test_batch_write_sync_maps_new_columns(monkeypatch):
    """批量写 ORM 时新列映射正确（Fake ORM + Fake Session）。"""
    import app.ai.services.execution_event_service as svc_mod

    created = []

    class FakeEventORM:
        def __init__(self, **kw):
            self.__dict__.update(kw)
            created.append(self)

    class FakeDB:
        def add(self, obj): pass
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass

    monkeypatch.setattr(svc_mod, "AgentExecutionEvent", FakeEventORM)
    monkeypatch.setattr(svc_mod, "SessionLocal", lambda: FakeDB())

    async def _make_svc():
        # 在事件循环内构造，避免同步上下文 get_event_loop 的 DeprecationWarning
        return ExecutionEventService(execution_id="exec-2")

    svc = asyncio.run(_make_svc())
    svc._batch_write_sync([{
        "execution_id": "exec-2", "trace_id": "t", "event_type": "interrupted",
        "sequence": 3, "content": {}, "source": "agent", "source_id": None,
        "metadata": {}, "level": 1, "category": "interrupt",
        "reply_id": "r9", "block_id": None, "tool_call_id": None,
        "interrupt_reason": "timeout", "ui_hint": "timeline", "event_version": 1,
    }])
    assert created[0].event_type == "interrupted"
    assert created[0].reply_id == "r9"
    assert created[0].interrupt_reason == "timeout"
    assert created[0].level == 1
