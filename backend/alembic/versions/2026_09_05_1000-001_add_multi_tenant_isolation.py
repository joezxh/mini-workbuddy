"""add multi-tenant isolation

Revision ID: 001
Revises:
Create Date: 2026-09-05 10:00:00.000000+08:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── 需要添加 tenant_id 列的业务表 ──────────────────────────────────
TENANT_TABLES = [
    # 系统管理
    "sys_user", "sys_role", "sys_user_role", "sys_audit_log",
    "sys_dictionary", "sys_dictionary_item",
    "sys_user_notification",
    "sys_infra_file", "sys_infra_file_content",
    # AI 会话 / Agent
    "ai_chat_session", "ai_chat_message",
    "ai_api_key", "ai_chat_model",
    "agent_config",
    "agent_team", "agent_team_member", "agent_team_edge",
    "agent_team_run", "agent_team_run_step", "agent_team_intervention",
    "agent_async_task", "agent_scheduled_task",
    "agent_execution", "agent_execution_event", "agent_trace",
    # 工具 / 技能 / MCP
    "ai_tool_definition",
    "ai_tool_group", "ai_tool_group_member",
    "ai_skill_package", "skill_rule",
    "ai_skill_version", "ai_skill_metrics",
    "ai_skill_evolution_config", "ai_skill_evolution_log", "ai_skill_script",
    "ai_mcp_api_key", "ai_mcp_client", "ai_mcp_square_template",
    "ai_web_search", "ai_web_search_log",
    "ai_skill_hub_repo",
    # 工作空间
    "ai_workspace",
    # Wiki
    "wiki_article", "wiki_article_version", "wiki_category",
]


def upgrade() -> None:
    # ── Step 1: 创建 sys_tenant_package 表 ──────────────────────────
    op.create_table(
        "sys_tenant_package",
        sa.Column("package_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False, comment="套餐名称"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", comment="状态"),
        sa.Column("remark", sa.String(500), comment="备注"),
        sa.Column("menu_ids", sa.JSON(), comment="关联菜单ID集合"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("package_id"),
    )

    # ── Step 2: 创建 sys_tenant 表 ─────────────────────────────────
    op.create_table(
        "sys_tenant",
        sa.Column("tenant_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False, comment="租户名称"),
        sa.Column("contact_name", sa.String(50), comment="联系人"),
        sa.Column("contact_mobile", sa.String(20), comment="联系电话"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", comment="状态"),
        sa.Column("package_id", sa.BigInteger(), sa.ForeignKey("sys_tenant_package.package_id"),
                  comment="租户套餐ID"),
        sa.Column("expire_time", sa.DateTime(), comment="过期时间"),
        sa.Column("account_count", sa.Integer(), server_default="0", comment="账号额度"),
        sa.Column("websites", sa.JSON(), comment="绑定域名列表"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id"),
        sa.UniqueConstraint("name"),
    )

    # ── Step 3: 为所有业务表添加 tenant_id 列 + 索引 ────────────────
    for table_name in TENANT_TABLES:
        op.add_column(
            table_name,
            sa.Column("tenant_id", sa.BigInteger(), nullable=True, comment="租户ID"),
        )
        op.create_index(
            f"ix_{table_name}_tenant_id",
            table_name,
            ["tenant_id"],
        )

    # ── Step 4: 创建默认系统租户 ────────────────────────────────────
    op.execute(
        "INSERT INTO sys_tenant (tenant_id, name, status) "
        "VALUES (0, '系统管理', 'active') "
        "ON CONFLICT (tenant_id) DO NOTHING"
    )

    # ── Step 5: 现有用户绑定到默认租户 ──────────────────────────────
    op.execute("UPDATE sys_user SET tenant_id = 0 WHERE tenant_id IS NULL")


def downgrade() -> None:
    # 逆序移除 tenant_id 列
    for table_name in reversed(TENANT_TABLES):
        op.drop_index(f"ix_{table_name}_tenant_id", table_name=table_name)
        op.drop_column(table_name, "tenant_id")

    op.drop_table("sys_tenant")
    op.drop_table("sys_tenant_package")
