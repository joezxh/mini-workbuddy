"""标准三层语义模型（CDM）+ 目录/场景 + 表绑定/关系校验。

纯增量：不改动 standard.py 的 meta_standard / meta_column_standard。
见 spec docs/superpowers/specs/2026-10-28-standard-cdm-graph-ui-design.md。
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, Float, ForeignKey, Index, Integer, String,
    Text, TIMESTAMP, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class MetaStandardCatalog(Base, TenantMixin):
    """目录/场景层级树（圈定对象标准与关系标准）。"""

    __tablename__ = "meta_standard_catalog"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    parent_id = Column(BigInteger, ForeignKey("meta_standard_catalog.id", ondelete="RESTRICT"), nullable=True, comment="父节点（null=根）")
    code = Column(String(64), nullable=False, comment="目录编码（租户内唯一）")
    name = Column(String(200), nullable=False, comment="目录名称")
    description = Column(Text, nullable=True, comment="说明")
    icon = Column(String(32), nullable=True, comment="展示图标/emoji")
    sort_order = Column(Integer, nullable=False, server_default="0", comment="同级排序")
    status = Column(String(32), nullable=False, server_default="draft", comment="draft|published")
    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    updater_id = Column(BigInteger, nullable=True, comment="最后更新者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_meta_catalog_code"),
        Index("idx_meta_catalog_tenant_parent", "tenant_id", "parent_id"),
    )


class MetaObjectStandard(Base, TenantMixin):
    """对象（表级）标准模板；catalog_id 可空=未归类。"""

    __tablename__ = "meta_object_standard"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    catalog_id = Column(BigInteger, ForeignKey("meta_standard_catalog.id", ondelete="RESTRICT"), nullable=True, comment="所属目录/场景（可空）")
    code = Column(String(64), nullable=False, comment="对象标准编码（租户内唯一）")
    name = Column(String(200), nullable=False, comment="对象名称")
    aliases_json = Column(JSONB, nullable=True, comment="别名（匹配物理表名/注释）")
    description = Column(Text, nullable=True, comment="说明")
    domain = Column(String(64), nullable=True, comment="主题域")
    status = Column(String(32), nullable=False, server_default="draft", comment="draft|published")
    current_version = Column(Integer, nullable=False, server_default="1", comment="当前版本号")
    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    updater_id = Column(BigInteger, nullable=True, comment="最后更新者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_meta_object_standard_code"),
        Index("idx_meta_object_standard_catalog", "tenant_id", "catalog_id"),
    )


class MetaObjectStandardAttribute(Base, TenantMixin):
    """对象↔属性 引用（M2M，落地属性全局复用）。"""

    __tablename__ = "meta_object_standard_attribute"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    object_id = Column(BigInteger, ForeignKey("meta_object_standard.id", ondelete="CASCADE"), nullable=False, comment="对象标准 ID")
    standard_id = Column(BigInteger, ForeignKey("meta_standard.id", ondelete="RESTRICT"), nullable=False, comment="属性标准 ID")
    required = Column(Boolean, nullable=False, server_default="false", comment="是否必填属性")
    sort_order = Column(Integer, nullable=False, server_default="0", comment="对象内排序")
    security_level_override = Column(String(8), nullable=True, comment="对象上下文安全等级覆盖")
    note = Column(String(500), nullable=True, comment="备注")

    __table_args__ = (
        UniqueConstraint("object_id", "standard_id", name="uq_meta_object_attribute"),
        Index("idx_meta_object_attribute_object", "object_id"),
    )


class MetaObjectRelation(Base, TenantMixin):
    """关系标准（对象→对象的人工定义关系）。"""

    __tablename__ = "meta_object_relation"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    catalog_id = Column(BigInteger, ForeignKey("meta_standard_catalog.id", ondelete="RESTRICT"), nullable=True, comment="所属目录/场景（可空）")
    code = Column(String(64), nullable=False, comment="关系编码（租户内唯一）")
    name = Column(String(200), nullable=False, comment="关系名称")
    from_object_id = Column(BigInteger, ForeignKey("meta_object_standard.id", ondelete="RESTRICT"), nullable=False, comment="起始对象")
    to_object_id = Column(BigInteger, ForeignKey("meta_object_standard.id", ondelete="RESTRICT"), nullable=False, comment="目标对象")
    relation_type = Column(String(16), nullable=False, comment="1:1|1:N|N:1|N:N")
    via_attribute_ids = Column(JSONB, nullable=True, comment="连接键引用的属性标准 id 列表（有序）")
    description = Column(Text, nullable=True, comment="说明")
    status = Column(String(32), nullable=False, server_default="draft", comment="draft|published")
    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    updater_id = Column(BigInteger, nullable=True, comment="最后更新者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_meta_object_relation_code"),
        Index("idx_meta_object_relation_from", "from_object_id"),
        Index("idx_meta_object_relation_to", "to_object_id"),
        Index("idx_meta_object_relation_catalog", "tenant_id", "catalog_id"),
    )


class MetaTableStandard(Base, TenantMixin):
    """表↔对象 绑定（镜像 meta_column_standard 评审语义，表侧 1:1）。"""

    __tablename__ = "meta_table_standard"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    table_id = Column(BigInteger, ForeignKey("meta_table.id", ondelete="CASCADE"), nullable=False, comment="物理表 ID（1:1 唯一）")
    object_standard_id = Column(BigInteger, ForeignKey("meta_object_standard.id", ondelete="RESTRICT"), nullable=False, comment="对象标准 ID")
    standard_version = Column(Integer, nullable=True, comment="绑定时对象版本")
    security_level_override = Column(String(8), nullable=True, comment="覆盖")
    status = Column(String(32), nullable=False, server_default="suggested", comment="suggested|accepted|rejected")
    source = Column(String(32), nullable=False, server_default="human", comment="rule|llm|human")
    confidence = Column(Float, nullable=True, comment="置信度（rule 通道产出）")
    evidence_json = Column(JSONB, nullable=True, comment="判定依据")
    reviewed_by = Column(BigInteger, nullable=True, comment="评审人")
    reviewed_at = Column(TIMESTAMP, nullable=True, comment="评审时间")
    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("table_id", name="uq_meta_table_standard_table"),
    )


class MetaTableStandardHistory(Base, TenantMixin):
    """表绑定变更历史（对齐 meta_column_standard_history）。"""

    __tablename__ = "meta_table_standard_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    table_id = Column(BigInteger, nullable=False, comment="物理表 ID")
    object_standard_id = Column(BigInteger, nullable=False, comment="对象标准 ID")
    standard_version = Column(Integer, nullable=True, comment="涉及版本")
    action = Column(String(32), nullable=False, comment="bind|unbind|accept|reject|override")
    snapshot_json = Column(JSONB, nullable=True, comment="变更时绑定快照")
    actor_user_id = Column(BigInteger, nullable=True, comment="操作人")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        Index("idx_meta_table_std_history_table", "table_id"),
    )


class MetaRelationCheck(Base, TenantMixin):
    """标准关系 vs 推断 meta_relation 的校验结论。"""

    __tablename__ = "meta_relation_check"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    standard_relation_id = Column(BigInteger, ForeignKey("meta_object_relation.id", ondelete="CASCADE"), nullable=False, comment="关系标准 ID")
    source_id = Column(BigInteger, ForeignKey("meta_data_source.id", ondelete="CASCADE"), nullable=False, comment="数据源 ID")
    database = Column(String(128), nullable=False, comment="库/schema 作用域（对齐 meta_relation.database）")
    inferred_relation_id = Column(BigInteger, ForeignKey("meta_relation.id", ondelete="SET NULL"), nullable=True, comment="命中的推断关系")
    verdict = Column(String(16), nullable=False, comment="hit|missing|conflict")
    confidence = Column(Float, nullable=True, comment="命中推断关系的置信度")
    evidence_json = Column(JSONB, nullable=True, comment="比对依据（两端表名/方向/差异）")
    checked_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="校验时间")

    __table_args__ = (
        UniqueConstraint("standard_relation_id", "source_id", "database", name="uq_meta_relation_check"),
        Index("idx_meta_relation_check_source", "source_id", "database"),
    )
