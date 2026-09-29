"""SOPEngine 单元测试（纯离线，注入假 executor/verifier，不依赖 LLM）。

spec: docs/design/sop-assistant-mode-design.md §4.2 / §4.5 / §4.8 / §5.1
"""
from __future__ import annotations

import asyncio
from typing import List, Optional

import pytest

from app.ai.sop import (
    SOPDefinition,
    SOPPhase,
    SOPStepDef,
    SOPRunState,
    Verdict,
)
from app.ai.sop.engine import SOPEngine


async def _drain(gen) -> List[dict]:
    """把异步事件生成器抽干为列表，便于同步断言。"""
    return [event async for event in gen]


def _run(gen) -> List[dict]:
    """避免依赖 pytest-asyncio 的运行模式配置，显式起一个事件循环。"""
    return asyncio.run(_drain(gen))


def _executor(recorder: Optional[list] = None, outputs: Optional[dict] = None):
    """构造记录调用、可定制产出的执行器。"""

    async def _exec(step: SOPStepDef, text: str) -> str:
        if recorder is not None:
            recorder.append((step.subject, text))
        if outputs and step.subject in outputs:
            return outputs[step.subject]
        return f"out::{step.subject}"

    return _exec


def _verifier(verdicts: List[Verdict]):
    """按调用顺序返回预设结论的验收器；用尽后默认通过。"""
    it = iter(verdicts)

    async def _verify(step: SOPStepDef, output: str) -> Verdict:
        try:
            return next(it)
        except StopIteration:
            return Verdict(passed=True, message="默认通过")

    return _verify


def _types(events: List[dict]) -> List[str]:
    return [e["type"] for e in events]


# ── 顺序推进 ────────────────────────────────────────────────────────────────


def test_sequential_steps_run_in_order_and_complete():
    """无验收步骤：按顺序推进，逐步交接，末了产出 completed。"""
    definition = SOPDefinition(
        name="顺序流程",
        steps=[
            SOPStepDef(subject="A", description="产出 A"),
            SOPStepDef(subject="B", description="产出 B"),
        ],
    )
    recorder: list = []
    engine = SOPEngine(definition, _executor(recorder))

    events = _run(engine.reply_stream("用户原始输入"))

    assert "completed" in _types(events)
    assert engine.state.phase == SOPPhase.COMPLETED
    assert [s.phase for s in engine.state.steps] == [SOPPhase.COMPLETED] * 2
    # 首步拿到用户输入，后续步骤以上一步产出为输入
    assert recorder[0] == ("A", "用户原始输入")
    assert recorder[1] == ("B", "out::A")
    # 交接摘要落库
    assert [h["from"] for h in engine.state.handovers] == ["A", "B"]


def test_step_events_carry_seq_and_status():
    """step 事件需带 seq / status，供前端 TimelineFlowPlayer 排序渲染（§5.2）。"""
    definition = SOPDefinition(
        name="t", steps=[SOPStepDef(subject="唯一", description="d")]
    )
    events = _run(SOPEngine(definition, _executor()).reply_stream("x"))

    steps = [e for e in events if e["type"] == "step"]
    assert [s["data"]["seq"] for s in steps] == [0, 0]
    assert steps[-1]["data"]["status"] == "done"


# ── AI 验收与重试 ───────────────────────────────────────────────────────────


def test_ai_verifier_reject_then_accept_increments_attempt():
    """验收驳回 → attempt++ 重试；通过后该步 COMPLETED（§5.1）。"""
    definition = SOPDefinition(
        name="t",
        steps=[
            SOPStepDef(
                subject="写稿", description="稿件合格", verifier_type="ai", max_attempts=3
            )
        ],
    )
    verifier = _verifier(
        [Verdict(passed=False, message="缺数据"), Verdict(passed=True, message="ok")]
    )
    engine = SOPEngine(definition, _executor(), verifier)

    events = _run(engine.reply_stream("x"))

    decisions = [e for e in events if e["type"] == "engine_decision"]
    assert len(decisions) == 2
    assert decisions[0]["data"]["passed"] is False
    assert decisions[1]["data"]["passed"] is True
    assert engine.state.steps[0].attempt == 2
    assert engine.state.steps[0].phase == SOPPhase.COMPLETED
    assert "completed" in _types(events)


def test_exceeding_max_attempts_fails_the_run():
    """attempt 达上限仍不通过 → 整流程 FAILED 且产出 error 事件。"""
    definition = SOPDefinition(
        name="t",
        steps=[
            SOPStepDef(
                subject="写稿", description="稿件合格", verifier_type="ai", max_attempts=2
            )
        ],
    )
    always_fail = _verifier([Verdict(passed=False, message="不合格")] * 5)
    engine = SOPEngine(definition, _executor(), always_fail)

    events = _run(engine.reply_stream("x"))

    assert engine.state.phase == SOPPhase.FAILED
    assert engine.state.steps[0].attempt == 2
    error = next(e for e in events if e["type"] == "error")
    assert "写稿" in error["data"]["message"]


def test_declaration_without_verifier_is_treated_as_passed():
    """声明 AI 验收但未装配 verifier：不静默判失败，显式放行并留痕。"""
    definition = SOPDefinition(
        name="t",
        steps=[SOPStepDef(subject="A", description="d", verifier_type="ai")],
    )
    engine = SOPEngine(definition, _executor(), verifier=None)

    events = _run(engine.reply_stream("x"))

    assert engine.state.steps[0].phase == SOPPhase.COMPLETED
    assert "视为通过" in (engine.state.steps[0].feedback or "")
    assert "completed" in _types(events)


# ── 人工验收挂起 / 恢复 ─────────────────────────────────────────────────────


def test_human_verifier_suspends_then_resume_confirmed():
    """人工验收：产出 hitl_pause 挂起；答复通过后从下一步继续（§4.9）。"""
    definition = SOPDefinition(
        name="t",
        steps=[
            SOPStepDef(subject="方案", description="方案可用", verifier_type="human"),
            SOPStepDef(subject="落地", description="执行完成"),
        ],
    )
    engine = SOPEngine(definition, _executor())

    events = _run(engine.reply_stream("x"))

    pause = next(e for e in events if e["type"] == "hitl_pause")
    assert pause["data"]["ui_hint"] == "verify"
    assert engine.state.phase == SOPPhase.AWAITING
    assert engine.state.current_index == 0

    resumed = _run(engine.reply_stream(resume={"confirmed": True, "message": "通过"}))

    assert engine.state.phase == SOPPhase.COMPLETED
    assert [s.phase for s in engine.state.steps] == [SOPPhase.COMPLETED] * 2
    assert "completed" in _types(resumed)


def test_human_verifier_rejection_returns_feedback():
    """人工驳回：带上原因走重试；超出 max_attempts 则 FAILED。"""
    definition = SOPDefinition(
        name="t",
        steps=[
            SOPStepDef(
                subject="方案", description="方案可用", verifier_type="human", max_attempts=1
            )
        ],
    )
    engine = SOPEngine(definition, _executor())

    _run(engine.reply_stream("x"))
    events = _run(engine.reply_stream(resume={"confirmed": False, "message": "缺预算"}))

    assert engine.state.steps[0].feedback == "缺预算"
    assert engine.state.steps[0].phase == SOPPhase.FAILED
    assert engine.state.phase == SOPPhase.FAILED
    assert any(e["type"] == "error" for e in events)


def test_resume_before_finish_persists_and_restores():
    """快照导出 → 新引擎恢复 → 续跑，状态不丢（§4.8）。"""
    definition = SOPDefinition(
        name="t",
        steps=[
            SOPStepDef(subject="方案", description="方案可用", verifier_type="human"),
            SOPStepDef(subject="落地", description="执行完成"),
        ],
    )
    first = SOPEngine(definition, _executor())
    _run(first.reply_stream("原始需求"))
    snapshot = first.snapshot()

    restored = SOPEngine.restore(snapshot, _executor())
    assert restored.state.current_index == 0
    assert restored.state.phase == SOPPhase.AWAITING

    events = _run(restored.reply_stream(resume={"confirmed": True}))

    assert restored.state.phase == SOPPhase.COMPLETED
    assert "completed" in _types(events)


def test_restore_rejects_mismatched_definition():
    """步骤增删后旧状态无法对齐 → 显式 ValueError，不静默错位。"""
    state = SOPRunState(
        definition=SOPDefinition(name="t", steps=[SOPStepDef(subject="A")]),
        steps=[],
    )
    changed = SOPDefinition(
        name="t", steps=[SOPStepDef(subject="A"), SOPStepDef(subject="B")]
    )
    with pytest.raises(ValueError):
        SOPEngine(changed, _executor(), state=state)


# ── loop=goal 微循环 ────────────────────────────────────────────────────────


def test_goal_loop_iterates_until_verifier_passes():
    """loop=goal：单步内部多轮"执行→验证→修订"，产出 goal-iter-k 分支事件（§4.5）。"""
    definition = SOPDefinition(
        name="t",
        steps=[
            SOPStepDef(
                subject="打磨正文",
                description="正文达标",
                verifier_type="ai",
                loop="goal",
                goal_max_iters=4,
            )
        ],
    )
    verifier = _verifier(
        [
            Verdict(passed=False, message="论据不足"),
            Verdict(passed=True, message="达标"),
        ]
    )
    engine = SOPEngine(definition, _executor(), verifier)

    events = _run(engine.reply_stream("x"))

    branches = [
        e["data"].get("branch_label") for e in events if e["type"] == "step"
    ]
    assert "goal-iter-1" in branches
    assert "goal-iter-2" in branches
    assert engine.state.steps[0].phase == SOPPhase.COMPLETED
    assert engine.state.steps[0].goal_iter == 2
    assert "completed" in _types(events)


def test_goal_loop_exhausted_hands_back_to_attempt_retry():
    """goal 轮次用尽仍未通过 → 交回引擎按 max_attempts 重试/失败。"""
    definition = SOPDefinition(
        name="t",
        steps=[
            SOPStepDef(
                subject="打磨正文",
                description="正文达标",
                verifier_type="ai",
                loop="goal",
                goal_max_iters=2,
                max_attempts=1,
            )
        ],
    )
    always_fail = _verifier([Verdict(passed=False, message="仍不达标")] * 10)
    engine = SOPEngine(definition, _executor(), always_fail)

    events = _run(engine.reply_stream("x"))

    assert engine.state.steps[0].phase == SOPPhase.FAILED
    assert engine.state.phase == SOPPhase.FAILED
    assert any(e["type"] == "error" for e in events)


def test_goal_loop_revision_feeds_verifier_message_back():
    """修订轮的输入需带上 verifier 意见，否则下一轮无从改进。"""
    recorder: list = []
    definition = SOPDefinition(
        name="t",
        steps=[
            SOPStepDef(
                subject="打磨",
                description="d",
                verifier_type="ai",
                loop="goal",
                goal_max_iters=3,
            )
        ],
    )
    verifier = _verifier(
        [Verdict(passed=False, message="缺案例"), Verdict(passed=True, message="ok")]
    )
    engine = SOPEngine(definition, _executor(recorder), verifier)

    _run(engine.reply_stream("原始需求"))

    assert len(recorder) == 2
    assert "缺案例" in recorder[1][1]
    assert "审核意见" in recorder[1][1]


# ── 产物 ────────────────────────────────────────────────────────────────────


def test_artifact_key_emits_artifact_event():
    """配置 artifact_key 的步骤完成后产出 artifact 事件（§5.2）。"""
    definition = SOPDefinition(
        name="t",
        steps=[
            SOPStepDef(subject="报告", description="d", artifact_key="report"),
            SOPStepDef(subject="收尾", description="d"),
        ],
    )
    events = _run(SOPEngine(definition, _executor()).reply_stream("x"))

    artifacts = [e for e in events if e["type"] == "artifact"]
    assert len(artifacts) == 1
    assert artifacts[0]["data"]["key"] == "report"
    assert artifacts[0]["data"]["content"] == "out::报告"
