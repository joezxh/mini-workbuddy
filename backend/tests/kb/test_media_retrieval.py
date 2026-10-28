"""检索 media_kind 过滤与媒体定位块测试（真实 PG schema，关键词路）。"""
import pytest

from app.models.kb.kb_collection import KbCollection
from app.models.kb.kb_document import KbDocument
from app.models.kb.kb_segment import KbSegment
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.services.kb.pgvector_store import PGVectorStore


@pytest.fixture()
def seeded(db):
    import uuid as _uuid
    kb = WikiKnowledge(tenant_id=1, name="媒体检索测试库", type=2,
                       kb_format="document", multimodal_enabled=True,
                       slug=f"media-test-{_uuid.uuid4().hex[:8]}")
    db.add(kb)
    db.flush()  # 自然主键，供 kb_collection FK
    coll = f"kb_{kb.id}"
    db.add(KbCollection(tenant_id=1, knowledge_id=kb.id, name=coll,
                        dimensions=768))
    db.add(KbDocument(tenant_id=1, knowledge_id=kb.id, collection=coll,
                      name="f.mp3", file_type="mp3"))
    db.flush()
    db.add(KbSegment(
        tenant_id=1, collection=coll, document_id="doc-txt", chunk_index=0,
        content="会议讨论了项目启动计划", chunk_type="text",
    ))
    db.add(KbSegment(
        tenant_id=1, collection=coll, document_id="doc-aud", chunk_index=0,
        content="录音转写：项目启动计划", chunk_type="audio",
        metadata_={"media_kind": "audio",
                   "media_locator": {"start_ms": 1000, "end_ms": 4000}},
    ))
    db.commit()
    return PGVectorStore(db, 1), coll


def test_hybrid_search_returns_both_by_default(seeded):
    store, coll = seeded
    hits = store.hybrid_search(coll, None, "项目启动计划", 10)
    assert {h.document_id for h in hits} == {"doc-txt", "doc-aud"}


def test_media_kind_filter_audio(seeded):
    store, coll = seeded
    hits = store.hybrid_search(coll, None, "项目启动计划", 10, media_kind="audio")
    assert [h.document_id for h in hits] == ["doc-aud"]
    media = hits[0].media
    assert media == {"kind": "audio",
                     "locator": {"start_ms": 1000, "end_ms": 4000}}


def test_media_kind_document_excludes_media(seeded):
    store, coll = seeded
    hits = store.hybrid_search(coll, None, "项目启动计划", 10,
                               media_kind="document")
    assert [h.document_id for h in hits] == ["doc-txt"]
    assert hits[0].media is None


def test_media_kind_filter_applies_to_vector_search(seeded):
    store, coll = seeded
    # 无向量（embedding NULL）时向量路无结果，仅验证过滤条件不报错且语义正确
    hits = store.search(coll, [0.1] * 768, 10, media_kind="audio")
    assert hits == []  # audio 段 embedding 为 NULL，向量路天然排除
