"""VectorStore 抽象层 + InMemory 实现。

设计:
- BaseVectorStore: 抽象基类, 跨 collection upsert/search/delete
- InMemoryVectorStore: 测试 / 本地开发用, 余弦相似度
- 后续 Phase 2.x 接入 PGVectorStore (直接读写 legal_info.full_text_vector 等 pgvector 列)
"""
from __future__ import annotations
import math
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseVectorStore(ABC):
    """向量库抽象基类。"""

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        id: str,
        vector: List[float],
        metadata: Dict[str, Any],
    ) -> None: ...

    @abstractmethod
    async def search(
        self,
        collection: str,
        query_vector: List[float],
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def delete(self, collection: str, id: str) -> bool: ...


def _cosine(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"dim mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-12
    nb = math.sqrt(sum(y * y for y in b)) or 1e-12
    return dot / (na * nb)


class InMemoryVectorStore(BaseVectorStore):
    """进程内向量库 - 测试与本地开发用。生产请使用 PGVectorStore。"""

    def __init__(self) -> None:
        self._data: Dict[str, List[Dict[str, Any]]] = {}

    async def upsert(
        self,
        collection: str,
        id: str,
        vector: List[float],
        metadata: Dict[str, Any],
    ) -> None:
        items = self._data.setdefault(collection, [])
        for it in items:
            if it["id"] == id:
                it["vector"] = list(vector)
                it["metadata"] = dict(metadata)
                return
        items.append({"id": id, "vector": list(vector), "metadata": dict(metadata)})

    async def search(
        self,
        collection: str,
        query_vector: List[float],
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        items = list(self._data.get(collection, []))
        if filter:
            items = [it for it in items if all(it["metadata"].get(k) == v for k, v in filter.items())]
        scored = [
            {
                "id": it["id"],
                "score": _cosine(it["vector"], query_vector),
                "metadata": it["metadata"],
            }
            for it in items
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[: max(0, top_k)]

    async def delete(self, collection: str, id: str) -> bool:
        items = self._data.get(collection, [])
        for i, it in enumerate(items):
            if it["id"] == id:
                items.pop(i)
                return True
        return False