"""0000_superagent_tables — SuperAgent 引擎核心 8 张运行时表。

Source 管理配置（github_source_cfg / feishu_source_cfg / policy_rules / role_models）
统一存入 ai_workspace 表的 JSON 字段或 config JSON，不新建配置表。
本 migration 只建 Engine 事务载体表：

  sa_trigger       — Source 产生的原始触发信号
  sa_ticket        — Engine 生命周期核心单位
  sa_effect        — Durable Effect Queue（6 kind + 指数退避）
  sa_thread        — Trigger 时间序列容器（Eval 串行单位）
  sa_subscription  — Ticket ↔ Thread 多对多（fan-out 不经过 Eval）
  sa_mandate       — 不可变授权（accept 时创建，Policy 变更不撤销）
  sa_assignment    — Ticket ↔ Executor 绑定
  sa_audit_log     — Engine 所有事务审计日志

Revision ID: 2026_11_08_0000_superagent
Revises: 2026_11_01_0013_add_twin_tables
Create Date: 2026-11-08 21:30:00.000000

对齐 dsh-superagent v0.1.0 + SuperAgent spec.md G1-G7 / FR7-FR12 / AC6-AC8。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "2026_11_08_0000_superagent"
down_revision = "2026_11_01_0013_add_twin_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============ 1. Thread ============
    op.create_table(
        "sa_thread",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), sa.ForeignKey("ai_workspace.id"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("ref_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("context", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("cursor", sa.String(64), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "source", "ref_id", name="uq_sa_thread_ws_src_ref"),
    )
    op.create_index("ix_sa_thread_ws", "sa_thread", ["workspace_id"])
    op.create_index("ix_sa_thread_source", "sa_thread", ["source"])

    # ============ 2. Trigger ============
    op.create_table(
        "sa_trigger",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), sa.ForeignKey("ai_workspace.id"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("ref_id", sa.String(128), nullable=False),
        sa.Column("thread_id", sa.String(32), sa.ForeignKey("sa_thread.id"), nullable=True),
        sa.Column("sender_id", sa.String(128), nullable=True),
        sa.Column("sender_name", sa.String(200), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("context", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("eval_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sa_trigger_ws", "sa_trigger", ["workspace_id"])
    op.create_index("ix_sa_trigger_source", "sa_trigger", ["source"])
    op.create_index("ix_sa_trigger_thread", "sa_trigger", ["thread_id"])
    op.create_index("ix_sa_trigger_status", "sa_trigger", ["status"])

    # ============ 3. Ticket ============
    op.create_table(
        "sa_ticket",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), sa.ForeignKey("ai_workspace.id"), nullable=False),
        sa.Column("trigger_id", sa.String(32), sa.ForeignKey("sa_trigger.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("intent_evidence", sa.Text(), nullable=True),
        sa.Column("acknowledgement", sa.String(500), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.TIMESTAMP(), nullable=True),
    )
    op.create_index("ix_sa_ticket_ws", "sa_ticket", ["workspace_id"])
    op.create_index("ix_sa_ticket_status", "sa_ticket", ["status"])
    op.create_index("ix_sa_ticket_trigger", "sa_ticket", ["trigger_id"])

    # ============ 4. Subscription ============
    op.create_table(
        "sa_subscription",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.String(32), sa.ForeignKey("sa_ticket.id"), nullable=False),
        sa.Column("thread_id", sa.String(32), sa.ForeignKey("sa_thread.id"), nullable=False),
        sa.Column("workspace_id", sa.BigInteger(), sa.ForeignKey("ai_workspace.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False, server_default="following"),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("ticket_id", "thread_id", name="uq_sa_sub_ticket_thread"),
    )
    op.create_index("ix_sa_sub_ticket", "sa_subscription", ["ticket_id"])
    op.create_index("ix_sa_sub_thread", "sa_subscription", ["thread_id"])
    op.create_index("ix_sa_sub_ws", "sa_subscription", ["workspace_id"])

    # ============ 5. Mandate ============
    op.create_table(
        "sa_mandate",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("ticket_id", sa.String(32), sa.ForeignKey("sa_ticket.id"), nullable=False, unique=True),
        sa.Column("workspace_id", sa.BigInteger(), sa.ForeignKey("ai_workspace.id"), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("strength", sa.String(20), nullable=False),
        sa.Column("scope", sa.String(1000), nullable=True),
        sa.Column("matched_rules", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_identity", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("trigger_id", sa.String(32), sa.ForeignKey("sa_trigger.id"), nullable=False),
        sa.Column("acknowledgement", sa.String(500), nullable=True),
        sa.Column("intent_evidence", sa.String(1000), nullable=True),
        sa.Column("worktree_name", sa.String(100), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sa_mandate_ws", "sa_mandate", ["workspace_id"])

    # ============ 6. Assignment ============
    op.create_table(
        "sa_assignment",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("ticket_id", sa.String(32), sa.ForeignKey("sa_ticket.id"), nullable=False),
        sa.Column("workspace_id", sa.BigInteger(), sa.ForeignKey("ai_workspace.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("executor_session", sa.String(128), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("final_report", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sa_assign_ticket", "sa_assignment", ["ticket_id"])
    op.create_index("ix_sa_assign_ws", "sa_assignment", ["workspace_id"])
    op.create_index("ix_sa_assign_status", "sa_assignment", ["status"])

    # ============ 7. Effect ============
    op.create_table(
        "sa_effect",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), sa.ForeignKey("ai_workspace.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ticket_id", sa.String(32), sa.ForeignKey("sa_ticket.id"), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due", sa.TIMESTAMP(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sa_effect_ws", "sa_effect", ["workspace_id"])
    op.create_index("ix_sa_effect_kind", "sa_effect", ["kind"])
    op.create_index("ix_sa_effect_status", "sa_effect", ["status"])
    op.create_index("ix_sa_effect_ticket", "sa_effect", ["ticket_id"])

    # ============ 8. Audit Log ============
    op.create_table(
        "sa_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.BigInteger(), sa.ForeignKey("ai_workspace.id"), nullable=False),
        sa.Column("ticket_id", sa.String(32), nullable=True),
        sa.Column("trigger_id", sa.String(32), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sa_audit_ws", "sa_audit_log", ["workspace_id"])
    op.create_index("ix_sa_audit_action", "sa_audit_log", ["action"])
    op.create_index("ix_sa_audit_created", "sa_audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_sa_audit_created", "sa_audit_log")
    op.drop_index("ix_sa_audit_action", "sa_audit_log")
    op.drop_index("ix_sa_audit_ws", "sa_audit_log")
    op.drop_table("sa_audit_log")

    op.drop_index("ix_sa_effect_ticket", "sa_effect")
    op.drop_index("ix_sa_effect_status", "sa_effect")
    op.drop_index("ix_sa_effect_kind", "sa_effect")
    op.drop_index("ix_sa_effect_ws", "sa_effect")
    op.drop_table("sa_effect")

    op.drop_index("ix_sa_assign_status", "sa_assignment")
    op.drop_index("ix_sa_assign_ws", "sa_assignment")
    op.drop_index("ix_sa_assign_ticket", "sa_assignment")
    op.drop_table("sa_assignment")

    op.drop_index("ix_sa_mandate_ws", "sa_mandate")
    op.drop_table("sa_mandate")

    op.drop_index("ix_sa_sub_ws", "sa_subscription")
    op.drop_index("ix_sa_sub_thread", "sa_subscription")
    op.drop_index("ix_sa_sub_ticket", "sa_subscription")
    op.drop_table("sa_subscription")

    op.drop_index("ix_sa_ticket_status", "sa_ticket")
    op.drop_index("ix_sa_ticket_trigger", "sa_ticket")
    op.drop_index("ix_sa_ticket_ws", "sa_ticket")
    op.drop_table("sa_ticket")

    op.drop_index("ix_sa_trigger_status", "sa_trigger")
    op.drop_index("ix_sa_trigger_thread", "sa_trigger")
    op.drop_index("ix_sa_trigger_source", "sa_trigger")
    op.drop_index("ix_sa_trigger_ws", "sa_trigger")
    op.drop_table("sa_trigger")

    op.drop_index("ix_sa_thread_source", "sa_thread")
    op.drop_index("ix_sa_thread_ws", "sa_thread")
    op.drop_table("sa_thread")
