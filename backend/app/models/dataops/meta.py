"""元数据快照：扫描任务 / 表 / 列（P2 Task 2）。

``uq_meta_table (source_id, database, table_name)`` 与
``uq_meta_column (table_id, column_name)`` 是扫描幂等的基础。
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, Float, ForeignKey, Index, Integer, String, Text,
    TIMESTAMP, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class MetaScanJob(Base, TenantMixin):
    """元数据扫描任务（异步、带进度；spec §5.2）。"""

    __tablename__ = "meta_scan_job"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    source_id = Column(
        BigInteger, ForeignKey("data_source.id", ondelete="CASCADE"), nullable=False, comment="数据源 ID"
    )
    database = Column(String(128), nullable=False, comment="扫描的库")
    # scan | profile
    job_kind = Column(String(32), nullable=False, server_default="scan", comment="任务类型: scan|profile")
    status = Column(
        String(32), nullable=False, server_default="pending",
        comment="状态: pending|running|succeeded|failed",
    )
    progress = Column(Float, nullable=False, server_default="0", comment="进度 0-100")
    with_profile = Column(Boolean, nullable=False, server_default="0", comment="是否顺带列画像")
    tables_json = Column(JSONB, nullable=True, comment="待扫描表清单")
    stats_json = Column(JSONB, nullable=True, comment="统计（表数/列数/truncated 等）")
    error_detail = Column(Text, nullable=True, comment="失败详情")
    duration_ms = Column(Integer, nullable=True, comment="耗时毫秒")
    started_at = Column(TIMESTAMP, nullable=True, comment="开始时间")
    finished_at = Column(TIMESTAMP, nullable=True, comment="结束时间")

    # 审计
    creator_id = Column(BigInteger, nullable=True, comment="创建者 ID")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        Index("idx_meta_scan_job_source", "source_id", "status"),
    )


class MetaTable(Base, TenantMixin):
    """表快照（spec §5.3）。"""

    __tablename__ = "meta_table"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    source_id = Column(
        BigInteger, ForeignKey("data_source.id", ondelete="CASCADE"), nullable=False, comment="数据源 ID"
    )
    database = Column(String(128), nullable=False, comment="库名")
    table_name = Column(String(256), nullable=False, comment="表名")
    table_type = Column(String(32), nullable=True, comment="表类型（BASE TABLE/VIEW 等）")
    table_comment = Column(Text, nullable=True, comment="表注释")
    row_count = Column(BigInteger, nullable=True, comment="行数（近似）")
    engine = Column(String(64), nullable=True, comment="存储引擎")
    column_count = Column(Integer, nullable=True, comment="列数")
    biz_name = Column(String(200), nullable=True, comment="业务名称（人工/规则补充）")
    biz_description = Column(Text, nullable=True, comment="业务描述")
    domain = Column(String(64), nullable=True, comment="数仓分层/主题域（ods/dwd/...）")
    profiled_at = Column(TIMESTAMP, nullable=True, comment="最近画像时间")

    # 审计
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    __table_args__ = (
        UniqueConstraint("source_id", "database", "table_name", name="uq_meta_table"),
        Index("idx_meta_table_domain", "domain"),
    )


class MetaColumn(Base, TenantMixin):
    """列快照（spec §5.4）。"""

    __tablename__ = "meta_column"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    table_id = Column(
        BigInteger, ForeignKey("meta_table.id", ondelete="CASCADE"), nullable=False, comment="所属表 ID"
    )
    column_name = Column(String(256), nullable=False, comment="列名")
    ordinal = Column(Integer, nullable=False, server_default="0", comment="列序号")
    data_type = Column(String(64), nullable=True, comment="数据类型（归一化）")
    column_type = Column(String(128), nullable=True, comment="完整列类型定义")
    nullable = Column(Boolean, nullable=False, server_default="1", comment="是否可空")
    column_key = Column(String(16), nullable=True, comment="键类型（PRI/UNI/MUL）")
    column_default = Column(String(256), nullable=True, comment="默认值")
    extra = Column(String(64), nullable=True, comment="额外信息（auto_increment 等）")
    column_comment = Column(Text, nullable=True, comment="列注释")
    biz_name = Column(String(200), nullable=True, comment="业务名称")
    biz_description = Column(Text, nullable=True, comment="业务描述")
    semantic_type = Column(String(64), nullable=True, comment="语义类型（手机号/金额/ID 等）")
    # L0-L3，L3 最敏感
    pii_level = Column(String(8), nullable=True, comment="PII 等级: L0|L1|L2|L3")
    profile_json = Column(JSONB, nullable=True, comment="画像结果（不存样本数据）")

    # 审计
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    __table_args__ = (
        UniqueConstraint("table_id", "column_name", name="uq_meta_column"),
    )
