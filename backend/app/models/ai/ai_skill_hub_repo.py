"""技能仓库（Skill Hub）配置数据模型。

记录用户可浏览的第三方 / 官方 skill 来源 Git 仓库。
官方仓库（is_official=True）不可删除，由系统初始化时确保存在。
"""
from __future__ import annotations

from sqlalchemy import Column, BigInteger, String, Boolean, Integer, TIMESTAMP
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiSkillHubRepo(Base, TenantMixin):
    """技能仓库来源配置表。"""

    __tablename__ = "ai_skill_hub_repo"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name = Column(String(100), nullable=False, comment="仓库展示名（如 官方仓库）")
    url = Column(String(512), nullable=False, unique=True, comment="Git 仓库地址（https）")
    branch = Column(String(100), nullable=False, server_default="main", comment="克隆分支")
    is_official = Column(
        Boolean, nullable=False, server_default="false", comment="是否官方仓库（官方不可删除）"
    )
    source_type = Column(
        String(20), nullable=False, server_default="git",
        comment="仓库来源类型：git=Git 仓库，skillhub=SkillHub 云市场",
    )
    username = Column(
        String(200), nullable=True, comment="仓库访问账号（留空则用全局配置 OFFICIAL_HUB_USERNAME）"
    )
    password = Column(
        String(200), nullable=True, comment="仓库访问密码（留空则用全局配置 OFFICIAL_HUB_PASSWORD）"
    )
    sort_order = Column(Integer, nullable=False, server_default="0", comment="展示排序")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        try:
            return f"<AiSkillHubRepo {self.id}:{self.name} official={self.is_official}>"
        except Exception:
            # 实例可能已脱离 Session（过期属性无法懒加载），避免 repr 抛错掩盖真实异常
            return "<AiSkillHubRepo detached>"
