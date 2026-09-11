"""本体（OWL）持久化模型 —— ontology / ontology_class / ontology_annotation。

背景
----
改造前 `WikiOwlEngine` 是「进程内 rdflib.Graph 内存单例」：重启丢数据，
且所有租户共享同一份本体（数据串租户）。三张表把本体按租户落到数据库：

* `ontology`            本体（租户内可有多份，按 code 唯一）
* `ontology_class`      本体类（类 URI / 标签 / 父类 URI 列表）
* `ontology_annotation` 目标对象（文章 / 片段 / 表 / 字段）到本体类的标注

约定
----
* `Base` 来自 `app.db.database`；租户表继承 `TenantMixin`；
* 状态用 `String(32)` + comment（不用 SAEnum，PG ENUM 后期变更困难）；
* 表名单数、`__table_args__` 具名索引/约束、字段中文 comment；
* `parent_uris` / `class_uris` 直接用裸 `JSONB`，**不加** `with_variant` 方言变体：
  变体类型在表达式构建期按默认类型选 comparator，`.contains()` 会退化成
  `LIKE '%…%'`，在 PostgreSQL 上直接报错（评审 IM-03）；
* `ontology.ttl_content` 存**全量 TTL 原文**，是本体唯一真相源；
  `ontology_class` / `ontology_annotation` 是从原文派生的查询索引（评审 R2-01/R2-02）。
"""
from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    TIMESTAMP,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin

# 与 `WikiArticle.owl_class_uris` 等既有列保持一致：**直接**用 JSONB。
# 不能用 `JSON().with_variant(JSONB, "postgresql")`：变体类型在表达式构建期
# 按默认类型 `JSON` 选 comparator，`.contains()` 会退化成 `LIKE '%…%'`，
# 在 PostgreSQL 上直接报 `invalid input syntax for type json`（评审 IM-03）。
JsonList = JSONB


class Ontology(Base, TenantMixin):
    """本体表：一个租户下的本体定义（含原始 TTL 内容）。"""

    __tablename__ = "ontology"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    code = Column(String(100), nullable=False, comment="本体编码（租户内唯一，如 default）")
    name = Column(String(200), nullable=True, comment="本体名称")
    description = Column(Text, nullable=True, comment="本体描述")

    namespace_uri = Column(String(500), nullable=True, comment="本体命名空间 URI")
    version = Column(Integer, nullable=False, server_default="1", comment="本体版本号")

    # draft=草稿 published=已发布 archived=已归档（不用 ENUM，便于后期扩展）
    status = Column(String(32), nullable=False, server_default="draft", comment="状态: draft|published|archived")
    # manual=手工建模 ttl_import=TTL 导入 build=系统构建
    source = Column(String(32), nullable=False, server_default="manual", comment="来源: manual|ttl_import|build")

    ttl_content = Column(Text, nullable=True, comment="TTL 原文（唯一真相源：规范化后的全量内容，类与标注索引均由它派生）")

    # 审计
    creator_id = Column(BigInteger, nullable=True, comment="创建者 ID")
    updater_id = Column(BigInteger, nullable=True, comment="最后更新者 ID")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_ontology_code"),
        # tenant_id 的索引由 TenantMixin（index=True）自动生成，不再手动建重复索引（评审 MI-04）
        Index("idx_ontology_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Ontology {self.code} v{self.version}>"


class OntologyClass(Base, TenantMixin):
    """本体类表：OWL Class 的持久化表示。"""

    __tablename__ = "ontology_class"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger,
        ForeignKey("ontology.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属本体 ID",
    )

    uri = Column(String(500), nullable=False, comment="类 URI（500×3 字节 < PG btree 条目上限 2704，见迁移 005）")
    label = Column(String(500), nullable=True, comment="中文标签")
    comment = Column(Text, nullable=True, comment="类描述")
    parent_uris = Column(JsonList, nullable=True, default=list, comment="父类 URI 列表")

    # active=生效 deprecated=已废弃
    status = Column(String(32), nullable=False, server_default="active", comment="状态: active|deprecated")
    display_order = Column(Integer, nullable=False, server_default="0", comment="展示顺序")

    # 审计
    creator_id = Column(BigInteger, nullable=True, comment="创建者 ID")
    updater_id = Column(BigInteger, nullable=True, comment="最后更新者 ID")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    __table_args__ = (
        UniqueConstraint("ontology_id", "uri", name="uq_ontology_class"),
        Index("idx_ontology_class_ontology", "ontology_id"),
        Index("idx_ontology_class_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<OntologyClass {self.uri}>"


class OntologyAnnotation(Base, TenantMixin):
    """本体标注表：目标对象（文章 / 片段 / 表 / 字段）↔ 本体类 的关联。"""

    __tablename__ = "ontology_annotation"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger,
        ForeignKey("ontology.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属本体 ID",
    )

    # article=文章 segment=片段 table=数据表 column=字段
    target_type = Column(String(32), nullable=False, server_default="article", comment="目标类型: article|segment|table|column")
    # 各类目标主键类型不一致（bigint / uuid / uri），统一以字符串存储
    target_id = Column(String(500), nullable=False, comment="目标对象 ID（字符串化）")
    class_uris = Column(JsonList, nullable=True, default=list, comment="关联的本体类 URI 列表")

    # 审计
    creator_id = Column(BigInteger, nullable=True, comment="创建者 ID")
    updater_id = Column(BigInteger, nullable=True, comment="最后更新者 ID")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    __table_args__ = (
        UniqueConstraint("ontology_id", "target_type", "target_id", name="uq_ontology_annotation"),
        Index("idx_ontology_annotation_target", "target_type", "target_id"),
        Index("idx_ontology_annotation_ontology", "ontology_id"),
    )

    def __repr__(self) -> str:
        return f"<OntologyAnnotation {self.target_type}:{self.target_id}>"
