"""SOPEngine — SOP 主干顺序编排引擎。

spec: docs/design/sop-assistant-mode-design.md §4.1~§4.5、§5.1

职责边界（保持单一）：
- 只做**宏观编排**：按 ``SOPDefinition.steps`` 顺序推进里程碑；
- 单步内部的"反复打磨"委托给 ``GoalStep``（``loop=goal``，§4.5）；
- 验收（AI/human）与 attempt 重试、AWAITING 挂起 / resume 恢复由本引擎负责；
- **不关心** LLM 怎么调、事件怎么落库——执行与验证以可注入的异步函数传入，
  Agent 层（``agent.py``）负责装配真实 LLM 与事件总线。

产出事件复用现有契约（§5.2）：``step`` / ``artifact`` / ``engine_decision`` /
``hitl_pause`` / ``hitl_resume`` / ``completed`` / ``error``。
"""
from __future__ import annotations

from typing import AsyncGenerator, Awaitable, Callable, Optional

from loguru import logger

from .goal_step import GoalStep
from .schemas import (
    SOPDefinition,
    SOPPhase,
    SOPRunState,
    SOPStepDef,
    StepRuntimeState,
    Verdict,
    VerifierType,
    init_run_state,
    LoopMode,
)

# 执行器：给定步骤定义与输入文本，产出该步交付内容
ExecutorFn = Callable[[SOPStepDef, str], Awaitable[str]]
# 验证器：给定步骤定义与产出内容，给出通过与否及反馈
VerifierFn = Callable[[SOPStepDef, str], Awaitable[Verdict]]


class SOPEngine:
    """SOP 顺序执行引擎。全部状态集中在 ``self.state``，可序列化后恢复。"""

    def __init__(
        self,
        definition: SOPDefinition,
        executor: ExecutorFn,
        verifier: Optional[VerifierFn] = None,
        state: Optional[SOPRunState] = None,
    ) -> None:
        self.definition = definition
        self.executor = executor
        self.verifier = verifier
        if state is None:
            self.state = init_run_state(definition)
        else:
            # 定义被改动（步骤增删）后旧状态无法对齐 —— 显式失败而非静默错位
            if len(state.steps) != len(definition.steps):
                raise ValueError(
                    "SOP 定义步骤数"
                    f"({len(definition.steps)})与持久化状态"
                    f"({len(state.steps)})不一致，无法恢复"
                )
            self.state = state

    # ── 持久化 / 恢复（§4.8）───────────────────────────────────────────────

    @classmethod
    def restore(
        cls,
        state_json: str,
        executor: ExecutorFn,
        verifier: Optional[VerifierFn] = None,
    ) -> "SOPEngine":
        """从持久化快照恢复；以快照内联的定义为准，避免模板改动导致错位。"""
        state = SOPRunState.model_validate_json(state_json)
        return cls(state.definition, executor, verifier=verifier, state=state)

    def snapshot(self) -> str:
        """导出可持久化的状态 JSON（存入消息 extra_data["sop_run"]）。"""
        return self.state.model_dump_json()

    # ── 主流程 ─────────────────────────────────────────────────────────────

    async def reply_stream(
        self,
        user_input: str = "",
        resume: Optional[dict] = None,
        execution_id: str = "",
    ) -> AsyncGenerator[dict, None]:
        """驱动 SOP 执行，逐步 yield 事件 dict。

        :param user_input: 首步输入（用户原始诉求）
        :param resume: 人工验收答复 ``{"confirmed": bool, "message": str}``；
            非空且当前处于 AWAITING 时先结算挂起，再从中断处续跑
        :param execution_id: 执行标识，随 ``completed`` 事件回传前端
        """
        if self.state.phase in (SOPPhase.COMPLETED, SOPPhase.FAILED):
            return

        try:
            if resume is not None:
                async for ev in self._apply_resume(resume):
                    yield ev

            while self.state.current_index < len(self.definition.steps):
                idx = self.state.current_index
                step = self.definition.steps[idx]
                st = self.state.steps[idx]

                if st.phase == SOPPhase.COMPLETED:
                    self.state.current_index += 1
                    continue

                # 已判失败的步骤不得被再次拉起（人工驳回达上限、恢复态异常等）
                if st.phase == SOPPhase.FAILED:
                    self.state.phase = SOPPhase.FAILED
                    yield {
                        "type": "error",
                        "data": {
                            "message": (
                                f"步骤「{step.subject}」失败："
                                f"{st.feedback or '超出最大尝试次数'}"
                            ),
                            "step_index": idx,
                        },
                    }
                    return

                self.state.phase = SOPPhase.RUNNING
                async for ev in self._run_step(idx, step, st, user_input):
                    yield ev

                if st.phase == SOPPhase.COMPLETED:
                    self._record_handover(step, st)
                    if step.artifact_key:
                        yield {
                            "type": "artifact",
                            "data": {
                                "key": step.artifact_key,
                                "title": step.subject,
                                "content": st.output or "",
                            },
                        }
                    self.state.current_index += 1
                    continue

                if st.phase == SOPPhase.AWAITING:
                    # 人工验收挂起：交出控制权，等待 resume 再次驱动
                    self.state.phase = SOPPhase.AWAITING
                    return

                if st.phase == SOPPhase.FAILED:
                    self.state.phase = SOPPhase.FAILED
                    yield {
                        "type": "error",
                        "data": {
                            "message": f"步骤「{step.subject}」失败：{st.feedback or '超出最大尝试次数'}",
                            "step_index": idx,
                        },
                    }
                    return

            self.state.phase = SOPPhase.COMPLETED
            yield {
                "type": "completed",
                "data": {"execution_id": execution_id, "sop_phase": "COMPLETED"},
            }
        except Exception as exc:  # noqa: BLE001 - 执行期异常统一收敛为 FAILED
            logger.exception(f"[SOP] 执行异常: {exc}")
            self.state.phase = SOPPhase.FAILED
            yield {"type": "error", "data": {"message": str(exc)}}

    # ── 单步 ───────────────────────────────────────────────────────────────

    async def _run_step(
        self,
        idx: int,
        step: SOPStepDef,
        st: StepRuntimeState,
        user_input: str,
    ) -> AsyncGenerator[dict, None]:
        """执行第 idx 步：运行 → 验收 → 落定终态。"""
        st.phase = SOPPhase.RUNNING
        st.attempt += 1
        st.goal_iter = 0
        yield self._step_event(st, "running")

        input_text = self._input_for(idx, user_input)

        # loop=goal 且非人工验收：委托 GoalStep 做"执行→验证→修订"微循环
        if step.loop == LoopMode.GOAL and step.verifier_type != VerifierType.HUMAN:
            goal = GoalStep(step, self.executor, self.verifier, st)
            async for ev in goal.run(input_text):
                yield ev
            if st.phase == SOPPhase.PENDING:
                # 微循环轮次用尽仍未通过 → 走 attempt 重试/失败判定
                self._fail_or_retry(step, st)
        else:
            st.output = await self.executor(step, input_text)
            async for ev in self._verify(step, st):
                yield ev

        yield self._step_event(st, self._status_of(st))

    async def _verify(
        self, step: SOPStepDef, st: StepRuntimeState
    ) -> AsyncGenerator[dict, None]:
        """按 verifier_type 验收当前产出。"""
        if step.verifier_type == VerifierType.NONE:
            st.phase = SOPPhase.COMPLETED
            st.feedback = None
            return

        if step.verifier_type == VerifierType.HUMAN:
            # 人工验收（§4.9）：不自动判定，挂起等前端答复
            st.phase = SOPPhase.AWAITING
            yield {
                "type": "hitl_pause",
                "data": {
                    "ui_hint": "verify",
                    "step_index": st.index,
                    "subject": step.subject,
                    "content": st.output or "",
                    "tool_calls": [],
                },
            }
            return

        if self.verifier is None:
            # 未装配 AI verifier 时不应静默判失败，显式记为通过并留痕
            logger.warning(f"[SOP] 步骤「{step.subject}」声明 AI 验收但未配置 verifier，视为通过")
            st.phase = SOPPhase.COMPLETED
            st.feedback = "未配置 AI 验收器，视为通过"
            return

        verdict = await self.verifier(step, st.output or "")
        yield {
            "type": "engine_decision",
            "data": {
                "passed": verdict.passed,
                "message": verdict.message,
                "step_index": st.index,
            },
        }
        st.feedback = verdict.message
        if verdict.passed:
            st.phase = SOPPhase.COMPLETED
        else:
            self._fail_or_retry(step, st)

    async def _apply_resume(self, resume: dict) -> AsyncGenerator[dict, None]:
        """结算挂起的人工验收答复，并把流程拉回 RUNNING。"""
        if self.state.phase != SOPPhase.AWAITING:
            return

        idx = self.state.current_index
        step = self.definition.steps[idx]
        st = self.state.steps[idx]
        confirmed = bool(resume.get("confirmed"))
        message = resume.get("message", "")

        yield {
            "type": "hitl_resume",
            "data": {"step_index": idx, "confirmed": confirmed, "message": message},
        }

        st.feedback = message or None
        if confirmed:
            st.phase = SOPPhase.COMPLETED
            self._record_handover(step, st)
            if step.artifact_key:
                yield {
                    "type": "artifact",
                    "data": {
                        "key": step.artifact_key,
                        "title": step.subject,
                        "content": st.output or "",
                    },
                }
            self.state.current_index += 1
        else:
            self._fail_or_retry(step, st)
            # 驳回达上限时整流程同步失败，避免主循环把该步重新拉起
            if st.phase == SOPPhase.FAILED:
                self.state.phase = SOPPhase.FAILED

        yield self._step_event(st, self._status_of(st))

        if self.state.phase != SOPPhase.FAILED:
            self.state.phase = SOPPhase.RUNNING

    # ── 辅助 ───────────────────────────────────────────────────────────────

    def _fail_or_retry(self, step: SOPStepDef, st: StepRuntimeState) -> None:
        """验收未通过：未达 max_attempts 则回到 PENDING 重试，否则 FAILED。"""
        if st.attempt >= max(1, step.max_attempts):
            st.phase = SOPPhase.FAILED
        else:
            st.phase = SOPPhase.PENDING

    def _input_for(self, idx: int, user_input: str) -> str:
        """首步用用户原始输入，后续步骤以上一步产出为输入。"""
        if idx == 0:
            return user_input
        prev = self.state.steps[idx - 1]
        return prev.output or user_input

    def _record_handover(self, step: SOPStepDef, st: StepRuntimeState) -> None:
        self.state.handovers.append(
            {"from": step.subject, "content": st.output or ""}
        )

    @staticmethod
    def _status_of(st: StepRuntimeState) -> str:
        return {
            SOPPhase.COMPLETED: "done",
            SOPPhase.AWAITING: "awaiting",
            SOPPhase.FAILED: "failed",
            SOPPhase.RUNNING: "running",
            SOPPhase.PENDING: "pending",
        }[st.phase]

    @staticmethod
    def _step_event(st: StepRuntimeState, status: str) -> dict:
        """步骤事件，content 与前端 UnifiedStep 字段对齐（§5.2）。"""
        return {
            "type": "step",
            "data": {
                "phase": st.phase.value,
                "event_type": "step",
                "title": st.subject,
                "seq": st.index,
                "status": status,
                "attempt": st.attempt,
                "max_attempts": st.max_attempts,
                "verifier_type": st.verifier_type,
                "feedback": st.feedback,
                "exec_mode": st.exec_mode,
                "group_id": st.group_id,
            },
        }
