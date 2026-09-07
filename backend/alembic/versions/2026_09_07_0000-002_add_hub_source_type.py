"""add skill hub source_type

Revision ID: 002_add_hub_source_type
Revises: 001
Create Date: 2026-09-07 12:00:00.000000+08:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002_add_hub_source_type"
down_revision: str = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_skill_hub_repo",
        sa.Column("source_type", sa.String(20), nullable=False, server_default="git"),
    )


def downgrade() -> None:
    op.drop_column("ai_skill_hub_repo", "source_type")
