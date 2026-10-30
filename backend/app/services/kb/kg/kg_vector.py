"""图谱向量助手（P4）：与 kb 段向量同模型同空间的嵌入入口。

实体/三元组向量必须与 kms_segment.embedding 用同一个 embedding 模型与维度，
否则检索融合时两路向量不可比（R5：严禁另起一套 embedder）。
构建阶段（P3）与检索阶段（P4）都要嵌入，抽成一处避免实现漂移。

embed_fn 是测试注入点（同步：texts -> 向量列表），与 kb 既有
index_mode._embed_texts / segment_service._embed_one 的约定一致。
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence

from app.config import settings


def embed_texts(
    texts: Sequence[str], embed_fn: Optional[Callable] = None
) -> list[list[float]]:
    """批量嵌入文本，返回与输入等长的向量列表。

    embed_fn 为测试注入点；None 时走 kb 的 build_embedding_model。
    """
    items = list(texts)
    if not items:
        return []
    if embed_fn is not None:
        return embed_fn(items)

    import asyncio

    from app.services.kb.rag.embedding_factory import build_embedding_model

    model = build_embedding_model(None)

    async def _run(batch: list[str]):
        resp = await model(batch)
        return list(resp.embeddings)

    return asyncio.run(_run(items))


def embed_query(text: str, embed_fn: Optional[Callable] = None) -> Optional[list[float]]:
    """嵌入单条查询；失败返回 None（调用方据此降级，不抛错）。"""
    try:
        vecs = embed_texts([text], embed_fn)
    except Exception:  # noqa: BLE001 - 嵌入服务不可达 -> 降级为不启用图通道
        return None
    return vecs[0] if vecs else None


def fit_vector(vector: Optional[Sequence[float]]) -> Optional[list[float]]:
    """把向量适配到生效维度（过长截断 / 过短补零）。"""
    from app.services.kb.vector_utils import fit_vector_dimension

    if vector is None:
        return None
    return fit_vector_dimension(vector, settings.EMBEDDING_DIMENSION)
