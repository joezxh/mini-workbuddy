"""写操作申请单：申请 → 批准 → 一次性令牌执行（P2 Task 2 建表，Task 10 用）。

``sql_sha256`` 是审批与执行一致性的锚点；``token_consumed`` 防令牌重放。
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, ForeignKey, String, Text, TIMESTAMP, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class DataWriteRequest(Base, TenantMixin):
    """数据写操作申请单（spec §5.7）。"""

    __tablename__ = "data_write_request"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    source_id = Column(
        BigInteger, ForeignKey("data_source.id", ondelete="CASCADE"), nullable=False, comment="数据源 ID"
    )
    database = Column(String(128), nullable=True, comment="目标库")
    sql_text = Column(Text, nullable=False, comment="申请时提交的 SQL 原文")
    sql_sha256 = Column(String(64), nullable=False, comment="SQL 摘要（审批/执行一致性锚点）")
    # update | delete | insert | ddl
    statement_type = Column(String(32), nullable=False, comment="语句类型: update|delete|insert|ddl")
    # 批准后发放的一次性令牌（执行时校验，消费后由 token_consumed 置位防重放）
    token = Column(String(64), nullable=True, comment="一次性执行令牌（approved 时生成）")
    impact_json = Column(JSONB, nullable=True, comment="dry-run 影响预估")
    status = Column(
        String(32), nullable=False, server_default="pending",
        comment="状态: pending|approved|rejected|executed|expired",
    )
    applicant_id = Column(BigInteger, nullable=True, comment="申请人")
    approver_id = Column(BigInteger, nullable=True, comment="批准人")
    token_consumed = Column(Boolean, nullable=False, server_default="0", comment="令牌是否已消费（防重放）")
    expires_at = Column(TIMESTAMP, nullable=True, comment="申请过期时间")
    executed_at = Column(TIMESTAMP, nullable=True, comment="执行时间")
    result_json = Column(JSONB, nullable=True, comment="执行结果（行数、耗时）")

    # 审计
    creator_id = Column(BigInteger, nullable=True, comment="创建者 ID")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    def __repr__(self) -> str:
        return f"<DataWriteRequest #{self.id} {self.statement_type} {self.status}>"
