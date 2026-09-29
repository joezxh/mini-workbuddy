"""SOPAgent / AgentFactory 接入测试（离线，注入假 executor，不依赖 LLM）。

覆盖 spec §4.1（Agent 装配）、§4.8（状态快照持久化）、§4.9（人工验收恢复）。
"""
from __future__ import annotations

import asyncio
from typing import List

from app.ai.agent_factory import AgentFactory, ResearchAgent
from app.ai.sop.agent import SOPAgent
from app.ai.sop.schemas import SOPDefinition, SOPStepDef


async def _drain(gen) -> List[dict]:
    return [event async for event in gen]


def _run(gen) -> List[dict]:
    return asyncio.run(_drain(gen))


def _sop_agent(definition: SOPDefinition, executor=None, verifier=None) -> SOPAgent:
    async def _exec(step: SOPStepDef, text: str) -> str:
        return f"out::{step.subject}"

    return SOPAgent(
        db=None, definition=definition,
        executor=executor or _exec, verifier=verifier,
    )


def _human_then_auto() -> SOPDefinition:
    """首步人工验收、次步自动通过的 two-step 流程。"""
    return SOPDefinition(
        name="two-step",
        steps=[
            SOPStepDef(subject="方案", description="方案可用", verifier_type="human"),
            SOPStepDef(subject="落地", description="执行完成"),
        ],
    )


# ── 引擎复用（resume 正确性的前提）──────────────────────────────────────────


def test_engine_reused_across_resume_not_restarted():
    """引擎必须跨 resume 复用：否则流程会从头重跑，attempt 归位。"""
    agent = _sop_agent(_human_then_auto())

    _run(agent.reply_stream("原始需求"))
    assert agent.run_state["phase"] == "AWAITING"

    _run(agent.reply_stream(None, resume={"confirmed": True}))

    state = agent.run_state
    assert state["phase"] == "COMPLETED"
    # 首步只执行过一次；若引擎被重建，此处会变成 1 且状态错乱
    assert state["steps"][0]["attempt"] == 1
    assert [s["phase"] for s in state["steps"]] == ["COMPLETED", "COMPLETED"]


# ── 状态快照（§4.8）─────────────────────────────────────────────────────────


def test_run_state_none_before_execution():
    """未开始执行时不应伪造状态。"""
    assert _sop_agent(_human_then_auto()).run_state is None


def test_run_state_exposes_definition_and_resumable_json():
    """快照需含定义、阶段、各步状态与可恢复的 runStateJson。"""
    agent = _sop_agent(_human_then_auto())

    _run(agent.reply_stream("需求"))
    state = agent.run_state

    assert state["definition"]["name"] == "two-step"
    assert state["phase"] == "AWAITING"
    assert state["steps"][0]["subject"] == "方案"
    assert state["runStateJson"]

    # 用快照恢复出的引擎应停在同一位置
    from app.ai.sop.engine import SOPEngine

    async def _exec(step: SOPStepDef, text: str) -> str:
        return f"out::{step.subject}"

    restored = SOPEngine.restore(state["runStateJson"], _exec)
    assert restored.state.current_index == 0
    assert restored.state.phase.value == "AWAITING"


def test_last_state_json_matches_snapshot():
    agent = _sop_agent(_human_then_auto())
    _run(agent.reply_stream("需求"))
    assert agent.last_state_json == agent.run_state["runStateJson"]


# ── 人工验收恢复（§4.9）─────────────────────────────────────────────────────


def test_resume_rejection_records_reason_and_fails():
    """驳回原因需落到步骤 feedback，便于前端展示与下一轮修订。"""
    definition = SOPDefinition(
        name="t",
        steps=[
            SOPStepDef(
                subject="方案", description="方案可用",
                verifier_type="human", max_attempts=1,
            )
        ],
    )
    agent = _sop_agent(definition)

    _run(agent.reply_stream("需求"))
    _run(agent.reply_stream(None, resume={"confirmed": False, "message": "缺预算"}))

    state = agent.run_state
    assert state["steps"][0]["feedback"] == "缺预算"
    assert state["steps"][0]["phase"] == "FAILED"
    assert state["phase"] == "FAILED"


def test_resume_confirmed_continues_to_next_step():
    agent = _sop_agent(_human_then_auto())
    _run(agent.reply_stream("需求"))
    _run(agent.reply_stream(None, resume={"confirmed": True}))

    assert agent.run_state["phase"] == "COMPLETED"
    assert agent.run_state["steps"][1]["output"] == "out::落地"


# ── AgentFactory 装配（§4.1）────────────────────────────────────────────────


def test_factory_sop_by_template_id():
    agent = AgentFactory(db=None).create_agent(
        "sop", {"sop_template_id": "buffett_value_investing"}
    )
    assert isinstance(agent, SOPAgent)
    assert agent.definition.name == "巴菲特价值投资分析"


def test_factory_sop_by_source_and_fallback():
    factory = AgentFactory(db=None)

    research = factory.create_agent("sop", {"sop_source": "builtin:research"})
    assert research.definition.source == "builtin:research"

    # 未指定时回退内置思考模板，保证 session_type=sop 总有可用编排
    fallback = factory.create_agent("sop", {})
    assert fallback.definition.source == "builtin:thinking"


def test_factory_sop_by_inline_definition():
    agent = AgentFactory(db=None).create_agent(
        "sop",
        {
            "sop_definition": {
                "name": "临时流程",
                "steps": [{"subject": "一步", "description": "完成"}],
            }
        },
    )
    assert isinstance(agent, SOPAgent)
    assert len(agent.definition.steps) == 1


def test_factory_unknown_session_type_still_rejects():
    import pytest

    with pytest.raises(ValueError):
        AgentFactory(db=None).create_agent("no_such_mode", {})


# ── thinking / deep_research 下沉开关（§4.1）────────────────────────────────


def test_thinking_and_research_switch_to_sop_when_use_sop():
    factory = AgentFactory(db=None)

    thinking = factory.create_agent("thinking", {"use_sop": True})
    assert isinstance(thinking, SOPAgent)
    assert thinking.definition.source == "builtin:thinking"

    research = factory.create_agent("deep_research", {"use_sop": True})
    assert isinstance(research, SOPAgent)
    assert research.definition.source == "builtin:research"


def test_deep_research_default_keeps_legacy_orchestrator():
    """默认不得切换：ResearchOrchestrator 会真实联网检索，SOP 默认执行器尚不具备。"""
    agent = AgentFactory(db=None).create_agent("deep_research", {})
    assert isinstance(agent, ResearchAgent)
    assert not isinstance(agent, SOPAgent)
