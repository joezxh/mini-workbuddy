"""add knowledge-graph instance tables (4): entity / entity-mention / triple / triple-mention

图谱知识库（type=4）实例层落库：实体实例（节点）/ 关系实例（边）+ 各自的切片提及表。
模式层复用 dataops CDM（meta_object_standard / meta_object_relation），本迁移零新增模式表。

实现方式沿用 003 迁移约定：直接以 ORM 元数据建表
（``app/models/kb/kg_*.py`` 是唯一事实来源），避免在迁移里二次声明列定义造成漂移；
``create_all`` 自带存在性判断，重复执行安全（幂等）。

向量 ANN 索引**本迁移不建**：当前生效维度为 2048（``settings.EMBEDDING_DIMENSION``），
超出 pgvector HNSW 的 2000 维上限（``column cannot have more than 2000 dimensions``），
且既有 ``kms_segment.embedding``（同为 vector(2048)）在全库同样**没有** ANN 索引——
本项目在 2048 维下即以顺序扫描做向量检索。kg_* 沿用同一策略：
P1 不写入向量，无需索引；P3/P4 真正写入后，再按实测数据选型
（IVFFlat 支持至 16000 维，或降维 / halfvec），避免无性能数据支撑的投机性索引。

Revision ID: 2026_10_30_0004_add_kg_tables
Revises: 2026_10_28_0003_add_standard_cdm_tables
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2026_10_30_0004_add_kg_tables"
down_revision: Union[str, None] = "2026_10_28_0003_add_standard_cdm_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables():
    from app.models.kb.kg_entity import KgEntity
    from app.models.kb.kg_entity_mention import KgEntityMention
    from app.models.kb.kg_triple import KgTriple
    from app.models.kb.kg_triple_mention import KgTripleMention

    # 顺序即建表顺序：entity -> entity_mention -> triple -> triple_mention
    return [
        KgEntity.__table__,
        KgEntityMention.__table__,
        KgTriple.__table__,
        KgTripleMention.__table__,
    ]


def upgrade() -> None:
    from app.db.database import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=_tables())

    # 别名 / 属性 GIN 索引：支持「按别名命中」「按属性值过滤」（与向量维度无关）
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kg_entity_aliases_gin "
        "ON kg_entity USING gin (aliases)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kg_entity_properties_gin "
        "ON kg_entity USING gin (properties)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kg_triple_properties_gin "
        "ON kg_triple USING gin (properties)"
    )


def downgrade() -> None:
    from app.db.database import Base

    # 逆序 drop：triple_mention -> triple -> entity_mention -> entity
    Base.metadata.drop_all(bind=op.get_bind(), tables=list(reversed(_tables())))
