"""AI助理会话与消息数据模型"""
from typing import Optional

from sqlalchemy import (
    Column, BigInteger, Integer, String, Text, Boolean,
    TIMESTAMP, ForeignKey, JSON
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiChatSession(Base, TenantMixin):
    """AI助理会话表"""
    __tablename__ = 'ai_chat_session'

    session_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='会话ID')
    user_id = Column(BigInteger, nullable=False, index=True, comment='用户ID')
    session_title = Column(String(200), comment='会话标题')
    session_type = Column(
        String(50), default='general',
        comment='会话类型：general-通用对话, thinking-深度思考, deep_research-深度研究, '
                'skill-技能模式, agent-专家Agent, team-专家团',
    )
    context_data = Column(JSON, comment='上下文数据')
    status = Column(String(20), default='active', comment='状态：active-活跃, archived-归档')
    message_count = Column(Integer, default=0, comment='消息数量')
    is_pinned = Column(Boolean, default=False, comment='是否置顶')
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment='创建时间')
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment='更新时间')

    # Agent 相关字段
    agent_id = Column(String(50), nullable=True, index=True, comment='关联的 Agent 配置 ID')
    context_version = Column(Integer, default=1, nullable=False, comment='上下文版本号')

    # AgentScope 框架扩展
    agent_mode = Column(
        String(32), nullable=True,
        comment='AgentScope 执行模式：skill/agent/team/thinking/deep_research/scheduled',
    )

    def __repr__(self):
        return f"<AiChatSession {self.session_id} user={self.user_id}>"


class AiChatMessage(Base, TenantMixin):
    """AI助理消息表"""
    __tablename__ = 'ai_chat_message'

    message_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='消息ID')
    session_id = Column(BigInteger, ForeignKey('ai_chat_session.session_id'), nullable=False, index=True, comment='会话ID')
    role = Column(String(20), nullable=False, comment='角色：user-用户, assistant-AI助理, system-系统')
    content = Column(Text, nullable=False, comment='消息内容')
    message_type = Column(String(20), default='text', comment='消息类型：text-文本, chart-图表, table-表格')
    tool_calls = Column(JSON, comment='工具调用')
    tool_results = Column(JSON, comment='工具结果')
    extra_data = Column(JSON, comment='扩展数据')
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment='创建时间')
    file_id = Column(BigInteger, ForeignKey('sys_infra_file.id', ondelete='SET NULL'), nullable=True, index=True, comment='文件ID（关联 infra_file.id）')

    # Agent 相关字段
    agent_id = Column(String(50), nullable=True, comment='执行此消息的 Agent ID')
    execution_time_ms = Column(Integer, nullable=True, comment='执行耗时(毫秒)')

    # AgentScope 框架扩展
    execution_id = Column(String(64), nullable=True, index=True, comment='关联 agent_execution.execution_id')

    # 关联
    file = relationship('SysInfraFile', foreign_keys=[file_id])

    def __repr__(self):
        return f"<AiChatMessage {self.message_id} session={self.session_id} role={self.role}>"

    @property
    def _extra(self) -> dict:
        """安全访问 extra_data JSON 字段"""
        if self.extra_data is None:
            self.extra_data = {}
        if not isinstance(self.extra_data, dict):
            return {}
        return self.extra_data
