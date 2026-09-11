"""KbIngestService 测试（P1 Task 3：向量生成 / embedding 接入）。

用假的 ``embed_fn`` 注入，避免真实调用 GPUStack；验证：
- 缺失 embedding 的切片会被自动向量化并落库
- 已提供 embedding 的切片不会被覆盖（embed_fn 不被调用）
- 集合声明维度与生成向量维度不一致时尽早失败
- embed_fn 返回数量与切片数不一致时失败
"""
from __future__ import annotations

from app.services.kb.ingest_service import KbIngestService
from app.services.kb.pgvector_store import PGVectorStore, SegmentInput

DIM = 768


def _fake_embed_factory(call_log: list):
    def _embed(texts):
        call_log.append(list(texts))
        return [[float(len(t)), 0.0] * (DIM // 2) for t in texts]

    return _embed


def _store(db, tid):
    return PGVectorStore(db, tid)


def test_ingest_generates_embeddings_and_stores(db):
    calls: list = []
    svc = KbIngestService(_store(db, 100), _fake_embed_factory(calls))
    svc.store.create_collection("kb_ing", DIM)

    n = svc.ingest_document(
        "kb_ing",
        "d1",
        [SegmentInput(chunk_index=i, content=f"片段{i}") for i in range(3)],
    )
    assert n == 3
    # embed_fn 被调用一次，接收 3 条文本
    assert calls == [["片段0", "片段1", "片段2"]]
    assert svc.store.count_segments("kb_ing") == 3
    # 幂等：重复 ingest 同一文档不新增行
    assert svc.ingest_document(
        "kb_ing", "d1", [SegmentInput(chunk_index=0, content="片段0")]
    ) == 1
    assert svc.store.count_segments("kb_ing") == 3


def test_ingest_keeps_provided_embedding(db):
    calls: list = []
    svc = KbIngestService(_store(db, 100), _fake_embed_factory(calls))
    svc.store.create_collection("kb_keep", DIM)

    segs = [
        # 已带向量，不应再调用 embed
        SegmentInput(chunk_index=0, content="a", embedding=[1.0] + [0.0] * (DIM - 1)),
        # 缺失向量，需自动生成
        SegmentInput(chunk_index=1, content="b"),
    ]
    svc.ingest_document("kb_keep", "d1", segs)
    # 仅对 content="b" 调用一次
    assert calls == [["b"]]


def test_ingest_dimension_mismatch_raises(db):
    svc = KbIngestService(_store(db, 100), lambda texts: [[0.1, 0.2, 0.3, 0.4] for _ in texts])
    svc.store.create_collection("kb_dim", DIM)

    try:
        svc.ingest_document(
            "kb_dim", "d1", [SegmentInput(chunk_index=0, content="x")]
        )
        assert False, "维度不一致应抛 ValueError"
    except ValueError as e:
        assert "维度" in str(e)


def test_ingest_embed_count_mismatch_raises(db):
    # 返回数量与切片数不一致
    svc = KbIngestService(_store(db, 100), lambda texts: [])
    svc.store.create_collection("kb_cnt", DIM)

    try:
        svc.ingest_document(
            "kb_cnt", "d1", [SegmentInput(chunk_index=0, content="x")]
        )
        assert False, "向量数不一致应抛 ValueError"
    except ValueError as e:
        assert "不一致" in str(e)
