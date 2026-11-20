# -*- coding: utf-8 -*-
"""submit 成功后 orchestrator 不写完成事件（team_done 由 RunCollector 负责）。"""
import asyncio
from types import SimpleNamespace

from app.ai.team.orchestrator import AgentScopeOrchestrator
from app.ai.msg_utils import text_msg


class Recorder:
    def __init__(self):
        self.events = []

    def record(self, **kw):
        self.events.append(kw)


def test_submit_emits_no_completion_event(monkeypatch):
    rec = Recorder()
    orch = AgentScopeOrchestrator(
        db=None, team=SimpleNamespace(team_code="t", id=1),
        run=SimpleNamespace(run_id="r1"), event_svc=rec)

    async def fake_create():
        return True

    monkeypatch.setattr(orch, "create_team", fake_create)
    orch._leader = SimpleNamespace(
        reply=lambda msg: asyncio.sleep(0, result=text_msg("leader", "assistant", "结论")))
    result = asyncio.run(orch.submit("任务"))
    assert result == "结论"
    assert all(e.get("event_type") not in ("TEAM_COMPLETE", "team_done") for e in rec.events)


def test_member_agent_reads_system_prompt_column(monkeypatch):
    """成员构建必须读 AgentConfig.system_prompt 列（既有列名），不得读不存在的 sys_prompt。"""
    import app.ai.tool_manager.manager as tool_manager
    import app.ai.team.orchestrator as orch_mod

    captured = {}

    class FakeAgent:
        def __init__(self, **kw):
            captured.update(kw)

    monkeypatch.setattr(orch_mod, "Agent", FakeAgent)
    monkeypatch.setattr(tool_manager, "build_toolkit", lambda db, keys: None)

    fake_config = SimpleNamespace(system_prompt="你是报价审核员。", tools=[])

    class FakeQuery:
        def filter(self, *a, **kw):
            return self

        def first(self):
            return fake_config

    orch = AgentScopeOrchestrator(
        db=SimpleNamespace(query=lambda model: FakeQuery()),
        team=SimpleNamespace(team_code="t", id=1),
        run=SimpleNamespace(run_id="r1"), event_svc=Recorder())
    member = SimpleNamespace(agent_config_id=1, role_name="报价审核员")
    orch._create_member_agent(member, model=object())
    assert captured["system_prompt"] == "你是报价审核员。"