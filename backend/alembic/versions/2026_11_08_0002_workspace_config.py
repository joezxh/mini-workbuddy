"""0002_workspace_config — sa_workspace_config（Task 8 遗留④）。

一张表绑定 workspace 的全部 SuperAgent 专属配置：
模型 / Policy / KB / MCP / 执行参数（max_workers 等）/ 安全设置。
launch Effect 的 worker 并发从 max_workers 解析（无配置回落默认 3）。

Revision ID: 2026_11_08_0002_wsconfig
Revises: 2026_11_08_0001_workbench
Create Date: 2026-11-09 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_11_08_0002_wsconfig"
down_revision = "2026_11_08_0001_workbench"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 开发库由 create_all 建表（AUTO_CREATE_TABLES=True），此迁移需幂等。
    if sa.inspect(op.get_bind()).has_table("sa_workspace_config"):
        return
    op.create_table(
        "sa_workspace_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.BigInteger(), sa.ForeignKey("ai_workspace.id"),
                  nullable=False, unique=True),
        # 模型（重用 AiChatModel，松引用不建硬 FK）
        sa.Column("default_model_id", sa.Integer(), nullable=True),
        sa.Column("jev_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("jev_router", sa.String(20), nullable=False, server_default="jev-first"),
        sa.Column("jev_confidence_threshold", sa.Float(), nullable=False, server_default="0.6"),
        # Policy
        sa.Column("policy_rules", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("jev_accept_threshold", sa.Float(), nullable=False, server_default="0.6"),
        sa.Column("proactive_auto_accept", sa.Boolean(), nullable=False, server_default=sa.false()),
        # KB
        sa.Column("kb_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("kb_weights", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("auto_ingest_worker_output", sa.Boolean(), nullable=False, server_default=sa.true()),
        # MCP
        sa.Column("mcp_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        # 执行
        sa.Column("max_workers", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("eval_timeout_ms", sa.Integer(), nullable=False, server_default="60000"),
        sa.Column("effect_concurrency", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        # 安全
        sa.Column("default_permission_mode", sa.String(20), nullable=False, server_default="confirm"),
        sa.Column("playwright_domain_whitelist", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("require_hitl_for_high_risk", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sa_workspace_config_ws", "sa_workspace_config", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_sa_workspace_config_ws", "sa_workspace_config")
    op.drop_table("sa_workspace_config")
