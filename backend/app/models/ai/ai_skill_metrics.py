"""AI 技能效果指标数据模型 - 用于 Skill 自动进化的评估。"""
from sqlalchemy import Column, BigInteger, String, Integer, Float, TIMESTAMP
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiSkillMetrics(Base, TenantMixin):
    """AI 技能效果指标表 - 评估 Skill 执行效果，驱动自动进化。"""
    __tablename__ = 'ai_skill_metrics'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    skill_id = Column(String(100), nullable=False, unique=True, comment='技能 ID（关联 ai_skill_package.package_id）')
    execution_count = Column(Integer, nullable=False, server_default='0', comment='累计执行次数')
    success_rate = Column(Float, nullable=False, server_default='0.0', comment='执行成功率 0-1')
    avg_latency = Column(Float, nullable=False, server_default='0.0', comment='平均耗时（秒）')
    user_rating = Column(Float, nullable=False, server_default='0.0', comment='用户评分 0-1')
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<AiSkillMetrics {self.skill_id} sr={self.success_rate}>"
