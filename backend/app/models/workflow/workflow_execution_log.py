"""工作流执行日志"""
from sqlalchemy import Column, BigInteger, String, Integer, Text, Index, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class WorkflowExecutionLog(Base, TenantMixin):
    """工作流执行日志"""
    __tablename__ = "workflow_execution_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    flow_id = Column(BigInteger, nullable=False, comment="FK → workflow_flow.id")
    execution_id = Column(String(64), nullable=True, comment="关联 agent_execution.execution_id")
    status = Column(String(20), nullable=False, server_default="pending",
                    comment="pending / running / success / failed / timeout / cancelled")
    input_data = Column(JSONB, nullable=True, comment="实际输入")
    output_data = Column(JSONB, nullable=True, comment="实际输出")
    error_message = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    retry_count = Column(Integer, nullable=False, server_default="0")
    platform_trace = Column(JSONB, nullable=True, comment="平台原始响应")
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_wf_exec_log_flow", "flow_id"),
        Index("idx_wf_exec_log_status", "status"),
        Index("idx_wf_exec_log_created", "created_at"),
    )
