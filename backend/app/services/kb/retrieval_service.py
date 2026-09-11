"""知识库检索服务（P1 Task 4：向量检索 + HNSW）。

把「向量检索」接到查询链路：``search_by_text`` 先用注入的 ``embed_fn`` 把查询文本
向量化，再调用 ``PGVectorStore.search``（余弦距离 + HNSW 索引）。与 ``KbIngestService``
对称——向量生成通过 ``embed_fn`` 注入，便于测试替换。
"""
from __future__ import annotations

from typing import Callable, List, Optional

from app.ai.embedding_client import get_embedding_client
from app.services.kb.pgvector_store import PGVectorStore, SearchResult


EmbedFn = Callable[[List[str]], List[List[float]]]


def build_embed_fn(code: Optional[str] = None) -> EmbedFn:
    """构造默认 ``embed_fn``：复用全局 EmbeddingClient 的同步批量接口。"""
    client = get_embedding_client(code)

    def _fn(texts: List[str]) -> List[List[float]]:
        return client.embed_batch_sync(texts)

    return _fn


class KbRetrievalService:
    """检索服务：查询向量化 + 向量检索。"""

    def __init__(self, store: PGVectorStore, embed_fn: EmbedFn):
        self.store = store
        self._embed_fn = embed_fn

    @classmethod
    def from_session(
        cls, db, tenant_id: int, embedding_code: Optional[str] = None
    ) -> "KbRetrievalService":
        store = PGVectorStore(db, tenant_id)
        return cls(store, build_embed_fn(embedding_code))

    def search_by_text(
        self,
        collection: str,
        query_text: str,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
        class_uris: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """文本检索：向量化查询后做余弦相似检索。

        :param class_uris: 本体类过滤（P4.3）；应传「后代扩展后」的 URI 列表
            （见 ``app.services.ontology.search_filter.expand_with_descendants``）
        """
        vectors = self._embed_fn([query_text])
        if not vectors:
            return []
        return self.store.search(
            collection, vectors[0], top_k, score_threshold, class_uris=class_uris
        )

    def search_by_vector(
        self,
        collection: str,
        query_vector: List[float],
        top_k: int = 10,
        score_threshold: Optional[float] = None,
        class_uris: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """向量检索（查询已向量化）。"""
        return self.store.search(
            collection, query_vector, top_k, score_threshold, class_uris=class_uris
        )

    def hybrid_search_by_text(
        self,
        collection: str,
        query_text: str,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
        rrf_k: int = 60,
        class_uris: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """中文混合检索（文本入口）：向量化查询后做向量 + 关键词 RRF 融合（P1 Task 5）。"""
        vectors = self._embed_fn([query_text])
        query_embedding = vectors[0] if vectors else None
        return self.store.hybrid_search(
            collection,
            query_embedding,
            query_text,
            top_k,
            score_threshold,
            rrf_k=rrf_k,
            class_uris=class_uris,
        )
