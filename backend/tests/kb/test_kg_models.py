"""图谱知识库 · 实例层数据模型契约测试。

覆盖：表结构、唯一约束、级联删除、状态默认值、租户列存在性。
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.kb.kg_entity import KgEntity
from app.models.kb.kg_entity_mention import KgEntityMention
from app.models.kb.kg_triple import KgTriple
from app.models.kb.kg_triple_mention import KgTripleMention
from app.models.wiki.wiki_knowledge import WikiKnowledge
from tests.kb.conftest import TENANT_A


def _make_kb(db, tenant_id=TENANT_A, slug="kg-kb-1", kb_type=4) -> WikiKnowledge:
    kb = WikiKnowledge(
        name="图谱库", slug=slug, type=kb_type, tenant_id=tenant_id,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def _make_entity(db, kb, entity_key="客户:1001", name="星海科技", tenant_id=TENANT_A):
    e = KgEntity(
        tenant_id=tenant_id, knowledge_id=kb.id, entity_key=entity_key,
        name=name, type_code="OBJ_CUSTOMER",
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def test_kg_tables_registered():
    assert KgEntity.__tablename__ == "kg_entity"
    assert KgEntityMention.__tablename__ == "kg_entity_mention"
    assert KgTriple.__tablename__ == "kg_triple"
    assert KgTripleMention.__tablename__ == "kg_triple_mention"


def test_entity_columns_carry_tenant_and_kg_fields():
    cols = {c.name for c in KgEntity.__table__.columns}
    assert {"id", "tenant_id", "knowledge_id", "entity_key", "name", "type_code",
            "aliases", "properties", "source_segment_ids", "source_document_ids",
            "embedding", "status", "created_at", "updated_at"} <= cols


def test_entity_status_defaults_to_suggested(db):
    kb = _make_kb(db)
    e = _make_entity(db, kb)
    assert e.status == "suggested"


def test_entity_key_unique_per_knowledge(db):
    kb = _make_kb(db)
    _make_entity(db, kb, entity_key="客户:1001")
    db.add(KgEntity(
        tenant_id=TENANT_A, knowledge_id=kb.id, entity_key="客户:1001", name="重复",
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_entity_key_may_repeat_across_knowledge(db):
    kb1 = _make_kb(db, slug="kg-kb-a")
    kb2 = _make_kb(db, slug="kg-kb-b")
    _make_entity(db, kb1, entity_key="客户:1001")
    _make_entity(db, kb2, entity_key="客户:1001")
    assert db.query(KgEntity).filter_by(entity_key="客户:1001").count() == 2


def test_triple_links_entities_and_cascades_on_entity_delete(db):
    kb = _make_kb(db)
    src = _make_entity(db, kb, entity_key="客户:1001", name="星海科技")
    dst = _make_entity(db, kb, entity_key="订单:B1", name="订单B1")
    t = KgTriple(
        tenant_id=TENANT_A, knowledge_id=kb.id, relation_code="REL_BELONGS",
        from_entity_id=src.id, to_entity_id=dst.id, predicate="隶属于", weight=0.9,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    assert t.status == "suggested"

    db.delete(src)
    db.commit()
    # 起点实体删除后，相关边随之清理，不留悬挂边
    assert db.query(KgTriple).filter_by(id=t.id).count() == 0


def _make_segment(db, tenant_id=TENANT_A, document_id="doc-1"):
    """提及表对 kms_segment.id 有外键，需真实切片行。"""
    from app.models.kb.kb_segment import KbSegment

    seg = KbSegment(
        tenant_id=tenant_id, collection="kb_1", document_id=document_id,
        chunk_index=0, content="测试切片",
    )
    db.add(seg)
    db.commit()
    db.refresh(seg)
    return seg


def test_triple_edge_unique(db):
    kb = _make_kb(db)
    src = _make_entity(db, kb, entity_key="A", name="A")
    dst = _make_entity(db, kb, entity_key="B", name="B")
    db.add(KgTriple(
        tenant_id=TENANT_A, knowledge_id=kb.id, relation_code="REL_X",
        from_entity_id=src.id, to_entity_id=dst.id,
    ))
    db.commit()
    db.add(KgTriple(
        tenant_id=TENANT_A, knowledge_id=kb.id, relation_code="REL_X",
        from_entity_id=src.id, to_entity_id=dst.id,
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert db.query(KgTriple).count() == 1


def test_mention_unique_per_entity_segment(db):
    kb = _make_kb(db)
    e = _make_entity(db, kb, entity_key="客户:1001")
    seg = _make_segment(db)
    db.add(KgEntityMention(
        tenant_id=TENANT_A, kg_entity_id=e.id, segment_id=seg.id, document_id="doc-1",
    ))
    db.commit()
    db.add(KgEntityMention(
        tenant_id=TENANT_A, kg_entity_id=e.id, segment_id=seg.id, document_id="doc-1",
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert db.query(KgEntityMention).count() == 1


def test_mention_cascades_on_entity_delete(db):
    kb = _make_kb(db)
    e = _make_entity(db, kb, entity_key="客户:1001")
    seg = _make_segment(db)
    db.add(KgEntityMention(
        tenant_id=TENANT_A, kg_entity_id=e.id, segment_id=seg.id, document_id="doc-1",
    ))
    db.commit()
    db.delete(e)
    db.commit()
    assert db.query(KgEntityMention).count() == 0


def test_knowledge_delete_cascades_kg_rows(db):
    kb = _make_kb(db)
    _make_entity(db, kb, entity_key="客户:1001")
    db.delete(kb)
    db.commit()
    assert db.query(KgEntity).count() == 0
