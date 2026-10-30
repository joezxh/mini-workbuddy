"""图谱知识库 · 实例层服务契约测试（KgService）：关系 / 隔离 / 守卫 / 统计。"""
import pytest
from fastapi import HTTPException

from app.models.wiki.wiki_knowledge import WikiKnowledge
from tests.kb.conftest import TENANT_A, TENANT_B


def _make_kb(db, tenant_id=TENANT_A, slug="kg-guard-1", kb_type=4):
    kb = WikiKnowledge(name="图谱库", slug=slug, type=kb_type, tenant_id=tenant_id)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


@pytest.fixture
def svc(db):
    kb = _make_kb(db)
    from app.services.kb.kg.kg_service import KgService

    return KgService(db, tenant_id=TENANT_A, knowledge_id=kb.id)


# ── 关系 ────────────────────────────────────────────────────────────────

def test_create_triple_links_entities(svc):
    a = svc.create_entity(name="A")
    b = svc.create_entity(name="B")
    t = svc.create_triple(
        from_entity_id=a.id, to_entity_id=b.id,
        relation_code="REL_BELONGS", predicate="隶属于", weight=0.9,
    )
    assert t.id
    assert t.status == "suggested"
    assert t.from_entity_id == a.id
    assert t.to_entity_id == b.id


def test_create_triple_idempotent_on_edge_key(svc):
    a = svc.create_entity(name="A")
    b = svc.create_entity(name="B")
    t1 = svc.create_triple(from_entity_id=a.id, to_entity_id=b.id, relation_code="REL_X")
    t2 = svc.create_triple(from_entity_id=a.id, to_entity_id=b.id, relation_code="REL_X")
    assert t1.id == t2.id
    assert len(svc.list_triples()) == 1


def test_create_triple_rejects_foreign_entity(svc):
    from app.models.kb.kg_entity import KgEntity

    a = svc.create_entity(name="A")
    other_kb = _make_kb(svc.db, slug="kg-guard-other")
    foreign = KgEntity(
        tenant_id=TENANT_A, knowledge_id=other_kb.id, entity_key="X", name="X",
    )
    svc.db.add(foreign)
    svc.db.commit()
    svc.db.refresh(foreign)

    with pytest.raises(HTTPException) as exc:
        svc.create_triple(
            from_entity_id=a.id, to_entity_id=foreign.id, relation_code="REL_X"
        )
    assert exc.value.status_code == 422


def test_list_triples_filters(svc):
    a = svc.create_entity(name="A")
    b = svc.create_entity(name="B")
    c = svc.create_entity(name="C")
    svc.create_triple(from_entity_id=a.id, to_entity_id=b.id, relation_code="REL_X")
    svc.create_triple(from_entity_id=a.id, to_entity_id=c.id, relation_code="REL_Y")
    assert len(svc.list_triples()) == 2
    assert len(svc.list_triples(relation_code="REL_X")) == 1
    assert len(svc.list_triples(status="suggested")) == 2


def test_review_triple_transitions(svc):
    a = svc.create_entity(name="A")
    b = svc.create_entity(name="B")
    t = svc.create_triple(from_entity_id=a.id, to_entity_id=b.id, relation_code="REL_X")
    svc.review_triple(t.id, "accepted")
    assert svc.get_triple(t.id).status == "accepted"
    with pytest.raises(HTTPException) as exc:
        svc.review_triple(t.id, "rejected")
    assert exc.value.status_code == 422


def test_review_triple_rejects_unknown_verdict(svc):
    a = svc.create_entity(name="A")
    b = svc.create_entity(name="B")
    t = svc.create_triple(from_entity_id=a.id, to_entity_id=b.id, relation_code="REL_X")
    with pytest.raises(HTTPException):
        svc.review_triple(t.id, "maybe")


def test_entity_adjacent_triples(svc):
    a = svc.create_entity(name="A")
    b = svc.create_entity(name="B")
    svc.create_triple(from_entity_id=a.id, to_entity_id=b.id, relation_code="REL_X")
    assert len(svc.entity_adjacent_triples(a.id)) == 1
    assert svc.entity_adjacent_triples(999999) == []


# ── 隔离与守卫 ──────────────────────────────────────────────────────────

def test_tenant_isolation(db):
    from app.services.kb.kg.kg_service import KgService

    kb_a = _make_kb(db, tenant_id=TENANT_A, slug="kg-iso-a")
    kb_b = _make_kb(db, tenant_id=TENANT_B, slug="kg-iso-b")
    s1 = KgService(db, tenant_id=TENANT_A, knowledge_id=kb_a.id)
    s2 = KgService(db, tenant_id=TENANT_B, knowledge_id=kb_b.id)
    e1 = s1.create_entity(name="A")
    # 行级隔离：租户 B 看不到租户 A 的实体
    assert s2.list_entities() == []
    assert s2.get_entity(e1.id) is None


def test_cross_tenant_knowledge_rejected(db):
    """跨租户访问他人知识库 → 404（不泄露存在性）。"""
    from app.services.kb.kg.kg_service import KgService

    kb_a = _make_kb(db, tenant_id=TENANT_A, slug="kg-iso-x")
    s = KgService(db, tenant_id=TENANT_B, knowledge_id=kb_a.id)
    with pytest.raises(HTTPException) as exc:
        s.list_entities()
    assert exc.value.status_code == 404


def test_non_graph_knowledge_rejected(db):
    from app.services.kb.kg.kg_service import KgService

    plain = _make_kb(db, slug="kg-guard-plain", kb_type=2)
    s = KgService(db, tenant_id=TENANT_A, knowledge_id=plain.id)
    with pytest.raises(HTTPException) as exc:
        s.create_entity(name="A")
    assert exc.value.status_code == 422


def test_unknown_knowledge_rejected(db):
    from app.services.kb.kg.kg_service import KgService

    s = KgService(db, tenant_id=TENANT_A, knowledge_id=999999)
    with pytest.raises(HTTPException) as exc:
        s.create_entity(name="A")
    assert exc.value.status_code == 404


def test_stats_counts(svc):
    a = svc.create_entity(name="A", type_code="T1")
    b = svc.create_entity(name="B", type_code="T1")
    svc.create_entity(name="C", type_code="T2")
    svc.create_triple(from_entity_id=a.id, to_entity_id=b.id, relation_code="REL_X")
    st = svc.stats()
    assert st["entities"] == 3
    assert st["relations"] == 1
    assert st["by_type"]["T1"] == 2
    assert st["by_relation"]["REL_X"] == 1
