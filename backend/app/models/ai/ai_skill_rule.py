"""Skill 规则数据模型"""
from sqlalchemy import Column, BigInteger, String, Boolean, Integer, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiSkillRule(Base, TenantMixin):
    """Skill 规则表"""
    __tablename__ = 'ai_skill_rule'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, comment='规则名称')
    conditions = Column(JSONB, nullable=True, comment='触发条件')
    package_id = Column(String(64), nullable=False, comment='Skill包ID')
    agent_name = Column(String(200), nullable=True, index=True, comment='关联专家名称（为空表示全局规则）')
    priority = Column(Integer, nullable=False, server_default='100', comment='优先级')
    is_active = Column(Boolean, nullable=False, server_default='true', comment='是否启用')
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<AiSkillRule {self.name} priority={self.priority}>"
