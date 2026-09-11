"""add ontology modeling tables (P4.2 建模六表与 CQ)

背景：
P4.1 解决「本体存哪里」（ontology / ontology_class / ontology_annotation），
本迁移补上治理侧的六张表（借鉴 ontomind 的 CQ 驱动建模方法）：
  * ontology_object_type   对象类型（业务概念，支持父子层级）
  * ontology_property      对象类型的属性
  * ontology_link_type     关系类型（含基数 cardinality）
  * ontology_mapping       对象类型 ↔ 物理表/列 的映射（原料来自 P2 元数据）
  * ontology_cq            能力问题（Competency Question）
  * ontology_version       版本快照（生成/对比是 Task 6，本迁移只建表）

顺带清理（P4.1 复审遗留，用户拍板挂本任务）：
  * MI-04：drop `ontology.idx_ontology_tenant` —— 与 TenantMixin(index=True)
    自动生成的 `ix_ontology_tenant_id` 完全重复；
  * `ontology_class.uri` 列宽 1000 → 500：1000 字符 URI 以 UTF-8 存储最长
    约 3000 字节，超过 PG btree 索引条目上限（约 2704 字节），会让
    `uq_ontology_class` 在写入多字节 URI 时报错。500×3=1500 字节安全，
    且 `MAX_URI_LENGTH` 同步收敛到 500（入库前校验）。表未上线
    （`wiki_owl` 路由 enabled=False），不存在存量超长数据。

说明：
* 状态字段用 `String(32)` 而非 PG ENUM（项目既有约定）；
* 六表不带 `tenant_id`（spec §5.2），经 `ontology_id` 归属本体；
  跨租户安全由 `ModelingService` 的租户链路保证；
* `source` 的 `llm` 取值保留但不产生（与 P2 spec 一致，不做 LLM 抽取通道）；
* 迁移幂等：表已存在时跳过创建（兼容 AUTO_CREATE_TABLES 先建表的环境）。

Revision ID: 005_add_ontology_modeling_tables
Revises: 004_add_ontology_tables
Create Date: 2026-09-10 00:00:00.000000+08:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "005_add_ontology_modeling_tables"
down_revision: Union[str, None] = "004_add_ontology_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MODELING_TABLES = (
    "ontology_object_type",
    "ontology_property",
    "ontology_link_type",
    "ontology_mapping",
    "ontology_cq",
    "ontology_version",
)


def _existing_tables() -> set:
    """当前库中已存在的表名集合（离线模式返回空集合）。"""
    if op.get_context().as_sql:
        return set()
    insp = sa.inspect(op.get_bind())
    return set(insp.get_table_names())


def _audit_columns() -> list:
    """六表共用的审计列。"""
    return [
        sa.Column("creator_id", sa.BigInteger(), nullable=True, comment="创建者 ID"),
        sa.Column("updater_id", sa.BigInteger(), nullable=True, comment="最后更新者 ID"),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False, comment="更新时间"),
    ]


def upgrade() -> None:
    existing = _existing_tables()

    # ── 附带清理 ────────────────────────────────────────────────────────────
    # MI-04：与 TenantMixin 自动索引重复
    op.execute("DROP INDEX IF EXISTS idx_ontology_tenant")
    # uri 列宽收敛（btree 条目上限风险，见文件头说明）
    if "ontology_class" in existing:
        op.alter_column(
            "ontology_class",
            "uri",
            existing_type=sa.String(1000),
            type_=sa.String(500),
            existing_nullable=False,
            comment="类 URI",
        )

    # ── 1. 对象类型 ─────────────────────────────────────────────────────────
    if "ontology_object_type" not in existing:
        op.create_table(
            "ontology_object_type",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
            sa.Column("ontology_id", sa.BigInteger(), nullable=False, comment="所属本体 ID"),
            sa.Column("code", sa.String(128), nullable=False, comment="对象类型编码（本体内唯一，如 customer）"),
            sa.Column("name", sa.String(200), nullable=False, comment="对象类型名称（如 客户）"),
            sa.Column("description", sa.Text(), nullable=True, comment="业务描述"),
            sa.Column("parent_id", sa.BigInteger(), nullable=True, comment="父对象类型 ID（自引用）"),
            sa.Column(
                "status",
                sa.String(32),
                nullable=False,
                server_default="suggested",
                comment="评审状态: suggested|accepted|rejected",
            ),
            sa.Column(
                "source",
                sa.String(32),
                nullable=False,
                server_default="human",
                comment="来源: rule|human|llm",
            ),
            sa.Column("confidence", sa.Float(), nullable=True, comment="置信度 0~1"),
            sa.Column("evidence_json", JSONB(), nullable=True, comment="来源证据"),
            *_audit_columns(),
            sa.ForeignKeyConstraint(["ontology_id"], ["ontology.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["parent_id"], ["ontology_object_type.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("ontology_id", "code", name="uq_ontology_object_type"),
        )
        op.create_index("idx_object_type_ontology", "ontology_object_type", ["ontology_id"])
        op.create_index("idx_object_type_parent", "ontology_object_type", ["parent_id"])
        op.create_index("idx_object_type_status", "ontology_object_type", ["status"])

    # ── 2. 属性 ─────────────────────────────────────────────────────────────
    if "ontology_property" not in existing:
        op.create_table(
            "ontology_property",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
            sa.Column("object_type_id", sa.BigInteger(), nullable=False, comment="所属对象类型 ID"),
            sa.Column("code", sa.String(128), nullable=False, comment="属性编码（对象类型内唯一）"),
            sa.Column("name", sa.String(200), nullable=False, comment="属性名称"),
            sa.Column(
                "data_type",
                sa.String(64),
                nullable=False,
                server_default="string",
                comment="数据类型: string|int|decimal|date|datetime|boolean 等",
            ),
            sa.Column("required", sa.Boolean(), nullable=False, server_default="false", comment="是否必填"),
            sa.Column("semantic_type", sa.String(128), nullable=True, comment="语义类型（如 手机号）"),
            sa.Column("status", sa.String(32), nullable=False, server_default="suggested", comment="评审状态: suggested|accepted|rejected"),
            sa.Column("source", sa.String(32), nullable=False, server_default="human", comment="来源: rule|human|llm"),
            sa.Column("confidence", sa.Float(), nullable=True, comment="置信度 0~1"),
            *_audit_columns(),
            sa.ForeignKeyConstraint(
                ["object_type_id"], ["ontology_object_type.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("object_type_id", "code", name="uq_ontology_property"),
        )
        op.create_index("idx_property_object_type", "ontology_property", ["object_type_id"])
        op.create_index("idx_property_status", "ontology_property", ["status"])

    # ── 3. 关系类型 ─────────────────────────────────────────────────────────
    if "ontology_link_type" not in existing:
        op.create_table(
            "ontology_link_type",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
            sa.Column("ontology_id", sa.BigInteger(), nullable=False, comment="所属本体 ID"),
            sa.Column("code", sa.String(128), nullable=False, comment="关系类型编码（本体内唯一）"),
            sa.Column("name", sa.String(200), nullable=False, comment="关系类型名称"),
            sa.Column("source_type_id", sa.BigInteger(), nullable=False, comment="起始对象类型 ID"),
            sa.Column("target_type_id", sa.BigInteger(), nullable=False, comment="目标对象类型 ID"),
            sa.Column("cardinality", sa.String(32), nullable=False, server_default="N:M", comment="基数: 1:1|1:N|N:M"),
            sa.Column("status", sa.String(32), nullable=False, server_default="suggested", comment="评审状态: suggested|accepted|rejected"),
            sa.Column("source", sa.String(32), nullable=False, server_default="human", comment="来源: rule|human|llm"),
            sa.Column("confidence", sa.Float(), nullable=True, comment="置信度 0~1"),
            sa.Column("evidence_json", JSONB(), nullable=True, comment="来源证据"),
            *_audit_columns(),
            sa.ForeignKeyConstraint(["ontology_id"], ["ontology.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["source_type_id"], ["ontology_object_type.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["target_type_id"], ["ontology_object_type.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("ontology_id", "code", name="uq_ontology_link_type"),
        )
        op.create_index("idx_link_type_ontology", "ontology_link_type", ["ontology_id"])
        op.create_index("idx_link_type_source", "ontology_link_type", ["source_type_id"])
        op.create_index("idx_link_type_target", "ontology_link_type", ["target_type_id"])

    # ── 4. 映射 ─────────────────────────────────────────────────────────────
    if "ontology_mapping" not in existing:
        op.create_table(
            "ontology_mapping",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
            sa.Column("ontology_id", sa.BigInteger(), nullable=False, comment="所属本体 ID"),
            sa.Column("object_type_id", sa.BigInteger(), nullable=False, comment="映射到的对象类型 ID"),
            sa.Column("target_type", sa.String(32), nullable=False, server_default="table", comment="映射目标类型: table|column"),
            sa.Column("source_id", sa.String(128), nullable=True, comment="P2 元数据对象 ID（字符串化）"),
            sa.Column("database", sa.String(128), nullable=True, comment="物理库名"),
            sa.Column("table_name", sa.String(200), nullable=False, comment="物理表名"),
            sa.Column("column_name", sa.String(200), nullable=True, comment="物理列名（target_type=column 时必填）"),
            sa.Column("status", sa.String(32), nullable=False, server_default="suggested", comment="评审状态: suggested|accepted|rejected"),
            sa.Column("source", sa.String(32), nullable=False, server_default="human", comment="来源: rule|human|llm"),
            sa.Column("confidence", sa.Float(), nullable=True, comment="置信度 0~1"),
            *_audit_columns(),
            sa.ForeignKeyConstraint(["ontology_id"], ["ontology.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["object_type_id"], ["ontology_object_type.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_mapping_ontology", "ontology_mapping", ["ontology_id"])
        op.create_index("idx_mapping_object_type", "ontology_mapping", ["object_type_id"])
        op.create_index("idx_mapping_target", "ontology_mapping", ["target_type", "table_name"])
        op.create_index("idx_mapping_status", "ontology_mapping", ["status"])

    # ── 5. 能力问题 ─────────────────────────────────────────────────────────
    if "ontology_cq" not in existing:
        op.create_table(
            "ontology_cq",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
            sa.Column("ontology_id", sa.BigInteger(), nullable=False, comment="所属本体 ID"),
            sa.Column("question", sa.Text(), nullable=False, comment="能力问题（自然语言）"),
            sa.Column("answer_hint", sa.Text(), nullable=True, comment="回答提示"),
            sa.Column("status", sa.String(32), nullable=False, server_default="active", comment="状态: active|archived"),
            sa.Column("linked_object_types", JSONB(), nullable=True, comment="关联的对象类型 code 列表（非空即视为已覆盖）"),
            *_audit_columns(),
            sa.ForeignKeyConstraint(["ontology_id"], ["ontology.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_cq_ontology", "ontology_cq", ["ontology_id"])
        op.create_index("idx_cq_status", "ontology_cq", ["status"])

    # ── 6. 版本快照 ─────────────────────────────────────────────────────────
    if "ontology_version" not in existing:
        op.create_table(
            "ontology_version",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
            sa.Column("ontology_id", sa.BigInteger(), nullable=False, comment="所属本体 ID"),
            sa.Column("version", sa.String(32), nullable=False, comment="版本号（由 Task 6 定义格式）"),
            sa.Column("snapshot_json", JSONB(), nullable=False, comment="快照内容"),
            sa.Column("change_note", sa.Text(), nullable=True, comment="变更说明"),
            sa.Column("author_user_id", sa.BigInteger(), nullable=True, comment="创建快照的用户 ID"),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False, comment="创建时间"),
            sa.ForeignKeyConstraint(["ontology_id"], ["ontology.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("ontology_id", "version", name="uq_ontology_version"),
        )
        op.create_index("idx_version_ontology", "ontology_version", ["ontology_id"])


def downgrade() -> None:
    existing = _existing_tables()

    if "ontology_version" in existing:
        op.drop_index("idx_version_ontology", table_name="ontology_version")
        op.drop_table("ontology_version")

    if "ontology_cq" in existing:
        op.drop_index("idx_cq_status", table_name="ontology_cq")
        op.drop_index("idx_cq_ontology", table_name="ontology_cq")
        op.drop_table("ontology_cq")

    if "ontology_mapping" in existing:
        op.drop_index("idx_mapping_status", table_name="ontology_mapping")
        op.drop_index("idx_mapping_target", table_name="ontology_mapping")
        op.drop_index("idx_mapping_object_type", table_name="ontology_mapping")
        op.drop_index("idx_mapping_ontology", table_name="ontology_mapping")
        op.drop_table("ontology_mapping")

    if "ontology_link_type" in existing:
        op.drop_index("idx_link_type_target", table_name="ontology_link_type")
        op.drop_index("idx_link_type_source", table_name="ontology_link_type")
        op.drop_index("idx_link_type_ontology", table_name="ontology_link_type")
        op.drop_table("ontology_link_type")

    if "ontology_property" in existing:
        op.drop_index("idx_property_status", table_name="ontology_property")
        op.drop_index("idx_property_object_type", table_name="ontology_property")
        op.drop_table("ontology_property")

    if "ontology_object_type" in existing:
        op.drop_index("idx_object_type_status", table_name="ontology_object_type")
        op.drop_index("idx_object_type_parent", table_name="ontology_object_type")
        op.drop_index("idx_object_type_ontology", table_name="ontology_object_type")
        op.drop_table("ontology_object_type")

    if "ontology_class" in existing:
        op.alter_column(
            "ontology_class",
            "uri",
            existing_type=sa.String(500),
            type_=sa.String(1000),
            existing_nullable=False,
            comment="类 URI",
        )

    # 恢复 MI-04 清理前的重复索引（仅当 ontology 表仍存在且索引缺失时）
    if "ontology" in existing:
        op.create_index("idx_ontology_tenant", "ontology", ["tenant_id"])
