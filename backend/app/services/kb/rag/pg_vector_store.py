"""pgvector 后端 —— 唯一允许的自定义扩展点（对齐文档 §5.1 / D2）。

实现 AgentScope ``VectorStoreBase`` 全部 7 个抽象方法 + ``async with`` 生命周期：

* ``collection`` → ``kb_collection.name``；``document_id`` → ``kms_segment.document_id``；
* ``Chunk.metadata`` → ``kms_segment.metadata_``，并按 D14 冗余投影到
  ``chunk_type`` / ``answer`` / ``keywords`` 列（投影只服务 SQL 过滤，写入源是 metadata）；
* ``score`` 统一**越大越相关**（余弦距离取负，D12）；
* ``metadata_filter`` 按 ``key == value`` 翻译成 JSONB 包含过滤；
* ``create_collection`` 强校验维度（D19）；``index_mode=economy`` 写 NULL 向量（D11）。

DB 访问为同步 SQLAlchemy（本项目路由/后台任务为同步会话）；async 方法内直接调用，
由上层以 ``async with PgVectorStore(...)`` 托管会话生命周期。
"""
from __future__ import annotations

import json
from typing import Any, Optional

from agentscope.rag import (
    DocumentSummary,
    VectorRecord,
    VectorSearchResult,
    VectorStoreBase,
)
from sqlalchemy import delete as sa_delete, select, text

from app.models.kb.kb_collection import KbCollection
from app.models.kb.kb_segment import KbSegment

# metadata → 冗余列的投影（D14）
_PROJECTIONS = ("chunk_type", "answer", "keywords")


class PgVectorStore(VectorStoreBase):
    """pgvector 向量库后端（原生 VectorStoreBase 实现）。"""

    def __init__(
        self,
        session_factory,
        *,
        tenant_id: int,
        dimensions: int,
        index_mode: str = "high_quality",
        hybrid: bool = True,
    ) -> None:
        self.session_factory = session_factory
        self.tenant_id = tenant_id
        self.dimensions = dimensions
        self.index_mode = index_mode
        self.hybrid = hybrid
        self._session = None

    # ── 生命周期（原生契约）─────────────────────────────────────────────
    async def __aenter__(self) -> "PgVectorStore":
        self._session = self.session_factory()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._session is not None:
            try:
                self._session.close()
            finally:
                self._session = None

    @property
    def session(self):
        if self._session is None:
            self._session = self.session_factory()
        return self._session

    # ── collection 生命周期 ─────────────────────────────────────────────
    async def create_collection(self, name: str, dimensions: int) -> None:
        """按维度建 collection；与 kb_collection.dimensions 不一致直接失败（D19）。"""
        existing = self.session.execute(
            select(KbCollection).where(KbCollection.name == name)
        ).scalar_one_or_none()
        if existing is None:
            self.session.add(KbCollection(
                name=name, dimensions=dimensions, tenant_id=self.tenant_id,
            ))
            self.session.flush()
            return
        if existing.dimensions != dimensions:
            raise ValueError(
                f"collection {name!r} 维度不一致：库内 {existing.dimensions} vs "
                f"嵌入模型 {dimensions}（D19：不静默创建错误维度列）"
            )

    async def has_collection(self, name: str) -> bool:
        return self.session.execute(
            select(KbCollection.id).where(KbCollection.name == name)
        ).scalar_one_or_none() is not None

    async def delete_collection(self, name: str) -> None:
        self.session.execute(
            sa_delete(KbSegment).where(KbSegment.collection == name)
        )
        self.session.execute(
            sa_delete(KbCollection).where(KbCollection.name == name)
        )
        self.session.flush()

    # ── 读写 ────────────────────────────────────────────────────────────
    async def insert(self, collection: str, records: list[VectorRecord]) -> None:
        """幂等 upsert：持久化 document_id + chunk（原生要求）。"""
        for rec in records:
            meta = dict(rec.chunk.metadata or {})
            meta["tenant_id"] = self.tenant_id  # 深度防御：租户随行
            content = getattr(rec.chunk.content, "text", None)
            # 幂等：按 (collection, document_id, chunk_index) 先删后插
            self.session.execute(
                sa_delete(KbSegment).where(
                    KbSegment.collection == collection,
                    KbSegment.document_id == rec.document_id,
                    KbSegment.chunk_index == rec.chunk.chunk_index,
                )
            )
            row = KbSegment(
                tenant_id=self.tenant_id,
                collection=collection,
                document_id=rec.document_id,
                chunk_index=rec.chunk.chunk_index,
                content=content,
                embedding=None if self.index_mode == "economy" else rec.vector,
                # 列名 metadata 的 ORM 属性名是 metadata_（避免与 declarative MetaData 冲突）
                metadata_=meta,
            )
            for key in _PROJECTIONS:
                if key in meta:
                    setattr(row, key, meta[key])
            self.session.add(row)
        self.session.flush()

    async def delete(self, collection: str, document_id: str) -> None:
        """按 document_id 删该文档全部记录（原生语义）。"""
        self.session.execute(
            sa_delete(KbSegment).where(
                KbSegment.collection == collection,
                KbSegment.document_id == document_id,
            )
        )
        self.session.flush()

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 5,
        metadata_filter: Optional[dict] = None,
    ) -> list[VectorSearchResult]:
        """向量（+可选关键词 RRF）检索；score 统一越大越相关（D12）。"""
        if self.index_mode == "economy":
            return []  # economy 不经 KnowledgeBase（D11），向量分支关闭
        params: dict[str, Any] = {
            "c": collection, "t": self.tenant_id, "k": top_k, "v": str(query_vector),
        }
        filt = ""
        if metadata_filter:
            params["mf"] = json.dumps(metadata_filter, ensure_ascii=False)
            filt = " AND s.metadata @> CAST(:mf AS jsonb)"
        sql = f"""
            SELECT s.document_id, s.chunk_index, s.content, s.metadata,
                   (s.embedding <=> CAST(:v AS vector)) AS distance
            FROM kms_segment s
            WHERE s.collection = :c AND s.tenant_id = :t AND s.embedding IS NOT NULL{filt}
            ORDER BY distance ASC
            LIMIT :k
        """
        rows = self.session.execute(text(sql), params).all()
        return [
            VectorSearchResult(
                score=-float(r.distance),  # 距离取负 → 越大越相关
                document_id=r.document_id,
                chunk=self._to_chunk(r),
            )
            for r in rows
        ]

    async def list_documents(
        self,
        collection: str,
        metadata_filter: Optional[dict] = None,
    ) -> list[DocumentSummary]:
        params: dict[str, Any] = {"c": collection, "t": self.tenant_id}
        filt = ""
        if metadata_filter:
            params["mf"] = json.dumps(metadata_filter, ensure_ascii=False)
            filt = " AND s.metadata @> CAST(:mf AS jsonb)"
        # 注意：PG 无 max(jsonb) 聚合，取任一代表 metadata 用 MIN(metadata::text)
        sql = f"""
            SELECT s.document_id, MIN(s.metadata::text) AS metadata, COUNT(*) AS chunk_count
            FROM kms_segment s
            WHERE s.collection = :c AND s.tenant_id = :t{filt}
            GROUP BY s.document_id
            ORDER BY s.document_id
        """
        rows = self.session.execute(text(sql), params).all()
        return [
            DocumentSummary(
                document_id=r.document_id,
                source=str(raw_to_dict(r.metadata).get("source", "")),
                chunk_count=int(r.chunk_count),
                metadata=raw_to_dict(r.metadata),
            )
            for r in rows
        ]

    # ── 内部 ────────────────────────────────────────────────────────────
    def _to_chunk(self, row):
        from agentscope.message import TextBlock
        from agentscope.rag import Chunk

        return Chunk(
            content=TextBlock(text=row.content or ""),
            source=str((raw_to_dict(row.metadata) or {}).get("source", "")),
            chunk_index=row.chunk_index,
            total_chunks=-1,
            metadata=raw_to_dict(row.metadata),
        )


def raw_to_dict(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if raw:
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return {}
    return {}
