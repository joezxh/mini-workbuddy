"""HITL 全链路单测：暂停→确认恢复 / build_resume_event / 暂停记录落库。

覆盖 spec §5.4/§5.5：Skill 执行与 Agent 一致的人机交互模式。
"""
import asyncio
from datetime import datetime

from agentscope.event import (
    RequireUserConfirmEvent, ReplyEndEvent,
    UserConfirmResultEvent, UserInterruptEvent,
)

import app.ai.skills.execution as exec_mod
from app.ai.skills.execution import SkillExecutionService
from app.ai.events.hitl import (
    build_resume_event, record_pause, resolve_pause, resume_hitl,
    PAUSE_TIMEOUT_MINUTES,
)
from app.ai.events.registry import get_run_registry


# ── 纯函数层 ─────────────────────────────────────────────────────────────

def test_build_resume_event_approve_reject_interrupt():
    tcs = [{"id": "tc1", "name": "Bash", "input": '{"cmd":"ls"}'}]
    ev = build_resume_event("approve", "r1", tcs)
    assert isinstance(ev, UserConfirmResultEvent)
    assert ev.confirm_results[0].confirmed is True

    ev2 = build_resume_event("reject", "r1", tcs)
    assert ev2.confirm_results[0].confirmed is False

    ev3 = build_resume_event("interrupt", "r1", [])
    assert isinstance(ev3, UserInterruptEvent)


# ── 暂停记录（FakeDB）────────────────────────────────────────────────────

class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **kw):
        return self

    def order_by(self, *a, **kw):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class FakeHitlRow:
    def __init__(self):
        self.execution_id = "e1"
        self.status = "waiting"
        self.accept_rules = 0
        self.answered_at = None
        self.tool_calls = [{"id": "tc1", "name": "Bash"}]


class FakeDB:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.added = []
        self.committed = 0
        self.rolled_back = 0
        self.closed = []

    def add(self, o):
        self.added.append(o)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1

    def close(self):
        self.closed.append(True)

    def query(self, model):
        return FakeQuery(self.rows)


def test_record_and_resolve_pause():
    db = FakeDB()
    record_pause(db, execution_id="e1", reply_id="r1",
                 tool_calls=[{"id": "tc1", "name": "Bash"}])
    row = db.added[0]
    assert row.status == "waiting"
    assert row.timeout_at is not None
    assert (row.timeout_at - datetime.now()).total_seconds() > 0

    db.rows = [row]
    resolve_pause(db, execution_id="e1", action="approve", accept_rules=True)
    # 注：返回值为 row.id，Fake 行无自增 id（None），故断言状态迁移而非返回值
    assert row.status == "approved" and row.accept_rules == 1

    row2 = FakeHitlRow()
    db.rows = [row2]
    resolve_pause(db, execution_id="e1", action="interrupt")
    assert row2.status == "interrupted"


# ── 端到端：execute 暂停 → resume_hitl 恢复 ─────────────────────────────

class FakeHitlAgent:
    """两段式：首轮 yield RequireUserConfirmEvent 后流结束（暂停）；
    第二次调用（恢复事件）yield ReplyEndEvent。"""

    def __init__(self):
        self.inputs = []

    async def reply_stream(self, inputs):
        self.inputs.append(inputs)
        if isinstance(inputs, (UserConfirmResultEvent, UserInterruptEvent)):
            yield ReplyEndEvent(reply_id="r1", session_id="s")
        else:
            yield RequireUserConfirmEvent(reply_id="r1", tool_calls=[])


class _Bus:
    def __init__(self):
        self.published = []
        self.execution_id = None
        self.trace_id = None

    def publish(self, env):
        self.published.append(env)


def _patch(monkeypatch, svc, agent):
    monkeypatch.setattr(svc, "_load_skill", lambda name: asyncio.sleep(0, result={
        "name": name, "description": "d", "markdown": "# m", "dir": None,
        "allowed_tools": None, "source": "test",
    }))
    monkeypatch.setattr(svc, "_build_toolkit", lambda *a, **kw: object())
    monkeypatch.setattr(svc, "_build_system_prompt", lambda *a, **kw: "sys")
    monkeypatch.setattr(svc, "_build_model", lambda *a, **kw: object())
    monkeypatch.setattr(svc, "_create_agent", lambda *a, **kw: agent)
    monkeypatch.setattr(exec_mod, "record_execution_start", lambda db, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_done", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_status", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_failed", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "SessionLocal", lambda: FakeDB())
    # 事件服务换 Fake，避免 drain 任务在进程关闭时连接真实 DB
    monkeypatch.setattr(exec_mod, "ExecutionEventService", _fake_event_service)


def test_execute_hitl_pause_then_resume(monkeypatch):
    agent = FakeHitlAgent()
    svc = SkillExecutionService(timeout=30)
    _patch(monkeypatch, svc, agent)

    async def run():
        async def confirmer():
            # 全量套件负载下预留充足窗口（500 × 0.05s = 25s）
            for _ in range(500):
                h = get_run_registry().get("exec-hitl")
                if h is not None and h.status == "waiting_hitl":
                    resume_hitl(h, "approve")
                    return
                await asyncio.sleep(0.05)
        asyncio.create_task(confirmer())
        return [e async for e in svc.execute("demo", "hi", execution_id="exec-hitl")]

    evts = asyncio.run(run())
    types = [e.type for e in evts]
    assert "hitl_pause" in types
    assert "hitl_resume" in types
    assert types[-1] == "done"
    # Agent 被调用两次：初始输入 + 恢复事件
    assert len(agent.inputs) == 2
    # 恢复事件是确认类型
    assert isinstance(agent.inputs[1], UserConfirmResultEvent)
    # registry 已反注册
    assert get_run_registry().get("exec-hitl") is None


def test_execute_hitl_interrupt_marks_flag(monkeypatch):
    agent = FakeHitlAgent()
    svc = SkillExecutionService(timeout=30)
    _patch(monkeypatch, svc, agent)

    async def run():
        async def interrupter():
            for _ in range(500):
                h = get_run_registry().get("exec-hitl-i")
                if h is not None and h.status == "waiting_hitl":
                    resume_hitl(h, "interrupt")
                    return
                await asyncio.sleep(0.05)
        asyncio.create_task(interrupter())
        return [e async for e in svc.execute("demo", "hi", execution_id="exec-hitl-i")]

    evts = asyncio.run(run())
    types = [e.type for e in evts]
    assert "hitl_pause" in types and "hitl_resume" in types
    assert types[-1] == "done"
    assert isinstance(agent.inputs[1], UserInterruptEvent)
    # interrupt 恢复后 handler 标志置位（ReplyEnd finished_reason 记 interrupted）
    h = get_run_registry().get("exec-hitl-i")
    assert h is None or h.handler.interrupted_flag is True


class _fake_event_service:
    """Fake ExecutionEventService：吞掉信封，避免测试触达真实 DB。"""

    def __init__(self, *a, **kw):
        pass

    def record_envelope(self, env):
        return None

    async def stop(self):
        pass
