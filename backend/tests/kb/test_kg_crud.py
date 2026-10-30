"""图谱知识库 · 实例层服务契约测试（KgService）：实体 / 关系 CRUD 与评审流转。"""
import pytest
from fastapi import HTTPException

from app.models.wiki.wiki_knowledge import WikiKnowledge
from tests.kb.conftest import TENANT_A, TENANT_B


def _make_kb(db, tenant_id=TENANT_A, slug="kg-svc-1", kb_type=4):
    kb = WikiKnowledge(name="图谱库", slug=slug, type=kb_type, tenant_id=tenant_id)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


@pytest.fixture
def kb(db):
    return _make_kb(db)


@pytest.fixture
def svc(db, kb):
    from app.services.kb.kg.kg_service import KgService

    return KgService(db, tenant_id=TENANT_A, knowledge_id=kb.id)


# ── 实体 ────────────────────────────────────────────────────────────────

def test_create_entity_defaults_to_suggested(svc):
    e = svc.create_entity(name="星海科技", type_code="OBJ_CUSTOMER")
    assert e.id
    assert e.status == "suggested"
    assert e.knowledge_id == svc.knowledge_id
    assert e.tenant_id == TENANT_A


def test_entity_key_auto_derived_and_idempotent(svc):
    e1 = svc.create_entity(name="星海科技", type_code="OBJ_CUSTOMER")
    e2 = svc.create_entity(name="星海科技", type_code="OBJ_CUSTOMER")
    assert e1.id == e2.id
    assert e1.entity_key == "OBJ_CUSTOMER:星海科技"
    assert len(svc.list_entities()) == 1


def test_entity_key_whitespace_normalized(svc):
    e = svc.create_entity(name="  星海   科技 ", type_code="OBJ_CUSTOMER")
    assert e.entity_key == "OBJ_CUSTOMER:星海 科技"


def test_explicit_entity_key_wins(svc):
    e = svc.create_entity(name="星海科技", entity_key="客户:1001")
    assert e.entity_key == "客户:1001"


def test_create_entity_requires_name(svc):
    with pytest.raises(HTTPException) as exc:
        svc.create_entity(name="")
    assert exc.value.status_code == 422


def test_list_entities_filters(svc):
    svc.create_entity(name="星海科技", type_code="OBJ_CUSTOMER")
    svc.create_entity(name="蓝海物流", type_code="OBJ_LOGISTICS")
    svc.create_entity(name="星海集团", type_code="OBJ_CUSTOMER")

    assert len(svc.list_entities()) == 3
    assert len(svc.list_entities(type_code="OBJ_CUSTOMER")) == 2
    assert len(svc.list_entities(keyword="星海")) == 2
    assert len(svc.list_entities(status="suggested")) == 3
    assert len(svc.list_entities(status="active")) == 0


def test_list_entities_matches_alias(svc):
    svc.create_entity(name="星海科技", type_code="OBJ_CUSTOMER", aliases=["Xinghai"])
    assert len(svc.list_entities(keyword="Xinghai")) == 1


def test_get_entity_scoped(svc):
    e = svc.create_entity(name="星海科技")
    assert svc.get_entity(e.id) is not None
    assert svc.get_entity(999999) is None


def test_update_entity_fields(svc):
    e = svc.create_entity(name="星海科技", type_code="OBJ_CUSTOMER")
    svc.update_entity(
        e.id, name="星海科技股份有限公司", type_code="OBJ_ENTERPRISE",
        aliases=["星海"], properties={"信用等级": "A"},
    )
    got = svc.get_entity(e.id)
    assert got.name == "星海科技股份有限公司"
    assert got.type_code == "OBJ_ENTERPRISE"
    assert got.aliases == ["星海"]
    assert got.properties == {"信用等级": "A"}


def test_delete_entity_removes_related_triples(svc):
    a = svc.create_entity(name="A")
    b = svc.create_entity(name="B")
    svc.create_triple(from_entity_id=a.id, to_entity_id=b.id, relation_code="REL_X")
    svc.delete_entity(a.id)
    assert svc.list_triples() == []
    assert svc.get_entity(b.id) is not None


def test_accept_entity_transitions(svc):
    e = svc.create_entity(name="星海科技")
    svc.accept_entity(e.id)
    assert svc.get_entity(e.id).status == "active"
    with pytest.raises(HTTPException) as exc:
        svc.accept_entity(e.id)
    assert exc.value.status_code == 422
