"""add db_name to meta_table (PG 族三级作用域第一级)

PG 族「物理库→schema→表」三级作用域：早期把物理库丢进 meta_scan_job，快照
只存 schema（``database`` 列），导致跨物理库同名 schema 的表混在一起、前端按
库过滤失效。新增 ``db_name`` 存物理库/连接库名（非 PG 族与 ``database`` 同值），
幂等唯一键随之升级为 (source_id, db_name, database, table_name)。

- 存量行：db_name 回填为 database（非 PG 族语义等价；PG 族旧快照本就未区分库，
  重扫即按新链路写入正确物理库）。
- 幂等：列/约束按当前状态判断，重复执行安全。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "2026_10_28_0002_add_meta_table_db_name"
down_revision: Union[str, None] = "2026_10_28_0001_seed_data_source_type_dict"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "meta_table"
_CONSTRAINT = "uq_meta_table"


def _column_exists(bind, name: str) -> bool:
    return bind.execute(
        sa.text("SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c LIMIT 1"),
        {"t": _TABLE, "c": name},
    ).first() is not None


def _constraint_exists(bind, name: str) -> bool:
    return bind.execute(
        sa.text("SELECT 1 FROM pg_constraint WHERE conname = :n LIMIT 1"),
        {"n": name},
    ).first() is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "db_name"):
        op.add_column(
            _TABLE,
            sa.Column("db_name", sa.String(length=128), nullable=False,
                      server_default="", comment="物理库/连接库名（PG 族三级作用域第一级；非 PG 族与 database 同值）"),
        )
        # 存量行回填：物理库=作用域名（非 PG 族完全等价）
        bind.execute(sa.text(f"UPDATE {_TABLE} SET db_name = database WHERE db_name = ''"))

    # 唯一键升级：(source_id, database, table_name) → (source_id, db_name, database, table_name)
    if _constraint_exists(bind, _CONSTRAINT):
        op.drop_constraint(_CONSTRAINT, _TABLE, type_="unique")
    op.create_unique_constraint(_CONSTRAINT, _TABLE,
                                ["source_id", "db_name", "database", "table_name"])


def downgrade() -> None:
    bind = op.get_bind()
    if _constraint_exists(bind, _CONSTRAINT):
        op.drop_constraint(_CONSTRAINT, _TABLE, type_="unique")
    op.create_unique_constraint(_CONSTRAINT, _TABLE,
                                ["source_id", "database", "table_name"])
    if _column_exists(bind, "db_name"):
        op.drop_column(_TABLE, "db_name")
