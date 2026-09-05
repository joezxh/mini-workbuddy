"""Wiki 文章表 - LLM-wiki 核心数据模型。

支持:
- Markdown 正文 (content)
- OWL 本体类标注 (owl_class_uris: JSONB 数组)
- 内容向量 (content_vector: pgvector, 用于 RAG 检索)
- Wiki 内部链接 (wiki_links: JSONB 数组)
- 反向链接 (backlinks: JSONB 数组, 由系统维护)
- 标签 (tags: JSONB 数组)
"""
from sqlalchemy import Column, BigInteger, String, Text, Integer, Boolean, TIMESTAMP, Index
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin
from app.config import settings


class WikiArticle(Base, TenantMixin):
    """Wiki 文章表。"""
    __tablename__ = 'wiki_article'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    slug = Column(String(200), nullable=False, unique=True, index=True, comment='URL 友好标识')
    title = Column(String(500), nullable=False, comment='文章标题')
    content = Column(Text, nullable=True, comment='Markdown 正文')
    summary = Column(String(1000), nullable=True, comment='摘要 (自动生成或手动填写)')

    # OWL 本体标注
    owl_class_uris = Column(JSONB, nullable=True, default=list, comment='关联的 OWL 类 URI 列表')

    # 向量 (RAG 检索)
    content_vector = Column(
        Vector(settings.EMBEDDING_DIMENSION),
        nullable=True,
        comment='内容向量 (embedding)',
    )

    # Wiki 链接
    wiki_links = Column(JSONB, nullable=True, default=list, comment='本文链接到的其他文章 slug 列表')
    backlinks = Column(JSONB, nullable=True, default=list, comment='链接到本文的其他文章 slug 列表')

    # 分类 & 标签
    category_id = Column(BigInteger, nullable=True, index=True, comment='所属分类 ID')
    tags = Column(JSONB, nullable=True, default=list, comment='标签列表')

    # 状态
    status = Column(Integer, nullable=False, server_default='1', comment='1=发布 0=草稿 -1=归档')
    is_featured = Column(Boolean, nullable=False, server_default='false', comment='是否精选')
    view_count = Column(Integer, nullable=False, server_default='0', comment='浏览次数')
    version = Column(Integer, nullable=False, server_default='1', comment='当前版本号')

    # 审计
    creator_id = Column(BigInteger, nullable=True, comment='创建者 ID')
    updater_id = Column(BigInteger, nullable=True, comment='最后编辑者 ID')
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment='创建时间')
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment='更新时间')

    __table_args__ = (
        Index('idx_wiki_article_slug', 'slug', unique=True),
        Index('idx_wiki_article_category', 'category_id'),
        Index('idx_wiki_article_status', 'status'),
    )

    def __repr__(self) -> str:
        return f"<WikiArticle {self.slug} v{self.version}>"
