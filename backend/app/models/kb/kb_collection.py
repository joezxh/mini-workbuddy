"""知识库 collection 元数据（AgentScope RAG Service 的 collection 映射）。"""
from sqlalchemy import BigInteger, Column, ForeignKey, Integer, JSON, String, TIMESTAMP, func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class KbCollection(Base, TenantMixin):
    """知识库集合元数据。

    ``name`` 是 AgentScope RAG Service 的逻辑 collection 名（形如 ``kb_<uuid>``），
    映射到底层 ``kb_segment`` 的 ``collection`` 列；不为每个 collection 单独建表。
    ``dimensions`` 是运行时向量维度真值（迁移里列的 ``Vector`` 维度只是默认值）。
    """

    __tablename__ = "kb_collection"

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
    # 表格 KB 字段定义（spec §10.2）：[{name,type,enabled,embedding(单选),filterable}]
    schema_config = Column(JSON, nullable=True, comment="表格 KB 字段定义")
    created_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间"
    )

    __table_args__ = (
        # TenantMixin 已含 tenant_id 索引
    )
