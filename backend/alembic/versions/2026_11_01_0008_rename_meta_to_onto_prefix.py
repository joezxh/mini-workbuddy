"""rename 本体治理/资产标签表前缀 meta_ -> onto_（幂等，兼容已部署库）

背景：设计真源表前缀统一为 onto_。迁移 ``0007`` 以 ORM ``create_all`` 建表，模型 ``__tablename__``
改为 ``onto_*`` 后，全新库直接建 ``onto_*``；本迁移只对**已部署库**（历史上 0007 建的是
``meta_ontology*`` / ``meta_asset_tag*``）做表名改名，并顺带把这些表上仍带 ``meta_`` 的
约束/索引名机械替换为 ``onto_``（与模型 ``__table_args__`` 命名对齐，避免 autogenerate 漂移）。

两条路径都收敛、重跑无害：
- 全新库：``meta_*`` 不存在 → 表改名跳过；``onto_*`` 表上约束/索引已是 ``onto_`` → 命中 0 条。
- 存量库：``meta_*`` 存在 → 改名为 ``onto_*``，再改约束/索引名。

Revision ID: 2026_11_01_0008_rename_meta_to_onto_prefix
Revises: 2026_10_31_0007_add_ontology_governance_tables
Create Date: 2026-11-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2026_11_01_0008_rename_meta_to_onto_prefix"
down_revision: Union[str, None] = "2026_10_31_0007_add_ontology_governance_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (旧表名, 新表名) —— 本体治理 8 张 + 资产标签 2 张
_PAIRS = (
    ("meta_ontology", "onto_ontology"),
    ("meta_ontology_version", "onto_ontology_version"),
    ("meta_ontology_build_job", "onto_ontology_build_job"),
    ("meta_ontology_build_item", "onto_ontology_build_item"),
    ("meta_ontology_cq", "onto_ontology_cq"),
    ("meta_ontology_evidence", "onto_ontology_evidence"),
    ("meta_ontology_semantic", "onto_ontology_semantic"),
    ("meta_ontology_publish", "onto_ontology_publish"),
    ("meta_asset_tag", "onto_asset_tag"),
    ("meta_asset_tag_binding", "onto_asset_tag_binding"),
)


def _table_exists(bind, name: str) -> bool:
    return bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = :n"
        ),
        {"n": name},
    ).first() is not None


def _rename_identifiers(bind, table: str, src: str, dst: str) -> None:
    """把 ``table`` 上名字仍含 ``src_`` 的约束/索引改名为 ``dst_``（先约束后索引，避免唯一/pkey 索引二次改名）。"""
    cons = bind.execute(
        sa.text(
            "SELECT c.conname FROM pg_constraint c "
            "JOIN pg_class r ON r.oid = c.conrelid "
            "WHERE r.relname = :t AND c.conname LIKE :like"
        ),
        {"t": table, "like": f"%{src}_%"},
    ).all()
    for (cname,) in cons:
        op.execute(
            f'ALTER TABLE "{table}" RENAME CONSTRAINT "{cname}" TO "{cname.replace(src, dst)}"'
        )
    idxs = bind.execute(
        sa.text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = :t AND indexname LIKE :like"
        ),
        {"t": table, "like": f"%{src}_%"},
    ).all()
    for (iname,) in idxs:
        op.execute(f'ALTER INDEX IF EXISTS "{iname}" RENAME TO "{iname.replace(src, dst)}"')


def upgrade() -> None:
    bind = op.get_bind()
    for old, new in _PAIRS:
        if _table_exists(bind, old) and not _table_exists(bind, new):
            op.execute(f'ALTER TABLE "{old}" RENAME TO "{new}"')
        # 改名后（或历史遗留 onto_ 表）把仍带 meta_ 的约束/索引对齐为 onto_
        if _table_exists(bind, new):
            _rename_identifiers(bind, new, "meta", "onto")


def downgrade() -> None:
    bind = op.get_bind()
    for old, new in reversed(_PAIRS):
        # 先把 onto_ 约束/索引回退为 meta_，再把表名回退
        if _table_exists(bind, new):
            _rename_identifiers(bind, new, "onto", "meta")
        if _table_exists(bind, new) and not _table_exists(bind, old):
            op.execute(f'ALTER TABLE "{new}" RENAME TO "{old}"')
