"""图谱知识库 · 关系 ↔ 切片提及（溯源 + 幂等）。Spec: §3.6。

与 ``kg_entity_mention`` 同构：一条关系可被多个切片提及，
``Unique(kg_triple_id, segment_id)`` 保证重复抽取不产生重复行。
P1 仅建表（供 P3 构建管线填充）。
"""
from sqlalchemy import (
    BigInteger, Column, ForeignKey, Index, String, TIMESTAMP, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class KgTripleMention(Base, TenantMixin):
    """关系 ↔ 切片提及（溯源锚点）。"""

    __tablename__ = "kg_triple_mention"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    kg_triple_id = Column(
        BigInteger,
        ForeignKey("kg_triple.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关系 -> kg_triple.id",
    )
    segment_id = Column(
        BigInteger,
        ForeignKey("kms_segment.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="提及所在切片 -> kms_segment.id",
    )
    document_id = Column(
        String(64), nullable=True, index=True,
        comment="提及所在文档 -> kms_document.uuid_code",
    )
    evidence = Column(JSONB, nullable=True, comment="提及依据（原文片段）")
    created_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间"
    )

    __table_args__ = (
        UniqueConstraint(
            "kg_triple_id", "segment_id", name="uq_kg_triple_mention"
        ),
    )

    def __repr__(self) -> str:
        return "<KgTripleMention triple={} seg={}>".format(
            self.kg_triple_id, self.segment_id
        )
