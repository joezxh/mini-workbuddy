"""图谱知识库 · 实体 ↔ 切片提及（溯源 + 幂等）。

Spec: §3.4（实例层）

存在的理由：
- **溯源双向可查**：实体 → 溯源切片（前端「溯源」Tab 右列）；
  文档 → 其贡献的全部实体（文档维度撤销 / 重建）。
- **提及幂等**：``Unique(kg_entity_id, segment_id)`` 让「同一实体在同一切片被提及
  多次」只落一行，抽取管线重复执行不产生重复数据（Yuxi 同款设计）。
- **文件级撤销**：删除文档时按 ``document_id`` 反查提及并清理贡献，
  实体本身在引用计数归零后才删（避免误删共享实体）。

P1 仅建表（供 P3 构建管线填充）；P1 的手工 CRUD 走 ``kg_entity.source_*_ids``。
"""
from sqlalchemy import (
    BigInteger, Column, ForeignKey, Index, String, TIMESTAMP, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class KgEntityMention(Base, TenantMixin):
    """实体 ↔ 切片提及（溯源锚点）。"""

    __tablename__ = "kg_entity_mention"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    kg_entity_id = Column(
        BigInteger,
        ForeignKey("kg_entity.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="实体 → kg_entity.id",
    )
    segment_id = Column(
        BigInteger,
        ForeignKey("kms_segment.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="提及所在切片 → kms_segment.id",
    )
    document_id = Column(
        String(64), nullable=True, index=True,
        comment="提及所在文档 → kms_document.uuid_code",
    )
    # 抽取依据原文片段（评审时人工核对用）
    evidence = Column(JSONB, nullable=True, comment="提及依据（原文片段）")
    created_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间"
    )

    __table_args__ = (
        UniqueConstraint(
            "kg_entity_id", "segment_id", name="uq_kg_entity_mention"
        ),
    )

    def __repr__(self) -> str:
        return f"<KgEntityMention entity={self.kg_entity_id} seg={self.segment_id}>"
