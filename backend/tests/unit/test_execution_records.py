"""执行主记录（agent_execution 表）写入单测：start/done/failed/timeout 生命周期。"""
from datetime import datetime

from app.ai.skills.execution_records import (
    record_execution_start, record_execution_done, record_execution_failed,
)


class FakeExecutionRow:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **kw):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class FakeDB:
    """add/commit/rollback/查询记账。rows 通过 query() 暴露给被测函数。"""
    def __init__(self, rows=None):
        self.rows = rows or []
        self.added = []
        self.committed = 0
        self.rolled_back = 0

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1

    def query(self, model):
        return FakeQuery(self.rows)


def test_start_creates_running_row():
    db = FakeDB()
    record_execution_start(
        db, execution_id="e1", session_id=7, user_id=3, execution_mode="skill",
        target_id="my-skill", user_input="hi", metadata={"worker_skill": "my-skill"},
        trace_id="t1",
    )
    row = db.added[0]
    assert row.execution_id == "e1"
    assert row.status == "running"
    assert row.execution_mode == "skill"
    assert row.target_id == "my-skill"
    assert row.started_at is not None
    assert db.committed == 1


def test_done_updates_existing_row():
    row = FakeExecutionRow(execution_id="e1", status="running")
    db = FakeDB(rows=[row])
    record_execution_done(db, "e1", output="final text", latency_ms=123,
                          input_tokens=10, output_tokens=20, iterations=3)
    assert row.status == "completed"
    assert row.output == "final text"
    assert row.latency_ms == 123
    assert row.finished_reason == "completed"
    assert row.input_tokens == 10 and row.output_tokens == 20 and row.iterations == 3
    assert row.completed_at is not None


def test_failed_marks_error():
    row = FakeExecutionRow(execution_id="e2", status="running")
    db = FakeDB(rows=[row])
    record_execution_failed(db, "e2", error="boom", latency_ms=50)
    assert row.status == "failed"
    assert row.error == "boom"
    assert row.finished_reason == "error"


def test_timeout_marks_cancelled_interrupted():
    row = FakeExecutionRow(execution_id="e3", status="running")
    db = FakeDB(rows=[row])
    record_execution_failed(db, "e3", error="执行超时（timeout）", latency_ms=500,
                            interrupt_reason="timeout")
    assert row.status == "cancelled"
    assert row.finished_reason == "interrupted"
    assert row.interrupt_reason == "timeout"


def test_missing_row_is_noop_no_crash():
    db = FakeDB(rows=[])
    record_execution_done(db, "ghost", output="x")   # 不存在 → 静默跳过
    assert db.committed == 0
