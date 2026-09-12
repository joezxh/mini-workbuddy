"""Wiki 混合检索服务（G1/G9）。

编排三种检索模式：
- semantic：PGVector 向量检索（依赖 embedding 配置，不可用时降级）
- keyword ：SQL LIKE 关键词检索
- hybrid  ：两者结果经 RRF（Reciprocal Rank Fusion）融合

检索行为统一返回 ``{items, mode}``，PGVector 不可用时自动降级为 keyword，
前端契约保持不变。
"""
from __future__ import annotations

import logging
import math
import time
from typing import List, Optional

from sqlalchemy import func, select

from app.ai.embedding_client import get_embedding_client
from app.core.tenant_context import get_tenant_id
from app.models.wiki.wiki_article import WikiArticle
from app.models.wiki.wiki_category import WikiCategory
from app.models.wiki.wiki_search_log import WikiSearchLog


logger = logging.getLogger(__name__)


def _cosine(vec1, vec2) -> float:
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    n1 = math.sqrt(sum(a * a for a in vec1))
    n2 = math.sqrt(sum(b * b for b in vec2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def _to_item(a: WikiArticle, score: float, include_content: bool = False) -> dict:
    content = a.content or ""
    return {
        "id": a.id,
        "slug": a.slug,
        "title": a.title,
        "summary": a.summary,
        "snippet": (content[:240] + ("…" if len(content) > 240 else "")),
        "score": round(score, 4),
        "category_id": a.category_id,
        "content": content if include_content else None,
    }


class WikiSearchService:
    """混合检索编排 + 审计落库。"""

    def __init__(self, db) -> None:
        self.db = db

    def search(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        top_k: int = 5,
        knowledge_id: Optional[int] = None,
        owl_class_filter: Optional[List[str]] = None,
        user_id: Optional[int] = None,
    ) -> dict:
        start = time.time()
        mode = mode if mode in ("semantic", "keyword", "hybrid") else "hybrid"

        semantic: List[dict] = []
        keyword: List[dict] = []
        if mode in ("semantic", "hybrid"):
            semantic = self._semantic_search(query, top_k, knowledge_id, owl_class_filter)
        if mode in ("keyword", "hybrid"):
            keyword = self._keyword_search(query, top_k, knowledge_id, owl_class_filter)

        if mode == "semantic":
            merged = semantic[:top_k]
            effective_mode = "semantic" if semantic else "keyword"
        elif mode == "keyword":
            merged = keyword[:top_k]
            effective_mode = "keyword"
        else:
            merged = self._rrf_merge(semantic, keyword, top_k)
            effective_mode = "hybrid" if (semantic and keyword) else ("semantic" if semantic else "keyword")

        latency_ms = int((time.time() - start) * 1000)
        self._log_search(query, effective_mode, len(merged), latency_ms, user_id)
        return {
            "query": query,
            "mode": effective_mode,
            "total": len(merged),
            "items": merged,
        }

    def _semantic_search(
        self,
        query: str,
        top_k: int,
        knowledge_id: Optional[int],
        owl_class_filter: Optional[List[str]],
    ) -> List[dict]:
        try:
            client = get_embedding_client()
            query_vec = client.embed_sync(query)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[WikiSearchService] embedding 不可用，语义检索降级: {e}")
            return []
        if not query_vec:
            return []

        stmt = (
            select(WikiArticle)
            .where(WikiArticle.content_vector.isnot(None))
            .order_by(WikiArticle.content_vector.cosine_distance(query_vec))
            .limit(top_k)
        )
        stmt = self._apply_filters(stmt, knowledge_id, owl_class_filter)
        try:
            articles = self.db.execute(stmt).scalars().all()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[WikiSearchService] 向量检索失败，降级: {e}")
            return []
        items = []
        for a in articles:
            vec = getattr(a, "content_vector", None)
            score = _cosine(query_vec, vec) if vec else 0.0
            items.append(_to_item(a, score, include_content=True))
        return items

    def _keyword_search(
        self,
        query: str,
        top_k: int,
        knowledge_id: Optional[int],
        owl_class_filter: Optional[List[str]],
    ) -> List[dict]:
        pattern = f"%{query}%"
        stmt = (
            select(WikiArticle)
            .where(WikiArticle.status >= 0)
            .where(WikiArticle.title.ilike(pattern) | WikiArticle.content.ilike(pattern))
            .order_by(WikiArticle.updated_at.desc())
            .limit(top_k)
        )
        stmt = self._apply_filters(stmt, knowledge_id, owl_class_filter)
        articles = self.db.execute(stmt).scalars().all()
        return [_to_item(a, 1.0 - 0.01 * i) for i, a in enumerate(articles)]

    def _apply_filters(self, stmt, knowledge_id, owl_class_filter):
        if knowledge_id is not None:
            join = WikiCategory.id == WikiArticle.category_id
            stmt = stmt.join(WikiCategory, join).where(
                WikiCategory.knowledge_id == knowledge_id
            )
        if owl_class_filter:
            stmt = stmt.where(WikiArticle.owl_class_uris.op("&&")(owl_class_filter))
        return stmt

    @staticmethod
    def _rrf_merge(semantic: List[dict], keyword: List[dict], top_k: int) -> List[dict]:
        """Reciprocal Rank Fusion: score = Σ 1/(k + rank_i)，k=60。"""
        k = 60.0
        scores: dict[int, float] = {}
        meta: dict[int, dict] = {}
        for rank, item in enumerate(semantic):
            scores[item["id"]] = scores.get(item["id"], 0.0) + 1.0 / (k + rank + 1)
            meta[item["id"]] = item
        for rank, item in enumerate(keyword):
            scores[item["id"]] = scores.get(item["id"], 0.0) + 1.0 / (k + rank + 1)
            meta[item["id"]] = item
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        result = []
        for aid, sc in ranked[:top_k]:
            it = meta[aid]
            it = dict(it)
            it["score"] = round(sc, 4)
            result.append(it)
        return result

    def _log_search(self, query: str, mode: str, result_count: int, latency_ms: int, user_id: Optional[int]) -> None:
        try:
            log = WikiSearchLog(
                tenant_id=get_tenant_id(),
                user_id=user_id,
                query=query,
                mode=mode,
                result_count=result_count,
                latency_ms=latency_ms,
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[WikiSearchService] 检索审计落库失败(忽略): {e}")
            try:
                self.db.rollback()
            except Exception:  # noqa: BLE001
                pass

    def history(self, *, page: int = 1, page_size: int = 20, mode: Optional[str] = None):
        """检索历史（管理后台 RAG 测试 Tab 旁可复用）。"""
        from sqlalchemy import desc

        stmt = select(WikiSearchLog)
        count_stmt = select(func.count()).select_from(WikiSearchLog)
        if mode:
            stmt = stmt.where(WikiSearchLog.mode == mode)
            count_stmt = count_stmt.where(WikiSearchLog.mode == mode)
        total = self.db.execute(count_stmt).scalar() or 0
        items = (
            self.db.execute(
                stmt.order_by(desc(WikiSearchLog.created_at))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": l.id,
                    "query": l.query,
                    "mode": l.mode,
                    "result_count": l.result_count,
                    "latency_ms": l.latency_ms,
                    "created_at": str(l.created_at) if l.created_at else None,
                }
                for l in items
            ],
        }
