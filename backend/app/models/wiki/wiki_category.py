"""Wiki 分类表 - 层级分类, 支持 OWL 类映射。

每个分类可映射到一个 OWL Class URI, 用于:
- 文章分类导航 (树形结构)
- OWL 本体关联 (category ↔ owl_class_uri)
"""
from sqlalchemy import Column, BigInteger, String, Text, Integer, TIMESTAMP, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class WikiCategory(Base, TenantMixin):
    """Wiki 分类表 (层级结构)。"""
    __tablename__ = 'wiki_category'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    name = Column(String(200), nullable=False, comment='分类名称')
    slug = Column(String(200), nullable=False, unique=True, index=True, comment='URL 友好标识')
    description = Column(Text, nullable=True, comment='分类描述')
    parent_id = Column(
        BigInteger,
        ForeignKey('wiki_category.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment='父分类 ID (null=顶级)',
    )
    owl_class_uri = Column(String(500), nullable=True, comment='关联的 OWL Class URI')
    sort_order = Column(Integer, nullable=False, server_default='0', comment='排序权重')
    article_count = Column(Integer, nullable=False, server_default='0', comment='文章计数 (冗余)')

    # 审计
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment='创建时间')
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment='更新时间')

    # 关系
    children = relationship('WikiCategory', back_populates='parent', cascade='all, delete-orphan')
    parent = relationship('WikiCategory', back_populates='children', remote_side=[id])

    __table_args__ = (
        Index('idx_wiki_category_slug', 'slug', unique=True),
        Index('idx_wiki_category_parent', 'parent_id'),
    )

    def __repr__(self) -> str:
        return f"<WikiCategory {self.slug}>"
