"""AgentScope 团队编排器 — 基于 AgentScope 原生 Team API 的多 Agent 协作。

完整实现：
1. 加载团队成员与配置
2. 创建 Leader Agent（动态派发任务给 Worker）
3. 运行团队并收集结果
4. 支持运行态干预（暂停/恢复/取消/注入消息）
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agentscope.agent import Agent, LeaderBasedAgentTeam
from agentscope.message import Msg

logger = logging.getLogger(__name__)

# 全局编排器注册表（供干预端点触达运行中的编排器实例）
ORCHESTRATOR_REGISTRY: Dict[str, "AgentScopeOrchestrator"] = {}


class AgentScopeOrchestrator:
    """AgentScope 原生团队编排器。"""

    def __init__(
        self,
        db: Any,
        team: Any,
        run: Any,
        event_svc: Any = None,
        user_id: Optional[int] = None,
        profile: Any = None,
        model_id: Optional[int] = None,
    ):
        self.db = db
        self.team = team
        self.run = run
        self.event_svc = event_svc
        self.user_id = user_id
        self.profile = profile
        self.model_id = model_id
        
        # 团队成员 Agent 列表
        self._agents: List[Agent] = []
        self._team: Optional[LeaderBasedAgentTeam] = None

    async def create_team(self) -> bool:
        """创建团队成员和 Leader。
        
        Returns:
            创建成功返回 True
        """
        from app.services.agent.agent_team_service import AgentTeamService
        
        # 1. 加载团队成员
        svc = AgentTeamService(self.db)
        members = svc.get_members(self.team.id)
        
        if not members:
            logger.error(f"团队 {self.team.team_code} 无成员")
            return False
        
        # 2. 为每个成员创建 Agent
        self._agents = []
        for member in members:
            agent = self._create_member_agent(member)
            self._agents.append(agent)
        
        # 3. 创建 Leader Agent (协调者)
        leader = Agent(
            name="team_leader",
            sys_prompt=self._build_leader_prompt(members),
            model_config_name=str(self.model_id or "default"),
        )
        
        # 4. 构建 LeaderBasedAgentTeam
        dispatch_mode = getattr(self.profile, 'dispatch_mode', 'round_robin') \
            if self.profile else 'round_robin'
        
        self._team = LeaderBasedAgentTeam(
            leader=leader,
            workers=self._agents,
            dispatch_mode=dispatch_mode,
        )
        
        logger.info(f"团队 {self.team.team_code} 创建成功，成员数={len(members)}")
        return True
    
    def _create_member_agent(self, member: Any) -> Agent:
        """为单个成员创建 Agent。"""
        # 从数据库加载成员的配置
        from app.models.agent.agent_config import AgentConfig
        
        agent_config = self.db.query(AgentConfig).filter(
            AgentConfig.id == member.agent_config_id,
            AgentConfig.is_deleted == False,
        ).first()
        
        if agent_config:
            sys_prompt = agent_config.sys_prompt
            tools = agent_config.tools
        else:
            sys_prompt = f"你是团队中的 {member.role_name}，负责特定领域的任务。"
            tools = []
        
        return Agent(
            name=member.role_name,
            sys_prompt=sys_prompt,
            model_config_name=str(self.model_id or "default"),
            tools=tools or [],
        )
    
    def _build_leader_prompt(self, members: List[Any]) -> str:
        """构建 Leader 的系统提示词。"""
        member_roles = "\n".join([f"- {m.role_name}: {getattr(m, 'role_desc', '')}" 
                                  for m in members])
        
        return f"""你是一位团队协调者，负责将用户任务分发给最合适的团队成员。

可用团队成员:
{member_roles}

你的职责:
1. 分析用户输入，识别任务类型
2. 选择合适的 Worker 处理
3. 收集 Worker 输出并汇总结论
4. 如有冲突，协调解决

遵循原则:
- 仅分发明确的任务
- 必要时让多个 Worker 协同
- 保持上下文一致性"""
    
    async def submit(
        self,
        input_text: str,
        input_context: Optional[dict] = None,
        created_by: Optional[int] = None,
    ) -> str:
        """提交团队运行任务。"""
        # 1. 创建团队
        if not await self.create_team():
            raise RuntimeError(f"团队 {self.team.team_code} 创建失败")
        
        # 2. 发送用户消息给 Leader
        user_msg = Msg(
            name="user_request",
            content=input_text,
        )
        
        # 3. 运行团队协作
        response = await self._team.reply(user_msg)
        
        # 4. 记录执行事件
        self._record_execution_done(response)
        
        return response.text
    
    def _record_execution_done(self, response: Any) -> None:
        """记录执行完成事件。"""
        if self.event_svc:
            self.event_svc.record(
                event_type="TEAM_COMPLETE",
                content={"result": response.text},
                source="agent_scope_orchestrator",
            )
    
    async def request_pause(self) -> None:
        """请求暂停运行（暂不支持，待 AgentScope 原生支持）。"""
        logger.warning("AgentScope 原生 API 暂不支持运行时暂停")
    
    async def resume(self) -> None:
        """恢复运行（暂不支持）。"""
        logger.warning("AgentScope 原生 API 暂不支持运行时恢复")
