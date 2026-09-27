"""add cross-mode context fields + finalize log

Revision ID: 2026_09_27_0000
Revises: 2026_09_21_0000
Create Date: 2026-09-27 10:00:00.000000

把 ai_context_storage 升级为支持跨模式检索:
- source_mode:业务来源模式(9 种之一)
- context_tags:JSONB 标签列表
- is_cross_mode_accessible:是否允许跨模式检索
- case_number:案件/工作空间标识

新建 ai_session_finalize_log 审计每次 finalize 状态(L2 + Mem0 同步结果)。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2026_09_27_0000"
down_revision: Union[str, None] = "2026_09_21_0000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """1) 扩展 ai_context_storage 4 字段 + 2 索引;2) 新建 ai_session_finalize_log 表 + 1 索引。"""
    # 1) 扩展 ai_context_storage
    op.add_column(
        "ai_context_storage",
        sa.Column(
            "source_mode",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'shared'"),
        ),
    )
    op.add_column(
        "ai_context_storage",
        sa.Column(
            "context_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "ai_context_storage",
        sa.Column(
            "is_cross_mode_accessible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "ai_context_storage",
        sa.Column("case_number", sa.String(64), nullable=True),
    )

    # 2) 数据回填:已有记录 source_mode 默认取 mode 字段(单语句幂等)
    op.execute(
        "UPDATE ai_context_storage SET source_mode = mode "
        "WHERE source_mode = 'shared' AND mode <> 'shared'"
    )

    # 3) 索引
    op.create_index(
        "ix_ai_context_storage_source_mode",
        "ai_context_storage",
        ["tenant_id", "session_id", "source_mode"],
    )
    op.create_index(
        "ix_ai_context_storage_cross_mode",
        "ai_context_storage",
        ["tenant_id", "source_mode", "is_cross_mode_accessible"],
        postgresql_where=sa.text("is_cross_mode_accessible = true"),
    )

    # 4) 新建 ai_session_finalize_log 表
    op.create_table(
        "ai_session_finalize_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("session_type", sa.String(32), nullable=False),
        sa.Column("source_mode", sa.String(32), nullable=False),
        sa.Column("l2_record_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "mem0_synced",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("mem0_memory_id", sa.String(64), nullable=True),
        sa.Column(
            "finalized_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_ai_session_finalize_log_session",
        "ai_session_finalize_log",
        ["tenant_id", "session_id", "finalized_at"],
    )


def downgrade() -> None:
    """回滚:删除 audit 表 + 索引,移除 4 字段(注:数据无法回滚)。"""
    op.drop_index(
        "ix_ai_session_finalize_log_session", table_name="ai_session_finalize_log"
    )
    op.drop_table("ai_session_finalize_log")
    op.drop_index(
        "ix_ai_context_storage_cross_mode", table_name="ai_context_storage"
    )
    op.drop_index(
        "ix_ai_context_storage_source_mode", table_name="ai_context_storage"
    )
    op.drop_column("ai_context_storage", "case_number")
    op.drop_column("ai_context_storage", "is_cross_mode_accessible")
    op.drop_column("ai_context_storage", "context_tags")
    op.drop_column("ai_context_storage", "source_mode")