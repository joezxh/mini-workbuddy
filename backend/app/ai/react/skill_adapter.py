"""Skill → FunctionTool 适配器 — 将 Skill 包装为 ReAct 可调用的工具。

当 ReAct 模式下需要使用 Skill 时，通过此适配器将 SkillExecutionService
包装为 AgentScope FunctionTool，注入到 ReActOrchestrator 的 Toolkit 中。
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def create_skill_tool(skill_name: str, skill_config: dict, db: Any) -> Any:
    """将 Skill 包装为 AgentScope FunctionTool。

    Args:
        skill_name: 技能名称
        skill_config: 技能配置 {"description": "...", "execution_mode": "direct|react"}
        db: SQLAlchemy Session

    Returns:
        FunctionTool 实例
    """
    from agentscope.tool import FunctionTool

    async def execute_skill(input: str) -> str:
        """执行技能并返回结果。

        Args:
            input: 传递给技能的输入文本。
        """
        from app.ai.skills.execution import SkillExecutionService

        service = SkillExecutionService()
        result_parts = []

        try:
            async for event in service.execute(
                skill_name=skill_name,
                user_message=input,
            ):
                if event.type == "done":
                    result_parts.append(event.data.get("result", ""))
                elif event.type == "text":
                    result_parts.append(event.data.get("content", ""))
        except Exception as e:
            logger.error("Skill %s 执行失败: %s", skill_name, e)
            return f"技能 {skill_name} 执行失败: {e}"

        return "\n".join(result_parts) if result_parts else f"技能 {skill_name} 无输出"

    return FunctionTool(
        execute_skill,
        name=f"skill_{skill_name}",
        description=skill_config.get("description", f"执行技能 {skill_name}"),
    )
