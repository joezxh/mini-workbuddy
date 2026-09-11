"""add data_write_request.token (P2 Task 10)

一次性执行令牌：审批通过后生成，执行时校验，消费后置 token_consumed 防重放。

Revision ID: 008_write_request_token
Revises: 007_dataops_tables
"""
from alembic import op
import sqlalchemy as sa

revision = "008_write_request_token"
down_revision = "007_dataops_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "data_write_request",
        sa.Column("token", sa.String(64), nullable=True, comment="一次性执行令牌（approved 时生成）"),
    )


def downgrade() -> None:
    op.drop_column("data_write_request", "token")
