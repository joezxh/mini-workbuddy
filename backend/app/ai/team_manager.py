"""TeamManager — AgentScope Team API 封装，管理多 Agent 协作编排。

提供团队创建、执行和监控的统一接口。
底层使用 AgentScope 的 Agent 协作机制。
"""
from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Dict, Optional
from sqlalchemy.orm import Session

from app.ai.team.orchestrator import AgentScopeOrchestrator

logger = logging.getLogger(__name__)


class TeamManager:
    """AgentScope Team Manager - 简化版委托给 Orchestrator。"""

    def __init__(self, db: Session):
        self._db = db

    async def run_team(
        self,
        team_id: Optional[int],
        user_input: str,
        model_id: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """运行团队编排并流式 yield 事件。

        Args:
            team_id: 团队 ID
            user_input: 用户输入
            model_id: 模型 ID

        Yields:
            SSE 友好的 dict 事件
        """
        if not team_id:
            yield {"type": "error", "data": {"message": "未指定团队 ID"}}
            return

        # 加载团队信息
        from app.services.agent.agent_team_service import AgentTeamService
        svc = AgentTeamService(self._db)

        try:
            team = svc.get_team(team_id)
        except Exception as e:
            yield {"type": "error", "data": {"message": f"加载团队失败：{e}"}}
            return

        if team is None:
            yield {"type": "error", "data": {"message": f"团队 {team_id} 不存在"}}
            return

        members = svc.get_members(team_id)
        if not members:
            yield {"type": "error", "data": {"message": "团队没有成员"}}
            return

        team_code = getattr(team, "team_code", f"team_{team_id}")
        team_name = getattr(team, "name", team_code)

        yield {
            "type": "team_start",
            "data": {
                "team_code": team_code,
                "team_name": team_name,
                "member_count": len(members),
                "input": user_input,
            },
        }

        # 创建 Orchestrator 并执行
        try:
            orchestrator = AgentScopeOrchestrator(
                db=self._db,
                team=team,
                run=None,  # TODO: 创建运行记录
                model_id=model_id,
            )
            
            result = await orchestrator.submit(input_text=user_input)
            
            yield {
                "type": "team_done",
                "data": {
                    "team_code": team_code,
                    "team_name": team_name,
                    "result": result,
                },
            }
        except Exception as e:
            logger.exception(f"团队执行失败：{e}")
            yield {"type": "error", "data": {"message": str(e)}}
