"""add agent_config.workflow_id

AgentConfig 模型新增 workflow_id（FK → workflow_flow.id），此前仅靠
create_all 不会为已存在的表补列，导致 ORM 查询报 UndefinedColumn。

幂等：列/索引已存在则跳过。

Revision ID: 013_agent_config_workflow_id
Revises: 013_add_workflow_tables
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "013_agent_config_workflow_id"
down_revision = "013_add_workflow_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("agent_config")}
    if "workflow_id" not in cols:
        op.add_column(
            "agent_config",
            sa.Column("workflow_id", sa.BigInteger(), nullable=True, comment="FK → workflow_flow.id"),
        )
    idx_names = {i["name"] for i in inspect(bind).get_indexes("agent_config")}
    if "idx_agent_config_workflow" not in idx_names:
        op.create_index("idx_agent_config_workflow", "agent_config", ["workflow_id"])


def downgrade() -> None:
    bind = op.get_bind()
    idx_names = {i["name"] for i in inspect(bind).get_indexes("agent_config")}
    if "idx_agent_config_workflow" in idx_names:
        op.drop_index("idx_agent_config_workflow", table_name="agent_config")
    cols = {c["name"] for c in inspect(bind).get_columns("agent_config")}
    if "workflow_id" in cols:
        op.drop_column("agent_config", "workflow_id")
