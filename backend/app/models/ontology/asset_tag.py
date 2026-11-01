"""资产标签体系（2 张，补 AF-03，spec §3.2）。

- ``onto_asset_tag``：租户内唯一 code，作圈选条件时写入 ``scope_json.tag_ids``；
- ``onto_asset_tag_binding``：标签↔资产绑定。``asset_id`` **故意不建外键**——元数据重扫会重建
  ``meta_table``/``meta_column`` 行，强外键会连带删掉人工标签（OntoMind“证据随重建丢失”的同构问题）。
"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, ForeignKey, Index, String, Text,
    TIMESTAMP, UniqueConstraint, func,
)

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class MetaAssetTag(Base, TenantMixin):
    """资产标签。"""

    __tablename__ = "onto_asset_tag"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    code = Column(String(64), nullable=False, comment="租户内唯一")
    name = Column(String(64), nullable=False, comment="展示名")
    color = Column(String(16), nullable=True, comment="十六进制色值，前端徽章直接用")
    tag_kind = Column(String(16), nullable=False, server_default="custom", comment="biz|security|quality|custom")
    description = Column(Text, nullable=True, comment="说明")

    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_onto_asset_tag_code"),
        CheckConstraint("tag_kind IN ('biz','security','quality','custom')", name="ck_onto_asset_tag_kind"),
        Index("idx_onto_asset_tag_tenant_kind", "tenant_id", "tag_kind"),
    )


class MetaAssetTagBinding(Base, TenantMixin):
    """标签↔资产绑定（asset_id 无外键，见模块 docstring）。"""

    __tablename__ = "onto_asset_tag_binding"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    tag_id = Column(
        BigInteger, ForeignKey("onto_asset_tag.id", ondelete="CASCADE"), nullable=False, comment="标签 ID"
    )
    asset_kind = Column(String(16), nullable=False, comment="table|column")
    asset_id = Column(BigInteger, nullable=False, comment="资产主键（不做外键，允许重扫后悬空）")
    source = Column(String(16), nullable=False, server_default="human", comment="human|rule")

    created_by = Column(BigInteger, nullable=True, comment="操作人")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "tag_id", "asset_kind", "asset_id", name="uq_onto_asset_tag_binding"),
        CheckConstraint("asset_kind IN ('table','column')", name="ck_onto_asset_tag_binding_kind"),
        Index("idx_onto_asset_tag_binding_asset", "asset_kind", "asset_id"),
    )
