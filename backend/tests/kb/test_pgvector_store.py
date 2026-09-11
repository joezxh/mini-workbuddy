"""PGVectorStore 骨架 + collection 管理测试（P1 Task 2）。"""
from __future__ import annotations

from sqlalchemy import select

from app.models.kb.kb_segment import KbSegment
from app.services.kb.pgvector_store import PGVectorStore, SegmentInput

DIM = 768


def _vec(seed: float) -> list:
    v = [0.0] * DIM
    v[0] = seed
    return v


def _store(db, tid):
    return PGVectorStore(db, tid)


def test_create_and_get_collection(db):
    s = _store(db, 100)
    coll = s.create_collection("kb_test1", DIM)
    assert coll.name == "kb_test1"
    assert coll.dimensions == DIM
    assert s.has_collection("kb_test1")
    assert s.get_collection("kb_test1").name == "kb_test1"
    assert s.count_segments("kb_test1") == 0

    # 同租户内重复 create 幂等，返回同一行
    coll2 = s.create_collection("kb_test1", DIM)
    assert coll2.id == coll.id
    assert len(s.list_collections()) == 1


def test_collection_tenant_isolation(db):
    a = _store(db, 100)
    b = _store(db, 200)
    a.create_collection("kb_shared", DIM)
    # 租户 B 看不到 A 的 collection
    assert b.get_collection("kb_shared") is None
    assert b.has_collection("kb_shared") is False
    assert b.list_collections() == []


def test_insert_idempotency_and_delete(db):
    s = _store(db, 100)
    s.create_collection("kb_doc", DIM)
    segs = [
        SegmentInput(chunk_index=i, content=f"c{i}", embedding=_vec(i)) for i in range(3)
    ]
    assert s.insert("kb_doc", "d1", segs) == 3
    assert s.count_segments("kb_doc") == 3

    # 再次 upsert 相同 (collection,document_id,chunk_index) → 更新不新增
    s.insert("kb_doc", "d1", [SegmentInput(chunk_index=0, content="c0-updated", embedding=_vec(9))])
    assert s.count_segments("kb_doc") == 3

    docs = s.list_documents("kb_doc")
    assert docs == ["d1"]

    # 删除文档
    assert s.delete_document("kb_doc", "d1") == 3
    assert s.count_segments("kb_doc") == 0


def test_insert_stores_class_uris_and_metadata(db):
    s = _store(db, 100)
    s.create_collection("kb_cls", DIM)
    s.insert(
        "kb_cls",
        "d1",
        [
            SegmentInput(
                chunk_index=0,
                content="x",
                embedding=_vec(1),
                metadata={"k": "v"},
                class_uris=["http://example.org/onto#ClassA"],
            )
        ],
    )
    row = db.execute(
        select(KbSegment).where(
            KbSegment.tenant_id == 100,
            KbSegment.collection == "kb_cls",
            KbSegment.document_id == "d1",
            KbSegment.chunk_index == 0,
        )
    ).scalar_one()
    assert row.class_uris == ["http://example.org/onto#ClassA"]
    assert row.metadata_ == {"k": "v"}


def test_segment_tenant_isolation(db):
    a = _store(db, 100)
    b = _store(db, 200)
    a.create_collection("kb_a", DIM)
    b.create_collection("kb_b", DIM)
    a.insert("kb_a", "d1", [SegmentInput(chunk_index=0, content="secret", embedding=_vec(1))])

    # B 伪造 A 的 collection 名也读不到 A 的切片（纵深防御）
    assert b.count_segments("kb_a") == 0
    assert b.list_documents("kb_a") == []
    assert b.get_collection("kb_a") is None

    # B 在自己的 collection 写入不受影响
    b.insert("kb_b", "d2", [SegmentInput(chunk_index=0, content="mine", embedding=_vec(2))])
    assert b.count_segments("kb_b") == 1


def test_delete_collection(db):
    s = _store(db, 100)
    s.create_collection("kb_del", DIM)
    s.insert("kb_del", "d1", [SegmentInput(chunk_index=0, content="x", embedding=_vec(1))])
    assert s.delete_collection("kb_del") is True
    assert s.has_collection("kb_del") is False
    assert s.count_segments("kb_del") == 0
    # 重复删除返回 False
    assert s.delete_collection("kb_del") is False


def test_search_returns_empty_for_no_embeddings(db):
    s = _store(db, 100)
    s.create_collection("kb_s", DIM)
    # 无切片：返回空列表且不再抛 NotImplementedError（Task 4 已实装）
    assert s.search("kb_s", _vec(1)) == []
    # 切片存在但 embedding 为 None：被 isnot(None) 过滤，仍为空
    s.insert("kb_s", "d1", [SegmentInput(chunk_index=0, content="x", embedding=None)])
    assert s.search("kb_s", _vec(1)) == []
