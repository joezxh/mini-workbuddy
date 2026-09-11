"""元数据标准：标准项 / 版本快照 / 字段绑定 / 变更历史（P2 Task 2）。

评审语义集中在 ``meta_column_standard``（source=rule|llm|human ×
status=suggested|accepted|rejected），替代被砍掉的独立 annotations 表（spec §2.2）。
"""
from sqlalchemy import (
    BigInteger, Column, Float, ForeignKey, Index, Integer, String, Text,
    TIMESTAMP, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class MetaStandard(Base, TenantMixin):
    """标准项（业务字段的命名/类型/安全口径，spec §5.5）。"""

    __tablename__ = "meta_standard"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    code = Column(String(64), nullable=False, comment="标准项编码（租户内唯一）")
    name = Column(String(200), nullable=False, comment="标准名称")
    aliases_json = Column(JSONB, nullable=True, comment="别名列表（规则匹配用）")
    description = Column(Text, nullable=True, comment="说明")
    semantic_type = Column(String(64), nullable=True, comment="语义类型")
    data_type_expect = Column(String(64), nullable=True, comment="期望数据类型")
    length_rule_json = Column(JSONB, nullable=True, comment="长度规则")
    security_level = Column(String(8), nullable=True, comment="安全等级: L0|L1|L2|L3")
    quality_rule_json = Column(JSONB, nullable=True, comment="质量规则")
    mask_rule = Column(String(200), nullable=True, comment="脱敏规则")
    domain = Column(String(64), nullable=True, comment="主题域")
    status = Column(
        String(32), nullable=False, server_default="draft", comment="状态: draft|published"
    )
    current_version = Column(Integer, nullable=False, server_default="1", comment="当前版本号")

    # 审计
    creator_id = Column(BigInteger, nullable=True, comment="创建者 ID")
    updater_id = Column(BigInteger, nullable=True, comment="最后更新者 ID")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_meta_standard_code"),
    )


class MetaStandardVersion(Base, TenantMixin):
    """标准项版本快照（spec §5.8）。"""

    __tablename__ = "meta_standard_version"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    standard_id = Column(
        BigInteger, ForeignKey("meta_standard.id", ondelete="CASCADE"), nullable=False, comment="标准项 ID"
    )
    version = Column(Integer, nullable=False, comment="版本号（标准项内自增）")
    snapshot_json = Column(JSONB, nullable=True, comment="版本快照（字段全量冻结）")
    change_note = Column(Text, nullable=True, comment="变更说明")
    author_user_id = Column(BigInteger, nullable=True, comment="操作人")

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("standard_id", "version", name="uq_meta_standard_version"),
    )


class MetaColumnStandard(Base, TenantMixin):
    """字段↔标准绑定（字段侧 1:1，spec §5.6）。"""

    __tablename__ = "meta_column_standard"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    column_id = Column(
        BigInteger, ForeignKey("meta_column.id", ondelete="CASCADE"), nullable=False,
        comment="列 ID（字段侧 1:1 唯一）",
    )
    standard_id = Column(
        BigInteger, ForeignKey("meta_standard.id", ondelete="RESTRICT"), nullable=False,
        comment="标准项 ID（RESTRICT：有绑定的标准不可删）",
    )
    standard_version = Column(Integer, nullable=True, comment="绑定时标准版本")
    security_level_override = Column(String(8), nullable=True, comment="安全等级覆盖")
    # suggested（待评审）| accepted（采纳）| rejected（驳回）
    status = Column(
        String(32), nullable=False, server_default="suggested",
        comment="评审状态: suggested|accepted|rejected",
    )
    # rule | llm（保留取值，本阶段不实现）| human
    source = Column(String(32), nullable=False, server_default="human", comment="来源: rule|llm|human")
    confidence = Column(Float, nullable=True, comment="置信度（rule 通道产出）")
    evidence_json = Column(JSONB, nullable=True, comment="判定依据（命中规则等）")
    reviewed_by = Column(BigInteger, nullable=True, comment="评审人")
    reviewed_at = Column(TIMESTAMP, nullable=True, comment="评审时间")

    # 审计
    creator_id = Column(BigInteger, nullable=True, comment="创建者 ID")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    __table_args__ = (
        UniqueConstraint("column_id", name="uq_meta_column_standard_column"),
        # 条件性唯一（standard 每租户一份标准码，但绑定按租户行隔离即可，无需额外约束）
    )


class MetaColumnStandardHistory(Base, TenantMixin):
    """绑定变更历史（解绑/重绑/评审流转留痕，spec §5.8）。"""

    __tablename__ = "meta_column_standard_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    column_id = Column(BigInteger, nullable=False, comment="列 ID")
    standard_id = Column(BigInteger, nullable=False, comment="标准项 ID")
    standard_version = Column(Integer, nullable=True, comment="涉及版本")
    # bind | unbind | accept | reject | override
    action = Column(String(32), nullable=False, comment="动作: bind|unbind|accept|reject|override")
    snapshot_json = Column(JSONB, nullable=True, comment="变更时绑定快照")
    actor_user_id = Column(BigInteger, nullable=True, comment="操作人")

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        Index("idx_meta_column_std_history_column", "column_id"),
    )
