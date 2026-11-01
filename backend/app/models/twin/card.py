"""孪生卡片与页面（spec §3.2 / §3.3）。卡片钉「本体+版本」，页面持有刷新策略。"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, ForeignKey, Index, Integer,
    String, Text, TIMESTAMP, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class TwinCard(Base, TenantMixin):
    """孪生卡片：一个孪生应用的顶层容器。"""

    __tablename__ = "twin_card"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name = Column(String(200), nullable=False, comment="卡片名")
    icon = Column(String(32), nullable=True, comment="图标字符")
    description = Column(Text, nullable=True, comment="说明")
    source_template_key = Column(String(64), nullable=True, comment="模板中心来源，可空")
    ontology_id = Column(BigInteger, ForeignKey("onto_ontology.id", ondelete="CASCADE"), nullable=False, comment="钉住的本体")
    ontology_version = Column(Integer, nullable=False, server_default="0", comment="钉住的版本；0=未发布本体")
    scene_key = Column(String(64), nullable=True, comment="等距视觉场景模板 key（非沙盘 onto_sandbox_scene）")
    scene_config_json = Column(JSONB, nullable=True, comment="P1 场景编辑器写入")
    runtime_state = Column(String(16), nullable=False, server_default="draft", comment="draft|live|paused")
    owner_id = Column(BigInteger, nullable=False, comment="归属用户")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "owner_id", "name", name="uq_twin_card_name"),
        CheckConstraint("runtime_state IN ('draft','live','paused')", name="ck_twin_card_state"),
        Index("idx_twin_card_owner", "tenant_id", "owner_id", "runtime_state"),
    )


class TwinPage(Base, TenantMixin):
    """卡片内的页面（对应原型顶部页面 Tab）。"""

    __tablename__ = "twin_page"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    card_id = Column(BigInteger, ForeignKey("twin_card.id", ondelete="CASCADE"), nullable=False, comment="所属卡片")
    name = Column(String(200), nullable=False, comment="页面名")
    sort_order = Column(Integer, nullable=False, server_default="0", comment="Tab 顺序")
    refresh_json = Column(JSONB, nullable=True, comment="{mode: interval|manual|off, interval_seconds: 10|30|0}")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("card_id", "name", name="uq_twin_page_name"),
        Index("idx_twin_page_card", "card_id", "sort_order"),
    )
