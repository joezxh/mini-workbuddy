"""Agent 配置服务"""
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.agent.agent_config import AgentConfig


class AgentConfigService:
    """Agent 配置管理服务"""

    def list_agents(
        self,
        db: Session,
        agent_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
        category: Optional[str] = None,
    ) -> tuple[int, List[AgentConfig]]:
        """获取 Agent 列表"""
        q = select(AgentConfig).where(AgentConfig.is_deleted == False)
        if agent_type:
            q = q.where(AgentConfig.agent_type == agent_type)
        if category:
            q = q.where(AgentConfig.category == category)
        if is_active is not None:
            q = q.where(AgentConfig.is_active == is_active)

        count_q = select(func.count()).select_from(q.subquery())
        total = db.scalar(count_q) or 0

        q = q.order_by(AgentConfig.sort_order, AgentConfig.id)
        q = q.offset((page - 1) * page_size).limit(page_size)
        rows = db.scalars(q).all()
        return total, list(rows)

    def get_by_id(self, db: Session, agent_id: int) -> Optional[AgentConfig]:
        """根据 ID 获取 Agent"""
        return db.scalars(
            select(AgentConfig).where(
                AgentConfig.id == agent_id,
                AgentConfig.is_deleted == False,
            )
        ).first()

    def get_by_code(self, db: Session, agent_code: str) -> Optional[AgentConfig]:
        """根据 code 获取 Agent"""
        return db.scalars(
            select(AgentConfig).where(
                AgentConfig.agent_code == agent_code,
                AgentConfig.is_deleted == False,
            )
        ).first()

    # 由 AgentConfigCreate 承载、映射到 AgentConfig 真实列的结构化字段。
    # 注意：模型配置列名为 model_config（非 llm_config）。
    _STRUCTURED_FIELDS = (
        "strategy_code",
        "execution_mode",
        "system_prompt",
        "tools",
        "skills",
        "mcp_servers",
        "llm_config",
        "knowledge_bases",
        "hitl_config",
        "react_config",
        "context_config",
    )

    def create(
        self,
        db: Session,
        agent_code: str,
        name: str,
        agent_type: str,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        is_active: bool = True,
        sort_order: int = 0,
        created_by: Optional[int] = None,
        category: Optional[str] = None,
        strategy_code: Optional[str] = None,
        execution_mode: Optional[str] = None,
        system_prompt: Optional[str] = None,
        tools: Optional[List[str]] = None,
        skills: Optional[List[str]] = None,
        mcp_servers: Optional[List[Any]] = None,
        model_config: Optional[Dict[str, Any]] = None,
        knowledge_bases: Optional[List[int]] = None,
        hitl_config: Optional[Dict[str, Any]] = None,
        react_config: Optional[Dict[str, Any]] = None,
        context_config: Optional[Dict[str, Any]] = None,
    ) -> AgentConfig:
        """创建 Agent 配置（持久化结构化配置字段）"""
        agent = AgentConfig(
            agent_code=agent_code,
            name=name,
            agent_type=agent_type,
            category=category,
            description=description,
            config=config,
            is_active=is_active,
            sort_order=sort_order,
            created_by=created_by,
            strategy_code=strategy_code,
            execution_mode=execution_mode,
            system_prompt=system_prompt,
            tools=tools or [],
            skills=skills or [],
            mcp_servers=mcp_servers or [],
            llm_config=model_config,
            knowledge_bases=knowledge_bases or [],
            hitl_config=hitl_config,
            react_config=react_config,
            context_config=context_config,
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        return agent

    def update(
        self,
        db: Session,
        agent_id: int,
        **fields,
    ) -> Optional[AgentConfig]:
        """更新 Agent 配置（支持任意已存在的字段，含结构化配置）"""
        agent = self.get_by_id(db, agent_id)
        if not agent:
            return None
        for k, v in fields.items():
            if not hasattr(agent, k):
                continue
            if v is None and k not in self._STRUCTURED_FIELDS:
                # 标量字段传 None 表示不更新；但结构化字段允许显式清空
                continue
            setattr(agent, k, v)
        db.commit()
        db.refresh(agent)
        return agent

    def toggle_active(
        self,
        db: Session,
        agent_id: int,
        is_active: Optional[bool] = None,
    ) -> Optional[AgentConfig]:
        """启用/禁用 Agent（is_active 为空则翻转）"""
        agent = self.get_by_id(db, agent_id)
        if not agent:
            return None
        agent.is_active = not agent.is_active if is_active is None else bool(is_active)
        db.commit()
        db.refresh(agent)
        return agent

    def delete(self, db: Session, agent_id: int) -> bool:
        """软删除 Agent"""
        agent = self.get_by_id(db, agent_id)
        if not agent:
            return False
        agent.is_deleted = True
        db.commit()
        return True

    def to_dict(self, agent: AgentConfig) -> Dict[str, Any]:
        """转换为字典（含全部结构化配置字段）"""
        return {
            "id": agent.id,
            "agent_code": agent.agent_code,
            "name": agent.name,
            "agent_type": agent.agent_type,
            "category": agent.category,
            "description": agent.description,
            "strategy_code": agent.strategy_code,
            "execution_mode": agent.execution_mode,
            "system_prompt": agent.system_prompt,
            "tools": agent.tools or [],
            "skills": agent.skills or [],
            "mcp_servers": agent.mcp_servers or [],
            "model_config": agent.llm_config,
            "knowledge_bases": agent.knowledge_bases or [],
            "hitl_config": agent.hitl_config,
            "react_config": agent.react_config,
            "context_config": agent.context_config,
            "config": agent.config,
            "is_active": agent.is_active,
            "sort_order": agent.sort_order,
            "created_by": agent.created_by,
            "created_at": str(agent.created_at) if agent.created_at else None,
            "updated_at": str(agent.updated_at) if agent.updated_at else None,
            "is_deleted": agent.is_deleted,
        }
