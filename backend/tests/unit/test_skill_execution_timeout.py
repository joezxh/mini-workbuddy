"""SkillExecutionService.execute() 超时熔断与主记录生命周期单测（Fake 全家桶，无 DB）。"""
import asyncio
import types

import pytest

import app.ai.skills.execution as exec_mod
from app.ai.skills.execution import SkillExecutionService, SkillEvent


class FakeBus:
    def __init__(self):
        self.published = []
        self.execution_id = "exec-test"
        self.trace_id = "trace-test"

    def publish(self, env):
        self.published.append(env)


class FakeAgent:
    """慢 Agent：reply_stream 每个事件 sleep，制造超时。"""
    def __init__(self, events, delay=0.0):
        self._events = events
        self._delay = delay

    async def reply_stream(self, inputs):
        for e in self._events:
            await asyncio.sleep(self._delay)
            yield e


class FakeRecords:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def _call(db, *a, **kw):
            self.calls.append((name, kw))
        return _call


def _patch_all(monkeypatch, svc, *, events, delay, timeout):
    monkeypatch.setattr(svc, "_load_skill", lambda name: asyncio.sleep(0, result={
        "name": name, "description": "d", "markdown": "# m", "dir": None,
        "allowed_tools": None, "source": "test",
    }))
    monkeypatch.setattr(svc, "_build_toolkit", lambda *a, **kw: object())
    monkeypatch.setattr(svc, "_build_system_prompt", lambda *a, **kw: "sys")
    monkeypatch.setattr(svc, "_build_model", lambda *a, **kw: object())
    monkeypatch.setattr(svc, "_create_agent", lambda *a, **kw: FakeAgent(events, delay))
    monkeypatch.setattr(svc, "timeout", timeout)
    monkeypatch.setattr(exec_mod, "record_execution_start", lambda db, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_done", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_failed", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "SessionLocal", lambda: None)
    monkeypatch.setattr(exec_mod, "EventBus", lambda event_service=None: FakeBus())


def test_timeout_emits_interrupt_events_and_marks_cancelled(monkeypatch):
    svc = SkillExecutionService(timeout=0.1)
    _patch_all(monkeypatch, svc,
               events=[types.SimpleNamespace()], delay=0.3, timeout=0.1)

    records = FakeRecords()
    monkeypatch.setattr(exec_mod, "record_execution_failed", lambda db, *a, **kw: records.calls.append(("failed", kw)))

    async def run():
        return [e async for e in svc.execute("demo", "hi")]

    evts = asyncio.run(run())
    # SSE 输出含超时 error
    assert any(e.type == "error" and "超时" in e.data["message"] for e in evts)
    # 主记录走 failed 路径且带 interrupt_reason=timeout
    failed = [c for c in records.calls if c[0] == "failed"]
    assert failed and failed[0][1]["interrupt_reason"] == "timeout"


def test_normal_run_calls_start_and_done(monkeypatch):
    from agentscope.event import ReplyStartEvent, ReplyEndEvent
    svc = SkillExecutionService(timeout=5)
    _patch_all(monkeypatch, svc,
               events=[ReplyStartEvent(reply_id="r1", session_id="s", name="demo", role="assistant"),
                       ReplyEndEvent(reply_id="r1", session_id="s")],
               delay=0.0, timeout=5)

    calls = []
    monkeypatch.setattr(exec_mod, "record_execution_start", lambda db, **kw: calls.append(("start", kw)))
    monkeypatch.setattr(exec_mod, "record_execution_done", lambda db, *a, **kw: calls.append(("done", kw)))

    async def run():
        return [e async for e in svc.execute("demo", "hi")]

    evts = asyncio.run(run())
    kinds = [c[0] for c in calls]
    assert kinds == ["start", "done"]
    assert any(e.type == "done" for e in evts)
