"""AgentExecution - Agent 执行记录表 (重构版)

作为执行历史快照存在，详细状态通过 Redis 管理。
事件日志通过 AgentExecutionEvent 表记录。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column, BigInteger, String, Text, Integer,
    DateTime, JSON, Index
)
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class ExecutionStatus(str, Enum):
    """执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_HITL = "waiting_hitl"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentExecution(Base, TenantMixin):
    """Agent 执行记录表"""
    __tablename__ = "agent_execution"

    # ── 主键与标识 ─────────────────────────────────────────────────────────
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    execution_id = Column(String(64), unique=True, nullable=False, index=True, comment="执行ID (UUID)")

    # ── 被执行对象 ─────────────────────────────────────────────────────────
    # 兼容 BigInt/String（统一存成 str），如 dify_flow/skill_package/agent_config/agent_team，
    # sqlbot 场景固定为 "0"。可空以便历史/过渡记录。
    target_id = Column(
        String(128), nullable=True, index=True,
        comment="被执行对象ID（dify_flow/skill_package/agent_config/agent_team，sqlbot=0）",
    )

    # ── 会话与用户 ─────────────────────────────────────────────────────────
    session_id = Column(BigInteger, nullable=True, index=True, comment="会话ID")
    user_id = Column(BigInteger, nullable=True, index=True, comment="用户ID")

    # ── 执行上下文 ─────────────────────────────────────────────────────────
    execution_mode = Column(String(50), nullable=False, comment="执行模式")
    status = Column(String(20), nullable=False, server_default="pending", comment="状态")
    user_input = Column(Text, nullable=True, comment="用户输入")
    output = Column(Text, nullable=True, comment="执行输出")
    error = Column(Text, nullable=True, comment="错误信息")

    # ── 链路追踪 ──────────────────────────────────────────────────────────
    trace_id = Column(String(64), nullable=True, index=True, comment="链路追踪ID")

    # ── 时间与性能 ────────────────────────────────────────────────────────
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    latency_ms = Column(Integer, nullable=True, comment="耗时（毫秒）")

    # ── 重试配置 ───────────────────────────────────────────────────────────
    retry_count = Column(Integer, nullable=False, server_default="0", comment="重试次数")
    max_retries = Column(Integer, nullable=False, server_default="3", comment="最大重试次数")

    # ── 执行快照 ───────────────────────────────────────────────────────────
    metadata_json = Column(JSON, nullable=True, comment="执行元数据快照")

    # ── 审计字段 ───────────────────────────────────────────────────────────
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

    __table_args__ = (
        Index("idx_execution_target", "target_id"),
        Index("idx_execution_status", "status"),
        Index("idx_execution_trace", "trace_id"),
    )

    def __repr__(self):
        return f"<AgentExecution {self.execution_id} status={self.status}>"
