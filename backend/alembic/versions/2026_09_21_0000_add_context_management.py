"""add context management tables

Revision ID: 2026_09_21_0000
Revises: 
Create Date: 2026-09-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2026_09_21_0000'
down_revision: Union[str, None] = '014_merge_heads'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create ai_context_storage table for multi-mode session context management.
    
    Schema includes:
    - Tenant isolation (tenant_id)
    - Session linkage (session_id → ai_chat_session)
    - Multi-mode support (mode field)
    - Vector embedding support (embedding_vector)
    - Automatic TTL expiration (expires_at)
    - Access frequency tracking (access_count)
    """
    # Create ai_context_storage table
    op.create_table(
        'ai_context_storage',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger, nullable=False),
        sa.Column('session_id', sa.BigInteger, nullable=False),
        sa.Column('user_id', sa.BigInteger, nullable=False),
        sa.Column('mode', sa.String(32), nullable=False),
        sa.Column('context_key', sa.String(255), nullable=False),
        sa.Column('context_data', postgresql.JSONB(astype=sa.JSON), nullable=False),
        sa.Column('embedding_vector', sa.Text),  # pgvector support
        sa.Column('priority', sa.Integer, server_default='5'),
        sa.Column('access_count', sa.Integer, server_default='0'),
        sa.Column('last_accessed', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        
        # Unique constraint on tenant/session/mode/key combination
        sa.UniqueConstraint(
            'tenant_id', 'session_id', 'mode', 'context_key',
            name='uk_tenant_session_mode_key'
        ),
        
        # Foreign key to ai_chat_session (ON DELETE CASCADE)
        sa.ForeignKeyConstraint(
            ['session_id'],
            ['ai_chat_session.session_id'],
            name='fk_ai_context_storage_session',
            ondelete='CASCADE'
        ),
    )
    
    # Create indexes for query optimization
    # Index 1: Tenant + mode access pattern (most common query)
    op.create_index(
        'ix_ai_context_storage_tenant_mode',
        'ai_context_storage',
        ['tenant_id', 'mode']
    )
    
    # Index 2: User + mode access pattern (user-level retrieval)
    op.create_index(
        'ix_ai_context_storage_user_mode',
        'ai_context_storage',
        ['tenant_id', 'user_id', 'mode']
    )
    
    # Index 3: Last accessed time (for TTL compaction & LRU eviction)
    # NOTE: 部分索引谓词不能用 NOW()(STABLE,非 IMMUTABLE),PG 会报
    # "functions in index predicate must be marked IMMUTABLE",故用普通索引
    op.create_index(
        'ix_ai_context_storage_last_access',
        'ai_context_storage',
        ['last_accessed'],
        descending=[True]
    )
    
    # Index 4: Expiration time (for batch cleanup jobs)
    op.create_index(
        'ix_ai_context_storage_expires',
        'ai_context_storage',
        ['expires_at'],
        postgresql_where=sa.text('expires_at IS NOT NULL')
    )


def downgrade() -> None:
    """
    Safely drop ai_context_storage table and its indexes.
    
    Note: This will delete all stored context data. Ensure no active
    sessions rely on this data before running downgrade.
    """
    # Drop indexes first (order doesn't matter but explicit is clearer)
    op.drop_index(
        'ix_ai_context_storage_expires',
        table_name='ai_context_storage'
    )
    op.drop_index(
        'ix_ai_context_storage_last_access',
        table_name='ai_context_storage'
    )
    op.drop_index(
        'ix_ai_context_storage_user_mode',
        table_name='ai_context_storage'
    )
    op.drop_index(
        'ix_ai_context_storage_tenant_mode',
        table_name='ai_context_storage'
    )
    
    # Drop the table
    op.drop_table('ai_context_storage')
