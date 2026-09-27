"""Wiki 知识库表 — 顶级知识库容器（G7）。

组织层级：
    知识库(knowledge) → 目录(category) → 文章(article) → 版本(version)

知识库是 wiki 内容的顶层组织根节点，对应管理控制台「知识库管理」页。

2026-09-27 统一化（spec §3.1）：知识库成为三类知识库的**唯一一级容器**，
新增 ``type`` 列区分内容层来源；server_default='1' 保证存量 wiki 数据零迁移。
"""
from enum import IntEnum

from sqlalchemy import Boolean, Column, BigInteger, String, Text, Integer, TIMESTAMP, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class KnowledgeType(IntEnum):
    """统一知识库容器类型（整数枚举，存 DB）。"""

    LLM_WIKI = 1      # llm-wiki：文章 + 版本 + OKF 合规
    GENERAL_KB = 2    # 通用 KB：文档 / 表格 / Q&A 切片检索（kb_collection）
    EXTERNAL_KB = 3   # 外部集成：连接器拉取 / 外部检索代理


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
    type = Column(
        Integer,
        nullable=False,
        server_default='1',
        comment='知识库类型: 1=llm-wiki 2=general-kb 3=external-kb',
    )
    # 二级形态（spec §10.2，Dify 对齐）：type=2 → document|table|qa；type=3 → connector|proxy；type=1 为 NULL
    kb_format = Column(String(16), nullable=True, comment='二级形态: document|table|qa|connector|proxy')
    multimodal_enabled = Column(
        Boolean, nullable=False, server_default='false',
        comment='type=2/document: 图片独立向量化（需 Vision Embedding 模型）',
    )
    # 索引模式（spec §10.2，Dify 对齐）：economy=仅关键词全文，摄取不消耗 embedding
    index_mode = Column(
        String(16), nullable=False, server_default='high_quality',
        comment='索引模式: high_quality=向量+全文 | economy=仅关键词，不消耗 embedding',
    )
    # 摄取编排（spec §10.7）
    pipeline_config = Column(
        JSONB, nullable=True,
        comment='摄取编排: {clean:[...], chunker:{type,params}, index:{...}}',
    )

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment='创建时间')
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment='更新时间'
    )

    __table_args__ = (
        Index('idx_kms_knowledge_slug', 'slug', unique=True),
        Index('idx_kms_knowledge_tenant', 'tenant_id'),
        Index('idx_kms_knowledge_tenant_type', 'tenant_id', 'type'),
    )

    def __repr__(self) -> str:
        return f"<WikiKnowledge {self.slug}>"
