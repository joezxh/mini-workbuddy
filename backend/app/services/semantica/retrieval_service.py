"""语义检索 / 概念过滤桥接（替代旧 ``ontology.search_filter`` 的 OntologyDrivenRetriever）。

旧实现靠 kb_segment.class_uris 做本体类层级扩展 + 向量过滤；新实现直接委托
semantica 的 pgvector 存储，按概念/类 URI 做 metadata 过滤。依赖方向保持单向：
semantica 层可消费上层检索，不被反向依赖。
"""
from __future__ import annotations

from typing import Any, List, Optional

from app.config import settings
from .client import SemanticaClient
from .scope import TenantScope


class SemanticRetriever:
    """基于 semantica pgvector 的语义检索入口。"""

    def __init__(self, scope: Optional[TenantScope] = None) -> None:
        self.scope = scope or TenantScope(tenant_id=0)
        self.client = SemanticaClient(scope=self.scope)

    def search_by_vector(
        self,
        query_vector: List[float],
        *,
        top_k: int = 10,
        concept_uris: Optional[List[str]] = None,
        kind: str = "entity",
    ) -> List[dict]:
        """向量检索；``concept_uris`` 非空时按类/概念 URI 过滤（metadata ``class_uri``）。"""
        store = self.client.vector_store(kind)
        meta_filter = None
        if concept_uris:
            meta_filter = {"class_uri": {"$in": list(concept_uris)}}
        return store.search(query_vector, top_k=top_k, filter=meta_filter)

    def upsert(
        self,
        vectors: List[List[float]],
        *,
        metadata: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        kind: str = "entity",
    ) -> List[str]:
        """写入/更新向量（metadata 可携带 ``class_uri`` 供检索时过滤）。"""
        store = self.client.vector_store(kind)
        return store.add(vectors, metadata=metadata, ids=ids)
