# backend/app/services/embedding_cache_service.py
"""向量缓存服务 - L1(Redis) + L2(LRU) 两级缓存"""
import hashlib
import threading
import numpy as np
from typing import Optional, List
from loguru import logger

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class EmbeddingCacheService:
    """向量缓存服务"""

    L1_CACHE_TTL = 86400
    L1_KEY_PREFIX = "emb:v1:"
    L2_CACHE_SIZE = 10000

    def __init__(self, redis_url: str = None, redis_client=None):
        """初始化向量缓存服务

        Args:
            redis_url: Redis URL（当 redis_client 未传入时使用）
            redis_client: 外部传入的 Redis 客户端实例（优先使用，避免重复创建连接）
        """
        self._redis_client = None
        self._l2_lock = threading.Lock()  # L2 缓存线程安全锁（Factory 单例多线程共享）
        self._l2_cache = {}
        self._l2_access_order = []

        # 优先使用外部传入的 redis_client（来自 Factory）
        if redis_client is not None:
            self._redis_client = redis_client
            try:
                self._redis_client.ping()
                logger.info("EmbeddingCacheService: Redis连接成功（外部传入）")
            except Exception as e:
                logger.warning(f"EmbeddingCacheService: 外部 Redis ping 失败: {e}")
                self._redis_client = None
        elif REDIS_AVAILABLE and redis_url:
            try:
                self._redis_client = redis.from_url(redis_url)
                self._redis_client.ping()
                logger.info("EmbeddingCacheService: Redis连接成功")
            except Exception as e:
                logger.warning(f"EmbeddingCacheService: Redis连接失败: {e}")

    def get_embedding(self, text: str, model: str = "miniLM") -> Optional[np.ndarray]:
        """获取文本向量嵌入"""
        if not text or not text.strip():
            return None

        cache_key = self._make_cache_key(text, model)

        vector = self._l2_get(cache_key)
        if vector is not None:
            return vector

        if self._redis_client:
            try:
                redis_key = f"{self.L1_KEY_PREFIX}{cache_key}"
                cached = self._redis_client.get(redis_key)
                if cached:
                    vector = np.frombuffer(cached, dtype=np.float32)
                    self._l2_set(cache_key, vector)
                    return vector
            except Exception as e:
                logger.debug(f"Redis缓存查询失败: {e}")

        return None

    def set_embedding(self, text: str, vector: np.ndarray, model: str = "miniLM"):
        """设置向量缓存"""
        cache_key = self._make_cache_key(text, model)

        if self._redis_client:
            try:
                redis_key = f"{self.L1_KEY_PREFIX}{cache_key}"
                self._redis_client.setex(redis_key, self.L1_CACHE_TTL, vector.tobytes())
            except Exception as e:
                logger.debug(f"Redis缓存写入失败: {e}")

        self._l2_set(cache_key, vector)

    def batch_get_embeddings(self, texts: List[str], model: str = "miniLM") -> List[Optional[np.ndarray]]:
        """批量获取向量"""
        results = []
        cache_keys = [self._make_cache_key(t, model) for t in texts]

        if self._redis_client:
            try:
                pipe = self._redis_client.pipeline()
                for key in cache_keys:
                    pipe.get(f"{self.L1_KEY_PREFIX}{key}")
                cached_values = pipe.execute()

                for i, cached in enumerate(cached_values):
                    if cached:
                        vec = np.frombuffer(cached, dtype=np.float32)
                        self._l2_set(cache_keys[i], vec)
                        results.append(vec)
                    else:
                        results.append(None)
            except Exception as e:
                logger.debug(f"批量缓存查询失败: {e}")
                results = [None] * len(texts)
        else:
            results = [None] * len(texts)

        return results

    # ------------------------------------------------------------------ #
    # 新增：自动流水线（缓存 → 生成 → 存储）
    # ------------------------------------------------------------------ #

    async def get_or_create_embedding(
        self,
        text: str,
        model: str = "miniLM",
        embedding_client=None,
    ) -> Optional[np.ndarray]:
        """
        获取向量：先查缓存，未命中则调用 EmbeddingClient 生成并自动缓存

        Args:
            text: 输入文本
            model: 模型标识（用于缓存key）
            embedding_client: EmbeddingClient 实例（缓存未命中时使用）
        """
        # 1. 查缓存
        cached = self.get_embedding(text, model=model)
        if cached is not None:
            return cached

        # 2. 需要生成
        if embedding_client is None:
            # 惰性导入避免循环依赖
            from app.ai.embedding_client import get_embedding_client
            embedding_client = get_embedding_client()

        try:
            embedding_list = await embedding_client.embed(text)
            if not embedding_list:
                return None
            vector = np.array(embedding_list, dtype=np.float32)
        except Exception as e:
            logger.error(f"[EmbeddingCacheService] 向量生成失败: {e}")
            return None

        # 3. 写入缓存
        self.set_embedding(text, vector, model=model)
        return vector

    async def batch_get_or_create_embeddings(
        self,
        texts: List[str],
        model: str = "miniLM",
        embedding_client=None,
    ) -> List[Optional[np.ndarray]]:
        """
        批量获取向量：缓存命中直接返回，未命中批量生成并缓存

        Returns:
            与输入顺序一致的向量列表（生成失败的位置为None）
        """
        if not texts:
            return []

        # 批量查缓存
        cache_results = self.batch_get_embeddings(texts, model=model)

        # 分离命中/未命中
        miss_indices = []
        miss_texts = []
        results: List[Optional[np.ndarray]] = [None] * len(texts)

        for i, vec in enumerate(cache_results):
            if vec is not None:
                results[i] = vec
            else:
                if texts[i] and texts[i].strip():
                    miss_indices.append(i)
                    miss_texts.append(texts[i].strip())

        if not miss_texts:
            return results

        # 批量生成未命中的向量
        if embedding_client is None:
            from app.ai.embedding_client import get_embedding_client
            embedding_client = get_embedding_client()

        try:
            generated = await embedding_client.embed_batch(miss_texts)
            for idx, emb_list in zip(miss_indices, generated):
                if emb_list:
                    vector = np.array(emb_list, dtype=np.float32)
                    results[idx] = vector
                    # 写入缓存
                    self.set_embedding(texts[idx], vector, model=model)
        except Exception as e:
            logger.error(f"[EmbeddingCacheService] 批量向量生成失败: {e}")

        return results

    # ------------------------------------------------------------------ #
    # 新增：数据库持久化辅助
    # ------------------------------------------------------------------ #

    def load_embedding_from_db(
        self,
        db,
        entity_type: str,
        entity_id: int,
    ) -> Optional[np.ndarray]:
        """
        从数据库加载向量（用于缓存预热）

        TODO: MinWorkBuddy 待适配 —— 需要定义通用的向量缓存表，
        替代原 risk_ext 域特定模型。

        Args:
            db: SQLAlchemy Session
            entity_type: 实体类型
            entity_id: 实体ID
        """
        # 原实现依赖已删除的 RiskEventExt / RiskPersonExt 模型
        raise NotImplementedError(
            "load_embedding_from_db 待 AgentScope 通用向量缓存适配"
        )

    # ------------------------------------------------------------------ #
    # 内部方法
    # ------------------------------------------------------------------ #

    def _make_cache_key(self, text: str, model: str) -> str:
        """生成缓存key"""
        return hashlib.sha256(f"{model}:{text}".encode()).hexdigest()[:32]

    def _l2_get(self, key: str) -> Optional[np.ndarray]:
        """L2本地缓存读取"""
        with self._l2_lock:
            if key in self._l2_cache:
                self._l2_access_order.remove(key)
                self._l2_access_order.append(key)
                return self._l2_cache[key]
            return None

    def _l2_set(self, key: str, value: np.ndarray):
        """L2本地缓存写入"""
        with self._l2_lock:
            if key in self._l2_cache:
                self._l2_access_order.remove(key)
            elif len(self._l2_cache) >= self.L2_CACHE_SIZE:
                oldest = self._l2_access_order.pop(0)
                del self._l2_cache[oldest]
            self._l2_cache[key] = value
            self._l2_access_order.append(key)