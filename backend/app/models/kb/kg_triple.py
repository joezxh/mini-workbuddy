"""图谱知识库 · 关系实例（=图谱边）。Spec: §3.5。

- ``relation_code`` → dataops CDM 的 ``meta_object_relation.code``（关系标准）。
  空串（而非 NULL）表示「自由谓词」：列保持可空以容忍历史数据，
  但服务层一律写非空串，使 ``uq_kg_triple_edge`` 的去重约束在自由谓词场景同样生效。
- 两端实体用 FK 指向 ``kg_entity.id``（``ondelete=CASCADE``）：
  删除实体时其相关边自动清理，不留悬挂边。
- ``weight`` 为抽取置信度（0~1），用于排序与前端置信度着色。
- ``evidence`` 保留抽取依据原文，供人工评审核对。

状态机沿用 dataops 既有评审词表：
``suggested``（待评审） → ``accepted``（已采纳） / ``rejected``（已驳回）。
"""
from sqlalchemy import (
    BigInteger, Column, Float, ForeignKey, Index, String, TIMESTAMP, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from pgvector.sqlalchemy import Vector

from app.config import settings
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class KgTriple(Base, TenantMixin):
    """关系实例 = 图谱边（from_entity -> to_entity）。"""

    __tablename__ = "kg_triple"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    knowledge_id = Column(
        BigInteger,
        ForeignKey("kms_knowledge.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属图谱知识库（kms_knowledge.id）",
    )
    collection = Column(
        String(128), nullable=False, default="", comment="集合名（kb_{knowledge_id}）"
    )
    relation_code = Column(
        String(64), nullable=True, index=True,
        comment="关系类型 -> meta_object_relation.code；空串=自由谓词",
    )
    from_entity_id = Column(
        BigInteger,
        ForeignKey("kg_entity.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="起点实体 -> kg_entity.id",
    )
    to_entity_id = Column(
        BigInteger,
        ForeignKey("kg_entity.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="终点实体 -> kg_entity.id",
    )
    predicate = Column(
        String(200), nullable=True, comment="自然语言谓词（如 隶属于 / 负责）"
    )
    weight = Column(
        Float, nullable=True, default=0.0, comment="抽取置信度 0~1"
    )
    properties = Column(JSONB, nullable=True, comment="边属性")
    evidence = Column(JSONB, nullable=True, comment="抽取依据（原文片段）")
    source_segment_ids = Column(JSONB, nullable=True, comment="溯源：kms_segment.id 列表")
    source_document_ids = Column(JSONB, nullable=True, comment="溯源：kms_document.uuid_code 列表")
    embedding = Column(
        Vector(settings.EMBEDDING_DIMENSION), nullable=True,
        comment="关系向量（与 kms_segment 同模型同空间，P3/P4 写入）",
    )
    status = Column(
        String(16), nullable=False, server_default="suggested",
        comment="状态: suggested|accepted|rejected",
    )
    created_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(),
        comment="更新时间",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "knowledge_id", "from_entity_id", "relation_code", "to_entity_id",
            name="uq_kg_triple_edge",
        ),
        Index("idx_kg_triple_tenant_kb_rel", "tenant_id", "knowledge_id", "relation_code"),
    )

    def __repr__(self) -> str:
        return "<KgTriple {}--{}->{}>".format(
            self.from_entity_id, self.relation_code or "", self.to_entity_id
        )
