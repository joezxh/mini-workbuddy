"""PGVectorStore —— MinWorkBuddy 知识库向量存储（AgentScope RAG Service 内核）。

直接落在 ``kb_collection`` / ``kb_segment`` / ``kb_ref`` 三张表上，满足
``VectorStoreBase`` 的契约语义：create / delete / has / insert / delete-doc /
list / search。

租户隔离：构造时必须传入 ``tenant_id``；所有读写都带 ``tenant_id`` 过滤
（纵深防御，P1 Task 6 再叠加 UserIdMapper）。无 ``tenant_id`` 一律不放行。

当前进度（P1 简报）：
- Task 2：collection 管理 + 写入/删除/列出骨架（已实现，测试全过）
- Task 3：embedding 接入由 ``app.services.kb.ingest_service.KbIngestService`` 提供
  （缺失向量经注入的 ``embed_fn`` 生成后写入，含维度校验）
- Task 4：``search`` 已实现（余弦距离 + HNSW 索引加速，迁移 006 已建索引）；
  文本检索由 ``app.services.kb.retrieval_service.KbRetrievalService`` 提供
- Task 5：``hybrid_search`` 已实现（向量召回 + 中文子串关键词召回（trigram-GIN 加速
  的 LIKE），RRF 融合；迁移 006 已建 ``ix_kb_segment_content_trgm`` GIN 索引与 pg_trgm 扩展）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import delete, func, select, type_coerce
from sqlalchemy import Text as sa_Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.kb.kb_collection import KbCollection
from app.models.kb.kb_segment import KbSegment


def _class_uris_any(class_uris):
    """构造 JSONB ``?|``（任一命中）过滤条件；右侧显式按 text[] 绑定。

    不做类型强转时 psycopg2 会把 Python list 绑定成 jsonb，
    触发 ``operator does not exist: jsonb ?| jsonb``。
    """
    return KbSegment.class_uris.op("?|")(
        type_coerce(list(class_uris), ARRAY(sa_Text))
    )


@dataclass
class SegmentInput:
    """单个切片输入（写入 ``kb_segment`` 的一行）。"""

    chunk_index: int
    content: Optional[str] = None
    embedding: Optional[List[float]] = None
    token_count: Optional[int] = None
    # 切片元数据（JSONB 列 "metadata"）
    metadata: Optional[dict] = None
    # 映射到的本体类 uri 列表（P4 Task 7 检索过滤用，前向兼容）
    class_uris: Optional[List[str]] = None


@dataclass
class SearchResult:
    """单条检索结果（Task 4 填充）。"""

    document_id: str
    chunk_index: int
    content: Optional[str]
    score: float
    metadata: Optional[dict] = None
    class_uris: Optional[List[str]] = None


class PGVectorStore:
    """基于 PostgreSQL + pgvector 的知识库向量存储。

    :param db: SQLAlchemy 会话（同一请求/事务内复用）
    :param tenant_id: 租户 ID，必填；缺失则拒绝构造
    """

    def __init__(self, db: Session, tenant_id: int) -> None:
        if tenant_id is None:
            raise ValueError("PGVectorStore 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    # ------------------------------------------------------------------ #
    # collection 管理
    # ------------------------------------------------------------------ #
    def create_collection(self, name: str, dimensions: int) -> KbCollection:
        """创建 collection 元数据；同租户内幂等（已存在则返回原行）。"""
        existing = self.get_collection(name)
        if existing is not None:
            return existing
        obj = KbCollection(
            tenant_id=self.tenant_id, name=name, dimensions=dimensions
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def get_collection(self, name: str) -> Optional[KbCollection]:
        return self.db.execute(
            select(KbCollection).where(
                KbCollection.tenant_id == self.tenant_id,
                KbCollection.name == name,
            )
        ).scalar_one_or_none()

    def has_collection(self, name: str) -> bool:
        return self.get_collection(name) is not None

    def list_collections(self) -> List[KbCollection]:
        return list(
            self.db.execute(
                select(KbCollection)
                .where(KbCollection.tenant_id == self.tenant_id)
                .order_by(KbCollection.name)
            ).scalars().all()
        )

    def delete_collection(self, name: str) -> bool:
        """删除 collection 元数据及其全部切片；不存在返回 False。"""
        coll = self.get_collection(name)
        if coll is None:
            return False
        self.db.execute(
            delete(KbSegment).where(
                KbSegment.tenant_id == self.tenant_id,
                KbSegment.collection == name,
            )
        )
        self.db.delete(coll)
        self.db.flush()
        return True

    # ------------------------------------------------------------------ #
    # 切片写入 / 删除 / 列出
    # ------------------------------------------------------------------ #
    def insert(self, collection: str, document_id: str, segments: List[SegmentInput]) -> int:
        """写入/更新文档的若干切片。

        幂等：以 ``(collection, document_id, chunk_index)`` 为冲突键做
        ``ON CONFLICT DO UPDATE``，重复入库不新增行（P1 验收：幂等）。

        :return: 本次 upsert 的切片数
        """
        if not segments:
            return 0
        rows = []
        for s in segments:
            rows.append(
                {
                    "tenant_id": self.tenant_id,
                    "collection": collection,
                    "document_id": document_id,
                    "chunk_index": s.chunk_index,
                    "content": s.content,
                    "embedding": s.embedding,
                    "token_count": s.token_count,
                    "metadata_": s.metadata,
                    "class_uris": s.class_uris,
                }
            )
        stmt = pg_insert(KbSegment).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["collection", "document_id", "chunk_index"],
            set_={
                "content": stmt.excluded.content,
                "embedding": stmt.excluded.embedding,
                "token_count": stmt.excluded.token_count,
                "metadata": stmt.excluded.metadata,
                "class_uris": stmt.excluded.class_uris,
                # tenant_id 保持不变（建表唯一约束不含 tenant_id，collection 名为全局唯一）
            },
        )
        self.db.execute(stmt)
        self.db.flush()
        return len(rows)

    def delete_document(self, collection: str, document_id: str) -> int:
        """删除某文档的全部切片；返回删除行数。"""
        n = self.db.execute(
            delete(KbSegment).where(
                KbSegment.tenant_id == self.tenant_id,
                KbSegment.collection == collection,
                KbSegment.document_id == document_id,
            )
        ).rowcount
        self.db.flush()
        return n

    def list_documents(self, collection: str) -> List[str]:
        """列出某 collection 下的去重 document_id（按字典序）。"""
        rows = self.db.execute(
            select(KbSegment.document_id)
            .where(
                KbSegment.tenant_id == self.tenant_id,
                KbSegment.collection == collection,
            )
            .distinct()
            .order_by(KbSegment.document_id)
        ).scalars().all()
        return list(rows)

    def count_segments(self, collection: str) -> int:
        return int(
            self.db.execute(
                select(func.count())
                .select_from(KbSegment)
                .where(
                    KbSegment.tenant_id == self.tenant_id,
                    KbSegment.collection == collection,
                )
            ).scalar()
            or 0
        )

    # ------------------------------------------------------------------ #
    # 检索（P1 Task 4：向量检索 + HNSW；Task 5 再叠加中文混合检索）
    # ------------------------------------------------------------------ #
    def search(
        self,
        collection: str,
        query_embedding: List[float],
        top_k: int = 10,
        score_threshold: Optional[float] = None,
        class_uris: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """向量相似检索（余弦距离 + HNSW 加速，迁移 006 已建索引）。

        :param collection: 集合名（同租户内）
        :param query_embedding: 查询向量（长度需与集合维度一致）
        :param top_k: 返回条数上限
        :param score_threshold: 余弦相似度阈值（[-1,1]，越大越相似）；
            仅返回 ``score >= score_threshold`` 的结果；None 表示不过滤
        :param class_uris: 本体类 URI 列表（P4.3 检索过滤）；JSONB ``?|`` 任一命中
            即通过（OR 语义），空列表/None 表示不过滤
        :return: 按相似度降序的 ``SearchResult`` 列表，``score`` 为余弦相似度
        """
        if not query_embedding:
            return []

        dist = KbSegment.embedding.cosine_distance(query_embedding)
        stmt = (
            select(
                KbSegment.document_id,
                KbSegment.chunk_index,
                KbSegment.content,
                KbSegment.metadata_.label("metadata"),
                KbSegment.class_uris,
                dist.label("distance"),
            )
            .where(
                KbSegment.tenant_id == self.tenant_id,
                KbSegment.collection == collection,
                KbSegment.embedding.isnot(None),
            )
            .order_by(dist.asc())
        )
        if score_threshold is not None:
            stmt = stmt.where((1 - dist) >= score_threshold)
        if class_uris:
            stmt = stmt.where(_class_uris_any(class_uris))
        stmt = stmt.limit(top_k)

        rows = self.db.execute(stmt).all()
        return [
            SearchResult(
                document_id=r.document_id,
                chunk_index=r.chunk_index,
                content=r.content,
                score=1 - float(r.distance),
                metadata=r.metadata,
                class_uris=r.class_uris,
            )
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    # 混合检索（P1 Task 5：pg_trgm 中文关键词 + 向量，RRF 融合）
    # ------------------------------------------------------------------ #
    def hybrid_search(
        self,
        collection: str,
        query_embedding: List[float],
        query_text: str,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
        rrf_k: int = 60,
        vector_top_n: Optional[int] = None,
        keyword_top_n: Optional[int] = None,
        class_uris: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """中文混合检索：向量召回 + 中文子串关键词召回，RRF 融合（P1 Task 5）。

        关键词召回基于 trigram-GIN（gin_trgm_ops，迁移 006 已建）可加速的 LIKE 子串
        匹配，按命中位置升序排名。原因：本环境 pg_trgm.similarity() 对 CJK 文本恒返回 0
        （其 trigram 仅对字母数字词生效），故改用子串召回作为中文关键词信号。

        :param query_embedding: 查询向量（可选；为 None/空则仅走关键词召回）
        :param query_text: 查询文本（可选；为空则仅走向量召回）
        :param rrf_k: RRF 常数（默认 60）
        :param vector_top_n: 向量召回候选数（默认 max(top_k*4, 50)）
        :param keyword_top_n: 关键词召回候选数（默认同 vector_top_n）
        :param score_threshold: 对融合后的 RRF 分数过滤（越高越相关）；
            None 表示不过滤
        :param class_uris: 本体类 URI 列表（P4.3 检索过滤，向量/关键词两路都过滤）；
            JSONB ``?|`` 任一命中即通过，空列表/None 表示不过滤
        :return: 按融合分数降序的 ``SearchResult`` 列表，``score`` 为 RRF 分数
        """
        if not query_embedding and not query_text:
            return []

        v_top = vector_top_n or max(top_k * 4, 50)
        k_top = keyword_top_n or v_top

        # 向量候选（按余弦距离升序取前 v_top）
        vector_hits: dict = {}
        if query_embedding:
            dist = KbSegment.embedding.cosine_distance(query_embedding)
            v_stmt = (
                select(
                    KbSegment.document_id,
                    KbSegment.chunk_index,
                    KbSegment.content,
                    KbSegment.metadata_.label("metadata"),
                    KbSegment.class_uris,
                )
                .where(
                    KbSegment.tenant_id == self.tenant_id,
                    KbSegment.collection == collection,
                    KbSegment.embedding.isnot(None),
                )
                .order_by(dist.asc())
            )
            if class_uris:
                v_stmt = v_stmt.where(_class_uris_any(class_uris))
            v_stmt = v_stmt.limit(v_top)
            for rank, row in enumerate(self.db.execute(v_stmt).all(), start=1):
                vector_hits[(row.document_id, row.chunk_index)] = (row, rank)

        # 关键词候选（中文子串召回）。
        # 注意：本环境的 pg_trgm.similarity() 对 CJK 文本恒返回 0（其 trigram 仅对
        # 字母数字词生效，中文不产生 trigram），故改用 trigram-GIN 可加速的 LIKE 子串
        # 匹配（精确子串召回），按命中位置升序排名后参与 RRF 融合。
        keyword_hits: dict = {}
        if query_text:
            escaped = (
                query_text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            like_pattern = f"%{escaped}%"
            pos = func.strpos(KbSegment.content, query_text)
            k_stmt = (
                select(
                    KbSegment.document_id,
                    KbSegment.chunk_index,
                    KbSegment.content,
                    KbSegment.metadata_.label("metadata"),
                    KbSegment.class_uris,
                    pos.label("pos"),
                )
                .where(
                    KbSegment.tenant_id == self.tenant_id,
                    KbSegment.collection == collection,
                    KbSegment.content.isnot(None),
                    KbSegment.content.like(like_pattern, escape="\\"),
                )
                .order_by(pos.asc(), func.length(KbSegment.content).asc())
            )
            if class_uris:
                k_stmt = k_stmt.where(_class_uris_any(class_uris))
            k_stmt = k_stmt.limit(k_top)
            for rank, row in enumerate(self.db.execute(k_stmt).all(), start=1):
                keyword_hits[(row.document_id, row.chunk_index)] = (row, rank, int(row.pos))

        # RRF 融合：对每个候选在所属列表中按 1/(k+rank) 累加
        fused: dict = {}
        for (key, (row, rank)) in vector_hits.items():
            fused[key] = {"row": row, "rrf": 1.0 / (rrf_k + rank), "sim": None}
        for (key, (row, rank, sim)) in keyword_hits.items():
            if key not in fused:
                fused[key] = {"row": row, "rrf": 0.0, "sim": sim}
            else:
                fused[key]["sim"] = sim
            fused[key]["rrf"] += 1.0 / (rrf_k + rank)

        items = sorted(fused.values(), key=lambda d: d["rrf"], reverse=True)
        if score_threshold is not None:
            items = [d for d in items if d["rrf"] >= score_threshold]
        items = items[:top_k]

        return [
            SearchResult(
                document_id=d["row"].document_id,
                chunk_index=d["row"].chunk_index,
                content=d["row"].content,
                score=d["rrf"],
                metadata=d["row"].metadata,
                class_uris=d["row"].class_uris,
            )
            for d in items
        ]
