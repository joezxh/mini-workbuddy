"""发布登记与卡片共享（spec §3.5 / §3.6）。

与 onto_ontology_publish 刻意分离：那张登记「本体→对外契约(skill|http|mcp)」，
本表登记「孪生页→只读路由」，混用会逼 ck_onto_publish_target 加 page 值并污染语义。
"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, ForeignKey, Index, Integer,
    String, TIMESTAMP, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class TwinPublish(Base, TenantMixin):
    """页面发布为独立只读页。"""

    __tablename__ = "twin_publish"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    card_id = Column(BigInteger, ForeignKey("twin_card.id", ondelete="CASCADE"), nullable=False, comment="卡片")
    page_id = Column(BigInteger, ForeignKey("twin_page.id", ondelete="CASCADE"), nullable=False, comment="页面")
    slug = Column(String(32), nullable=False, comment="随机不可猜串（禁止用自增 id 派生，防枚举）")
    access = Column(String(16), nullable=False, server_default="org", comment="org|role（public 留 P1）")
    role_codes_json = Column(JSONB, nullable=True, comment="access=role 时生效的角色码数组")
    snapshot_json = Column(JSONB, nullable=True, comment="发布时冻结的页面+组件配置")
    version = Column(Integer, nullable=False, server_default="1", comment="发布版本号，重复发布 +1")
    status = Column(String(16), nullable=False, server_default="enabled", comment="enabled|disabled")
    published_by = Column(BigInteger, nullable=False, comment="发布人")
    published_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="发布时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_twin_publish_slug"),
        CheckConstraint("access IN ('org','role')", name="ck_twin_publish_access"),
        CheckConstraint("status IN ('enabled','disabled')", name="ck_twin_publish_status"),
        Index("idx_twin_publish_page", "page_id", "status"),
    )


class TwinCardShare(Base, TenantMixin):
    """卡片可见性授予（驱动原型「共享给我的（只读）」）。"""

    __tablename__ = "twin_card_share"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    card_id = Column(BigInteger, ForeignKey("twin_card.id", ondelete="CASCADE"), nullable=False, comment="卡片")
    grantee_type = Column(String(16), nullable=False, comment="user|role")
    grantee_id = Column(BigInteger, nullable=True, comment="grantee_type=user 时的用户 id")
    grantee_code = Column(String(64), nullable=True, comment="grantee_type=role 时的角色码")
    perm = Column(String(16), nullable=False, server_default="read", comment="read|edit")
    source = Column(String(16), nullable=False, server_default="manual", comment="manual|request")
    expires_at = Column(TIMESTAMP, nullable=True, comment="过期时间；NULL=长期")
    granted_by = Column(BigInteger, nullable=False, comment="授予人")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        CheckConstraint("grantee_type IN ('user','role')", name="ck_twin_share_type"),
        CheckConstraint("perm IN ('read','edit')", name="ck_twin_share_perm"),
        CheckConstraint("source IN ('manual','request')", name="ck_twin_share_source"),
        Index("idx_twin_share_card", "card_id", "grantee_type"),
    )
