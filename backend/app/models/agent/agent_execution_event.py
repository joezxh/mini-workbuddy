"""AgentExecutionEvent - Agent 执行事件日志表

记录 Agent 执行过程中的所有事件，用于审计和调试。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, BigInteger, String, Integer, SmallInteger, JSON, DateTime, Index
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin

# 事件类型枚举统一取自 schemas 权威模块（spec 2026-09-21 §4.2）。
# schemas 不依赖 models，此处反向引用无循环风险。
from app.schemas.agent.event_types import ExecutionEventType  # noqa: F401


class AgentExecutionEvent(Base, TenantMixin):
    """Agent 执行事件日志表"""
    __tablename__ = "agent_execution_event"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # ── 执行关联 ───────────────────────────────────────────────────────────
    execution_id = Column(String(64), nullable=False, index=True, comment="执行 ID")
    trace_id = Column(String(64), nullable=True, index=True, comment="链路追踪 ID")

    # ── 事件信息 ───────────────────────────────────────────────────────────
    event_type = Column(String(30), nullable=False, comment="事件类型")
    sequence = Column(Integer, nullable=False, comment="事件序号")
    content = Column(JSON, nullable=True, comment="事件内容（根据类型结构化存储）")

    # ── 事件来源 ───────────────────────────────────────────────────────────
    source = Column(String(50), nullable=True, comment="事件来源: agent/mcp/skill")
    source_id = Column(String(100), nullable=True, comment="来源标识")

    # ── 元数据 ─────────────────────────────────────────────────────────────
    event_metadata = Column("metadata", JSON, nullable=True, comment="附加元数据")

    # ── 分级与关联（spec 2026-09-21 §6.1，DDL 47）──────────────────────────
    level = Column(SmallInteger, nullable=True, comment="最低分发层级 LOG=0/DB=1/STREAM=2/UI=3")
    category = Column(String(20), nullable=True, comment="事件分类")
    reply_id = Column(String(64), nullable=True, comment="AgentScope reply_id")
    block_id = Column(String(64), nullable=True, comment="内容块 ID")
    tool_call_id = Column(String(64), nullable=True, comment="工具调用关联 ID")
    interrupt_reason = Column(String(20), nullable=True, comment="中断原因")
    ui_hint = Column(String(20), nullable=True, comment="前端渲染路由提示")
    event_version = Column(SmallInteger, nullable=False, server_default="1", comment="事件格式版本")

    # ── 时间戳 ────────────────────────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_event_execution_seq", "execution_id", "sequence"),
        Index("idx_event_type", "event_type"),
        Index("idx_event_trace", "trace_id"),
        Index("idx_event_reply", "execution_id", "reply_id"),
        Index("idx_event_category_level", "category", "level"),
    )
