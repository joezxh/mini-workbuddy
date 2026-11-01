"""meta_data_source 增加资产粗分类物化列 external_type（AF-01，Q1 裁决 B）

设计真源：docs/superpowers/specs/2026-11-01-asset-catalog-alignment-design.md §1.1。

- 加列（可空起步）→ 按 source_type→external_type 矩阵回填存量 → NOT NULL DEFAULT 'other'；
- CHECK 限枚举（先 DROP IF EXISTS 再 ADD，幂等重跑无害）；
- (tenant_id, external_type) 索引支撑 E40 目录树聚合；
- 与 startup_migrations 的兜底语句同义（AUTO_CREATE_TABLES 路径不走本迁移）。

Revision ID: 2026_11_01_0010_add_source_external_type
Revises: 2026_11_01_0009_seed_demo_ontologies
Create Date: 2026-11-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2026_11_01_0010_add_source_external_type"
down_revision: Union[str, None] = "2026_11_01_0009_seed_demo_ontologies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: 回填矩阵自包含（迁移不依赖应用层模块，防其后续演化使历史迁移漂移）；与
#: app/services/dataops/source_types.py 的 DEFAULT_EXTERNAL_TYPE_BY_SOURCE_TYPE 同步维护。
_BACKFILL_MATRIX = {
    "mysql": "rdbms", "oracle": "rdbms", "postgresql": "rdbms",
    "sqlserver": "rdbms", "dm": "rdbms", "kingbase": "rdbms",
    "clickhouse": "warehouse", "doris": "warehouse", "starrocks": "warehouse",
    "es": "search", "excel": "file",
}
_CHECK_ENUM = ("rdbms", "tsdb", "warehouse", "graph", "kv", "vector", "search", "file", "saas", "other")


def upgrade() -> None:
    op.execute("ALTER TABLE meta_data_source ADD COLUMN IF NOT EXISTS external_type VARCHAR(32)")
    for code, ext in _BACKFILL_MATRIX.items():
        op.execute(
            sa.text("UPDATE meta_data_source SET external_type = :ext "
                    "WHERE external_type IS NULL AND lower(source_type) = :code")
            .bindparams(ext=ext, code=code)
        )
    op.execute("UPDATE meta_data_source SET external_type = 'other' WHERE external_type IS NULL")
    op.alter_column(
        "meta_data_source", "external_type",
        existing_type=sa.String(32), nullable=False, server_default="other",
    )
    op.execute("ALTER TABLE meta_data_source DROP CONSTRAINT IF EXISTS ck_meta_data_source_external_type")
    op.execute(
        "ALTER TABLE meta_data_source ADD CONSTRAINT ck_meta_data_source_external_type "
        f"CHECK (external_type IN {tuple(_CHECK_ENUM)!r})".replace("'", "'")
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_meta_data_source_tenant_extype "
        "ON meta_data_source (tenant_id, external_type)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_meta_data_source_tenant_extype")
    op.execute("ALTER TABLE meta_data_source DROP CONSTRAINT IF EXISTS ck_meta_data_source_external_type")
    op.execute("ALTER TABLE meta_data_source DROP COLUMN IF EXISTS external_type")
