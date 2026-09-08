"""ReActOrchestrator — Plan → Execute → Reflect → Adjust 循环编排器。

设计参考 ResearchOrchestrator 的 emit 闭包模式：
子方法无法直接 yield（yield 是语句关键字），故通过 pending_out 列表缓冲，
再由外层 async generator 冲刷出去。

全局注册表 REACT_REGISTRY 供 HITL REST API 触达运行中的编排器实例。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

logger = logging.getLogger(__name__)

# 全局注册表：供 HITL REST API 触达运行中的编排器实例
REACT_REGISTRY: Dict[str, "ReActOrchestrator"] = {}


# ── 数据模型 ──────────────────────────────────────────────────────────

@dataclass
class PlanStep:
    """执行计划中的单个步骤。"""
    id: str               # "step_1", "step_2"...
    title: str            # 步骤标题
    description: str      # 详细描述
    status: str = "pending"  # pending / running / done / failed / skipped
    result: str = ""      # 执行结果摘要
    tool_calls: list = field(default_factory=list)  # [{name, input, output}]
    depth: int = 0        # 嵌套深度（0=外层, 1=Skill 内部...）

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "description": self.description,
            "status": self.status, "result": self.result,
            "tool_calls": self.tool_calls, "depth": self.depth,
        }


@dataclass
class ExecutionPlan:
    """ReAct 执行计划。"""
    goal: str             # 用户目标
    steps: List[PlanStep] = field(default_factory=list)
    current_step: int = 0
    status: str = "planning"  # planning / executing / reflecting / done / cancelled
    iteration: int = 0

    def to_dict(self) -> dict:
        return {
            "goal": self.goal, "steps": [s.to_dict() for s in self.steps],
            "current_step": self.current_step, "status": self.status,
            "iteration": self.iteration,
        }


# ── 核心编排器 ────────────────────────────────────────────────────────

class ReActOrchestrator:
    """ReAct 计划执行编排器 — Plan → Execute → Reflect → Adjust 循环。

    构造参数从 AgentConfig.react_config JSONB 读取：
    - max_iters: 最大迭代步数（默认 10）
    - timeout_seconds: 超时时间（默认 300s）
    - interaction_mode: auto / approve / confirm_steps
    - reflection_mode: lightweight / deep
    """

    def __init__(
        self,
        db: Any,
        model_id: Optional[int] = None,
        tools: Optional[list] = None,
        react_config: Optional[dict] = None,
        sys_prompt: str = "",
        skills: Optional[list] = None,
    ):
        self.db = db
        self.model_id = model_id
        self.tools = tools or []
        self.skills = skills or []
        self.sys_prompt = sys_prompt

        cfg = react_config or {}
        self.max_iters = cfg.get("max_iters", 10)
        self.timeout_seconds = cfg.get("timeout_seconds", 300)
        self.interaction_mode = cfg.get("interaction_mode", "auto")
        self.reflection_mode = cfg.get("reflection_mode", "lightweight")

        # HITL 暂停/恢复门控
        self._gate = asyncio.Event()
        self._gate.set()  # 默认不暂停
        self._cancelled = False
        self._run_id = str(uuid.uuid4())
        self._plan: Optional[ExecutionPlan] = None

    async def run(self, user_text: str) -> AsyncGenerator[dict, None]:
        """执行 ReAct 循环，yield SSE 兼容的 dict 事件。

        事件格式与 SSEBridge 消费协议一致：
        {"type": "react_start", ...} → SSEBridge → 前端 EventSource
        """
        REACT_REGISTRY[self._run_id] = self
        _start = time.perf_counter()

        try:
            yield {"type": "react_start", "goal": user_text,
                   "plan_summary": f"目标: {user_text[:100]}"}

            # ── 1. 生成计划 ─────────────────────────────────────────
            from app.ai.react.plan_generator import PlanGenerator
            generator = PlanGenerator(model_id=self.model_id)

            yield {"type": "react_progress", "message": "正在生成执行计划...",
                   "current_step": 0, "total_steps": 0}

            plan = await generator.generate(
                goal=user_text,
                tools=[{"name": getattr(t, "name", str(t)),
                        "description": getattr(t, "description", "")}
                       for t in self.tools] if self.tools else None,
                skills=[{"name": s, "description": s} for s in self.skills],
                max_steps=self.max_iters,
            )
            self._plan = plan
            yield {"type": "react_plan", "steps": [s.to_dict() for s in plan.steps]}

            # ── 2. approve 模式：等待用户确认计划 ────────────────────
            if self.interaction_mode == "approve":
                yield {"type": "react_confirm", "step_id": "__plan__",
                       "question": "是否批准执行此计划？",
                       "options": [
                           {"label": "批准执行", "value": "approve",
                            "description": "按计划执行"},
                           {"label": "取消", "value": "cancel",
                            "description": "取消执行"},
                       ],
                       "allow_custom": False}
                await self._gate.wait()
                if self._cancelled:
                    yield {"type": "react_done", "final_result": "用户已取消执行"}
                    return

            # ── 3. 逐步执行 ─────────────────────────────────────────
            plan.status = "executing"
            for idx, step in enumerate(plan.steps):
                if self._cancelled:
                    break

                # 超时检查
                elapsed = time.perf_counter() - _start
                if elapsed > self.timeout_seconds:
                    yield {"type": "react_error", "message": "执行超时",
                           "step_id": step.id}
                    break

                step.status = "running"
                plan.current_step = idx + 1
                plan.iteration = idx + 1

                yield {"type": "react_step_start", "step_id": step.id,
                       "title": step.title, "depth": step.depth}

                # 执行步骤
                result = await self._execute_step(step, user_text)
                step.result = result
                step.status = "done" if result and not result.startswith("执行失败") else "failed"

                yield {"type": "react_step_done", "step_id": step.id,
                       "title": step.title, "result": result[:500] if result else "",
                       "status": step.status}

                # ── 反思（deep 模式）────────────────────────────────
                if self.reflection_mode == "deep" and step.status == "done":
                    yield {"type": "react_progress",
                           "message": f"反思步骤: {step.title}...",
                           "current_step": idx + 1,
                           "total_steps": len(plan.steps)}
                    reflection = await generator.reflect(step, result, user_text)
                    yield {"type": "react_reflect", "step_id": step.id,
                           "assessment": reflection.get("reason", ""),
                           "adjusted": reflection.get("needs_adjust", False)}

                    if reflection.get("needs_adjust"):
                        new_steps = await generator.adjust(plan, reflection, user_text)
                        # 保留已完成步骤 + 替换后续步骤
                        plan.steps = plan.steps[:idx + 1] + new_steps
                        yield {"type": "react_plan_update",
                               "steps": [s.to_dict() for s in plan.steps]}

                # ── confirm_steps 模式：关键步骤暂停 ────────────────
                if (self.interaction_mode == "confirm_steps"
                        and idx < len(plan.steps) - 1):
                    yield {"type": "react_confirm", "step_id": step.id,
                           "question": f"步骤「{step.title}」已完成，是否继续？",
                           "options": [
                               {"label": "继续执行", "value": "continue"},
                               {"label": "跳过下一步", "value": "skip"},
                               {"label": "取消", "value": "cancel"},
                           ],
                           "allow_custom": True}
                    await self._gate.wait()
                    if self._cancelled:
                        break

            # ── 4. 汇总报告 ─────────────────────────────────────────
            plan.status = "done"
            completed = [s for s in plan.steps if s.status == "done"]
            summary_parts = [
                f"- {s.title}: {s.result[:200]}" for s in completed
            ]
            summary = (
                f"## 执行报告\n\n"
                f"目标: {user_text}\n\n"
                f"完成 {len(completed)}/{len(plan.steps)} 步:\n"
                + "\n".join(summary_parts)
            )

            yield {"type": "react_report", "summary": summary,
                   "steps_completed": len(completed), "result": summary}
            yield {"type": "react_done", "final_result": summary}

        except Exception as e:
            logger.exception("ReAct 执行异常: %s", e)
            yield {"type": "react_error", "message": str(e)}
        finally:
            REACT_REGISTRY.pop(self._run_id, None)

    async def _execute_step(self, step: PlanStep, goal: str) -> str:
        """执行单个步骤（通过 LLM 调用）。

        若步骤关联了工具或技能，后续可扩展为 AgentScope Agent 的工具调用模式。
        当前使用 llm_complete 直接生成执行结果。
        """
        from app.ai.research.llm import llm_complete

        tool_context = ""
        if step.tool_calls:
            tool_context = (
                "\n已有工具调用记录: "
                + json.dumps(step.tool_calls, ensure_ascii=False)
            )

        prompt = (
            f"你是一个任务执行助手。请完成以下步骤。\n\n"
            f"用户目标：{goal}\n\n"
            f"当前步骤：{step.title}\n"
            f"步骤描述：{step.description}"
            f"{tool_context}\n\n"
            f"请直接执行并给出结果。"
        )

        try:
            result = await llm_complete(prompt, self.model_id)
            return result
        except Exception as e:
            logger.error("步骤执行失败 [%s]: %s", step.id, e)
            return f"执行失败: {e}"

    # ── HITL 控制 ────────────────────────────────────────────────────

    def request_pause(self) -> None:
        """请求暂停（在下一次门控点生效）。"""
        self._gate.clear()
        logger.info("[ReAct %s] 已请求暂停", self._run_id[:8])

    def resume(self, answer: Optional[str] = None) -> None:
        """恢复执行。"""
        self._gate.set()
        logger.info("[ReAct %s] 已恢复, answer=%s", self._run_id[:8], answer)

    def cancel(self) -> None:
        """取消执行。"""
        self._cancelled = True
        self._gate.set()  # 解除门控让循环检测到 cancelled
        logger.info("[ReAct %s] 已取消", self._run_id[:8])

    def get_status(self) -> dict:
        """获取当前运行状态（供 REST API 消费）。"""
        return {
            "run_id": self._run_id,
            "plan": self._plan.to_dict() if self._plan else None,
            "cancelled": self._cancelled,
            "interaction_mode": self.interaction_mode,
        }
