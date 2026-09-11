"""本体建模与治理模型 —— P4.2 六张表。

背景
----
P4.1 的三张表（`ontology` / `ontology_class` / `ontology_annotation`）解决了
「本体存哪里」；本文件的六张表解决「本体怎么治理」——借鉴 ontomind 的
CQ（能力问题）驱动建模方法：

* `ontology_object_type`   对象类型（业务概念，如「客户」「合同」）
* `ontology_property`      对象类型的属性（字段级）
* `ontology_link_type`     关系类型（对象类型之间的关系，含基数）
* `ontology_mapping`       对象类型 ↔ 物理表/列 的映射（原料来自 P2 元数据）
* `ontology_cq`            能力问题（Competency Question，本体要回答的业务问题）
* `ontology_version`       版本快照（快照生成/对比是 Task 6，本文件只建表）

约定
----
* `Base` 来自 `app.db.database`；审计列与 P4.1 一致；
* 状态用 `String(32)` + comment，**不用 SAEnum**（PG ENUM 后期变更困难）；
* 表名单数、`__table_args__` 具名索引/约束、字段中文 comment；
* **不继承 `TenantMixin`**：spec §5.2 的字段里没有 `tenant_id`，六表全部经
  `ontology_id` 归属到本体（本体行带租户）。跨租户安全由
  `app.services.ontology.modeling_service.ModelingService` 的「先按租户解析
  本体、再操作子表」链路保证——不允许任何调用方拿裸 `ontology_id` 直查子表；
* `source` 的 `llm` 取值保留但本阶段不产生（与 P2 spec 的一致决定：不做 LLM 抽取通道）。
"""
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    String,
    TIMESTAMP,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.database import Base

#: 评审状态：候选（suggested）→ 接受（accepted）/ 拒绝（rejected），允许改回。
#: 候选生成与阈值在 Task 5 实现（复用 P2 的 rule_engine 阈值，不得重新定义）。
REVIEW_STATUSES = ("suggested", "accepted", "rejected")

#: 来源：rule=规则抽取 human=人工建模 llm=LLM 抽取（保留取值，本阶段不实现）
SOURCES = ("rule", "human", "llm")


class OntologyObjectType(Base):
    """对象类型表：本体中的业务概念（类）。"""

    __tablename__ = "ontology_object_type"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger,
        ForeignKey("ontology.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属本体 ID",
    )

    code = Column(String(128), nullable=False, comment="对象类型编码（本体内唯一，如 customer）")
    name = Column(String(200), nullable=False, comment="对象类型名称（如 客户）")
    description = Column(Text, nullable=True, comment="业务描述")
    parent_id = Column(
        BigInteger,
        ForeignKey("ontology_object_type.id", ondelete="SET NULL"),
        nullable=True,
        comment="父对象类型 ID（自引用，构成概念层级）",
    )

    # suggested=候选 accepted=已接受 rejected=已拒绝（评审流转，Task 5 生成候选）
    status = Column(String(32), nullable=False, server_default="suggested", comment="评审状态: suggested|accepted|rejected")
    # rule=规则抽取 human=人工建模 llm=LLM 抽取（保留取值，本阶段不产生）
    source = Column(String(32), nullable=False, server_default="human", comment="来源: rule|human|llm")
    confidence = Column(Float, nullable=True, comment="置信度 0~1（规则/LLM 通道产生，人工建模为空）")
    evidence_json = Column(
        JSONB,
        nullable=True,
        comment="来源证据（如 P2 表名、列重叠率等，由生成方写入）",
    )

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
        UniqueConstraint("ontology_id", "code", name="uq_ontology_object_type"),
        Index("idx_object_type_ontology", "ontology_id"),
        Index("idx_object_type_parent", "parent_id"),
        Index("idx_object_type_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<OntologyObjectType {self.code}>"


class OntologyProperty(Base):
    """属性表：对象类型的字段级属性。"""

    __tablename__ = "ontology_property"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    object_type_id = Column(
        BigInteger,
        ForeignKey("ontology_object_type.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属对象类型 ID",
    )

    code = Column(String(128), nullable=False, comment="属性编码（对象类型内唯一，如 customer_name）")
    name = Column(String(200), nullable=False, comment="属性名称（如 客户名称）")
    data_type = Column(String(64), nullable=False, server_default="string", comment="数据类型: string|int|decimal|date|datetime|boolean 等")
    required = Column(Boolean, nullable=False, server_default="false", comment="是否必填")
    semantic_type = Column(String(128), nullable=True, comment="语义类型（如 手机号 / 证件号，供检索与校验使用）")

    status = Column(String(32), nullable=False, server_default="suggested", comment="评审状态: suggested|accepted|rejected")
    source = Column(String(32), nullable=False, server_default="human", comment="来源: rule|human|llm")
    confidence = Column(Float, nullable=True, comment="置信度 0~1")

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
        UniqueConstraint("object_type_id", "code", name="uq_ontology_property"),
        Index("idx_property_object_type", "object_type_id"),
        Index("idx_property_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<OntologyProperty {self.code}>"


class OntologyLinkType(Base):
    """关系类型表：对象类型之间的关系（含基数）。"""

    __tablename__ = "ontology_link_type"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger,
        ForeignKey("ontology.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属本体 ID",
    )

    code = Column(String(128), nullable=False, comment="关系类型编码（本体内唯一，如 signs）")
    name = Column(String(200), nullable=False, comment="关系类型名称（如 签订）")
    source_type_id = Column(
        BigInteger,
        ForeignKey("ontology_object_type.id", ondelete="CASCADE"),
        nullable=False,
        comment="起始对象类型 ID",
    )
    target_type_id = Column(
        BigInteger,
        ForeignKey("ontology_object_type.id", ondelete="CASCADE"),
        nullable=False,
        comment="目标对象类型 ID",
    )
    cardinality = Column(String(32), nullable=False, server_default="N:M", comment="基数: 1:1|1:N|N:M")

    status = Column(String(32), nullable=False, server_default="suggested", comment="评审状态: suggested|accepted|rejected")
    source = Column(String(32), nullable=False, server_default="human", comment="来源: rule|human|llm")
    confidence = Column(Float, nullable=True, comment="置信度 0~1")
    evidence_json = Column(JSONB, nullable=True, comment="来源证据（如列对重叠率）")

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
        UniqueConstraint("ontology_id", "code", name="uq_ontology_link_type"),
        Index("idx_link_type_ontology", "ontology_id"),
        Index("idx_link_type_source", "source_type_id"),
        Index("idx_link_type_target", "target_type_id"),
    )

    def __repr__(self) -> str:
        return f"<OntologyLinkType {self.code}>"


class OntologyMapping(Base):
    """映射表：对象类型 ↔ 物理表/列（原料来自 P2 的元数据扫描）。"""

    __tablename__ = "ontology_mapping"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger,
        ForeignKey("ontology.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属本体 ID",
    )
    object_type_id = Column(
        BigInteger,
        ForeignKey("ontology_object_type.id", ondelete="CASCADE"),
        nullable=False,
        comment="映射到的对象类型 ID",
    )

    # table=整表映射 column=列映射
    target_type = Column(String(32), nullable=False, server_default="table", comment="映射目标类型: table|column")
    # P2 侧物理对象的 ID（sys_meta_table.id / sys_meta_column.id），类型不统一故用字符串
    source_id = Column(String(128), nullable=True, comment="P2 元数据对象 ID（字符串化）")
    database = Column(String(128), nullable=True, comment="物理库名")
    table_name = Column(String(200), nullable=False, comment="物理表名")
    column_name = Column(String(200), nullable=True, comment="物理列名（target_type=column 时必填）")

    status = Column(String(32), nullable=False, server_default="suggested", comment="评审状态: suggested|accepted|rejected")
    source = Column(String(32), nullable=False, server_default="human", comment="来源: rule|human|llm")
    confidence = Column(Float, nullable=True, comment="置信度 0~1")

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
        Index("idx_mapping_ontology", "ontology_id"),
        Index("idx_mapping_object_type", "object_type_id"),
        Index("idx_mapping_target", "target_type", "table_name"),
        Index("idx_mapping_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<OntologyMapping {self.table_name}→{self.object_type_id}>"


class OntologyCq(Base):
    """能力问题表（Competency Question）：本体必须能回答的业务问题。

    CQ 是本体建模的验收口径——`cq_coverage()` 统计「已关联对象类型的 active CQ」
    占比，用于量化本体的覆盖进度（Task 9 的 `ontology_answer_cq` Tool 消费）。
    """

    __tablename__ = "ontology_cq"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger,
        ForeignKey("ontology.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属本体 ID",
    )

    question = Column(Text, nullable=False, comment="能力问题（自然语言，如「哪些合同将在 30 天内到期？」）")
    answer_hint = Column(Text, nullable=True, comment="回答提示（该问题应由哪些数据/路径回答）")
    # active=生效 archived=已归档（CQ 不参与 suggested/accepted 评审流转）
    status = Column(String(32), nullable=False, server_default="active", comment="状态: active|archived")
    # 关联的对象类型 **code** 列表（而非 id：code 是建模语言，快照/导出可读）。
    # 覆盖度口径：本列表非空即视为「该 CQ 已被本体覆盖」。
    linked_object_types = Column(JSONB, nullable=True, default=list, comment="关联的对象类型 code 列表")

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
        Index("idx_cq_ontology", "ontology_id"),
        Index("idx_cq_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<OntologyCq {self.question[:30]}>"


class OntologyVersion(Base):
    """版本快照表：本体建模结果的不可变快照（生成/对比/回滚是 Task 6）。"""

    __tablename__ = "ontology_version"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger,
        ForeignKey("ontology.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属本体 ID",
    )

    version = Column(String(32), nullable=False, comment="版本号（如 v1.0.0 或 ISO 时间戳，由 Task 6 定义）")
    snapshot_json = Column(JSONB, nullable=False, comment="快照内容（对象类型/属性/关系/映射/CQ 的冻结视图）")
    change_note = Column(Text, nullable=True, comment="变更说明")
    author_user_id = Column(BigInteger, nullable=True, comment="创建快照的用户 ID")

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("ontology_id", "version", name="uq_ontology_version"),
        Index("idx_version_ontology", "ontology_id"),
    )

    def __repr__(self) -> str:
        return f"<OntologyVersion {self.version}>"
