"""ai_session_finalize_log ORM 模型。

记录每次会话收尾的 L2 落库 + Mem0 同步状态,用于运维监控 Mem0 健康度。
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Index,
    String,
    Text,
    TIMESTAMP,
    func,
)

from app.db.database import Base


class AISessionFinalizeLog(Base):
    """会话 finalize 审计日志。"""

    __tablename__ = "ai_session_finalize_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    tenant_id = Column(BigInteger, nullable=False, index=True, comment="租户 ID")
    session_id = Column(BigInteger, nullable=False, index=True, comment="会话 ID")
    user_id = Column(BigInteger, nullable=False, index=True, comment="用户 ID")
    session_type = Column(
        String(32), nullable=False, comment="会话类型(general/skill/...)"
    )
    source_mode = Column(
        String(32), nullable=False, comment="业务来源模式"
    )
    l2_record_id = Column(BigInteger, nullable=True, comment="L2 落库 id")
    mem0_synced = Column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="是否已同步到 Mem0",
    )
    mem0_memory_id = Column(
        String(64), nullable=True, comment="Mem0 记忆 ID"
    )
    finalized_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="收尾时间",
    )
    error_message = Column(Text, nullable=True, comment="错误信息")

    __table_args__ = (
        Index(
            "ix_ai_session_finalize_log_session",
            "tenant_id",
            "session_id",
            "finalized_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AISessionFinalizeLog id={self.id} session={self.session_id} "
            f"type={self.session_type} mem0_synced={self.mem0_synced}>"
        )