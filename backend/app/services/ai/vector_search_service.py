"""向量检索服务 - 事件相似度与聚合引擎

基于pgvector提供：
1. 事件相似度去重（MD5+向量双校验）
2. 相似事件批量聚合（降低LLM批次成本）
3. 历史相似案例快速检索（辅助风险评分）
"""
import hashlib
from typing import Dict, Any, Optional, List

import numpy as np
from sqlalchemy.orm import Session

# TODO: 域特定模型已移除，向量检索服务待适配
# from app.models.risk_event import RiskEvent
# from app.models.risk_ext import RiskEventExt
from app.services.ai.embedding_service import EmbeddingService


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """计算两个向量的余弦相似度"""
    if a is None or b is None:
        return 0.0
    a = np.array(a, dtype=np.float32)
    b = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class VectorSearchService:
    """向量检索服务 - 事件相似度与聚合引擎"""

    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = EmbeddingService(db)

    def _embed_text_sync(self, text: str) -> Optional[List[float]]:
        """在同步调用链里执行 embedding（使用同步接口，避免创建临时事件循环）。"""
        return self.embedding_service.embed_text_sync(text)

    @staticmethod
    def compute_content_hash(title: Optional[str], content: Optional[str]) -> str:
        """计算事件内容的SHA256哈希（用于快速去重）"""
        text = f"{title or ''}|{content or ''}"
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def check_hash_duplicate(self, content_hash: str) -> Optional[int]:
        """TODO: 待 MinWorkBuddy 通用向量缓存表适配"""
        raise NotImplementedError("check_hash_duplicate 待通用向量缓存适配")

    def find_duplicate_or_similar(
        self,
        event_id: int,
        title: str,
        content: str,
        similarity_threshold: float = 0.92
    ) -> Dict[str, Any]:
        """TODO: 待 MinWorkBuddy 通用向量缓存表适配"""
        raise NotImplementedError("find_duplicate_or_similar 待通用向量缓存适配")

    # ------------------------------------------------------------------ #
    # 相似度检索
    # ------------------------------------------------------------------ #

    def _vector_search(
        self,
        query_embedding: Any,
        exclude_event_id: int = None,
        threshold: float = 0.85,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """TODO: 待 MinWorkBuddy 通用向量缓存表适配"""
        raise NotImplementedError("_vector_search 待通用向量缓存适配")

    # ------------------------------------------------------------------ #
    # 聚合批次构建
    # ------------------------------------------------------------------ #

    def build_similarity_batches(
        self,
        event_ids: List[int],
        batch_similarity_threshold: float = 0.85
    ) -> List[List[int]]:
        """TODO: 待 MinWorkBuddy 通用向量缓存表适配"""
        raise NotImplementedError("build_similarity_batches 待通用向量缓存适配")

    def _batch_get_embeddings_from_db(self, event_ids: List[int]) -> Dict[int, np.ndarray]:
        """TODO: 待 MinWorkBuddy 通用向量缓存表适配"""
        raise NotImplementedError("_batch_get_embeddings_from_db 待通用向量缓存适配")

    # ------------------------------------------------------------------ #
    # 辅助方法
    # ------------------------------------------------------------------ #

    def _suggest_cluster(self, similar_events: List[Dict]) -> Optional[int]:
        """建议聚类ID：取相似事件中最大的cluster_id"""
        if not similar_events:
            return None

        clusters = [e["cluster_id"] for e in similar_events if e.get("cluster_id")]
        if clusters:
            return max(clusters)
        return None

    def _save_content_hash(self, event_id: int, content_hash: str):
        """TODO: 待 MinWorkBuddy 通用向量缓存表适配"""
        raise NotImplementedError("_save_content_hash 待通用向量缓存适配")
