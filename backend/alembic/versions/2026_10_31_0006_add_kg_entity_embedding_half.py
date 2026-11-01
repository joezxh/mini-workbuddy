"""kg_entity 半精度向量列（halfvec 生成列）+ HNSW 索引

问题：``KgEntity.embedding_half`` 是 2026-10-31 加进模型的后加列，而
``2026_10_30_0004_add_kg_tables`` 用 ``Base.metadata.create_all`` 建表——
对已存在的表整体跳过、不会补列，于是运行库与模型漂移，ORM 的 SELECT
展开全部列时报 ``column kg_entity.embedding_half does not exist``，
图谱查询接口（/graph/cdm-check、/graph/entities、/graph/relations …）全部 500。

本迁移只补 0004 之后新增的差异，不改既有列：

* ``embedding_half halfvec(dim)`` —— 生成列 ``embedding::halfvec``，维度取自
  ``embedding`` 列的真实 typmod（2048），避免与配置默认值失配；
* ``idx_kg_entity_embedding_half_hnsw`` —— HNSW 对 halfvec 的维度上限是 4000，
  2048 维可用（对 vector 的上限只有 2000，这正是引入 halfvec 的原因）。

Revision ID: 2026_10_31_0006_add_kg_entity_embedding_half
Revises: 2026_10_31_0005_add_kms_segment_graph_columns
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2026_10_31_0006_add_kg_entity_embedding_half"
down_revision: Union[str, None] = "2026_10_31_0005_add_kms_segment_graph_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _embedding_dim(bind) -> int:
    """取 embedding 列的真实维度（pgvector 用 typmod 存维度）。"""
    dim = bind.execute(sa.text(
        "SELECT a.atttypmod FROM pg_attribute a "
        "WHERE a.attrelid = 'kg_entity'::regclass AND a.attname = 'embedding'"
    )).scalar()
    if not dim or int(dim) <= 0:
        from app.config import settings

        dim = int(settings.EMBEDDING_DIMENSION)
    return int(dim)


def upgrade() -> None:
    bind = op.get_bind()

    # pgvector < 0.7 没有 halfvec：此时跳过（该列只服务 ANN 索引，缺失不影响正确性）
    if bind.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'halfvec'"
    )).first() is None:
        return

    has_col = bind.execute(sa.text(
        "SELECT 1 FROM pg_attribute WHERE attrelid = 'kg_entity'::regclass "
        "AND attname = 'embedding_half' AND NOT attisdropped"
    )).first()
    if has_col is None:
        dim = _embedding_dim(bind)
        op.execute(
            f"ALTER TABLE kg_entity ADD COLUMN embedding_half halfvec({dim}) "
            "GENERATED ALWAYS AS (embedding::halfvec) STORED"
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kg_entity_embedding_half_hnsw "
        "ON kg_entity USING hnsw (embedding_half halfvec_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_kg_entity_embedding_half_hnsw")
    op.execute("ALTER TABLE kg_entity DROP COLUMN IF EXISTS embedding_half")
