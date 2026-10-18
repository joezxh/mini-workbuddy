"""知识库 collection 元数据（AgentScope RAG Service 的 collection 映射）。"""
from sqlalchemy import BigInteger, Column, ForeignKey, Integer, JSON, String, TIMESTAMP, func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class KbCollection(Base, TenantMixin):
    """知识库集合元数据。

    ``name`` 是 AgentScope RAG Service 的逻辑 collection 名，遵循约定 ``kb_{knowledge_id}``
    （管线 / 路由 / index_mode 均据此反查知识库与维度，不可使用随机名），
    映射到底层 ``kb_segment`` 的 ``collection`` 列；不为每个 collection 单独建表。

    表格知识库启用「一个知识库多个集合」后，集合名可为 ``kb_{knowledge_id}_{slug}``
    ——仍保留 ``kb_`` 前缀与知识库 ID，故 :func:`resolve_knowledge_id` 正则放宽后
    既有反查链路零改动；普通文档知识库仍维持 ``kb_{knowledge_id}`` 1:1。

    ``dimensions`` 是运行时向量维度真值（迁移里列的 ``Vector`` 维度只是默认值）。
    """

    __tablename__ = "kms_collection"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name = Column(String(128), nullable=False, unique=True, comment="集合名(逻辑名)")
    dimensions = Column(Integer, nullable=False, comment="向量维度")
    knowledge_id = Column(
        BigInteger,
        ForeignKey("kms_knowledge.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="所属统一知识库容器（type=2）",
    )
    # 表格 KB 字段定义（spec §10.2）：[{name,type,enabled,embedding,filterable}]
    # embedding 可为 1~N 个字段（组合成向量化内容），不再是单选。
    schema_config = Column(JSON, nullable=True, comment="表格 KB 字段定义")
    # 检索设置（spec §10.5 设置面板）：embedding/rerank 模型 + top_k + score_threshold
    retrieval_settings = Column(
        JSON, nullable=True,
        comment="检索设置: {embedding_provider,embedding_model,embedding_dimensions,"
                "rerank_provider,rerank_model,top_k,score_threshold}",
    )
    created_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间"
    )

    __table_args__ = (
        # TenantMixin 已含 tenant_id 索引
    )
