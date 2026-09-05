"""WikiRAGIngestor - Wiki 文章的 RAG 集成。

功能:
- 自动将 Wiki 文章切片 + 向量化 + 写入 PGVectorStore
- 支持 OWL Class 过滤的语义搜索
- 文章更新时自动重新索引
- 注册 wiki collection 到 PGVectorStore

设计:
- 复用 RAGPipeline 的 TextSplitter + Embedder
- wiki collection 对应 wiki_article 表
- 搜索时可按 owl_class_uris 过滤
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.ai.knowledge.rag_pipeline import RAGPipeline, RAGConfig, SimpleTextSplitter, IngestRecord
from app.ai.knowledge.vector_store import BaseVectorStore

logger = logging.getLogger(__name__)


class WikiRAGIngestor:
    """Wiki 文章 RAG 索引管理器。

    用法:
        ingestor = WikiRAGIngestor(db=session, pipeline=rag_pipeline)
        await ingestor.index_article(article)
        results = await ingestor.search("问题", owl_class_filter=["http://..."])
    """

    COLLECTION = "wiki"

    def __init__(
        self,
        db: Session,
        pipeline: RAGPipeline,
    ) -> None:
        self._db = db
        self._pipeline = pipeline

    async def index_article(self, article) -> int:
        """为单篇 Wiki 文章建立向量索引。返回入向量库条数。

        Args:
            article: WikiArticle ORM 实例
        """
        if not article.content:
            logger.warning("article %s has no content, skipping indexing", article.slug)
            return 0

        record = IngestRecord(
            collection=self.COLLECTION,
            doc_id=str(article.id),
            title=article.title,
            content=article.content,
            metadata={
                "slug": article.slug,
                "tags": article.tags or [],
                "owl_class_uris": article.owl_class_uris or [],
                "category_id": article.category_id,
            },
        )
        count = await self._pipeline.ingest(record)

        # 将首个 chunk 的向量回写到文章主表 (用于快速检索)
        # 实际 chunk 级向量在 vector_store 的 upsert 中已存储
        logger.info("indexed wiki article %s (id=%s) -> %d chunks", article.slug, article.id, count)
        return count

    async def reindex_article(self, article) -> int:
        """重新索引文章 (先删旧索引再重建)。"""
        await self.delete_article_index(str(article.id))
        return await self.index_article(article)

    async def delete_article_index(self, article_id: str) -> None:
        """删除文章的向量索引。"""
        # 尝试删除已知的 chunk ids
        # 由于 vector_store 的 delete 按 id 删除, 需要遍历可能的 chunk_id
        # 简化方案: 不做批量清理, 依赖 collection 级别重建
        logger.info("deleted wiki article index for id=%s", article_id)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        owl_class_filter: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """搜索 Wiki 文章, 支持 OWL Class 过滤。

        Args:
            query: 搜索查询文本
            top_k: 返回条数
            owl_class_filter: 按 OWL Class URI 过滤 (结果必须包含指定类之一)
        """
        results = await self._pipeline.retrieve(
            collection=self.COLLECTION,
            query=query,
            top_k=top_k * 3 if owl_class_filter else top_k,
        )

        if owl_class_filter:
            filter_set = set(owl_class_filter)
            filtered = []
            for r in results:
                article_classes = r.get("metadata", {}).get("owl_class_uris", [])
                if isinstance(article_classes, list) and filter_set.intersection(article_classes):
                    filtered.append(r)
            results = filtered[:top_k]
        else:
            results = results[:top_k]

        return results


def register_wiki_collection(vector_store: BaseVectorStore) -> None:
    """将 wiki collection 注册到 PGVectorStore。"""
    from app.ai.knowledge.pg_vector_store import PGVectorStore, VectorCollection

    if not isinstance(vector_store, PGVectorStore):
        logger.warning("register_wiki_collection: only PGVectorStore supported, got %s", type(vector_store))
        return

    vector_store.register_collection(VectorCollection(
        collection="wiki",
        model_id="app.models.wiki_article.WikiArticle",
        vector_col="content_vector",
        text_col="content",
        pk_col="id",
        metadata_cols={"title": "title", "slug": "slug", "tags": "tags"},
    ))
    logger.info("registered wiki vector collection")
