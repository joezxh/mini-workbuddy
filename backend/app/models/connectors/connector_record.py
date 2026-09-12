"""连接器落库模型（P3 Task 7）。

``ConnectorIngest``：每条被拉取并映射后的记录一行（按租户+连接器类型+外部 ID 幂等
upsert）。``ConnectorSyncState``：每个「租户+连接器类型」维护一个增量游标，供下一轮
增量拉取使用。
"""
from sqlalchemy import (
    BigInteger, Column, JSON, String, TIMESTAMP, UniqueConstraint, func,
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
