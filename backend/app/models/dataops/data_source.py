"""数据源连接（P2 Task 2）。

凭据安全：密码经 Fernet 加密存 ``password_enc``（``app.ai.dataops.crypto``），
API 永不返回明文，仅回 ``has_password`` 布尔。
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, Integer, JSON, String, Text, TIMESTAMP, UniqueConstraint, func,
)

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class DataSource(Base, TenantMixin):
    """数据源连接配置（类型由数据字典 ``data_source_type`` 维护）。"""

    __tablename__ = "meta_data_source"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name = Column(String(128), nullable=False, comment="显示名称")
    # 取值合法性以字典 data_source_type 启用项为准（见 services/dataops/source_types.py）
    source_type = Column(String(32), nullable=False, comment="数据源类型（字典 item_code）")
    host = Column(String(256), nullable=False, comment="主机")
    port = Column(Integer, nullable=False, comment="端口")
    username = Column(String(128), nullable=True, comment="用户名")
    password_enc = Column(Text, nullable=True, comment="密码密文（Fernet，永不外显）")
    database = Column(String(128), nullable=True, comment="默认库")
    charset = Column(String(32), nullable=False, server_default="utf8mb4", comment="字符集")
    # 类型特有参数（dbSchema/mode/extra/timeout 等，仿 SQLBot DatasourceConf），永不含密码
    config_json = Column(JSON, nullable=True, comment="类型特有参数 JSON（不含凭据）")
    # unknown | online | offline（探活后更新）
    status = Column(
        String(32), nullable=False, server_default="unknown", comment="状态: unknown|online|offline"
    )
    is_default = Column(Boolean, nullable=False, server_default="0", comment="是否租户默认数据源")

    # 审计
    creator_id = Column(BigInteger, nullable=True, comment="创建者 ID")
    updater_id = Column(BigInteger, nullable=True, comment="最后更新者 ID")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    __table_args__ = (
        # 租户内名称唯一：全局唯一会跨租户泄露名称占用情况（对 spec「unique」的租户化收窄）
        UniqueConstraint("tenant_id", "name", name="uq_data_source_name"),
    )

    def __repr__(self) -> str:
        return f"<DataSource {self.name}({self.source_type})>"
