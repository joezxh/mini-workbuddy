"""AgentHitlPause - 人机交互暂停记录表（spec §5.4/§5.5；DDL 47 重建）。

此前模型被移除但 agent_execution_service 仍存在悬空引用，本任务恢复。
"""
from __future__ import annotations

from sqlalchemy import Column, BigInteger, String, JSON, SmallInteger, DateTime, Index
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AgentHitlPause(Base, TenantMixin):
    """人机交互暂停记录。"""
    __tablename__ = "agent_hitl_pause"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    execution_id = Column(String(64), nullable=False, comment="执行 ID")
    reply_id = Column(String(64), nullable=True, comment="AgentScope reply_id")
    tool_calls = Column(JSON, nullable=True, comment="待确认工具调用列表")
    suggested_rules = Column(JSON, nullable=True, comment="建议授权规则")
    status = Column(String(20), nullable=False, server_default="waiting",
                    comment="waiting/approved/rejected/interrupted")
    accept_rules = Column(SmallInteger, nullable=False, server_default="0",
                          comment="是否接受授权规则")
    timeout_at = Column(DateTime, nullable=True, comment="超时提示时刻")
    answered_at = Column(DateTime, nullable=True, comment="用户应答时刻")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # 索引显式命名，与 DDL 47 保持一致（tenant_id 索引由 TenantMixin 的 index=True 生成）
    __table_args__ = (
        Index("idx_hitl_execution", "execution_id"),
        Index("idx_hitl_status", "status"),
    )
