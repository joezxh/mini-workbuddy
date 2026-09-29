"""GoalStep — ``loop=goal`` 步骤内部的"执行 → 验证 → 修订"微循环。

spec: docs/design/sop-assistant-mode-design.md §4.5

适用场景：单步没有固定子结构、需要"反复打磨直到通过"（写正文、写代码、
推理论证等）。宏观多里程碑仍由 ``SOPEngine`` 顺序推进，本类只负责
**单步内部**的迭代收敛。

每一轮迭代产出：
- ``step`` 事件（``branch_label="goal-iter-k"``）标注第几轮
- ``engine_decision`` 事件（verifier 结论 ``{passed, message}``）
"""
from __future__ import annotations

from typing import AsyncGenerator, Awaitable, Callable, Optional

from .schemas import (
    SOPStepDef,
    SOPPhase,
    StepRuntimeState,
    Verdict,
    VerifierType,
)

ExecutorFn = Callable[[SOPStepDef, str], Awaitable[str]]
VerifierFn = Callable[[SOPStepDef, str], Awaitable[Verdict]]


class GoalStep:
    """把单个步骤包装成「Goal 微循环」。

    迭代结束后的终态写在 ``StepRuntimeState.phase`` 上：
    - ``COMPLETED``：某轮验证通过；
    - ``PENDING``：所有轮次用尽仍未通过，交由引擎按 ``max_attempts`` 决定重试或失败。
    """

    def __init__(
        self,
        step: SOPStepDef,
        executor: ExecutorFn,
        verifier: Optional[VerifierFn],
        state: StepRuntimeState,
    ) -> None:
        self.step = step
        self.executor = executor
        self.verifier = verifier
        self.st = state

    async def run(self, input_text: str) -> AsyncGenerator[dict, None]:
        """执行微循环，逐轮 yield 事件。"""
        st = self.st
        base_input = input_text
        draft = input_text
        max_iters = max(1, self.step.goal_max_iters)

        for it in range(1, max_iters + 1):
            st.goal_iter = it

            output = await self.executor(self.step, draft)
            st.output = output
            yield self._iter_event(it, "running")

            # 无 verifier / 配置了 none：一轮即通过（仅做迭代执行）
            if self.step.verifier_type == VerifierType.NONE or self.verifier is None:
                st.phase = SOPPhase.COMPLETED
                st.feedback = None
                yield self._iter_event(it, "done")
                return

            verdict = await self.verifier(self.step, output)
            yield {
                "type": "engine_decision",
                "data": {
                    "passed": verdict.passed,
                    "message": verdict.message,
                    "step_index": st.index,
                    "goal_iter": it,
                },
            }
            st.feedback = verdict.message

            if verdict.passed:
                st.phase = SOPPhase.COMPLETED
                yield self._iter_event(it, "done")
                return

            draft = self._revise(base_input, draft, output, verdict)

        # 轮次用尽仍未通过：交回引擎走 attempt 重试 / 失败判定
        st.phase = SOPPhase.PENDING
        yield self._iter_event(st.goal_iter, "pending")

    def _revise(
        self, base_input: str, draft: str, output: str, verdict: Verdict
    ) -> str:
        """按 verifier 意见构造下一轮输入。

        ``goal_verifier_reset_ctx=True`` 时每轮回到原始输入（只带上轮产出与意见），
        避免上下文被历史修订污染；False 时在草稿上持续累积。
        """
        base = base_input if self.step.goal_verifier_reset_ctx else draft
        return (
            f"{base}\n\n[上一轮产出]\n{output}\n\n"
            f"[审核意见]\n{verdict.message}\n\n"
            "请根据审核意见修订后重新产出完整结果。"
        )

    def _iter_event(self, iteration: int, status: str) -> dict:
        st = self.st
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
                "branch_label": f"goal-iter-{iteration}",
                "goal_iter": iteration,
            },
        }
