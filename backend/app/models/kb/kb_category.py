"""通用知识库分类表 —— 三类知识库共用的二级分类容器。

2026-09-27 由 ``models/wiki/wiki_category.py`` 改造而来（spec §3.2）：

* 表名 ``kms_category`` → ``kb_category``（ALTER ... RENAME，历史数据天然兼容）；
* 类名 ``WikiCategory`` → ``KbCategory``，全仓 import 同步更新；
* 新增 ``kb_type`` 冗余列（随 knowledge_id 回填容器内 type，null=未归类）。

层级与 OWL 映射语义不变：``parent_id`` 自引用成树，``owl_class_uri`` 仅 llm-wiki 使用。
"""
from sqlalchemy import Column, BigInteger, String, Text, Integer, TIMESTAMP, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class KbCategory(Base, TenantMixin):
    """通用知识库分类（层级结构）。"""

    __tablename__ = 'kb_category'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    name = Column(String(200), nullable=False, comment='分类名称')
    slug = Column(String(200), nullable=False, unique=True, index=True, comment='URL 友好标识')
    description = Column(Text, nullable=True, comment='分类描述')
    knowledge_id = Column(
        BigInteger,
        ForeignKey('kms_knowledge.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
        comment='所属知识库 ID (null=未归类)',
    )
    parent_id = Column(
        BigInteger,
        ForeignKey('kb_category.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment='父分类 ID (null=顶级)',
    )
    owl_class_uri = Column(String(500), nullable=True, comment='关联的 OWL Class URI（llm-wiki 专用）')
    sort_order = Column(Integer, nullable=False, server_default='0', comment='排序权重')
    article_count = Column(Integer, nullable=False, server_default='0', comment='文章计数 (冗余)')
    kb_type = Column(Integer, nullable=True, comment='冗余的知识库类型（随 knowledge_id 回填；null=未归类）')

    # 审计
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment='创建时间')
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment='更新时间')

    # 关系
    children = relationship('KbCategory', back_populates='parent', cascade='all, delete-orphan')
    parent = relationship('KbCategory', back_populates='children', remote_side=[id])

    __table_args__ = (
        Index('idx_kb_category_slug', 'slug', unique=True),
        Index('idx_kb_category_parent', 'parent_id'),
    )

    def __repr__(self) -> str:
        return f"<KbCategory {self.slug}>"
