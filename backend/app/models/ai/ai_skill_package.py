"""AI 技能包注册数据模型"""
from sqlalchemy import Column, BigInteger, String, Boolean, Integer, TIMESTAMP, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiSkillPackage(Base, TenantMixin):
    """AI 技能包注册表"""
    __tablename__ = 'ai_skill_package'

    id          = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    package_id  = Column(String(64), nullable=False, unique=True, comment='技能包业务 ID')
    name        = Column(String(128), nullable=False, comment='技能包名称')
    description = Column(Text, nullable=True, comment='描述')
    icon        = Column(String(32), server_default='tool', nullable=True, comment='图标标识')
    category    = Column(String(64), server_default='other', nullable=True, comment='类目')
    version     = Column(String(32), server_default='1.0.0', nullable=True, comment='版本')
    enabled     = Column(Boolean, nullable=False, server_default='true', comment='是否启用')
    file_path   = Column(String(256), nullable=False, comment='相对于 backend/data/skills/ 的路径')
    # SKILL.md 文件内容（数据库优先于文件系统）
    skill_markdown = Column(Text, nullable=True, comment='SKILL.md 文件内容，执行时优先于文件系统')
    created_by  = Column(BigInteger, nullable=True, comment='创建者 ID')
    created_at  = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at  = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_skill_package_category', 'category'),
        Index('idx_skill_package_enabled', 'enabled'),
    )

    def __repr__(self):
        return f"<AiSkillPackage {self.package_id}:{self.name}>"
