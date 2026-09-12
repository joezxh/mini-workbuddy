"""add workflow management tables

新增 workflow_flow / workflow_execution_log / workflow_chain 三张表；
agent_config 新增 workflow_id 列。

Revision ID: 013_add_workflow_tables
Revises: 012_chat_model_api_fields
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB


revision = "013_add_workflow_tables"
down_revision = "012_chat_model_api_fields"
branch_labels = None
depends_on = None


def _existing(bind):
    insp = inspect(bind)
    tables = set(insp.get_table_names())
    result = {}
    for t in ("workflow_flow", "workflow_execution_log", "workflow_chain", "agent_config"):
        if t in tables:
            result[t] = {c["name"] for c in insp.get_columns(t)}
        else:
            result[t] = set()
    return tables, result


def upgrade() -> None:
    bind = op.get_bind()
    tables, cols = _existing(bind)

    # 1. workflow_flow
    if "workflow_flow" not in tables:
        op.create_table(
            "workflow_flow",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger, nullable=True, index=True),
            sa.Column("flow_code", sa.String(100), nullable=False),
            sa.Column("flow_name", sa.String(200), nullable=False),
            sa.Column("platform_type", sa.String(50), nullable=False, server_default="dify"),
            sa.Column("flow_type", sa.String(50), nullable=False),
            sa.Column("base_url", sa.String(500), nullable=False),
            sa.Column("api_key_enc", sa.Text, nullable=False),
            sa.Column("input_schema", JSONB, nullable=False, server_default="{}"),
            sa.Column("output_schema", JSONB, nullable=True),
            sa.Column("config", JSONB, nullable=True),
            sa.Column("description", sa.Text),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created_by", sa.BigInteger),
            sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
            sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
            sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        )
        op.create_index("uq_workflow_flow_code_tenant", "workflow_flow",
                        ["flow_code", "tenant_id"], unique=True)
        op.create_index("idx_workflow_flow_platform", "workflow_flow", ["platform_type"])

    # 2. workflow_execution_log
    if "workflow_execution_log" not in tables:
        op.create_table(
            "workflow_execution_log",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger, nullable=True, index=True),
            sa.Column("flow_id", sa.BigInteger, nullable=False),
            sa.Column("execution_id", sa.String(64), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("input_data", JSONB, nullable=True),
            sa.Column("output_data", JSONB, nullable=True),
            sa.Column("error_message", sa.Text),
            sa.Column("latency_ms", sa.Integer),
            sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("platform_trace", JSONB, nullable=True),
            sa.Column("started_at", sa.TIMESTAMP),
            sa.Column("completed_at", sa.TIMESTAMP),
            sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        )
        op.create_index("idx_wf_exec_log_flow", "workflow_execution_log", ["flow_id"])
        op.create_index("idx_wf_exec_log_status", "workflow_execution_log", ["status"])
        op.create_index("idx_wf_exec_log_created", "workflow_execution_log", ["created_at"])

    # 3. workflow_chain
    if "workflow_chain" not in tables:
        op.create_table(
            "workflow_chain",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger, nullable=True, index=True),
            sa.Column("chain_code", sa.String(100), nullable=False),
            sa.Column("chain_name", sa.String(200), nullable=False),
            sa.Column("steps", JSONB, nullable=False, server_default="[]"),
            sa.Column("description", sa.Text),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("created_by", sa.BigInteger),
            sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
            sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
            sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        )
        op.create_index("uq_workflow_chain_code_tenant", "workflow_chain",
                        ["chain_code", "tenant_id"], unique=True)

    # 4. agent_config.workflow_id
    if "agent_config" in cols and "workflow_id" not in cols["agent_config"]:
        op.add_column("agent_config",
                       sa.Column("workflow_id", sa.BigInteger, nullable=True,
                                 comment="FK → workflow_flow.id"))
        op.create_index("idx_agent_config_workflow", "agent_config", ["workflow_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables, cols = _existing(bind)

    if "agent_config" in cols and "workflow_id" in cols["agent_config"]:
        op.drop_index("idx_agent_config_workflow", "agent_config")
        op.drop_column("agent_config", "workflow_id")
    if "workflow_chain" in tables:
        op.drop_table("workflow_chain")
    if "workflow_execution_log" in tables:
        op.drop_table("workflow_execution_log")
    if "workflow_flow" in tables:
        op.drop_table("workflow_flow")
