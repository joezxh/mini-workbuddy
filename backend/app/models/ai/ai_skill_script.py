"""AI 技能脚本数据模型"""
from sqlalchemy import Column, BigInteger, String, Boolean, Integer, TIMESTAMP, Text, Index, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiSkillScript(Base, TenantMixin):
    """AI 技能脚本表"""
    __tablename__ = 'ai_skill_script'

    id          = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    package_id  = Column(String(64), nullable=False, comment='所属技能包 ID')
    script_id   = Column(String(64), nullable=False, comment='脚本业务 ID')
    name        = Column(String(128), nullable=False, comment='脚本名称')
    description = Column(Text, nullable=True, comment='描述')
    command     = Column(Text, nullable=False, comment='执行命令模板，含 {param} 占位符')
    params      = Column(JSONB, nullable=True, comment='参数定义 JSON')
    sort_order  = Column(Integer, server_default='0', nullable=True, comment='排序')
    enabled     = Column(Boolean, nullable=False, server_default='true', comment='是否启用')
    created_at  = Column(TIMESTAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('package_id', 'script_id'),
        Index('idx_skill_script_package', 'package_id'),
        Index('idx_skill_script_enabled', 'enabled'),
    )

    def __repr__(self):
        return f"<AiSkillScript {self.package_id}/{self.script_id}>"
