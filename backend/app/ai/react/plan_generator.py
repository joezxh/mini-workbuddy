"""ReAct 计划生成器 — LLM 驱动的计划生成、反思评估、计划调整。

复用 app.ai.research.llm 的 llm_json / llm_complete 调用基础设施，
保持与 ResearchOrchestrator 一致的 LLM 调用模式。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.ai.research.llm import llm_json, llm_complete
from app.ai.react.orchestrator import PlanStep, ExecutionPlan

logger = logging.getLogger(__name__)


# ── Prompt 模板 ────────────────────────────────────────────────────────

_PROMPT_GENERATE_PLAN = """你是一个任务规划专家。用户的目标如下：
<goal>{goal}</goal>

可用的工具：
<tools>{tool_descriptions}</tools>

可用的技能：
<skills>{skill_descriptions}</skills>

请将目标分解为不超过 {max_steps} 个具体、可执行的步骤。
每个步骤应明确：
1. 步骤标题
2. 具体描述（需要做什么）
3. 使用的工具或技能（如有）

输出 JSON：
{{"steps": [{{"title": "...", "description": "...", "tool": "tool_name or null", "skill": "skill_name or null"}}]}}"""

_PROMPT_REFLECT = """你是任务执行的质量评估官。

当前步骤：{step_title}
步骤描述：{step_description}
执行结果：{result}
用户原始目标：{goal}

请评估：
1. 该步骤是否达到预期？(satisfied: true/false)
2. 是否需要调整后续计划？(needs_adjust: true/false)
3. 如需调整，具体建议是什么？

输出 JSON：
{{"satisfied": true, "needs_adjust": false, "reason": "...", "suggestions": []}}"""

_PROMPT_ADJUST = """你是任务规划专家。原计划执行过程中发现需要调整。

用户原始目标：{goal}

当前计划：
{current_plan}

已完成的步骤及结果：
{completed_results}

反思评估：
{reflection}

请调整后续计划（保留未变更的步骤，修改/新增/跳过需要的步骤）。
输出 JSON：
{{"steps": [{{"title": "...", "description": "...", "tool": "tool_name or null", "skill": "skill_name or null"}}]}}"""


# ── PlanGenerator ──────────────────────────────────────────────────────

class PlanGenerator:
    """LLM 驱动的计划生成与调整。"""

    def __init__(self, model_id: Optional[int] = None):
        self.model_id = model_id

    async def generate(
        self,
        goal: str,
        tools: Optional[List[dict]] = None,
        skills: Optional[List[dict]] = None,
        max_steps: int = 10,
    ) -> ExecutionPlan:
        """根据用户目标和可用工具/技能，生成执行计划。"""
        tool_descs = "\n".join(
            f"- {t.get('name', '')}: {t.get('description', '')}"
            for t in (tools or [])
        ) or "（无可用工具）"
        skill_descs = "\n".join(
            f"- {s.get('name', '')}: {s.get('description', '')}"
            for s in (skills or [])
        ) or "（无可用技能）"

        prompt = _PROMPT_GENERATE_PLAN.format(
            goal=goal,
            tool_descriptions=tool_descs,
            skill_descriptions=skill_descs,
            max_steps=max_steps,
        )
        try:
            result = await llm_json(prompt, self.model_id)
        except Exception as e:
            logger.error("计划生成失败: %s", e)
            raise

        steps = []
        for i, s in enumerate(result.get("steps", [])[:max_steps]):
            steps.append(PlanStep(
                id=f"step_{i + 1}",
                title=s.get("title", f"步骤 {i + 1}"),
                description=s.get("description", ""),
            ))
        return ExecutionPlan(goal=goal, steps=steps)

    async def reflect(
        self,
        step: PlanStep,
        result: str,
        goal: str,
    ) -> Dict[str, Any]:
        """评估步骤执行结果（深度反思模式）。"""
        prompt = _PROMPT_REFLECT.format(
            step_title=step.title,
            step_description=step.description,
            result=result[:2000],
            goal=goal,
        )
        try:
            return await llm_json(prompt, self.model_id)
        except Exception as e:
            logger.error("反思评估失败: %s", e)
            return {
                "satisfied": True,
                "needs_adjust": False,
                "reason": f"反思失败: {e}",
            }

    async def adjust(
        self,
        plan: ExecutionPlan,
        reflection: Dict[str, Any],
        goal: str,
    ) -> List[PlanStep]:
        """基于反思结果调整后续计划。"""
        current_plan_text = "\n".join(
            f"{s.id}: {s.title} [{s.status}] {s.description}"
            for s in plan.steps
        )
        completed_text = "\n".join(
            f"{s.id}: {s.title} → {s.result[:200]}"
            for s in plan.steps if s.status == "done"
        ) or "（无已完成步骤）"
        suggestions = reflection.get("suggestions", [])
        reflection_text = (
            f"原因: {reflection.get('reason', '')}\n"
            f"建议: {'; '.join(suggestions)}"
        )

        prompt = _PROMPT_ADJUST.format(
            goal=goal,
            current_plan=current_plan_text,
            completed_results=completed_text,
            reflection=reflection_text,
        )
        try:
            result = await llm_json(prompt, self.model_id)
        except Exception as e:
            logger.error("计划调整失败: %s", e)
            return plan.steps  # 失败时保持原计划

        new_steps = []
        for i, s in enumerate(result.get("steps", [])):
            new_steps.append(PlanStep(
                id=f"step_adj_{i + 1}",
                title=s.get("title", f"调整步骤 {i + 1}"),
                description=s.get("description", ""),
            ))
        return new_steps
