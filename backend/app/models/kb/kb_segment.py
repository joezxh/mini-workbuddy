"""知识库切片（chunk）+ 向量（pgvector）。"""
from sqlalchemy import (
    BigInteger, Column, ForeignKey, Index, Integer, String, Text, TIMESTAMP,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from pgvector.sqlalchemy import Vector

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin
from app.config import settings


class KbSegment(Base, TenantMixin):
    """知识库切片：content + embedding + metadata + 本体类归属。

    ``class_uris`` 是**前向兼容 P4 Task 7（本体驱动检索）**的列：把切片映射到的
    本体（ontology_class.uri）列表，供检索时按本体类过滤。P1 计划未含，本简报
    在 Task 1 迁移一并加入，避免二次迁移。
    """

    __tablename__ = "kms_segment"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    collection = Column(String(128), nullable=False, comment="集合名")
    document_id = Column(String(128), nullable=False, comment="文档 ID")
    chunk_index = Column(Integer, nullable=False, comment="文档内切片序号")
    content = Column(Text, nullable=True, comment="切片文本")
    embedding = Column(
        Vector(settings.GPUSTACK_EMBEDDING_DIMENSION), nullable=True, comment="向量"
    )
    token_count = Column(Integer, nullable=True, comment="token 数")
    metadata_ = Column("metadata", JSONB, nullable=True, comment="切片元数据")
    class_uris = Column(
        JSONB, nullable=True, comment="映射到的本体类 uri 列表（P4 Task 7 检索过滤用）"
    )

    # ── 类型化切片（spec §10.2，Dify 对齐）────────────────────────────────
    chunk_type = Column(
        String(16), nullable=False, server_default='text',
        comment='切片类型: text|qa|table_row|image|parent|child',
    )
    # 父子分段：父块 chunk_type='parent'（embedding 为 NULL），子块指向父块
    parent_id = Column(
        BigInteger, ForeignKey('kms_segment.id', ondelete='CASCADE'),
        nullable=True, index=True, comment='父子分段: 子块 → 父块',
    )
    answer = Column(
        Text, nullable=True,
        comment='chunk_type=qa: 完整答案（content=问题，仅问题做 embedding）',
    )
    keywords = Column(JSONB, nullable=True, comment='手动关键词（全文检索加权）')

    created_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间"
    )

    __table_args__ = (
        UniqueConstraint(
            "collection", "document_id", "chunk_index", name="uq_kms_segment"
        ),
        Index("idx_kms_segment_parent", "parent_id"),
    )
