"""图谱检索通道测试（P4）：向量召回 -> 种子子图 -> PPR -> 回溯过滤 -> 降级。"""
import pytest

from app.config import settings
from app.models.kb.kg_entity import KgEntity
from app.models.kb.kb_segment import KbSegment
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.services.kb.kg import kg_retriever
from app.services.kb.kg.kg_neo4j_store import compute_chunk_id
from tests.kb.conftest import TENANT_A

DIM = settings.EMBEDDING_DIMENSION


@pytest.fixture
def kb(db):
    obj = WikiKnowledge(name="图谱库", slug="kg-ret-1", type=4, tenant_id=TENANT_A)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def _vec():
    return [0.1] * DIM


def _entity(db, kb, name="星海科技", key="客户:1001", label="CUS", with_vec=True):
    e = KgEntity(
        tenant_id=TENANT_A, knowledge_id=kb.id, collection=f"kb_{kb.id}",
        entity_key=key, name=name, type_code=label, status="active",
        embedding=_vec() if with_vec else None,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _segment(db, kb, doc_uuid="doc-1", index=0, content="星海科技下单内容"):
    seg = KbSegment(
        collection=f"kb_{kb.id}", document_id=doc_uuid, chunk_index=index,
        content=content, tenant_id=TENANT_A,
    )
    db.add(seg)
    db.commit()
    db.refresh(seg)
    return seg


class FakeStore:
    """假 Neo4j store：返回预置子图。"""

    def __init__(self, subgraph=None, boom=False):
        self.subgraph = subgraph or {"nodes": [], "edges": []}
        self.boom = boom
        self.calls = []

    def seed_subgraph(self, seed_ids, depth=2, limit=1000):
        self.calls.append({"seeds": list(seed_ids), "depth": depth, "limit": limit})
        if self.boom:
            raise RuntimeError("neo4j down")
        return self.subgraph


def _subgraph_with_chunk(kb, seg, entity):
    """构造「切片 -MENTIONS-> 实体」的子图。"""
    from app.services.kb.kg.kg_graph_store import node_id_for_entity

    eid = node_id_for_entity(entity)
    cid = compute_chunk_id(kb.id, seg.document_id, seg.chunk_index)
    return {
        "nodes": [
            {"id": eid, "name": entity.name, "label": entity.type_code, "kind": "Entity"},
            {"id": cid, "name": "切片", "label": "Chunk", "kind": "Chunk",
             "document_id": seg.document_id, "chunk_index": seg.chunk_index},
        ],
        "edges": [
            {"id": "m1", "from": cid, "to": eid, "relation_type": "MENTIONS"},
        ],
    }

# ── RRF ─────────────────────────────────────────────────────────────────
def test_rrf_fuse_orders_by_reciprocal_rank():
    out = kg_retriever.rrf_fuse([[("a", 0.9), ("b", 0.5)], [("b", 0.8)]])
    assert out[0][0] == "b", "两路都命中的应排前"


def test_rrf_fuse_respects_weights():
    base = [("a", 1.0)]
    graph = [("b", 1.0)]
    heavy_graph = kg_retriever.rrf_fuse([base, graph], weights=[1.0, 5.0])
    heavy_base = kg_retriever.rrf_fuse([base, graph], weights=[1.0, 0.1])
    assert heavy_graph[0][0] == "b"
    assert heavy_base[0][0] == "a"


def test_rrf_fuse_single_source_keeps_order():
    out = kg_retriever.rrf_fuse([[("a", 0.9), ("b", 0.5)]])
    assert [k for k, _ in out] == ["a", "b"]


# ── 检索器 ───────────────────────────────────────────────────────────────
def test_recall_returns_chunk_level_results(db, kb):
    seg = _segment(db, kb)
    ent = _entity(db, kb)
    store = FakeStore(_subgraph_with_chunk(kb, seg, ent))

    r = kg_retriever.KgRetriever(
        db, TENANT_A, kb.id, embed_fn=lambda t: [_vec()], neo4j_store=store
    )
    out = r.recall("星海科技")

    assert out["enabled"] is True
    assert out["results"], "图通道必须产出 chunk 级结果"
    hit = out["results"][0]
    assert hit["document_id"] == seg.document_id
    assert hit["chunk_index"] == seg.chunk_index
    assert hit["content"] == seg.content
    assert hit["metadata"]["fusion_sources"] == ["graph"]
    assert hit["metadata"]["score_type"] == "graph"


def test_recall_uses_seed_entities(db, kb):
    seg = _segment(db, kb)
    ent = _entity(db, kb)
    store = FakeStore(_subgraph_with_chunk(kb, seg, ent))

    kg_retriever.KgRetriever(
        db, TENANT_A, kb.id, embed_fn=lambda t: [_vec()], neo4j_store=store
    ).recall("星海科技")

    assert store.calls and store.calls[0]["seeds"], "必须用实体作为种子"
    assert store.calls[0]["depth"] <= 3, "跳数硬封顶 3"


def test_recall_drops_chunks_invisible_in_pg(db, kb):
    """PG 是可见性权威：子图里有、PG 里没有的切片必须丢弃。"""
    seg = _segment(db, kb, doc_uuid="doc-1", index=0)
    ent = _entity(db, kb)
    fake = _subgraph_with_chunk(kb, seg, ent)
    fake["nodes"][1]["id"] = "unknown-chunk-id"  # PG 侧查不到
    store = FakeStore(fake)

    out = kg_retriever.KgRetriever(
        db, TENANT_A, kb.id, embed_fn=lambda t: [_vec()], neo4j_store=store
    ).recall("星海科技")
    assert out["results"] == []


def test_recall_degrades_when_neo4j_down(db, kb):
    _entity(db, kb)
    store = FakeStore(boom=True)
    out = kg_retriever.KgRetriever(
        db, TENANT_A, kb.id, embed_fn=lambda t: [_vec()], neo4j_store=store
    ).recall("星海科技")
    assert out["enabled"] is False
    assert out["results"] == []
    assert out["reason"] == "neo4j_unavailable"


def test_recall_degrades_when_embedding_unavailable(db, kb):
    _entity(db, kb)

    def boom(texts):
        raise RuntimeError("embed service down")

    out = kg_retriever.KgRetriever(
        db, TENANT_A, kb.id, embed_fn=boom, neo4j_store=FakeStore()
    ).recall("星海科技")
    assert out["enabled"] is False
    assert out["reason"] == "embedding_unavailable"


def test_recall_without_vector_entities_returns_no_seed(db, kb):
    _entity(db, kb, with_vec=False)
    out = kg_retriever.KgRetriever(
        db, TENANT_A, kb.id, embed_fn=lambda t: [_vec()], neo4j_store=FakeStore()
    ).recall("星海科技")
    assert out["enabled"] is True
    assert out["reason"] == "no_seed"
    assert out["results"] == []
