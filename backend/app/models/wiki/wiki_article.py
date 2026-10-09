"""Wiki 文章表 - LLM-wiki 核心数据模型。

支持:
- Markdown 正文 (content)
- OWL 本体类标注 (owl_class_uris: JSONB 数组)
- 内容向量 (content_vector: pgvector, 用于 RAG 检索)
- Wiki 内部链接 (wiki_links: JSONB 数组)
- 反向链接 (backlinks: JSONB 数组, 由系统维护)
- 标签 (tags: JSONB 数组)
"""
from sqlalchemy import Column, BigInteger, String, Text, Integer, Boolean, TIMESTAMP, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin
from app.config import settings


class WikiArticle(Base, TenantMixin):
    """Wiki 文章表。"""
    __tablename__ = 'kms_article'

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
    knowledge_id = Column(
        BigInteger,
        ForeignKey('kms_knowledge.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
        comment='所属知识库 ID (null=未归类)',
    )
    category_id = Column(BigInteger, nullable=True, index=True, comment='所属分类 ID')
    tags = Column(JSONB, nullable=True, default=list, comment='标签列表')

    # 状态
    status = Column(Integer, nullable=False, server_default='1', comment='1=发布 0=草稿 -1=归档')
    is_featured = Column(Boolean, nullable=False, server_default='false', comment='是否精选')
    view_count = Column(Integer, nullable=False, server_default='0', comment='浏览次数')
    version = Column(Integer, nullable=False, server_default='1', comment='当前版本号')

    # ── OKF 合规层（spec §9.2，Google Open Knowledge Format v0.2）──────────
    # 全部 nullable + 向后兼容；status 不改列，导出时映射 0→draft / 1→stable / -1→deprecated
    okf_type = Column(
        String(64), nullable=True,
        comment='OKF type: concept|howto|reference|decision|metric 或自定义（缺省导出为 concept）',
    )
    resource = Column(String(500), nullable=True, comment='OKF resource: 底层资产 URI')
    sources = Column(
        JSONB, nullable=True,
        comment='OKF §5.1 溯源家族: [{resource(必填), id, title, author, usage_count, last_modified}]',
    )
    verified = Column(JSONB, nullable=True, comment='OKF §5.2 验证事件列表: [{by, at}]')
    stale_after = Column(TIMESTAMP, nullable=True, comment='OKF §5.5 绝对过期时间点')
    # OKF §10 Attested Computation 契约：{runtime(必填), parameters, computation, executor, attester}
    attested_computation = Column(
        JSONB, nullable=True,
        comment='OKF §10 Attested Computation: {runtime, parameters, computation, executor, attester}',
    )

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
