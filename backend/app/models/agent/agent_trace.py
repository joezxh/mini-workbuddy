"""Agent 执行链路记录数据模型"""
from sqlalchemy import Column, BigInteger, String, Text, Boolean, Integer, TIMESTAMP, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AgentTrace(Base, TenantMixin):
    """Agent 执行链路记录表"""
    __tablename__ = 'agent_trace'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trace_id = Column(String(64), nullable=False, index=True, comment='链路ID')
    session_id = Column(BigInteger, nullable=True, index=True, comment='会话ID')
    user_id = Column(BigInteger, nullable=True, index=True, comment='用户ID')
    agent_id = Column(String(100), nullable=False, index=True, comment='Agent ID')
    agent_type = Column(String(20), nullable=False, comment='Agent类型')
    input_prompt = Column(Text, nullable=True, comment='输入提示词')
    output_result = Column(Text, nullable=True, comment='输出结果')
    skills_used = Column(JSONB, nullable=True, comment='使用的Skill列表')
    tools_used = Column(JSONB, nullable=True, comment='使用的工具列表')
    error = Column(Text, nullable=True, comment='错误信息')
    status = Column(String(20), nullable=False, server_default='OK', comment='状态: OK/ERROR')
    start_time = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment='开始时间')
    end_time = Column(TIMESTAMP, nullable=True, comment='结束时间')
    duration_ms = Column(Integer, nullable=True, comment='执行耗时(毫秒)')
    extra_metadata = Column('metadata', JSONB, nullable=True, comment='扩展元数据')
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    # ─── Phase 5: Config Trace 字段 ───────────────────────────────────
    agent_config_id = Column(BigInteger, nullable=True, index=True, comment='关联 Agent 配置 ID')
    team_config_id = Column(BigInteger, nullable=True, index=True, comment='关联 Team 配置 ID')
    workspace_config_id = Column(BigInteger, nullable=True, comment='关联 Workspace 配置 ID')
    component_ids = Column(JSONB, nullable=True, comment='关联组件 ID 集合 {"skill": [...], "tool": [...]}')

    def __repr__(self):
        return f"<AgentTrace {self.trace_id} agent={self.agent_id}>"