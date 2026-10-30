"""Neo4j 投影层契约测试（P2）。

不连真实 Neo4j：注入假 session 工厂，断言「Cypher 形状 + 参数 + 结果归一化」，
重点覆盖三件不可妥协的事：**label 隔离**、**幂等 MERGE**、**可完整撤销**。
"""
import pytest

from app.services.kb.kg import kg_neo4j_store as store


class FakeResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def __iter__(self):
        return iter(self._rows)

    def single(self):
        return self._rows[0] if self._rows else None


class FakeSession:
    def __init__(self, recorder, rows=None):
        self.recorder = recorder
        self.rows = rows or []

    def run(self, query, **params):
        self.recorder.append((query, params))
        return FakeResult(self.rows)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeNode:
    def __init__(self, props, labels):
        self._properties = props
        self.labels = labels


class FakeRel:
    def __init__(self, props, rtype, start, end):
        self._properties = props
        self.type = rtype
        self.start_node = start
        self.end_node = end


def _recorder():
    calls: list = []
    factory = lambda: FakeSession(calls)  # noqa: E731
    return calls, factory


# ── label 校验（防注入）─────────────────────────────────────────────────
def test_safe_label_accepts_positive_int():
    assert store.safe_neo4j_label(12) == "mwb_kb_12"


def test_safe_label_rejects_injection():
    for bad in ["mwb_kb_1] MATCH (n) DETACH DELETE n //", "1; DROP", None, "abc"]:
        with pytest.raises((ValueError, TypeError)):
            store.safe_neo4j_label(bad)


def test_safe_label_rejects_non_positive():
    for bad in [0, -1]:
        with pytest.raises(ValueError):
            store.safe_neo4j_label(bad)


# ── 稳定 ID ─────────────────────────────────────────────────────────────
def test_ids_are_deterministic_and_distinct():
    a = store.compute_entity_id(1, "星海科技", "客户")
    b = store.compute_entity_id(1, "星海科技", "客户")
    c = store.compute_entity_id(1, "星海科技", "供应商")
    d = store.compute_entity_id(2, "星海科技", "客户")
    assert a == b and len(a) == 32
    assert a != c and a != d


def test_triple_and_chunk_ids():
    t1 = store.compute_triple_id(1, "e1", "PLACES", "e2")
    t2 = store.compute_triple_id(1, "e1", "PLACES", "e3")
    assert t1 != t2
    assert store.compute_chunk_id(1, "doc-1", 0) != store.compute_chunk_id(1, "doc-1", 1)


# ── 写入：label 隔离 + 幂等 MERGE ────────────────────────────────────────
def test_entity_upsert_uses_kb_specific_label():
    calls, factory = _recorder()
    s = store.KgNeo4jStore(7, session_factory=factory)
    s.upsert_entity(
        entity_id="eid1", name="星海", label="客户", normalized_name="星海"
    )
    query, params = calls[0]
    # 三段式 label：:Entity + MwbKG + 每库 label
    assert ":Entity:MwbKG:`mwb_kb_7`" in query
    assert "MERGE" in query
    assert params["entity_id"] == "eid1"
    assert params["kb_id"] == 7
    assert params["label"] == "客户"


def test_entity_upsert_is_idempotent_same_query():
    """重复投影同一实体：查询串与参数完全一致 → MERGE 幂等，不产生重复节点。"""
    calls, factory = _recorder()
    s = store.KgNeo4jStore(7, session_factory=factory)
    kwargs = dict(entity_id="eid1", name="星海", label="客户", normalized_name="星海")
    s.upsert_entity(**kwargs)
    s.upsert_entity(**kwargs)
    assert calls[0] == calls[1]


def test_cross_kb_labels_are_isolated():
    calls, factory = _recorder()
    store.KgNeo4jStore(7, session_factory=factory).upsert_entity(
        entity_id="e", name="n", label="l", normalized_name="n"
    )
    store.KgNeo4jStore(8, session_factory=factory).upsert_entity(
        entity_id="e", name="n", label="l", normalized_name="n"
    )
    assert "mwb_kb_7" in calls[0][0]
    assert "mwb_kb_8" in calls[1][0]
    assert "mwb_kb_8" not in calls[0][0]


def test_relation_upsert_carries_semantic_type_as_property():
    calls, factory = _recorder()
    s = store.KgNeo4jStore(7, session_factory=factory)
    s.upsert_relation(
        triple_id="t1", src_entity_id="e1", tgt_entity_id="e2",
        relation_type="PLACES", extractor_type="llm",
    )
    query, params = calls[0]
    # 关系类型名固定为 RELATION，语义类型走属性（Yuxi 约定）
    assert ":RELATION" in query and "MENTIONS" not in query
    assert params["relation_type"] == "PLACES"
    assert params["triple_id"] == "t1"


def test_mention_upsert_links_chunk_to_entity():
    calls, factory = _recorder()
    s = store.KgNeo4jStore(7, session_factory=factory)
    s.upsert_mention(chunk_id="c1", entity_id="e1", document_id="doc-1")
    query, params = calls[0]
    assert "MENTIONS" in query
    assert params["chunk_id"] == "c1" and params["entity_id"] == "e1"


def test_delete_kb_is_scoped_and_detachable():
    calls, factory = _recorder()
    s = store.KgNeo4jStore(9, session_factory=factory)
    s.delete_kb()
    query = calls[0][0].strip()
    assert query.startswith("MATCH (n:MwbKG:`mwb_kb_9`)")
    assert "DETACH DELETE" in query


def test_delete_empty_ids_is_noop():
    calls, factory = _recorder()
    s = store.KgNeo4jStore(9, session_factory=factory)
    s.delete_entities([])
    s.delete_chunks([])
    assert calls == []


# ── 读取：子图归一化 / 跳数封顶 / 路径 ────────────────────────────────────
def test_seed_subgraph_normalizes_nodes_and_edges():
    node_a = FakeNode({"entity_id": "e1", "name": "星海", "label": "客户"}, ["Entity"])
    node_b = FakeNode({"entity_id": "e2", "name": "订单", "label": "订单"}, ["Entity"])
    rel = FakeRel({"triple_id": "t1", "type": "PLACES"}, "RELATION", node_a, node_b)
    rows = [{"nodes": [node_a, node_b], "relationships": [rel]}]

    calls, factory = _recorder()
    calls.append(None)  # 占位，避免空录
    s = store.KgNeo4jStore(7, session_factory=lambda: FakeSession(calls, rows))
    out = s.seed_subgraph(["e1"], depth=2, limit=100)

    assert {n["id"] for n in out["nodes"]} == {"e1", "e2"}
    assert out["edges"][0]["from"] == "e1"
    assert out["edges"][0]["to"] == "e2"
    assert out["edges"][0]["relation_type"] == "PLACES"


def test_seed_subgraph_clamps_depth_to_three():
    calls, factory = _recorder()
    s = store.KgNeo4jStore(7, session_factory=factory)
    s.seed_subgraph(["e1"], depth=99)
    assert calls[0][1]["depth"] == 3


def test_seed_subgraph_empty_seeds_short_circuits():
    calls, factory = _recorder()
    s = store.KgNeo4jStore(7, session_factory=factory)
    assert s.seed_subgraph([]) == {"nodes": [], "edges": []}
    assert calls == []


def test_subgraph_falls_back_when_apoc_missing():
    """apoc 不可用时退回等价展开模板，而不是把异常抛给检索链路。"""
    calls: list = []

    class BoomSession(FakeSession):
        def run(self, query, **params):
            calls.append((query, params))
            if "apoc" in query:
                raise RuntimeError("apoc not installed")
            return FakeResult([])

    s = store.KgNeo4jStore(7, session_factory=lambda: BoomSession(calls))
    out = s.seed_subgraph(["e1"], depth=1)
    assert out == {"nodes": [], "edges": []}
    assert any("apoc" in q for q, _ in calls)
    assert any("apoc" not in q for q, _ in calls)


def test_paths_returns_normalized_sequence():
    node_a = FakeNode({"entity_id": "e1", "name": "A", "label": "X"}, ["Entity"])
    node_b = FakeNode({"entity_id": "e2", "name": "B", "label": "X"}, ["Entity"])
    rel = FakeRel({"triple_id": "t1", "type": "OWNS"}, "RELATION", node_a, node_b)
    path = type("P", (), {"nodes": [node_a, node_b], "relationships": [rel]})()

    calls: list = []
    s = store.KgNeo4jStore(7, session_factory=lambda: FakeSession(calls, [{"p": path}]))
    out = s.paths("e1", "e2")
    assert out and out[0]["edges"][0]["relation_type"] == "OWNS"


def test_stats_never_raises_when_unavailable():
    class Dead:
        def session(self):
            raise store.KgNeo4jUnavailable("down")

    calls: list = []
    s = store.KgNeo4jStore(7, session_factory=lambda: FakeSession(calls))
    s._session_factory = lambda: (_ for _ in ()).throw(store.KgNeo4jUnavailable("down"))
    assert s.stats() == {}
