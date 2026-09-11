"""add ontology tables (P4.1 本体持久化与租户隔离)

背景：
`WikiOwlEngine` 原为「进程内 rdflib.Graph 内存单例」，重启即丢且跨租户共享本体。
本迁移新增三张按 `tenant_id` 隔离的本体表，作为引擎的持久化后端：
  * `ontology`            本体定义（含 TTL 原始内容）
  * `ontology_class`      OWL 类（URI / 标签 / 父类 URI 列表）
  * `ontology_annotation` 目标对象（文章 / 片段 / 表 / 字段）↔ 本体类标注

说明：
* 状态字段用 `String(32)` 而非 PG ENUM（枚举类型后期变更困难，项目既有约定）；
* `parent_uris` / `class_uris` 用裸 `JSONB`（与 `wiki_article.owl_class_uris` 一致；
  不用 `JSON().with_variant(JSONB)`，否则 `.contains()` 会退化成 LIKE）；
* 迁移幂等：表已存在时跳过创建（兼容 AUTO_CREATE_TABLES 先建表的环境）。

Revision ID: 004_add_ontology_tables
Revises: 003_add_sys_dictionary_tenant_id
Create Date: 2026-09-10 00:00:00.000000+08:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "004_add_ontology_tables"
down_revision: Union[str, None] = "003_add_sys_dictionary_tenant_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_tables() -> set:
    """当前库中已存在的表名集合。

    离线模式（`alembic upgrade --sql`）没有真实连接，无法反射，返回空集合。
    """
    if op.get_context().as_sql:
        return set()
    insp = sa.inspect(op.get_bind())
    return set(insp.get_table_names())


def upgrade() -> None:
    existing = _existing_tables()

    if "ontology" not in existing:
        op.create_table(
            "ontology",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
            sa.Column("tenant_id", sa.BigInteger(), nullable=True, comment="租户ID"),
            sa.Column("code", sa.String(100), nullable=False, comment="本体编码（租户内唯一，如 default）"),
            sa.Column("name", sa.String(200), nullable=True, comment="本体名称"),
            sa.Column("description", sa.Text(), nullable=True, comment="本体描述"),
            sa.Column("namespace_uri", sa.String(500), nullable=True, comment="本体命名空间 URI"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1", comment="本体版本号"),
            sa.Column(
                "status",
                sa.String(32),
                nullable=False,
                server_default="draft",
                comment="状态: draft|published|archived",
            ),
            sa.Column(
                "source",
                sa.String(32),
                nullable=False,
                server_default="manual",
                comment="来源: manual|ttl_import|build",
            ),
            sa.Column("ttl_content", sa.Text(), nullable=True, comment="TTL 原文（唯一真相源：规范化后的全量内容，类与标注索引均由它派生）"),
            sa.Column("creator_id", sa.BigInteger(), nullable=True, comment="创建者 ID"),
            sa.Column("updater_id", sa.BigInteger(), nullable=True, comment="最后更新者 ID"),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False, comment="创建时间"),
            sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False, comment="更新时间"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "code", name="uq_ontology_code"),
        )
        op.create_index("ix_ontology_tenant_id", "ontology", ["tenant_id"])
        op.create_index("idx_ontology_tenant", "ontology", ["tenant_id"])
        op.create_index("idx_ontology_status", "ontology", ["status"])

    if "ontology_class" not in existing:
        op.create_table(
            "ontology_class",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
            sa.Column("tenant_id", sa.BigInteger(), nullable=True, comment="租户ID"),
            sa.Column("ontology_id", sa.BigInteger(), nullable=False, comment="所属本体 ID"),
            sa.Column("uri", sa.String(1000), nullable=False, comment="类 URI"),
            sa.Column("label", sa.String(500), nullable=True, comment="中文标签"),
            sa.Column("comment", sa.Text(), nullable=True, comment="类描述"),
            sa.Column("parent_uris", JSONB(), nullable=True, comment="父类 URI 列表"),
            sa.Column(
                "status",
                sa.String(32),
                nullable=False,
                server_default="active",
                comment="状态: active|deprecated",
            ),
            sa.Column("display_order", sa.Integer(), nullable=False, server_default="0", comment="展示顺序"),
            sa.Column("creator_id", sa.BigInteger(), nullable=True, comment="创建者 ID"),
            sa.Column("updater_id", sa.BigInteger(), nullable=True, comment="最后更新者 ID"),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False, comment="创建时间"),
            sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False, comment="更新时间"),
            sa.ForeignKeyConstraint(["ontology_id"], ["ontology.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("ontology_id", "uri", name="uq_ontology_class"),
        )
        op.create_index("ix_ontology_class_tenant_id", "ontology_class", ["tenant_id"])
        op.create_index("idx_ontology_class_ontology", "ontology_class", ["ontology_id"])
        op.create_index("idx_ontology_class_status", "ontology_class", ["status"])

    if "ontology_annotation" not in existing:
        op.create_table(
            "ontology_annotation",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
            sa.Column("tenant_id", sa.BigInteger(), nullable=True, comment="租户ID"),
            sa.Column("ontology_id", sa.BigInteger(), nullable=False, comment="所属本体 ID"),
            sa.Column(
                "target_type",
                sa.String(32),
                nullable=False,
                server_default="article",
                comment="目标类型: article|segment|table|column",
            ),
            sa.Column("target_id", sa.String(500), nullable=False, comment="目标对象 ID（字符串化）"),
            sa.Column("class_uris", JSONB(), nullable=True, comment="关联的本体类 URI 列表"),
            sa.Column("creator_id", sa.BigInteger(), nullable=True, comment="创建者 ID"),
            sa.Column("updater_id", sa.BigInteger(), nullable=True, comment="最后更新者 ID"),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False, comment="创建时间"),
            sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False, comment="更新时间"),
            sa.ForeignKeyConstraint(["ontology_id"], ["ontology.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("ontology_id", "target_type", "target_id", name="uq_ontology_annotation"),
        )
        op.create_index("ix_ontology_annotation_tenant_id", "ontology_annotation", ["tenant_id"])
        op.create_index("idx_ontology_annotation_target", "ontology_annotation", ["target_type", "target_id"])
        op.create_index("idx_ontology_annotation_ontology", "ontology_annotation", ["ontology_id"])


def downgrade() -> None:
    existing = _existing_tables()

    if "ontology_annotation" in existing:
        op.drop_index("idx_ontology_annotation_ontology", table_name="ontology_annotation")
        op.drop_index("idx_ontology_annotation_target", table_name="ontology_annotation")
        op.drop_index("ix_ontology_annotation_tenant_id", table_name="ontology_annotation")
        op.drop_table("ontology_annotation")

    if "ontology_class" in existing:
        op.drop_index("idx_ontology_class_status", table_name="ontology_class")
        op.drop_index("idx_ontology_class_ontology", table_name="ontology_class")
        op.drop_index("ix_ontology_class_tenant_id", table_name="ontology_class")
        op.drop_table("ontology_class")

    if "ontology" in existing:
        op.drop_index("idx_ontology_status", table_name="ontology")
        op.drop_index("idx_ontology_tenant", table_name="ontology")
        op.drop_index("ix_ontology_tenant_id", table_name="ontology")
        op.drop_table("ontology")
