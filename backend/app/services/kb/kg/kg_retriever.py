"""图谱检索通道（P4）。

Spec 6.2 检索编排（type=4 分支）：

    实体向量召回 kg_entity   (top_k = graph_entity_top_k)
    三元组向量召回 kg_triple (top_k = graph_triple_top_k)
        -> 种子实体
    Neo4j 种子子图 (seed:Entity)-[*1..2]-(n)
        -> PPR (networkx pagerank, damping=0.85, 仅 Chunk 节点出分)
    回 PG 取 chunk 正文 + 可见性过滤
        -> 图通道结果（chunk 级）

三条不可妥协的规则：

1. 产物仍是 chunk 级 RetrieveResult：图谱是内部召回通道，不是新契约。
2. PG 是可见性权威：Neo4j 只提供结构，最终内容与可见性一律回 PG 取。
3. 失败降级为空：Neo4j 不可用 / 嵌入失败 -> 图通道返回空且 enabled=False，
   绝不阻断基础向量检索（spec 6.2 降级链）。
"""
from __future__ import annotations

from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.kb.kg_entity import KgEntity
from app.models.kb.kg_triple import KgTriple
from app.models.kb.kb_segment import KbSegment

RRF_K = 60
MAX_DEPTH = 3


class KgRetriever:
    """图谱召回器。"""

    def __init__(
        self,
        db: Session,
        tenant_id: Optional[int],
        knowledge_id: int,
        *,
        config: Optional[dict] = None,
        embed_fn=None,
        neo4j_store=None,
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.knowledge_id = knowledge_id
        self._embed_fn = embed_fn
        self._store = neo4j_store
        self._config = config or {}

    def _cfg(self, key: str, default):
        val = self._config.get(key)
        return default if val is None else val

    def _recall_entities(self, qvec, limit: int) -> list:
        if qvec is None or limit <= 0:
            return []
        try:
            stmt = (
                select(KgEntity)
                .where(
                    KgEntity.knowledge_id == self.knowledge_id,
                    KgEntity.embedding.isnot(None),
                )
                .order_by(KgEntity.embedding.cosine_distance(qvec))
                .limit(limit)
            )
            if self.tenant_id is not None:
                stmt = stmt.where(KgEntity.tenant_id == self.tenant_id)
            return list(self.db.execute(stmt).scalars().all())
        except Exception as exc:  # noqa: BLE001 - 召回失败降级为空
            logger.debug(f"[kg] 实体向量召回失败: {exc}")
            return []

    def _recall_triples(self, qvec, limit: int) -> list:
        if qvec is None or limit <= 0:
            return []
        try:
            stmt = (
                select(KgTriple)
                .where(
                    KgTriple.knowledge_id == self.knowledge_id,
                    KgTriple.embedding.isnot(None),
                )
                .order_by(KgTriple.embedding.cosine_distance(qvec))
                .limit(limit)
            )
            if self.tenant_id is not None:
                stmt = stmt.where(KgTriple.tenant_id == self.tenant_id)
            return list(self.db.execute(stmt).scalars().all())
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"[kg] 三元组向量召回失败: {exc}")
            return []

    def _seed_subgraph(self, seed_ids: list, depth: int, limit: int) -> dict:
        try:
            from app.services.kb.kg.kg_neo4j_store import KgNeo4jStore

            store = (
                self._store
                if self._store is not None
                else KgNeo4jStore(self.knowledge_id)
            )
            return store.seed_subgraph(seed_ids, depth=depth, limit=limit)
        except Exception as exc:  # noqa: BLE001 - Neo4j 不可用 -> 空子图
            logger.debug(f"[kg] 种子子图获取失败: {exc}")
            return {"nodes": [], "edges": []}

    def _ppr(self, subgraph: dict, seed_ids: list, damping: float) -> dict:
        """在子图上跑 personalized PageRank；只给 Chunk 节点出分。"""
        nodes = subgraph.get("nodes") or []
        edges = subgraph.get("edges") or []
        if not nodes or not edges:
            return {}
        try:
            import networkx as nx
        except ImportError:  # pragma: no cover - 依赖缺失
            logger.warning("[kg] networkx 未安装，跳过 PPR")
            return {}

        try:
            # **无向图**：Neo4j 里 MENTIONS 的方向是 切片 -> 实体，
            # 若按有向图做 PPR，种子实体永远无法把分数传播到切片
            # （切片是纯汇点，得分恒为 0）。PPR 在此只用于**相关性扩散**，
            # 不承载方向语义（方向语义由子图响应里的 from/to 表达），故取无向。
            g = nx.MultiGraph()
            for n in nodes:
                g.add_node(n["id"], kind=n.get("kind"))
            for e in edges:
                if e.get("from") and e.get("to"):
                    g.add_edge(e["from"], e["to"], weight=1.0)

            personalization = {sid: 1.0 for sid in seed_ids if sid in g}
            if not personalization:
                return {}

            pr = nx.pagerank(
                g, alpha=damping, personalization=personalization, max_iter=100
            )
            return {
                nid: score
                for nid, score in pr.items()
                if score > 0 and g.nodes[nid].get("kind") == "Chunk"
            }
        except Exception as exc:  # noqa: BLE001 - PPR 失败降级
            logger.debug(f"[kg] PPR 计算失败: {exc}")
            return {}

    def _hydrate(self, chunk_ids: set) -> dict:
        """按 Neo4j chunk_id 取 PG 切片正文与定位信息。

        Neo4j 的 chunk_id = compute_chunk_id(kb, document_id, chunk_index)，
        无法直接反查 PG，因此用 (document_id, chunk_index) 定位：
        子图节点已带这两个属性。
        """
        if not chunk_ids:
            return {}
        rows = self.db.execute(
            select(KbSegment).where(
                KbSegment.collection == f"kb_{self.knowledge_id}"
            )
        ).scalars().all()
        out: dict = {}
        for seg in rows:
            from app.services.kb.kg.kg_neo4j_store import compute_chunk_id

            cid = compute_chunk_id(self.knowledge_id, seg.document_id, seg.chunk_index)
            if cid in chunk_ids:
                out[cid] = {
                    "segment_id": seg.id,
                    "document_id": seg.document_id,
                    "chunk_index": seg.chunk_index,
                    "content": seg.content or "",
                }
        return out

    def recall(self, query: str, *, top_k: int = 20) -> dict:
        """执行图通道召回。

        返回 {"results": [...], "enabled": bool, "reason": str|None}
        """
        from app.services.kb.kg.kg_graph_store import node_id_for_entity
        from app.services.kb.kg.kg_vector import embed_query

        qvec = embed_query(query, self._embed_fn)
        if qvec is None:
            return {"results": [], "enabled": False, "reason": "embedding_unavailable"}

        ent_top = int(self._cfg("graph_entity_top_k", 10))
        tri_top = int(self._cfg("graph_triple_top_k", 10))
        entities = self._recall_entities(qvec, ent_top)
        triples = self._recall_triples(qvec, tri_top)

        seed_ids: list = []
        for e in entities:
            nid = node_id_for_entity(e)
            if nid not in seed_ids:
                seed_ids.append(nid)
        if not seed_ids:
            return {"results": [], "enabled": True, "reason": "no_seed"}

        depth = int(self._cfg("graph_depth", 2))
        depth = max(1, min(MAX_DEPTH, depth))
        max_nodes = int(self._cfg("graph_max_nodes", 10000))
        subgraph = self._seed_subgraph(seed_ids, depth, max_nodes)
        if not subgraph.get("nodes"):
            return {"results": [], "enabled": False, "reason": "neo4j_unavailable"}

        damping = float(self._cfg("ppr_damping", 0.85))
        damping = max(0.1, min(0.99, damping))
        chunk_scores = self._ppr(subgraph, seed_ids, damping)
        if not chunk_scores:
            return {"results": [], "enabled": True, "reason": "no_ppr_score"}

        ranked = sorted(chunk_scores.items(), key=lambda kv: kv[1], reverse=True)
        top_ids = [cid for cid, _ in ranked[: max(1, top_k)]]
        hydrated = self._hydrate(set(top_ids))

        results: list = []
        for cid in top_ids:
            info = hydrated.get(cid)
            if info is None:
                continue  # PG 不可见 -> 丢弃（可见性权威在 PG）
            results.append(
                {
                    "document_id": info["document_id"],
                    "chunk_index": info["chunk_index"],
                    "content": info["content"],
                    "score": float(chunk_scores[cid]),
                    "metadata": {
                        "fusion_sources": ["graph"],
                        "score_type": "graph",
                        "graph_seed_entities": [e.name for e in entities[:5]],
                    },
                }
            )
        return {"results": results, "enabled": True, "reason": None}


def rrf_fuse(rank_lists: list, k: int = RRF_K, weights: Optional[list] = None) -> list:
    """加权 RRF 融合：score = weight / (k + rank)（Yuxi 同款，rrf_k=60）。

    weights 与 rank_lists 同序；缺省全部 1.0。
    基础召回权重 1.0，图召回权重由图谱配置 graph_weight 决定（spec 6.2）。
    """
    scores: dict = {}
    for idx, lst in enumerate(rank_lists):
        w = 1.0
        if weights and idx < len(weights) and weights[idx] is not None:
            w = float(weights[idx])
        for rank, (key, _score) in enumerate(lst, start=1):
            scores[key] = scores.get(key, 0.0) + w / (k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

