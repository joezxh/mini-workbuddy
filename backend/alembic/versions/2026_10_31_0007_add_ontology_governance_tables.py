"""add ontology governance tables (10) + CDM 加列 + pg_trgm 检索索引 + 存量回填

设计真源：docs/superpowers/specs/2026-10-31-ontology-capability-design.md §3.2 / §3.5 / §3.6。

内容（§3.5）：
  ① 10 张新表（原 7 + meta_asset_tag / meta_asset_tag_binding / meta_ontology_publish）；
  ② 既有表加列（meta_standard_catalog.ontology_id、object/relation/standard/attribute 的
     review_status 等、object/relation 新建 source 列）；
  ③ §3.6 四个 pg_trgm GIN 索引（仅加速 LIKE，禁止 similarity()）；
  ④ D3 rev.2：meta_object_standard / meta_object_relation 建 source 列（原表无此列）；
  ⑤ 已有 source 的两张映射表（meta_table_standard / meta_column_standard）注释收敛为
     rule|human|llm_draft 并加同枚举 CHECK（核查修正：meta_standard 实际无 source 列，故不在此列）。

约定：
- 建表用 ORM 元数据 ``create_all``（模型是唯一事实来源，幂等）；加列/CHECK/索引一律幂等，
  空库（先 0003 create_all 已带新列）与存量库（需 ALTER 补列）两条路径都收敛、重跑无害。
- 存量回填：published → review_status=accepted，其余 suggested；对象属性绑定历史行按 established 处理。
- downgrade 逆序 drop，**不删 pg_trgm 扩展**（被迁移 006 与 kb_* 共用）。

Revision ID: 2026_10_31_0007_add_ontology_governance_tables
Revises: 2026_10_31_0006_add_kg_entity_embedding_half
Create Date: 2026-10-31
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2026_10_31_0007_add_ontology_governance_tables"
down_revision: Union[str, None] = "2026_10_31_0006_add_kg_entity_embedding_half"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 10 张新表（create_all 自动按 FK 依赖排序，此处列出仅用于 downgrade 逆序）
_NEW_TABLES = (
    "meta_ontology",
    "meta_ontology_version",
    "meta_ontology_build_job",
    "meta_ontology_build_item",
    "meta_ontology_cq",
    "meta_ontology_evidence",
    "meta_ontology_semantic",
    "meta_ontology_publish",
    "meta_asset_tag",
    "meta_asset_tag_binding",
)

_TRGM_INDEXES = (
    "ix_meta_table_name_trgm",
    "ix_meta_table_comment_trgm",
    "ix_meta_column_name_trgm",
    "ix_meta_column_comment_trgm",
)

# (表, 列定义 SQL)：ADD COLUMN IF NOT EXISTS，幂等
_ADDED_COLUMNS = (
    ("meta_standard_catalog", "ontology_id BIGINT"),
    ("meta_object_standard", "source VARCHAR(16) NOT NULL DEFAULT 'rule'"),
    ("meta_object_standard", "review_status VARCHAR(16) NOT NULL DEFAULT 'suggested'"),
    ("meta_object_standard", "reviewed_by BIGINT"),
    ("meta_object_standard", "reviewed_at TIMESTAMP"),
    ("meta_object_standard", "confidence DOUBLE PRECISION"),
    ("meta_object_standard", "evidence_ref BIGINT"),
    ("meta_object_standard_attribute", "review_status VARCHAR(16) NOT NULL DEFAULT 'suggested'"),
    ("meta_object_relation", "source VARCHAR(16) NOT NULL DEFAULT 'rule'"),
    ("meta_object_relation", "review_status VARCHAR(16) NOT NULL DEFAULT 'suggested'"),
    ("meta_object_relation", "reviewed_by BIGINT"),
    ("meta_object_relation", "reviewed_at TIMESTAMP"),
    ("meta_object_relation", "confidence DOUBLE PRECISION"),
    ("meta_object_relation", "evidence_ref BIGINT"),
    ("meta_standard", "review_status VARCHAR(16) NOT NULL DEFAULT 'suggested'"),
    ("meta_standard", "reviewed_by BIGINT"),
    ("meta_standard", "reviewed_at TIMESTAMP"),
)

# (表, 约束名, CHECK 表达式)：ADD CONSTRAINT 前查 pg_constraint
_CHECK_CONSTRAINTS = (
    ("meta_object_standard", "ck_meta_object_standard_source", "source IN ('rule','human','llm_draft')"),
    ("meta_object_standard", "ck_meta_object_standard_review", "review_status IN ('suggested','accepted','rejected')"),
    ("meta_object_standard_attribute", "ck_meta_object_attribute_review", "review_status IN ('suggested','accepted','rejected')"),
    ("meta_object_relation", "ck_meta_object_relation_source", "source IN ('rule','human','llm_draft')"),
    ("meta_object_relation", "ck_meta_object_relation_review", "review_status IN ('suggested','accepted','rejected')"),
    ("meta_standard", "ck_meta_standard_review", "review_status IN ('suggested','accepted','rejected')"),
    # 映射表：source 列早已存在，本次收敛取值域 + CHECK（存量只 rule/human，落新枚举内）
    ("meta_table_standard", "ck_meta_table_standard_source", "source IN ('rule','human','llm_draft')"),
    ("meta_column_standard", "ck_meta_column_standard_source", "source IN ('rule','human','llm_draft')"),
)

_COMMENT_UPDATES = (
    ("meta_table_standard", "source", "rule|human|llm_draft"),
    ("meta_column_standard", "source", "来源: rule|human|llm_draft"),
)

_ADDED_INDEXES = (
    ("meta_standard_catalog", "idx_meta_catalog_ontology", "tenant_id, ontology_id"),
    ("meta_object_standard", "idx_meta_object_standard_review", "tenant_id, review_status"),
    ("meta_object_relation", "idx_meta_object_relation_review", "tenant_id, review_status"),
)


def _has_constraint(bind, name: str) -> bool:
    return bind.execute(
        sa.text("SELECT 1 FROM pg_constraint WHERE conname = :n"), {"n": name}
    ).first() is not None


def upgrade() -> None:
    bind = op.get_bind()

    # ① 10 张新表：以 ORM 元数据建表（模型唯一事实来源，自带存在性判断）
    from app.db.database import Base
    from app.models.dataops.asset_tag import MetaAssetTag, MetaAssetTagBinding
    from app.models.dataops.ontology import (
        MetaOntology, MetaOntologyBuildItem, MetaOntologyBuildJob, MetaOntologyCq,
        MetaOntologyEvidence, MetaOntologyPublish, MetaOntologySemantic, MetaOntologyVersion,
    )

    new_tables = [
        MetaOntology.__table__, MetaOntologyVersion.__table__, MetaOntologyBuildJob.__table__,
        MetaOntologyBuildItem.__table__, MetaOntologyCq.__table__, MetaOntologyEvidence.__table__,
        MetaOntologySemantic.__table__, MetaOntologyPublish.__table__,
        MetaAssetTag.__table__, MetaAssetTagBinding.__table__,
    ]
    Base.metadata.create_all(bind=bind, tables=new_tables)

    # ② 既有表加列（ADD COLUMN IF NOT EXISTS 幂等：空库已被 create_all 带上时跳过）
    for table, coldef in _ADDED_COLUMNS:
        op.execute(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS {coldef}')

    # ④/⑤ source 收敛 + review_status CHECK（PG 无 ADD CONSTRAINT IF NOT EXISTS，需先查）
    for table, cname, expr in _CHECK_CONSTRAINTS:
        if not _has_constraint(bind, cname):
            op.execute(f'ALTER TABLE "{table}" ADD CONSTRAINT "{cname}" CHECK ({expr})')

    # 注释收敛（不影响行为，仅为消除 rule|llm 误导）
    for table, col, comment in _COMMENT_UPDATES:
        op.execute(f'COMMENT ON COLUMN "{table}"."{col}" IS \'{comment}\'')

    # 加列后的普通索引
    for table, iname, cols in _ADDED_INDEXES:
        op.execute(f'CREATE INDEX IF NOT EXISTS "{iname}" ON "{table}" ({cols})')

    # ③ §3.6 元数据全文检索索引（扩展已由迁移 006 创建，幂等复用；只用 GIN 加速 LIKE）
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_meta_table_name_trgm "
        "ON meta_table USING gin (table_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_meta_table_comment_trgm "
        "ON meta_table USING gin (table_comment gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_meta_column_name_trgm "
        "ON meta_column USING gin (column_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_meta_column_comment_trgm "
        "ON meta_column USING gin (column_comment gin_trgm_ops)"
    )

    # ④ 存量回填：使既有已发布元素不掉出门禁（published→accepted，其余 suggested）
    for table in ("meta_object_standard", "meta_object_relation", "meta_standard"):
        op.execute(
            f"UPDATE \"{table}\" SET review_status = "
            "CASE WHEN status = 'published' THEN 'accepted' ELSE 'suggested' END"
        )
    # 既有对象↔属性绑定视为已确立，避免历史 M2M 行被判为待审而卡门禁
    op.execute("UPDATE meta_object_standard_attribute SET review_status = 'accepted'")

    # 目录归属：为每个已有目录的租户创建 code='default' 默认本体，并把根目录挂上去（幂等）
    tenant_ids = bind.execute(
        sa.text("SELECT DISTINCT tenant_id FROM meta_standard_catalog WHERE tenant_id IS NOT NULL")
    ).scalars().all()
    for tid in tenant_ids:
        existing = bind.execute(
            sa.text("SELECT id FROM meta_ontology WHERE tenant_id = :t AND code = 'default'"),
            {"t": tid},
        ).first()
        if existing is None:
            bind.execute(
                sa.text(
                    "INSERT INTO meta_ontology (tenant_id, code, name, description, status, current_version) "
                    "VALUES (:t, 'default', '默认本体', '迁移内为既有目录归属创建的默认本体', 'draft', 0)"
                ),
                {"t": tid},
            )
            existing = bind.execute(
                sa.text("SELECT id FROM meta_ontology WHERE tenant_id = :t AND code = 'default'"),
                {"t": tid},
            ).first()
        op.execute(
            sa.text(
                "UPDATE meta_standard_catalog SET ontology_id = :oid "
                "WHERE tenant_id = :t AND parent_id IS NULL AND ontology_id IS NULL"
            ).bindparams(oid=existing[0], t=tid)
        )


def downgrade() -> None:
    bind = op.get_bind()

    # 逆序：先 drop 4 个 trgm 索引（不删 pg_trgm 扩展），再 drop 普通索引/约束/列，最后 drop 10 表
    for iname in _TRGM_INDEXES:
        op.execute(f'DROP INDEX IF EXISTS "{iname}"')

    for table, iname, _cols in _ADDED_INDEXES:
        op.execute(f'DROP INDEX IF EXISTS "{iname}"')

    for table, cname, _expr in _CHECK_CONSTRAINTS:
        op.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{cname}"')

    for table, coldef in reversed(_ADDED_COLUMNS):
        col = coldef.split()[0]
        op.execute(f'ALTER TABLE "{table}" DROP COLUMN IF EXISTS "{col}"')

    from app.db.database import Base

    for tbl in reversed(_NEW_TABLES):
        t = Base.metadata.tables.get(tbl)
        if t is not None:
            t.drop(bind=bind, checkfirst=True)
        else:
            op.execute(f'DROP TABLE IF EXISTS "{tbl}" CASCADE')
