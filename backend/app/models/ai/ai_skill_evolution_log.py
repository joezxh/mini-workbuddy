"""AI 技能进化日志数据模型 - 记录 Skill 自动进化历史。"""
from sqlalchemy import Column, BigInteger, String, Integer, TIMESTAMP
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiSkillEvolutionLog(Base, TenantMixin):
    """AI 技能进化日志表 - 触发 / 结果 / 回滚记录。"""
    __tablename__ = 'ai_skill_evolution_log'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    skill_id = Column(String(100), nullable=False, index=True, comment='技能 ID')
    from_version = Column(Integer, nullable=True, comment='源版本号')
    to_version = Column(Integer, nullable=True, comment='目标版本号')
    trigger_type = Column(String(50), nullable=False, comment='触发类型: performance / requirement / competition')
    result = Column(String(50), nullable=False, comment='结果: success / failed / rolled_back')
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<AiSkillEvolutionLog {self.skill_id} {self.from_version}->{self.to_version} {self.result}>"
