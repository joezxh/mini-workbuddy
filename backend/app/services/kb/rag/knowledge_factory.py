"""KnowledgeBase 原生装配（对齐文档 §5.5 / D10 / D19）。

``metadata_filter`` 在构造期固化（原生 search 无该参数）：租户维度强制写入，
临时筛选由调用方叠加后构造临时句柄（复用同一 store）。

生命周期：返回的 KnowledgeBase 不持有连接开关，调用方必须
``async with PgVectorStore(...)`` 覆盖所有 ``kb.*`` 调用；本模块提供
``knowledge_base(...)`` 异步上下文管理器统一托管。
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from agentscope.rag import KnowledgeBase
from sqlalchemy import select

from app.models.kb.kb_collection import KbCollection
from app.services.kb.rag.embedding_factory import EmbeddingSettings, build_embedding_model
from app.services.kb.rag.pg_vector_store import PgVectorStore


def _resolve_dimensions(session, collection_name: str, cfg: EmbeddingSettings | None) -> int:
    """维度以 kb_collection 为准；与嵌入模型不一致时由 create_collection 报错（D19）。"""
    coll = session.execute(
        select(KbCollection).where(KbCollection.name == collection_name)
    ).scalar_one_or_none()
    if coll is not None:
        return coll.dimensions
    if cfg and cfg.dimensions:
        return cfg.dimensions
    raise ValueError(f"collection {collection_name!r} 不存在且未指定嵌入维度")


@asynccontextmanager
async def knowledge_base(
    session_factory,
    *,
    collection_name: str,
    tenant_id: int,
    name: str,
    description: str = "",
    embedding_cfg: EmbeddingSettings | None = None,
    index_mode: str = "high_quality",
    metadata_filter: Optional[dict] = None,
):
    """构造并托管原生 KnowledgeBase 句柄（含 store 生命周期）。"""
    store = PgVectorStore(
        session_factory, tenant_id=tenant_id,
        dimensions=_resolve_dimensions(session_factory(), collection_name, embedding_cfg),
        index_mode=index_mode,
    )
    await store.__aenter__()
    try:
        kb = KnowledgeBase(
            name=name,
            description=description,
            embedding_model=build_embedding_model(embedding_cfg),
            vector_store=store,
            collection=collection_name,
            metadata_filter={"tenant_id": tenant_id, **(metadata_filter or {})},
        )
        yield kb
    finally:
        await store.__aexit__(None, None, None)
