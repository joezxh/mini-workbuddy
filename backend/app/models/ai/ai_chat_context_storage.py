"""AI 上下文存储 ORM 模型(ai_context_storage)。

原表由 alembic/versions/2026_09_21_0000_add_context_management.py 创建。
2026_09_27 迁移新增 4 字段:source_mode / context_tags / is_cross_mode_accessible / case_number。
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Index,
    Integer,
    String,
    Text,
    TIMESTAMP,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base


class AIChatContextStorage(Base):
    """AI 跨模式会话上下文存储表(L 2 短期记忆 + 案件/工作空间维度)。

    行级多租户隔离;每次 persist_l2_context 写入一条记录。
    """

    __tablename__ = "ai_context_storage"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    tenant_id = Column(BigInteger, nullable=False, index=True, comment="租户 ID")
    session_id = Column(BigInteger, nullable=False, comment="会话 ID")
    user_id = Column(BigInteger, nullable=False, comment="用户 ID")
    mode = Column(String(32), nullable=False, comment="模式(dify/sqlbot/...)")
    context_key = Column(String(255), nullable=False, comment="上下文 key")
    context_data = Column(JSONB, nullable=False, comment="上下文 JSON 数据")
    embedding_vector = Column(Text, comment="向量嵌入(pgvector)")
    priority = Column(Integer, server_default="5", comment="优先级 1-10,数字越小越优先")
    access_count = Column(Integer, server_default="0", comment="访问次数")
    last_accessed = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), comment="最后访问时间"
    )
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True, comment="过期时间")

    # ── 2026_09_27 新增 4 字段(跨模式上下文) ─────────────────────
    source_mode = Column(
        String(32),
        nullable=False,
        server_default="shared",
        comment="业务来源模式(general/react/thinking/deep_research/skill/agent/team/scheduled/shared)",
    )
    context_tags = Column(
        JSONB, server_default="[]", comment="上下文标签列表"
    )
    is_cross_mode_accessible = Column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="是否允许跨模式检索",
    )
    case_number = Column(
        String(64), nullable=True, comment="案件/工作空间标识"
    )

    __table_args__ = (
        Index(
            "uk_ai_context_storage_tenant_session_mode_key",
            "tenant_id",
            "session_id",
            "mode",
            "context_key",
            unique=True,
        ),
        Index(
            "ix_ai_context_storage_source_mode",
            "tenant_id",
            "session_id",
            "source_mode",
        ),
        Index(
            "ix_ai_context_storage_cross_mode",
            "tenant_id",
            "source_mode",
            "is_cross_mode_accessible",
        ),
        Index(
            "ix_ai_context_storage_tenant_mode",
            "tenant_id",
            "mode",
        ),
        Index(
            "ix_ai_context_storage_user_mode",
            "tenant_id",
            "user_id",
            "mode",
        ),
        Index(
            "ix_ai_context_storage_last_access",
            "last_accessed",
            postgresql_where="expires_at IS NULL OR expires_at > NOW()",
        ),
        Index(
            "ix_ai_context_storage_expires",
            "expires_at",
            postgresql_where="expires_at IS NOT NULL",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AIChatContextStorage id={self.id} tenant={self.tenant_id} "
            f"session={self.session_id} mode={self.source_mode}>"
        )