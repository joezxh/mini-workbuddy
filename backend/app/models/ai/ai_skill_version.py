"""AI 技能版本数据模型 - 用于 Skill 自动进化的版本管理。"""
from sqlalchemy import Column, BigInteger, String, Integer, Boolean, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiSkillVersion(Base, TenantMixin):
    """AI 技能版本表 - 记录 Skill 每次进化的版本快照。"""
    __tablename__ = 'ai_skill_version'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    skill_id = Column(String(100), nullable=False, index=True, comment='技能 ID（关联 ai_skill_package.package_id）')
    version_number = Column(Integer, nullable=False, comment='版本号（自增）')
    changes = Column(JSONB, nullable=True, comment='版本变更说明 JSON')
    is_stable = Column(Boolean, nullable=False, server_default='false', comment='是否稳定版本')
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<AiSkillVersion {self.skill_id} v{self.version_number}>"
