"""Embedding 客户端

配置模式（显式二选一，互不降级）：
  A. DB 模式（按 code 精确选择）：
     调用方传入 code → 在 ai_chat_model 表按 code 精确匹配（status=1），
     关联 ai_api_key 获取 url/api_key，构建 OpenAI 兼容后端。
     字段映射：ai_api_key.url → base_url, ai_api_key.api_key → api_key,
              ai_chat_model.model → model, ai_chat_model.dimensions → dimension。
  B. .env 模式（不传 code）：
     依据 settings.EMBEDDING_PROVIDER 构建后端（gpustack / dashscope）。

两种模式互不降级：DB 模式失败则抛 ValueError，不会回退到 .env。

支持的提供商（.env 模式）：
  - gpustack  ：本地 GPUStack 部署（OpenAI 兼容模式，httpx 调用）
  - dashscope ：阿里百炼原生 DashScope HTTP API（非 OpenAI 兼容模式，httpx 调用）
"""
from __future__ import annotations

import time as _time
from typing import List, Optional

import httpx
from loguru import logger

from app.config import settings


class _BaseEmbeddingBackend:
    """Embedding 后端基类：定义公共调用接口"""

    async def embed(self, text: str) -> List[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

    def embed_batch_sync(self, texts: List[str]) -> List[List[float]]:
        """同步版本的批量 embed，避免在子线程中创建临时事件循环"""
        raise NotImplementedError


class _OpenAICompatibleBackend(_BaseEmbeddingBackend):
    """OpenAI 兼容 Embedding 后端（用于 GPUStack）"""

    def __init__(self, api_url: str, api_key: str, model: str, dimension: int):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dimension = dimension

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """OpenAI 标准格式批量请求：{\"data\": [{\"embedding\": [...], \"index\": 0}, ...]}"""
        if not texts:
            return []

        payload = {"model": self.model, "input": texts}

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.api_url}/embeddings",
                    json=payload,
                    headers=self._headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Embedding API 返回错误状态码: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Embedding 请求失败: {e}")
            raise

        items: list = data.get("data", [])
        items.sort(key=lambda x: x["index"])
        return [item["embedding"][: self.dimension] for item in items]

    def embed_batch_sync(self, texts: List[str]) -> List[List[float]]:
        """同步版本批量请求"""
        if not texts:
            return []

        payload = {"model": self.model, "input": texts}
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{self.api_url}/embeddings",
                    json=payload,
                    headers=self._headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[EmbeddingClient] 同步请求错误状态码: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"[EmbeddingClient] 同步 Embedding 请求失败: {e}")
            raise

        items: list = data.get("data", [])
        items.sort(key=lambda x: x["index"])
        return [item["embedding"][: self.dimension] for item in items]


class _DashScopeBackend(_BaseEmbeddingBackend):
    """阿里百炼原生 DashScope HTTP API 后端（非 OpenAI 兼容模式）

    接口文档：https://help.aliyun.com/zh/model-studio/text-embedding-synchronous-api
    端点：POST https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding
    请求格式：
        {
          "model": "text-embedding-v3",
          "input": {"texts": ["...", "..."]},
          "parameters": {"dimension": 1024}
        }
    响应格式：
        {
          "output": {
            "embeddings": [{"text_index": 0, "embedding": [...]}, ...]
          }
        }
    """

    _ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
    # text-embedding-v3 单次最多 25 条，text-embedding-v4 最多 10 条
    _BATCH_SIZE = 25

    def __init__(self, api_key: str, model: str, dimension: int):
        self.api_key = api_key
        self.model = model
        self.dimension = dimension

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _call_once(self, client: httpx.AsyncClient, texts: List[str]) -> List[List[float]]:
        """调用一次 DashScope 原生接口，返回与 texts 顺序一致的向量列表"""
        payload: dict = {
            "model": self.model,
            "input": {"texts": texts},
            "parameters": {"dimension": self.dimension},
        }
        try:
            response = await client.post(
                self._ENDPOINT,
                json=payload,
                headers=self._headers,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[DashScope] Embedding API 返回错误状态码: "
                f"{e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"[DashScope] Embedding 请求失败: {e}")
            raise

        embeddings_raw: list = data.get("output", {}).get("embeddings", [])
        # 按 text_index 排序保证顺序一致
        embeddings_raw.sort(key=lambda x: x["text_index"])
        return [item["embedding"] for item in embeddings_raw]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """自动分批（每批最多 _BATCH_SIZE 条）并按原始顺序拼接结果"""
        if not texts:
            return []

        results: List[List[float]] = []
        async with httpx.AsyncClient(timeout=120.0) as client:
            for i in range(0, len(texts), self._BATCH_SIZE):
                batch = texts[i : i + self._BATCH_SIZE]
                batch_results = await self._call_once(client, batch)
                results.extend(batch_results)
        return results

    def embed_batch_sync(self, texts: List[str]) -> List[List[float]]:
        """同步版本：自动分批并按原始顺序拼接结果"""
        if not texts:
            return []

        results: List[List[float]] = []
        with httpx.Client(timeout=120.0) as client:
            for i in range(0, len(texts), self._BATCH_SIZE):
                batch = texts[i : i + self._BATCH_SIZE]
                payload: dict = {
                    "model": self.model,
                    "input": {"texts": batch},
                    "parameters": {"dimension": self.dimension},
                }
                try:
                    response = client.post(
                        self._ENDPOINT,
                        json=payload,
                        headers=self._headers,
                    )
                    response.raise_for_status()
                    data = response.json()
                except httpx.HTTPStatusError as e:
                    logger.error(
                        f"[DashScope] 同步请求错误状态码: {e.response.status_code} - {e.response.text}"
                    )
                    raise
                except Exception as e:
                    logger.error(f"[DashScope] 同步 Embedding 请求失败: {e}")
                    raise

                embeddings_raw: list = data.get("output", {}).get("embeddings", [])
                embeddings_raw.sort(key=lambda x: x["text_index"])
                results.extend([item["embedding"] for item in embeddings_raw])
        return results


# ── DB 模型定义表缓存（按 code 分槽）─────────────────────────────────────────
# key: code 字符串；value: {"backend": _BaseEmbeddingBackend, "ts": float}
_db_config_cache: dict[str, dict] = {}
_DB_CACHE_TTL = 60  # 缓存有效期(秒)


def _try_build_from_db_by_code(code: str) -> Optional[_BaseEmbeddingBackend]:
    """按 code 从 ai_chat_model 表精确构建 Embedding 后端（DB 模式）。

    在 ai_chat_model 表中按 code 精确匹配（status=1），关联 ai_api_key
    （status=1，且 url / api_key 均非空）获取访问凭证，构建
    _OpenAICompatibleBackend 实例。DB 模式仅支持 OpenAI 兼容协议。
    结果按 code 缓存 60s，避免每次调用都查库。
    """
    if not code:
        return None

    now = _time.time()
    cached = _db_config_cache.get(code)
    if cached and (now - cached["ts"]) < _DB_CACHE_TTL:
        return cached["backend"]

    try:
        from app.db.database import SessionLocal
        from app.models.ai.ai_api_key import AiChatModel, AiApiKey
        db = SessionLocal()
        try:
            model = (
                db.query(AiChatModel)
                .filter(AiChatModel.code == code, AiChatModel.status == 1)
                .first()
            )
            if not model:
                logger.warning(f"[EmbeddingClient] 未找到 code={code} 的启用模型定义")
                return None

            api_key_obj = db.query(AiApiKey).filter(
                AiApiKey.id == model.key_id, AiApiKey.status == 1
            ).first()
            if not api_key_obj or not api_key_obj.url or not api_key_obj.api_key:
                logger.warning(f"[EmbeddingClient] code={code} 关联 API Key 不可用")
                return None

            api_url = api_key_obj.url.rstrip("/")
            # OpenAI 兼容协议自动补全 /v1 路径后缀
            if not api_url.endswith("/v1"):
                api_url = api_url + "/v1"
            backend = _OpenAICompatibleBackend(
                api_url=api_url,
                api_key=api_key_obj.api_key,
                model=model.model,
                dimension=model.dimensions or 768,
            )
            _db_config_cache[code] = {"backend": backend, "ts": now}
            logger.info(
                f"[EmbeddingClient] 使用 DB 模型定义(code={code}): "
                f"{model.name} ({model.model}), url={api_url}, dim={model.dimensions}"
            )
            return backend
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[EmbeddingClient] DB 模型定义查询失败: {e}")
        return None

    return None


def _build_backend_from_env() -> _BaseEmbeddingBackend:
    """依据 .env 配置创建 Embedding 后端（.env 模式）"""
    provider = (settings.EMBEDDING_PROVIDER or "gpustack").lower().strip()

    if provider == "dashscope":
        api_key = settings.ALIBABA_API_KEY
        if not api_key:
            raise ValueError(
                "EMBEDDING_PROVIDER=dashscope 但 ALIBABA_API_KEY 未配置，"
                "请在 .env 中设置 ALIBABA_API_KEY"
            )
        logger.info(
            f"[EmbeddingClient] 降级 .env 百炼 DashScope API："
            f"model={settings.DASHSCOPE_EMBEDDING_MODEL}, "
            f"dim={settings.DASHSCOPE_EMBEDDING_DIMENSION}"
        )
        return _DashScopeBackend(
            api_key=api_key,
            model=settings.DASHSCOPE_EMBEDDING_MODEL,
            dimension=settings.DASHSCOPE_EMBEDDING_DIMENSION,
        )

    # 默认 gpustack
    logger.info(
        f"[EmbeddingClient] 降级 .env GPUStack："
        f"url={settings.GPUSTACK_API_URL}, "
        f"model={settings.GPUSTACK_EMBEDDING_MODEL}, "
        f"dim={settings.GPUSTACK_EMBEDDING_DIMENSION}"
    )
    return _OpenAICompatibleBackend(
        api_url=settings.GPUSTACK_API_URL,
        api_key=settings.GPUSTACK_API_KEY,
        model=settings.GPUSTACK_EMBEDDING_MODEL,
        dimension=settings.GPUSTACK_EMBEDDING_DIMENSION,
    )


class EmbeddingClient:
    """对外公共 Embedding 客户端，封装具体后端实现

    配置来源由构造参数显式决定：
        - backend + provider 注入：由 get_embedding_client(code=...) 构建（DB 模式）
        - 不传 backend：由 .env 配置构建（.env 模式），provider 取 EMBEDDING_PROVIDER
    """

    def __init__(
        self,
        backend: Optional[_BaseEmbeddingBackend] = None,
        provider: str = "",
    ):
        if backend is not None:
            self._backend: _BaseEmbeddingBackend = backend
        else:
            self._backend = _build_backend_from_env()
        self._provider = provider or (settings.EMBEDDING_PROVIDER or "gpustack").lower().strip()

    async def embed(self, text: str) -> List[float]:
        """对单条文本进行向量化，返回 embedding 向量"""
        return await self._backend.embed(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """对多条文本批量向量化，返回与输入顺序一致的 embedding 向量列表"""
        return await self._backend.embed_batch(texts)

    def embed_sync(self, text: str) -> List[float]:
        """同步单条文本向量化"""
        return self._backend.embed_batch_sync([text])[0]

    def embed_batch_sync(self, texts: List[str]) -> List[List[float]]:
        """同步批量文本向量化"""
        return self._backend.embed_batch_sync(texts)

    def refresh(self):
        """强制刷新后端配置（.env 模式单例调用；DB 模式每次新建实例天然生效）"""
        _db_config_cache.clear()
        if self._provider.startswith("db:"):
            # DB 模式：清缓存后重建当前 code 对应后端
            code = self._provider[len("db:"):]
            backend = _try_build_from_db_by_code(code)
            if backend is None:
                raise ValueError(f"刷新失败：无法通过 code={code} 重建 Embedding 后端")
            self._backend = backend
        else:
            self._backend = _build_backend_from_env()
        logger.info("[EmbeddingClient] 后端配置已刷新")

    @property
    def provider(self) -> str:
        """返回当前使用的提供商标识（DB 模式为 db:<code>，.env 模式为 provider 名）"""
        return self._provider


# 全局单例（仅用于 .env 默认模式）
_embedding_client: EmbeddingClient | None = None


def get_embedding_client(code: Optional[str] = None) -> EmbeddingClient:
    """获取 EmbeddingClient。

    配置模式二选一：
        - code 非空：DB 模式，按 code 精确选择 ai_chat_model，失败抛 ValueError（不降级）。
        - code 为空：.env 模式，复用全局单例（默认配置）。
    """
    if code:
        backend = _try_build_from_db_by_code(code)
        if backend is None:
            raise ValueError(
                f"无法通过 code={code} 构建 Embedding 后端"
                f"（请检查 ai_chat_model.code 与关联 ai_api_key 配置）"
            )
        return EmbeddingClient(backend=backend, provider=f"db:{code}")

    # 不传 code → .env 模式，复用全局单例
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client


# 向后兼容：保留直接导入 embedding_client 的引用（.env 默认模式）
def __getattr__(name: str):
    if name == "embedding_client":
        return get_embedding_client()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
