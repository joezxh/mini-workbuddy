"""AI 技能进化配置数据模型 - 每个技能独立的进化参数配置。"""
from sqlalchemy import Column, BigInteger, String, Float, Boolean, TIMESTAMP
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiSkillEvolutionConfig(Base, TenantMixin):
    """AI 技能进化配置表 - 动态管理每个技能的进化阈值/权重/开关。"""
    __tablename__ = 'ai_skill_evolution_config'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    skill_id = Column(String(100), nullable=False, unique=True, index=True, comment='技能 ID（关联 ai_skill_package.package_id）')
    threshold = Column(Float, nullable=False, server_default='0.7', comment='评估阈值，低于此值触发进化')
    weight_success = Column(Float, nullable=False, server_default='0.4', comment='成功率权重')
    weight_latency = Column(Float, nullable=False, server_default='0.2', comment='延迟权重')
    weight_user_rating = Column(Float, nullable=False, server_default='0.3', comment='用户评分权重')
    resource_score = Column(Float, nullable=False, server_default='0.8', comment='资源评估得分')
    is_auto_enabled = Column(Boolean, nullable=False, server_default='false', comment='是否启用自动进化评估')
    # 进化时使用的 LLM 文本模型（关联 ai_chat_model.code），NULL 表示用默认模型
    model_code = Column(String(100), nullable=True, index=True, comment='进化使用的 LLM 文本模型编码（关联 ai_chat_model.code），空则使用默认模型')
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<AiSkillEvolutionConfig {self.skill_id} threshold={self.threshold}>"
