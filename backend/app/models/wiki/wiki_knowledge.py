"""Wiki 知识库表 — 顶级知识库容器（G7）。

组织层级：
    知识库(knowledge) → 目录(category) → 文章(article) → 版本(version)

知识库是 wiki 内容的顶层组织根节点，对应管理控制台「知识库管理」页。
"""
from sqlalchemy import Column, BigInteger, String, Text, Integer, TIMESTAMP, Index
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class WikiKnowledge(Base, TenantMixin):
    """Wiki 知识库（顶级容器）。"""

    __tablename__ = 'kms_knowledge'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    name = Column(String(200), nullable=False, comment='知识库名称')
    slug = Column(String(200), nullable=False, unique=True, index=True, comment='URL 友好标识')
    description = Column(Text, nullable=True, comment='简介')
    icon = Column(String(100), nullable=True, comment='图标')
    cover_url = Column(String(500), nullable=True, comment='封面图 URL')
    owner_id = Column(BigInteger, nullable=True, comment='负责人 ID')
    status = Column(Integer, nullable=False, server_default='1', comment='1=启用 0=归档')

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment='创建时间')
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment='更新时间'
    )

    __table_args__ = (
        Index('idx_kms_knowledge_slug', 'slug', unique=True),
        Index('idx_kms_knowledge_tenant', 'tenant_id'),
    )

    def __repr__(self) -> str:
        return f"<WikiKnowledge {self.slug}>"
