"""多模态图文资产（spec §10.2/§10.3 multimodal）：切片附件图片。

服务层校验：单图 ≤ 2MB、单 segment ≤ 10 张（对齐 Dify 限制）。
"""
from sqlalchemy import (
    BigInteger, Column, ForeignKey, Integer, String, TIMESTAMP, func,
)

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class KbSegmentAsset(Base, TenantMixin):
    __tablename__ = "kms_segment_asset"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    segment_id = Column(BigInteger, ForeignKey("kms_segment.id", ondelete="CASCADE"),
                        nullable=False, index=True, comment="所属切片")
    file_path = Column(String(500), nullable=False, comment="存储路径/对象 URL")
    mime_type = Column(String(64), nullable=False, comment="图片 MIME")
    size = Column(Integer, nullable=False, comment="字节数")
    width = Column(Integer, nullable=True, comment="宽")
    height = Column(Integer, nullable=True, comment="高")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
