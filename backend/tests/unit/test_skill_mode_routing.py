"""Skill 执行模式动态切换单测：resolve/ENGINE_DECISION/引擎路由/unsupported。"""
import asyncio
import types

import app.ai.skills.execution as exec_mod
from app.ai.skills.execution import SkillExecutionService, resolve_execution_mode


def test_resolve_execution_mode():
    assert resolve_execution_mode("plan") == "plan"
    assert resolve_execution_mode("PLAN") == "plan"
    assert resolve_execution_mode(None) == "llm"
    assert resolve_execution_mode("bogus") == "llm"      # 非法回退 llm
    assert resolve_execution_mode("knowledge") == "knowledge"
    assert resolve_execution_mode("workflow") == "workflow"  # 合法但引擎未接入


class FakeModeAgent:
    """模拟 ReactAgent 等封装器：yield dict 事件。"""

    async def reply_stream(self, inputs):
        yield {"type": "progress", "data": {"stage": "planning"}}
        yield {"type": "done", "data": {"result": "ok"}}


class FakeDB:
    def add(self, o):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def query(self, model):
        return types.SimpleNamespace(filter=lambda *a, **kw: self,
                                     order_by=lambda *a, **kw: self,
                                     first=lambda: None)


class _Bus:
    def __init__(self):
        self.published = []
        self.execution_id = None
        self.trace_id = None

    def publish(self, env):
        self.published.append(env)


def _patch(monkeypatch, svc):
    monkeypatch.setattr(svc, "_load_skill", lambda name: asyncio.sleep(0, result={
        "name": name, "description": "d", "markdown": "# m", "dir": None,
        "allowed_tools": None, "source": "test",
    }))
    monkeypatch.setattr(svc, "_build_toolkit", lambda *a, **kw: object())
    monkeypatch.setattr(svc, "_build_system_prompt", lambda *a, **kw: "sys")
    monkeypatch.setattr(svc, "_build_model", lambda *a, **kw: object())
    monkeypatch.setattr(exec_mod, "record_execution_start", lambda db, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_done", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_status", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_failed", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "SessionLocal", lambda: FakeDB())
    # 事件服务换 Fake，避免 drain 任务在进程关闭时连接真实 DB
    monkeypatch.setattr(exec_mod, "ExecutionEventService", _fake_event_service)


def test_engine_decision_emitted_first(monkeypatch):
    svc = SkillExecutionService(timeout=5, db=FakeDB())
    _patch(monkeypatch, svc)

    async def run():
        return [e async for e in svc.execute("demo", "hi", execution_id="e-mode")]

    evts = asyncio.run(run())
    assert evts[0].type == "engine_decision"
    assert evts[0].data["engine_code"] == "skill:llm"
    assert evts[0].data["mode"] == "llm"


def test_workflow_mode_reports_unsupported(monkeypatch):
    svc = SkillExecutionService(timeout=5, db=FakeDB())
    _patch(monkeypatch, svc)

    async def run():
        return [e async for e in svc.execute("demo", "hi", execution_id="e-wf",
                                             execution_mode="workflow")]

    evts = asyncio.run(run())
    types_ = [e.type for e in evts]
    assert types_[0] == "engine_decision"
    assert types_[1] == "error"
    assert "暂不支持" in evts[1].data["message"]
    # unsupported 也是终态：done 不应出现
    assert "done" not in types_


def test_plan_mode_routes_to_factory_agent(monkeypatch):
    svc = SkillExecutionService(timeout=5, db=FakeDB())
    _patch(monkeypatch, svc)

    from app.ai import agent_factory
    monkeypatch.setattr(
        agent_factory.AgentFactory, "create_agent",
        lambda self, session_type, config: FakeModeAgent(),
    )

    async def run():
        return [e async for e in svc.execute("demo", "hi", execution_id="e-plan",
                                             execution_mode="plan")]

    evts = asyncio.run(run())
    types_ = [e.type for e in evts]
    assert types_[0] == "engine_decision" and evts[0].data["mode"] == "plan"
    assert "progress" in types_          # FakeModeAgent 的事件直通
    assert "done" in types_


class _fake_event_service:
    """Fake ExecutionEventService：吞掉信封，避免测试触达真实 DB。"""

    def __init__(self, *a, **kw):
        pass

    def record_envelope(self, env):
        return None

    async def stop(self):
        pass
