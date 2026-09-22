"""SkillExecutionService.execute() 超时熔断与主记录生命周期单测（Fake 全家桶，无 DB）。"""
import asyncio
import types

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


def _patch_all(monkeypatch, svc, *, events, delay):
    """打全量 Fake 补丁；返回本用例内创建的 FakeBus 实例列表（供信封断言）。"""
    buses = []

    def _fake_bus(event_service=None):
        bus = FakeBus()
        buses.append(bus)
        return bus

    monkeypatch.setattr(svc, "_load_skill", lambda name: asyncio.sleep(0, result={
        "name": name, "description": "d", "markdown": "# m", "dir": None,
        "allowed_tools": None, "source": "test",
    }))
    monkeypatch.setattr(svc, "_build_toolkit", lambda *a, **kw: object())
    monkeypatch.setattr(svc, "_build_system_prompt", lambda *a, **kw: "sys")
    monkeypatch.setattr(svc, "_build_model", lambda *a, **kw: object())
    monkeypatch.setattr(svc, "_create_agent", lambda *a, **kw: FakeAgent(events, delay))
    monkeypatch.setattr(exec_mod, "record_execution_start", lambda db, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_done", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_failed", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "SessionLocal", lambda: None)
    monkeypatch.setattr(exec_mod, "EventBus", _fake_bus)
    # 事件服务换 Fake，避免 drain 任务在进程关闭时连接真实 DB
    monkeypatch.setattr(exec_mod, "ExecutionEventService", _fake_event_service)
    return buses


def test_timeout_emits_interrupt_events_and_marks_cancelled(monkeypatch):
    svc = SkillExecutionService(timeout=0.1)
    buses = _patch_all(monkeypatch, svc,
                       events=[types.SimpleNamespace()], delay=0.3)

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
    # 中断双信封：interrupt_requested + interrupted
    assert buses, "EventBus 未被实例化"
    assert {e.event_type for e in buses[-1].published} >= {"interrupt_requested", "interrupted"}


def test_normal_run_calls_start_and_done(monkeypatch):
    from agentscope.event import ReplyStartEvent, ReplyEndEvent
    svc = SkillExecutionService(timeout=5)
    _patch_all(monkeypatch, svc,
               events=[ReplyStartEvent(reply_id="r1", session_id="s", name="demo", role="assistant"),
                       ReplyEndEvent(reply_id="r1", session_id="s")],
               delay=0.0)

    calls = []
    monkeypatch.setattr(exec_mod, "record_execution_start", lambda db, **kw: calls.append(("start", kw)))
    monkeypatch.setattr(exec_mod, "record_execution_done", lambda db, *a, **kw: calls.append(("done", kw)))

    async def run():
        return [e async for e in svc.execute("demo", "hi")]

    evts = asyncio.run(run())
    kinds = [c[0] for c in calls]
    assert kinds == ["start", "done"]
    assert any(e.type == "done" for e in evts)


def test_client_disconnect_finalizes_record(monkeypatch):
    """GeneratorExit（SSE 客户端断连）路径：主记录仍被收尾（failed），不会永久 running。"""
    svc = SkillExecutionService(timeout=5)
    _patch_all(monkeypatch, svc,
               events=[types.SimpleNamespace() for _ in range(5)], delay=0.05)

    records = FakeRecords()
    monkeypatch.setattr(exec_mod, "record_execution_failed", lambda db, *a, **kw: records.calls.append(("failed", kw)))
    monkeypatch.setattr(exec_mod, "record_execution_done", lambda db, *a, **kw: records.calls.append(("done", kw)))
    monkeypatch.setattr(svc, "_record_metrics", lambda *a, **kw: records.calls.append(("metrics", a)))

    async def run():
        gen = svc.execute("demo", "hi")
        got = []
        # 消费到 progress（engine_decision / start / progress）即断：
        # Task 11 起 engine_decision 是首个事件，此处按类型等待而非按序号
        while not any(e.type == "progress" for e in got):
            evt = await asyncio.wait_for(gen.__anext__(), timeout=5)
            got.append(evt)
        # 模拟客户端断连：aclose() 在挂起的 yield 处抛 GeneratorExit
        await gen.aclose()
        return got

    got = asyncio.run(run())
    assert got and got[-1].type == "progress"
    kinds = [c[0] for c in records.calls]
    # 断连路径：主记录被收尾为 failed（且仅一次），并记录 metrics；不应记 done
    assert kinds.count("failed") == 1
    assert "done" not in kinds
    assert "metrics" in kinds


def test_skill_not_found_finalizes_and_closes(monkeypatch):
    """技能不存在早退路径：主记录 failed + metrics + DB 会话关闭，不泄漏。"""
    svc = SkillExecutionService(timeout=5)
    buses = _patch_all(monkeypatch, svc, events=[], delay=0.0)
    monkeypatch.setattr(svc, "_load_skill", lambda name: asyncio.sleep(0, result=None))

    records = FakeRecords()
    closed = []
    monkeypatch.setattr(exec_mod, "record_execution_failed", lambda db, *a, **kw: records.calls.append(("failed", kw)))
    monkeypatch.setattr(exec_mod, "SessionLocal", lambda: _FakeDB(closed))
    monkeypatch.setattr(svc, "_record_metrics", lambda *a, **kw: records.calls.append(("metrics", a)))

    async def run():
        return [e async for e in svc.execute("missing", "hi")]

    evts = asyncio.run(run())
    assert any(e.type == "error" and "技能不存在" in e.data["message"] for e in evts)
    kinds = [c[0] for c in records.calls]
    assert kinds.count("failed") == 1
    assert "done" not in kinds
    assert "metrics" in kinds
    assert closed == [True]  # DB 会话已关闭
    assert buses and any(
        e.event_type == "error" for e in buses[-1].published
    )


class _FakeDB:
    def __init__(self, closed):
        self._closed = closed

    def close(self):
        self._closed.append(True)


class _fake_event_service:
    """Fake ExecutionEventService：吞掉信封，避免测试触达真实 DB。"""

    def __init__(self, *a, **kw):
        pass

    def record_envelope(self, env):
        return None

    async def stop(self):
        pass
