"""add tenant_id to sys_dictionary (drift fix)

sys_dictionary 通过 TenantMixin 在 ORM 层声明了 tenant_id，但数据库表由
AUTO_CREATE_TABLES (create_all) 在早期模型尚未继承 TenantMixin 时建立，
create_all 不会为已存在的表追加新列，导致查询报
`column sys_dictionary.tenant_id does not exist`。

本迁移幂等补齐该列（仅当列不存在时执行），使库结构与模型一致。
（迁移链 001/002 的库结构已由 create_all 产出，故通过 stamp 标记为已应用。）

Revision ID: 003_add_sys_dictionary_tenant_id
Revises: 002_add_hub_source_type
Create Date: 2026-09-07 13:00:00.000000+08:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003_add_sys_dictionary_tenant_id"
down_revision: str = "002_add_hub_source_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = {c["name"] for c in insp.get_columns("sys_dictionary")}

    if "tenant_id" not in existing:
        op.add_column(
            "sys_dictionary",
            sa.Column("tenant_id", sa.BigInteger(), nullable=True, comment="租户ID"),
        )
        op.create_index(
            "ix_sys_dictionary_tenant_id",
            "sys_dictionary",
            ["tenant_id"],
        )

    # 幂等补默认系统租户（对应迁移 001 的 Step4，stamp 后未实际执行）
    op.execute(
        "INSERT INTO sys_tenant (tenant_id, name, status) "
        "VALUES (0, '系统管理', 'active') "
        "ON CONFLICT (tenant_id) DO NOTHING"
    )


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    existing = {c["name"] for c in insp.get_columns("sys_dictionary")}
    if "tenant_id" in existing:
        op.drop_index("ix_sys_dictionary_tenant_id", table_name="sys_dictionary")
        op.drop_column("sys_dictionary", "tenant_id")
