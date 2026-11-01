"""图谱知识库 · 实体实例（=图谱节点）。

Spec: ``docs/superpowers/specs/2026-10-30-kg-knowledge-base-design.md`` §3.3

分层职责：
- **模式层**复用 dataops CDM（``meta_object_standard.code`` = 实体类型标准），
  本表只存实例，``type_code`` 指向模式层编码，**不在此重复定义类层次**；
- **属性实例**用 JSONB 承载（``properties``），key 对齐 ``meta_standard.code``——
  属性 schema 已在模式层定义，实例值形态随类型而变，JSONB 让「加属性」零迁移；
- **溯源**保留来源切片 / 文档 ID 列表（P1 手工维护，P3 由抽取管线回填）；
- **向量**与 ``kms_segment.embedding`` 同模型同空间（复用 kb 的 ``embedding_factory``），
  使实体向量与切片向量可直接融合检索。维度按生效配置声明，禁止硬编码。

状态机沿用 dataops 既有评审词表，**不发明新词**：
``suggested``（待评审） → ``active``（已采纳） / ``deprecated``（已废弃）。
"""
from sqlalchemy import (
    BigInteger, Column, Computed, ForeignKey, Index, String, TIMESTAMP,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import deferred

from pgvector.sqlalchemy import Vector

from app.config import settings
from app.db.database import Base
from app.models.kb.kg_vector_types import HalfVector
from app.models.tenant_mixin import TenantMixin


class KgEntity(Base, TenantMixin):
    """实体实例 = 图谱节点。"""

    __tablename__ = "kg_entity"

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
    entity_key = Column(
        String(512), nullable=False,
        comment="规范化去重键（如 客户:1001），跨文档合并同一实体",
    )
    name = Column(String(500), nullable=False, comment="实体名")
    type_code = Column(
        String(64), nullable=True, index=True,
        comment="实体类型 → meta_object_standard.code；空=未归类",
    )
    aliases = Column(JSONB, nullable=True, comment="别名列表（抽取给出的同义名）")
    properties = Column(JSONB, nullable=True, comment="属性实例值 {属性code: 值}")
    source_segment_ids = Column(JSONB, nullable=True, comment="溯源：kms_segment.id 列表")
    source_document_ids = Column(JSONB, nullable=True, comment="溯源：kms_document.uuid_code 列表")
    embedding = Column(
        Vector(settings.EMBEDDING_DIMENSION), nullable=True,
        comment="实体向量（与 kms_segment 同模型同空间，P3 写入）",
    )
    # 半精度副本（生成列）：2048 维超出 pgvector HNSW 对 vector 的 2000 维上限，
    # 故用 halfvec(2048) + HNSW 承载 ANN 索引（实测 3.7~5x 加速，召回由
    # hnsw.ef_search 调节）。生成列由 DB 计算，永不失同步。见 spec §9.2。
    #
    # ``deferred(...)``：该列只服务于原生 SQL 的 ANN 查询（``embedding_half <=> ...``），
    # Python 侧从不读写；deferred 让默认 SELECT 不展开它，即使某个库尚未补上这列
    # （模型先行、库滞后的常见漂移）也不会让整表查询直接 UndefinedColumn 抛 500。
    embedding_half = deferred(Column(
        "embedding_half",
        HalfVector(settings.EMBEDDING_DIMENSION),
        Computed("embedding::halfvec", persisted=True),
        nullable=True,
        comment="半精度向量副本（生成列，仅供 HNSW ANN 召回）",
    ))
    status = Column(
        String(16), nullable=False, server_default="suggested",
        comment="状态: suggested|active|deprecated",
    )
    created_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(),
        comment="更新时间",
    )

    __table_args__ = (
        # 去重幂等：同一库内 entity_key 唯一（租户维度隔离）
        UniqueConstraint(
            "tenant_id", "knowledge_id", "entity_key", name="uq_kg_entity_key"
        ),
        Index("idx_kg_entity_tenant_kb_type", "tenant_id", "knowledge_id", "type_code"),
    )

    def __repr__(self) -> str:
        return f"<KgEntity {self.entity_key}>"
