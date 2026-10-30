"""PG → Neo4j 投影编排与 CRUD 接入测试（P2）。

覆盖三件事：
1. 业务映射正确（PG 行 → 确定性节点/边 ID）
2. 手工 CRUD 会触发投影，且**撤销完整**（delete 走 unproject）
3. **best-effort 降级**：Neo4j 抛错时 PG 事实写入照常成功（不阻断）
"""
import pytest

from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.services.kb.kg import kg_graph_store, kg_neo4j_store
from tests.kb.conftest import TENANT_A


class FakeStore:
    """记录调用的假投影 store（接口与 KgNeo4jStore 的写入面一致）。"""

    def __init__(self, kb_id, fail=False):
        self.kb_id = kb_id
        self.fail = fail
        self.entities = []
        self.relations = []
        self.chunks = []
        self.mentions = []
        self.deleted_entities = []
        self.deleted_relations = []
        self.deleted_chunks = []
        self.deleted_kb = 0

    def _boom(self):
        if self.fail:
            raise kg_neo4j_store.KgNeo4jUnavailable("fake down")

    def upsert_entity(self, **kw):
        self._boom()
        self.entities.append(kw)

    def upsert_relation(self, **kw):
        self._boom()
        self.relations.append(kw)

    def upsert_chunk(self, **kw):
        self._boom()
        self.chunks.append(kw)

    def upsert_mention(self, **kw):
        self._boom()
        self.mentions.append(kw)

    def delete_entities(self, ids):
        self._boom()
        self.deleted_entities.extend(ids)

    def delete_relations(self, ids, **kw):
        self._boom()
        self.deleted_relations.extend(ids)

    def delete_chunks(self, ids):
        self._boom()
        self.deleted_chunks.extend(ids)

    def delete_kb(self):
        self._boom()
        self.deleted_kb += 1

    def stats(self):
        return {"Entity": len(self.entities)}


@pytest.fixture
def kb(db):
    obj = WikiKnowledge(name="图谱库", slug="kg-proj-1", type=4, tenant_id=TENANT_A)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@pytest.fixture
def fake(monkeypatch, kb):
    """把 KgNeo4jStore 替换为假实现，并捕获实例以便断言。"""
    created = {}

    def factory(kb_id, **kwargs):
        # 共享单个实例：一次业务操作内多次取 store 应命中同一投影目标，
        # 断言才与真实语义一致（否则每次调用都新建，无法观测累计写入）
        if "store" not in created:
            created["store"] = FakeStore(kb_id)
        return created["store"]

    monkeypatch.setattr(kg_neo4j_store, "KgNeo4jStore", factory)
    # kg_graph_store 已 from ... import KgNeo4jStore，需替换其模块内引用
    monkeypatch.setattr(kg_graph_store, "KgNeo4jStore", factory)
    return created


@pytest.fixture
def svc(db, kb):
    from app.services.kb.kg.kg_service import KgService

    return KgService(db, tenant_id=TENANT_A, knowledge_id=kb.id)


# ── 业务映射 ─────────────────────────────────────────────────────────────
def test_entity_node_id_is_deterministic(db, kb, svc):
    e = svc.create_entity(name="星海科技", type_code="CUS")
    n1 = kg_graph_store.node_id_for_entity(e)
    n2 = kg_graph_store.node_id_for_entity(e)
    assert n1 == n2 and len(n1) == 32


def test_entity_node_id_differs_across_kb_and_type(db, kb, svc):
    e1 = svc.create_entity(name="星海科技", type_code="CUS")
    e2 = svc.create_entity(name="星海科技", type_code="SUP")
    assert kg_graph_store.node_id_for_entity(e1) != kg_graph_store.node_id_for_entity(e2)


def test_relation_id_uses_endpoint_node_ids(db, kb, svc):
    a = svc.create_entity(name="星海科技", type_code="CUS")
    b = svc.create_entity(name="订单B1", type_code="ORD")
    t = svc.create_triple(from_entity_id=a.id, to_entity_id=b.id,
                          relation_code="PLACES")
    rid = kg_graph_store.relation_id_for(t, a, b)
    assert len(rid) == 32
    # 端点不同则 ID 不同
    t2 = svc.create_triple(from_entity_id=b.id, to_entity_id=a.id,
                           relation_code="PLACES")
    assert rid != kg_graph_store.relation_id_for(t2, b, a)


def test_relation_id_degrades_when_endpoint_missing(db, kb, svc):
    """端点实体被删/查不到时退化为 #id，不抛错（该边待 reconcile 补齐）。"""
    a = svc.create_entity(name="星海科技", type_code="CUS")
    b = svc.create_entity(name="订单B1", type_code="ORD")
    t = svc.create_triple(from_entity_id=a.id, to_entity_id=b.id,
                          relation_code="PLACES")
    rid = kg_graph_store.relation_id_for(t, None, None)
    assert rid and len(rid) == 32


# ── 单条投影 ─────────────────────────────────────────────────────────────
def test_project_entity_writes_node(db, kb, svc, fake):
    e = svc.create_entity(name="星海科技", type_code="CUS")
    ok = kg_graph_store.project_entity(db, e)
    assert ok is True
    store = fake["store"]
    assert store.entities and store.entities[0]["name"] == "星海科技"
    assert store.entities[0]["label"] == "CUS"


def test_project_relation_ensures_both_endpoints(db, kb, svc, fake):
    a = svc.create_entity(name="星海科技", type_code="CUS")
    b = svc.create_entity(name="订单B1", type_code="ORD")
    t = svc.create_triple(from_entity_id=a.id, to_entity_id=b.id,
                          relation_code="PLACES")
    fake["store"] = FakeStore(kb.id)  # 清掉 CRUD 期间的调用
    assert kg_graph_store.project_relation(db, t) is True
    store = fake["store"]
    assert len(store.entities) == 2          # 两端节点先 MERGE
    assert len(store.relations) == 1
    assert store.relations[0]["relation_type"] == "PLACES"


def test_project_mention_creates_chunk_and_edge(db, kb, svc, fake):
    e = svc.create_entity(name="星海科技", type_code="CUS")
    ok = kg_graph_store.project_mention(
        kb_id=kb.id, document_id="doc-1", chunk_index=3, entity=e, content_preview="摘要"
    )
    assert ok is True
    store = fake["store"]
    assert store.chunks and store.chunks[0]["document_id"] == "doc-1"
    assert store.mentions and store.mentions[0]["entity_id"] == (
        kg_graph_store.node_id_for_entity(e)
    )


# ── CRUD 接入（P2 验收：手工建的实体/关系在 Neo4j 可见）──────────────────
def test_create_entity_triggers_projection(svc, fake):
    svc.create_entity(name="星海科技", type_code="CUS")
    assert fake["store"].entities, "手工建实体必须投影到 Neo4j"


def test_create_triple_triggers_projection(svc, fake):
    a = svc.create_entity(name="星海科技", type_code="CUS")
    b = svc.create_entity(name="订单B1", type_code="ORD")
    svc.create_triple(from_entity_id=a.id, to_entity_id=b.id, relation_code="PLACES")
    assert fake["store"].relations, "手工建关系必须投影到 Neo4j"


def test_update_entity_triggers_reprojection(svc, fake):
    e = svc.create_entity(name="星海科技", type_code="CUS")
    fake["store"].entities.clear()
    svc.update_entity(e.id, name="星海科技(更名)")
    assert fake["store"].entities[0]["name"] == "星海科技(更名)"


def test_delete_entity_unprojects_node(svc, fake):
    e = svc.create_entity(name="星海科技", type_code="CUS")
    nid = kg_graph_store.node_id_for_entity(e)
    svc.delete_entity(e.id)
    assert nid in fake["store"].deleted_entities


def test_delete_triple_unprojects_edge_only(svc, fake):
    """删边只删这条 RELATION，不得误伤端点实体（DETACH DELETE 会误伤）。"""
    a = svc.create_entity(name="星海科技", type_code="CUS")
    b = svc.create_entity(name="订单B1", type_code="ORD")
    t = svc.create_triple(from_entity_id=a.id, to_entity_id=b.id, relation_code="PLACES")
    fake["store"].deleted_entities.clear()
    svc.delete_triple(t.id)
    assert fake["store"].deleted_relations
    assert fake["store"].deleted_entities == []


# ── 降级：Neo4j 故障不得阻断 PG 事实写入 ──────────────────────────────────
def test_neo4j_down_does_not_block_entity_creation(monkeypatch, db, kb, svc):
    def factory(kb_id, **kwargs):
        return FakeStore(kb_id, fail=True)

    monkeypatch.setattr(kg_graph_store, "KgNeo4jStore", factory)
    e = svc.create_entity(name="星海科技", type_code="CUS")
    assert e.id, "Neo4j 不可用时 PG 事实仍必须写入成功"
    assert kg_graph_store.project_entity(db, e) is False


def test_neo4j_down_does_not_block_relation_creation(monkeypatch, db, kb, svc):
    monkeypatch.setattr(kg_graph_store, "KgNeo4jStore",
                        lambda kid, **kw: FakeStore(kid, fail=True))
    a = svc.create_entity(name="A", type_code="X")
    b = svc.create_entity(name="B", type_code="X")
    t = svc.create_triple(from_entity_id=a.id, to_entity_id=b.id, relation_code="R")
    assert t.id
    assert kg_graph_store.project_relation(db, t) is False


def test_delete_survives_neo4j_down(monkeypatch, svc):
    monkeypatch.setattr(kg_graph_store, "KgNeo4jStore",
                        lambda kid, **kw: FakeStore(kid, fail=True))
    e = svc.create_entity(name="星海科技", type_code="CUS")
    svc.delete_entity(e.id)  # 不得抛出
    assert svc.list_entities() == []


# ── 撤销 / 对账 ──────────────────────────────────────────────────────────
def test_unproject_kb_removes_whole_label(db, kb, fake):
    assert kg_graph_store.unproject_kb(kb.id) is True
    assert fake["store"].deleted_kb == 1


def test_unproject_chunks(db, kb, fake):
    n = kg_graph_store.unproject_chunks(kb.id, "doc-1", [0, 1, 2])
    assert n == 3
    assert len(fake["store"].deleted_chunks) == 3


def test_reconcile_reports_counts_and_reprojects(db, kb, svc, fake):
    a = svc.create_entity(name="星海科技", type_code="CUS")
    b = svc.create_entity(name="订单B1", type_code="ORD")
    svc.create_triple(from_entity_id=a.id, to_entity_id=b.id, relation_code="PLACES")
    fake["store"] = FakeStore(kb.id)

    out = kg_graph_store.reconcile(db, kb.id, TENANT_A)
    assert out["entities"] == 2
    assert out["relations"] == 1
    assert out["entities_projected"] == 2
    assert out["ok"] is True
    # 两个实体的节点都出现在投影里（project_relation 会再 MERGE 一次端点，属幂等重复）
    projected_ids = {e["entity_id"] for e in fake["store"].entities}
    assert {
        kg_graph_store.node_id_for_entity(a),
        kg_graph_store.node_id_for_entity(b),
    } <= projected_ids


def test_reconcile_ok_false_when_projection_fails(db, kb, svc, monkeypatch):
    svc.create_entity(name="星海科技", type_code="CUS")
    monkeypatch.setattr(kg_graph_store, "KgNeo4jStore",
                        lambda kid, **kw: FakeStore(kid, fail=True))
    out = kg_graph_store.reconcile(db, kb.id, TENANT_A)
    assert out["entities"] == 1 and out["ok"] is False
