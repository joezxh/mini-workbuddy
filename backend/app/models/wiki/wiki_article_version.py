"""Wiki 文章版本历史表 - 记录每次编辑的快照。

每次保存文章时自动创建一条版本记录, 支持:
- 版本对比 (diff)
- 版本回滚
- 编辑审计 (editor + change_note)
"""
from sqlalchemy import Column, BigInteger, String, Text, Integer, TIMESTAMP, ForeignKey, Index
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class WikiArticleVersion(Base, TenantMixin):
    """Wiki 文章版本历史。"""
    __tablename__ = 'wiki_article_version'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    article_id = Column(
        BigInteger,
        ForeignKey('wiki_article.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment='关联文章 ID',
    )
    version = Column(Integer, nullable=False, comment='版本号 (从 1 递增)')
    title = Column(String(500), nullable=False, comment='版本标题快照')
    content = Column(Text, nullable=True, comment='版本正文快照 (Markdown)')
    slug = Column(String(200), nullable=True, comment='版本 slug 快照')
    change_note = Column(String(500), nullable=True, comment='编辑说明')

    # 审计
    editor_id = Column(BigInteger, nullable=True, comment='编辑者 ID')
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment='版本创建时间')

    __table_args__ = (
        Index('idx_wiki_version_article_version', 'article_id', 'version', unique=True),
    )

    def __repr__(self) -> str:
        return f"<WikiArticleVersion article={self.article_id} v{self.version}>"
