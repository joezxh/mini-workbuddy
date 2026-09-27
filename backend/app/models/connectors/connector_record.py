"""连接器落库模型（P3 Task 7）。

``ConnectorIngest``：每条被拉取并映射后的记录一行（按租户+连接器类型+外部 ID 幂等
upsert）。``ConnectorSyncState``：每个「租户+连接器类型」维护一个增量游标，供下一轮
增量拉取使用。
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, ForeignKey, Integer, JSON, String, TIMESTAMP,
    Text, UniqueConstraint, func,
)

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class ConnectorIngest(Base, TenantMixin):
    """连接器落库记录（一条外部记录一行）。"""

    __tablename__ = "meta_connector_ingest"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    connector_type = Column(String(32), nullable=False, comment="连接器类型: http|dingtalk|feishu|wecom")
    external_id = Column(String(255), nullable=False, comment="外部记录唯一标识（缺省由 payload 哈希生成）")
    payload = Column(JSON, nullable=False, comment="映射后的记录（目标字段）")
    cursor_value = Column(String(255), nullable=True, comment="该记录的增量游标值")
    ingested_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="落库时间")

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "connector_type", "external_id",
            name="uq_connector_ingest",
        ),
    )


class ConnectorInstance(Base, TenantMixin):
    """外部知识库连接器**实例层**（spec §3.4）。

    与落库层 ``ConnectorIngest`` 分离：本表管理「连到哪个外部系统、怎么连、多久同步一次」，
    落库层只记录被拉取回来的数据。``routers/connectors/connector.py`` 的 CRUD 依赖本模型。
    """

    __tablename__ = "kms_connector_instance"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    knowledge_id = Column(
        BigInteger,
        ForeignKey("kms_knowledge.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="所属统一知识库容器（type=3）",
    )
    code = Column(String(200), nullable=False, comment="实例编码（租户内唯一）")
    name = Column(String(200), nullable=False, comment="实例显示名")
    connector_type = Column(
        String(32), nullable=False, comment="连接器类型（registry 枚举: http|dingtalk|feishu|wecom）"
    )
    config = Column(JSON, nullable=True, comment="连接参数；敏感字段 Fernet 加密")
    sync_enabled = Column(Boolean, nullable=False, server_default="false", comment="是否启用定时同步")
    sync_interval_min = Column(Integer, nullable=False, server_default="60", comment="同步间隔（分钟）")
    target_collection = Column(String(128), nullable=True, comment="落库目标 → kb_collection.name")
    status = Column(String(32), nullable=False, server_default="active", comment="active|error|disabled")
    last_sync_at = Column(TIMESTAMP, nullable=True, comment="最近一次同步时间")
    error_detail = Column(Text, nullable=True, comment="最近一次失败详情")
    creator_id = Column(BigInteger, nullable=True, comment="创建人")
    updater_id = Column(BigInteger, nullable=True, comment="更新人")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_connector_instance_code"),
    )


class ConnectorSyncLog(Base, TenantMixin):
    """连接器同步**作业日志**（spec §3.5）——每次触发一条，记录真实结果。"""

    __tablename__ = "kms_connector_sync_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    instance_id = Column(
        BigInteger,
        ForeignKey("kms_connector_instance.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属实例",
    )
    connector_type = Column(String(32), nullable=False, comment="连接器类型快照")
    status = Column(
        String(32), nullable=False, server_default="pending",
        comment="pending|running|success|failed",
    )
    added = Column(Integer, nullable=False, server_default="0", comment="新增条数")
    updated = Column(Integer, nullable=False, server_default="0", comment="更新条数")
    deleted = Column(Integer, nullable=False, server_default="0", comment="删除条数")
    cursor_value = Column(String(255), nullable=True, comment="本次同步后的增量游标")
    duration_ms = Column(Integer, nullable=True, comment="耗时（毫秒）")
    error_detail = Column(Text, nullable=True, comment="失败详情")
    started_at = Column(TIMESTAMP, nullable=True, comment="开始时间")
    finished_at = Column(TIMESTAMP, nullable=True, comment="结束时间")
    creator_id = Column(BigInteger, nullable=True, comment="触发人")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")


class ConnectorSyncState(Base, TenantMixin):
    """每个「租户+连接器类型」的增量游标状态。"""

    __tablename__ = "meta_connector_sync_state"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    connector_type = Column(String(32), nullable=False, comment="连接器类型")
    last_cursor = Column(String(255), nullable=True, comment="最近一次同步的最大游标值")
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "connector_type",
            name="uq_connector_sync_state",
        ),
    )
