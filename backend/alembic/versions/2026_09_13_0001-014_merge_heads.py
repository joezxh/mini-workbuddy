"""merge heads (011 dangling branch + 013 chain)

011_rename_legacy_tables 的内容已在存量库执行完毕；006 依赖被调整为直连 005 后，
011 成为悬空头。此合并节点将 011 与 013 链并回单头，消除 multiple heads。

Revision ID: 014_merge_heads
Revises: 011_rename_legacy_tables, 013_agent_config_workflow_id
Create Date: 2026-09-13
"""
from alembic import op

revision = "014_merge_heads"
down_revision = ("011_rename_legacy_tables", "013_agent_config_workflow_id")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
