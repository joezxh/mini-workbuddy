"""Embedding 业务服务

封装向量生成、存储、检索的完整流水线：
  1. 文本向量化（支持批量+自动重试）
  2. 向量持久化到 pgvector
  3. 基于向量相似度的事件/人员检索
  4. 与 EmbeddingCacheService 集成实现多级缓存
"""
from __future__ import annotations

import asyncio
from typing import List, Optional, Dict, Any

import numpy as np
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.embedding_client import get_embedding_client, EmbeddingClient
from app.config import settings
# TODO: 域特定模型已移除，Embedding 业务服务待适配
# from app.models.risk_ext import RiskEventExt, RiskPersonExt
from app.services.embedding_cache_service import EmbeddingCacheService


class EmbeddingService:
    """向量服务：生成 → 缓存 → 存储 → 检索"""

    def __init__(
        self,
        db: Session,
        redis_url: str = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.db = db
        self._client: EmbeddingClient = get_embedding_client()

        # ── 通过 Factory 获取共享的 EmbeddingCacheService ──────────
        from app.services.birt_service_factory import Factory
        self._cache = Factory.get_embedding_cache_service()
        if self._cache is None:
            # 降级：独立创建缓存（使用传入的 redis_url 或 settings.REDIS_URL）
            self._cache = EmbeddingCacheService(redis_url or settings.REDIS_URL)

        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._dimension = settings.EMBEDDING_DIMENSION

    # ------------------------------------------------------------------ #
    # 核心生成接口
    # ------------------------------------------------------------------ #

    def embed_text_sync(self, text: str) -> List[float]:
        """单条文本向量化同步接口（带重试），供子线程直接调用"""
        if not text or not text.strip():
            return []

        # 1. 查缓存
        cached = self._cache.get_embedding(text, model=self._client.provider)
        if cached is not None:
            return cached.tolist()

        # 2. 调用同步API生成（带重试）
        for attempt in range(1, self._max_retries + 1):
            try:
                embedding = self._client.embed_batch_sync([text])[0]
                break
            except Exception as e:
                if attempt == self._max_retries:
                    logger.error(f"[EmbeddingService] 同步向量生成最终失败（{attempt}次重试）: {e}")
                    raise
                wait = self._retry_delay * (2 ** (attempt - 1))
                logger.warning(f"[EmbeddingService] 同步向量生成失败（第{attempt}次），{wait}s后重试: {e}")
                import time
                time.sleep(wait)

        # 3. 写入缓存
        self._cache.set_embedding(text, np.array(embedding, dtype=np.float32), model=self._client.provider)
        return embedding

    async def embed_text(self, text: str) -> List[float]:
        """单条文本向量化（带重试）"""
        if not text or not text.strip():
            return []

        # 1. 查缓存
        cached = self._cache.get_embedding(text, model=self._client.provider)
        if cached is not None:
            return cached.tolist()

        # 2. 调用API生成（带重试）
        embedding = await self._embed_with_retry(text)

        # 3. 写入缓存
        self._cache.set_embedding(text, np.array(embedding, dtype=np.float32), model=self._client.provider)

        return embedding

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量文本向量化（自动分批+重试）"""
        if not texts:
            return []

        # 去空并保留原始索引映射
        valid_items = [(i, t.strip()) for i, t in enumerate(texts) if t and t.strip()]
        if not valid_items:
            return [[] for _ in texts]

        indices, valid_texts = zip(*valid_items)

        # 批量查缓存
        cache_results = self._cache.batch_get_embeddings(list(valid_texts), model=self._client.provider)

        # 分离命中/未命中
        miss_indices = []
        miss_texts = []
        results_map: Dict[int, List[float]] = {}

        for idx, vec in zip(indices, cache_results):
            if vec is not None:
                results_map[idx] = vec.tolist()
            else:
                miss_indices.append(idx)
                miss_texts.append(valid_texts[indices.index(idx)])

        # 批量生成未命中的向量
        if miss_texts:
            generated = await self._embed_batch_with_retry(list(miss_texts))
            for idx, emb in zip(miss_indices, generated):
                results_map[idx] = emb
                # 写入缓存
                self._cache.set_embedding(
                    valid_texts[indices.index(idx)],
                    np.array(emb, dtype=np.float32),
                    model=self._client.provider,
                )

        # 按原始顺序组装结果
        return [results_map.get(i, []) for i in range(len(texts))]

    # ------------------------------------------------------------------ #
    # 数据库持久化
    # ------------------------------------------------------------------ #

    def save_event_embedding(self, event_id: int, embedding: List[float]) -> None:
        """TODO: 待 MinWorkBuddy 通用向量缓存表适配"""
        raise NotImplementedError("save_event_embedding 待通用向量缓存适配")

    def save_person_embedding(self, person_id: int, embedding: List[float]) -> None:
        """TODO: 待 MinWorkBuddy 通用向量缓存表适配"""
        raise NotImplementedError("save_person_embedding 待通用向量缓存适配")

    async def embed_and_save_event(self, event_id: int, event_text: str) -> List[float]:
        """TODO: 待 MinWorkBuddy 通用向量缓存表适配"""
        raise NotImplementedError("embed_and_save_event 待通用向量缓存适配")

    async def embed_and_save_person(self, person_id: int, person_text: str) -> List[float]:
        """TODO: 待 MinWorkBuddy 通用向量缓存表适配"""
        raise NotImplementedError("embed_and_save_person 待通用向量缓存适配")

    # ------------------------------------------------------------------ #
    # 相似度检索（基于 pgvector）
    # ------------------------------------------------------------------ #

    def find_similar_events(
        self,
        event_id: int,
        threshold: float = 0.85,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """TODO: 待 MinWorkBuddy 通用向量缓存表适配"""
        raise NotImplementedError("find_similar_events 待通用向量缓存适配")

    def find_similar_persons(
        self,
        person_id: int,
        threshold: float = 0.85,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """TODO: 待 MinWorkBuddy 通用向量缓存表适配"""
        raise NotImplementedError("find_similar_persons 待通用向量缓存适配")

    def batch_find_similar_events(
        self,
        event_id: int,
        thresholds: List[float] = None,
        limit_per_threshold: int = 20,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """TODO: 待 MinWorkBuddy 通用向量缓存表适配"""
        raise NotImplementedError("batch_find_similar_events 待通用向量缓存适配")

    # ------------------------------------------------------------------ #
    # 内部辅助
    # ------------------------------------------------------------------ #

    async def _embed_with_retry(self, text: str) -> List[float]:
        """单条生成，带指数退避重试"""
        for attempt in range(1, self._max_retries + 1):
            try:
                return await self._client.embed(text)
            except Exception as e:
                if attempt == self._max_retries:
                    logger.error(f"[EmbeddingService] 向量生成最终失败（{attempt}次重试）: {e}")
                    raise
                wait = self._retry_delay * (2 ** (attempt - 1))
                logger.warning(f"[EmbeddingService] 向量生成失败（第{attempt}次），{wait}s后重试: {e}")
                await asyncio.sleep(wait)

    async def _embed_batch_with_retry(self, texts: List[str]) -> List[List[float]]:
        """批量生成，带重试"""
        for attempt in range(1, self._max_retries + 1):
            try:
                return await self._client.embed_batch(texts)
            except Exception as e:
                if attempt == self._max_retries:
                    logger.error(f"[EmbeddingService] 批量向量生成最终失败（{attempt}次重试）: {e}")
                    raise
                wait = self._retry_delay * (2 ** (attempt - 1))
                logger.warning(f"[EmbeddingService] 批量向量生成失败（第{attempt}次），{wait}s后重试: {e}")
                await asyncio.sleep(wait)