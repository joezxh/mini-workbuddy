"""add meta_relation (P2 Task 13)

三方投票（键命名法 / 同名属性法 / 采样重叠率法）产出的表间关系持久化，
综合置信度取各票最大值，评审状态沿用 suggested/accepted/rejected。

Revision ID: 009_meta_relation
Revises: 008_write_request_token
"""
from alembic import op
import sqlalchemy as sa

revision = "009_meta_relation"
down_revision = "008_write_request_token"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meta_relation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("database", sa.String(128), nullable=False),
        sa.Column("left_table", sa.String(256), nullable=False),
        sa.Column("left_column", sa.String(256), nullable=False),
        sa.Column("right_table", sa.String(256), nullable=False),
        sa.Column("right_column", sa.String(256), nullable=False),
        sa.Column("vote_key", sa.Float(), nullable=True),
        sa.Column("vote_name", sa.Float(), nullable=True),
        sa.Column("vote_overlap", sa.Float(), nullable=True),
        sa.Column("method_votes_json", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(32), server_default="suggested", nullable=False),
        sa.Column("source", sa.String(32), server_default="rule", nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["data_source.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_meta_relation_source_db", "meta_relation", ["source_id", "database"])
    op.create_index("idx_meta_relation_lr", "meta_relation", ["left_table", "right_table"])


def downgrade() -> None:
    op.drop_table("meta_relation")
