"""基础设施 - 文件管理模型

适配现有数据库表 infra_file / infra_file_content。
"""
from sqlalchemy import Column, BigInteger, Integer, String, Text, TIMESTAMP, ForeignKey, Sequence
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class SysInfraFile(Base, TenantMixin):
    """文件元数据表（database.infra_file）"""
    __tablename__ = 'sys_infra_file'

    id = Column(Integer, Sequence('infra_file_id_seq'), primary_key=True, autoincrement=False, comment='文件编号')
    config_id = Column(BigInteger, nullable=True, index=True, comment='配置编号')
    name = Column(String(256), nullable=True, comment='文件名')
    path = Column(String(512), nullable=False, comment='文件路径（磁盘）')
    url = Column(String(1024), nullable=False, comment='文件 URL')
    type = Column(String(128), nullable=True, comment='文件类型/MIME')
    size = Column(Integer, nullable=False, default=0, comment='文件大小（字节）')
    creator = Column(String(64), nullable=True, comment='创建者')
    create_time = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment='创建时间')
    updater = Column(String(64), nullable=True, comment='更新者')
    update_time = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment='更新时间')
    deleted = Column(String(1), nullable=False, default='0', comment='是否删除')

    def __repr__(self):
        return f"<SysInfraFile {self.id} {self.name}>"


class SysInfraFileContent(Base, TenantMixin):
    """文件内容表（database.infra_file_content，字节流备份）"""
    __tablename__ = 'sys_infra_file_content'

    id = Column(Integer, Sequence('infra_file_content_id_seq'), primary_key=True, autoincrement=False, comment='编号')
    config_id = Column(BigInteger, nullable=False, index=True, comment='配置编号')
    path = Column(String(512), nullable=False, comment='文件路径')
    content = Column(Text, nullable=False, comment='文件内容（字节流）')
    creator = Column(String(64), nullable=True, comment='创建者')
    create_time = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment='创建时间')
    updater = Column(String(64), nullable=True, comment='更新者')
    update_time = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment='更新时间')
    deleted = Column(String(1), nullable=False, default='0', comment='是否删除')

    def __repr__(self):
        return f"<SysInfraFileContent {self.id} path={self.path}>"
