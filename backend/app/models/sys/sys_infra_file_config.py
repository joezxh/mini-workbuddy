"""基础设施 - 文件存储配置模型（sys_infra_file_config）。

对齐 Java FileConfigDO：按 code 选取客户端，master 配置为默认存储；
config 以 JSONB 存放各存储后端的差异化配置。
"""
from sqlalchemy import BigInteger, Boolean, Column, Integer, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class SysInfraFileConfig(Base, TenantMixin):
    """文件存储配置表"""
    __tablename__ = "sys_infra_file_config"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="配置编号")
    name = Column(String(64), nullable=False, comment="配置名称")
    code = Column(String(64), nullable=False, index=True, comment="配置编码（业务按此选取）")
    storage = Column(Integer, nullable=False, comment="存储类型：1=DB 10=LOCAL 20=S3")
    config = Column(JSONB, nullable=True, default=dict, comment="存储配置 JSON")
    remark = Column(String(256), nullable=True, comment="备注")
    is_master = Column(Boolean, nullable=False, default=False, index=True, comment="是否主配置")
    creator = Column(String(64), nullable=True, comment="创建者")
    create_time = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updater = Column(String(64), nullable=True, comment="更新者")
    update_time = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    deleted = Column(String(1), nullable=False, default="0", comment="是否删除")

    def __repr__(self):
        return f"<SysInfraFileConfig {self.id} {self.code} storage={self.storage}>"
