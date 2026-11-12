"""0001_workbench_tables — SuperAgent 工作台 3 张表（Task 4.6）。

  sa_feed_post  — Feed 时间线（5 kind，quiet 去抖语义）
  sa_idea       — Idea 卡（emo/pitch/detail，fingerprint 去重）
  sa_goal       — Goal（steps 五态 + proposals + version）

Revision ID: 2026_11_08_0001_workbench
Revises: 2026_11_08_0000_superagent
Create Date: 2026-11-08 23:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_11_08_0001_workbench"
down_revision = "2026_11_08_0000_superagent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============ 1. Feed Post ============
    op.create_table(
        "sa_feed_post",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.BigInteger(), sa.ForeignKey("ai_workspace.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("prompt", sa.String(1000), nullable=True),
        sa.Column("goal_id", sa.String(32), nullable=True),
        sa.Column("ref_type", sa.String(32), nullable=True),
        sa.Column("ref_id", sa.String(64), nullable=True),
        sa.Column("quiet", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sa_feed_post_ws", "sa_feed_post", ["workspace_id"])
    op.create_index("ix_sa_feed_post_kind", "sa_feed_post", ["kind"])
    op.create_index("ix_sa_feed_post_goal_id", "sa_feed_post", ["goal_id"])
    op.create_index("ix_sa_feed_post_created", "sa_feed_post", ["created_at"])
    op.create_index("ix_sa_feed_ws_kind", "sa_feed_post", ["workspace_id", "kind"])

    # ============ 2. Idea ============
    op.create_table(
        "sa_idea",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.BigInteger(), sa.ForeignKey("ai_workspace.id"), nullable=False),
        sa.Column("emo", sa.String(10), nullable=False, server_default="💡"),
        sa.Column("pitch", sa.String(300), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="chat"),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("src", sa.String(64), nullable=True),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "fingerprint", name="uq_sa_idea_ws_fingerprint"),
    )
    op.create_index("ix_sa_idea_ws", "sa_idea", ["workspace_id"])
    op.create_index("ix_sa_idea_created", "sa_idea", ["created_at"])
    op.create_index("ix_sa_idea_ws_pinned", "sa_idea", ["workspace_id", "pinned"])

    # ============ 3. Goal ============
    op.create_table(
        "sa_goal",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), sa.ForeignKey("ai_workspace.id"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("context", sa.String(300), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cron", sa.String(64), nullable=True),
        sa.Column("next_checkin", sa.String(40), nullable=True),
        sa.Column("due", sa.String(40), nullable=True),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("steps", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("proposals", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("notes", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sa_goal_ws", "sa_goal", ["workspace_id"])
    op.create_index("ix_sa_goal_status", "sa_goal", ["status"])
    op.create_index("ix_sa_goal_ws_status", "sa_goal", ["workspace_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_sa_goal_ws_status", "sa_goal")
    op.drop_index("ix_sa_goal_status", "sa_goal")
    op.drop_index("ix_sa_goal_ws", "sa_goal")
    op.drop_table("sa_goal")

    op.drop_index("ix_sa_idea_ws_pinned", "sa_idea")
    op.drop_index("ix_sa_idea_created", "sa_idea")
    op.drop_index("ix_sa_idea_ws", "sa_idea")
    op.drop_table("sa_idea")

    op.drop_index("ix_sa_feed_ws_kind", "sa_feed_post")
    op.drop_index("ix_sa_feed_post_created", "sa_feed_post")
    op.drop_index("ix_sa_feed_post_goal_id", "sa_feed_post")
    op.drop_index("ix_sa_feed_post_kind", "sa_feed_post")
    op.drop_index("ix_sa_feed_post_ws", "sa_feed_post")
    op.drop_table("sa_feed_post")
