"""本体驱动的检索过滤（P4.3 / P4 Task 7）。

消费 P1 预留的 ``kb_segment.class_uris``（JSONB，切片摄取时写入的本体类归属），
把「按本体类检索」接进查询链路：

1. **后代扩展**：用户选父类（如「贷款」）时，子类（如「房贷」）的切片也应命中
   —— ``expand_with_descendants`` 沿 ``ontology_class.parent_uris`` 向下遍历，
   把选中类扩展为「选中类 + 全部后代类」。环路安全（visited + 深度上限）。
2. **组合入口**：``OntologyDrivenRetriever`` 把扩展后的 URI 列表交给
   ``KbRetrievalService``（JSONB ``?|`` OR 语义过滤），向量与混合检索都支持。

依赖方向：ontology → kb（本体层消费知识库检索），kb 不反向依赖 ontology。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ontology.ontology import OntologyClass
from app.services.kb.retrieval_service import KbRetrievalService

# 层级遍历深度上限：防御脏数据成环时的过度展开
_MAX_HIERARCHY_DEPTH = 10


def expand_with_descendants(
    db: Session,
    tenant_id: int,
    ontology_id: int,
    class_uris: Optional[List[str]],
    max_depth: int = _MAX_HIERARCHY_DEPTH,
) -> Optional[List[str]]:
    """把选中的类 URI 扩展为「选中类 + 全部后代类 URI」。

    空列表/None 返回 None（与「不过滤」语义一致）；悬空父类引用安全跳过。
    """
    if not class_uris:
        return None

    selected: List[str] = [u for u in dict.fromkeys(class_uris) if u]
    if not selected:
        return None

    # 类目量级有限（几百以内），全量载入做图遍历即可
    rows = db.execute(
        select(OntologyClass.uri, OntologyClass.parent_uris).where(
            OntologyClass.tenant_id == tenant_id,
            OntologyClass.ontology_id == ontology_id,
            OntologyClass.status == "active",
        )
    ).all()

    # parent_uri -> [child_uri, ...]
    children: Dict[str, List[str]] = {}
    for uri, parents in rows:
        for parent in parents or []:
            children.setdefault(parent, []).append(uri)

    result: List[str] = list(selected)
    seen: Set[str] = set(selected)
    frontier: List[str] = list(selected)
    depth = 0
    while frontier and depth < max_depth:
        nxt: List[str] = []
        for uri in frontier:
            for child in children.get(uri, []):
                if child not in seen:
                    seen.add(child)
                    nxt.append(child)
                    result.append(child)
        frontier = nxt
        depth += 1
    return result


class OntologyDrivenRetriever:
    """组合入口：本体类后代扩展 + KB 检索（纯向量 / 中文混合）。

    用法::

        retriever = OntologyDrivenRetriever(
            db, KbRetrievalService.from_session(db, tenant_id))
        hits = retriever.search_by_text(
            collection, "逾期贷款处置", tenant_id=100, ontology_id=oid,
            class_uris=["http://onto/Loan"], hybrid=True)
    """

    def __init__(self, db: Session, retrieval: KbRetrievalService) -> None:
        self.db = db
        self.retrieval = retrieval

    def resolve_scope(
        self,
        tenant_id: int,
        ontology_id: Optional[int],
        class_uris: Optional[List[str]],
    ) -> Optional[List[str]]:
        """解析检索范围：扩展后代类；不选类时返回 None（不过滤）。

        传了 ``class_uris`` 却缺 ``ontology_id`` 时显式报错（不静默全量放行）。
        """
        if not class_uris:
            return None
        if ontology_id is None:
            raise ValueError("按本体类检索必须提供 ontology_id")
        return expand_with_descendants(self.db, tenant_id, ontology_id, class_uris)

    def search_by_text(
        self,
        collection: str,
        query_text: str,
        tenant_id: int,
        ontology_id: Optional[int] = None,
        class_uris: Optional[List[str]] = None,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
        hybrid: bool = False,
    ):
        """本体驱动的文本检索；``hybrid=True`` 走中文混合检索（pg_trgm + RRF）。"""
        scope = self.resolve_scope(tenant_id, ontology_id, class_uris)
        if hybrid:
            return self.retrieval.hybrid_search_by_text(
                collection, query_text, top_k, score_threshold, class_uris=scope
            )
        return self.retrieval.search_by_text(
            collection, query_text, top_k, score_threshold, class_uris=scope
        )

    def search_by_vector(
        self,
        collection: str,
        query_vector: List[float],
        tenant_id: int,
        ontology_id: Optional[int] = None,
        class_uris: Optional[List[str]] = None,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
    ):
        """本体驱动的向量检索（查询已向量化）。"""
        scope = self.resolve_scope(tenant_id, ontology_id, class_uris)
        return self.retrieval.search_by_vector(
            collection, query_vector, top_k, score_threshold, class_uris=scope
        )
