"""add kg_triple LLM review columns (review_verdict / review_note / reviewed_at)

关系 LLM 二次复核（证据复核 pass）的落库字段。三列全部可空：
未复核的历史数据 ``review_verdict IS NULL``，前端不显示复核徽标。

实现沿用 0002 迁移约定：information_schema 存在性判断 + ADD COLUMN，
重复执行安全（幂等）；SQLite 单测库由 ``Base.metadata.create_all`` 建列，不走本迁移。

Revision ID: 2026_11_24_0000_kg_review
Revises: 2026_11_22_0002_synccols
Create Date: 2026-11-24
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2026_11_24_0000_kg_review"
down_revision = "2026_11_22_0002_synccols"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    return bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).first() is not None


def _has_table(bind, table: str) -> bool:
    return bind.execute(
        sa.text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}
    ).scalar() is not None


_COLUMNS = (
    ("review_verdict", "VARCHAR(16)",
     "复核结论: supported|weak|unsupported|review_failed"),
    ("review_note", "TEXT", "复核理由（一句话）"),
    ("reviewed_at", "TIMESTAMP", "最近一次复核时间"),
)


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "kg_triple"):
        return
    for column, type_sql, comment in _COLUMNS:
        if _has_column(bind, "kg_triple", column):
            continue
        op.execute(f"ALTER TABLE kg_triple ADD COLUMN {column} {type_sql}")
        op.execute(f"COMMENT ON COLUMN kg_triple.{column} IS '{comment}'")
    # 复核页高频查询：按结论过滤待处理关系
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kg_triple_review_verdict "
        "ON kg_triple (knowledge_id, review_verdict)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "kg_triple"):
        return
    op.execute("DROP INDEX IF EXISTS ix_kg_triple_review_verdict")
    for column, _type, _c in _COLUMNS:
        if _has_column(bind, "kg_triple", column):
            op.execute(f"ALTER TABLE kg_triple DROP COLUMN {column}")
