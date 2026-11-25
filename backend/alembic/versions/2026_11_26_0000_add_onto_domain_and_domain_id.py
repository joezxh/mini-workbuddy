"""add onto_domain + domain_id FKs on meta_table / onto_ontology.

新领域表由 ORM 元数据 create_all 建表（模型为唯一事实来源）；两张存量表以
ADD COLUMN IF NOT EXISTS / 查 pg_constraint 补 FK / CREATE INDEX IF NOT EXISTS
收敛，空库（create_all 已带列）与存量库两条路径都幂等可重跑。

FK 统一 ON DELETE SET NULL：领域是可选标注，删除领域只解除分组，不级联删除
元数据表或本体。原 meta_table.domain（数仓分层/主题域字符串列）保持不动。

Revision ID: 2026_11_26_0000_add_onto_domain
Revises: 2026_11_24_0000_kg_review
Create Date: 2026-11-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2026_11_26_0000_add_onto_domain"
down_revision: Union[str, None] = "2026_11_24_0000_kg_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FK_SPECS = (
    ("meta_table", "fk_meta_table_domain_id", "idx_meta_table_domain_id", "domain_id"),
    ("onto_ontology", "fk_onto_ontology_domain_id", "idx_onto_ontology_tenant_domain", "tenant_id, domain_id"),
)


def _has_table(bind, name: str) -> bool:
    return bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = :n"
        ),
        {"n": name},
    ).first() is not None


def _has_column(bind, table: str, column: str) -> bool:
    return bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).first() is not None


def _has_constraint(bind, name: str) -> bool:
    return bind.execute(
        sa.text("SELECT 1 FROM pg_constraint WHERE conname = :n"), {"n": name}
    ).first() is not None


def upgrade() -> None:
    bind = op.get_bind()

    from app.db.database import Base
    from app.models.ontology.domain import OntoDomain

    Base.metadata.create_all(bind=bind, tables=[OntoDomain.__table__])

    for table, fk_name, _idx_name, _idx_cols in _FK_SPECS:
        if not _has_table(bind, table):
            continue
        if not _has_column(bind, table, "domain_id"):
            op.execute(f'ALTER TABLE "{table}" ADD COLUMN domain_id BIGINT')
        if not _has_constraint(bind, fk_name):
            op.execute(
                f'ALTER TABLE "{table}" ADD CONSTRAINT "{fk_name}" '
                'FOREIGN KEY (domain_id) REFERENCES onto_domain(id) ON DELETE SET NULL'
            )

    for table, _fk_name, idx_name, idx_cols in _FK_SPECS:
        if _has_table(bind, table):
            op.execute(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table}" ({idx_cols})')


def downgrade() -> None:
    bind = op.get_bind()

    for table, fk_name, idx_name, _idx_cols in _FK_SPECS:
        op.execute(f'DROP INDEX IF EXISTS "{idx_name}"')
        if _has_constraint(bind, fk_name):
            op.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT "{fk_name}"')
        if _has_column(bind, table, "domain_id"):
            op.execute(f'ALTER TABLE "{table}" DROP COLUMN domain_id')

    if _has_table(bind, "onto_domain"):
        from app.db.database import Base
        from app.models.ontology.domain import OntoDomain

        OntoDomain.__table__.drop(bind=bind, checkfirst=True)
