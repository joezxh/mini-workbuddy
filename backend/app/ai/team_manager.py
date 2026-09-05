"""TeamManager — AgentScope Team API 封装，管理多 Agent 协作编排。

提供团队创建、执行和监控的统一接口。
底层使用 AgentScope 的 Agent 协作机制。

TODO: 完整实现待 AgentScope Team API 稳定后接入。
"""
from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class TeamManager:
    """管理 AgentScope Team 的创建和执行。

    职责：
    1. 从数据库加载团队配置与成员
    2. 创建 Leader + Worker Agent
    3. 运行团队编排并流式返回结果
    """

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
            yield {"type": "error", "data": {"message": f"加载团队失败: {e}"}}
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

        # TODO: 完整 AgentScope Team API 集成
        # 1. 为每个 member 创建 AgentScope Agent（从 agent_config 读取 sys_prompt）
        # 2. 创建 Leader Agent（协调者）
        # 3. Leader 分析用户输入，派发给合适的 Worker
        # 4. 收集 Worker 结果
        # 5. Leader 汇总并输出最终结论

        # 当前 stub：模拟团队执行过程
        for i, member in enumerate(members):
            agent_name = getattr(member, "role_name", None) or f"成员{i+1}"
            yield {
                "type": "team_worker_start",
                "data": {"agent_name": agent_name, "index": i},
            }
            # 模拟 worker 执行
            yield {
                "type": "team_worker_done",
                "data": {
                    "agent_name": agent_name,
                    "index": i,
                    "output": f"[{agent_name}] 已处理（stub 模式，待 AgentScope Team API 接入）",
                },
            }

        final_output = (
            f"团队 {team_name} 已完成分析（stub 模式）。\n\n"
            f"输入：{user_input[:200]}\n"
            f"参与成员：{len(members)} 人\n\n"
            "完整编排待 AgentScope Team API 接入后实现。"
        )

        yield {
            "type": "team_done",
            "data": {
                "team_code": team_code,
                "team_name": team_name,
                "result": final_output,
            },
        }

    def create_team_agents(
        self,
        members: List[Dict[str, Any]],
        model_id: Optional[int] = None,
    ) -> List[Any]:
        """为团队成员创建 AgentScope Agent 实例。

        Args:
            members: 团队成员列表（含 agent_config_id、role_name 等）
            model_id: 模型 ID

        Returns:
            AgentScope Agent 列表
        """
        from agentscope.agent import Agent

        agents = []
        for m in members:
            agent_name = m.get("role_name") or m.get("agent_name", "worker")
            sys_prompt = m.get("sys_prompt", f"你是团队中的 {agent_name}，负责特定领域的任务。")

            agent = Agent(
                name=agent_name,
                sys_prompt=sys_prompt,
                model_config_name=str(model_id or "default"),
            )
            agents.append(agent)

        return agents
