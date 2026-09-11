"""PGVectorStore.search 向量检索测试（P1 Task 4：向量检索 + HNSW）。

HNSW 索引已在迁移 006 建好（vector_cosine_ops），本测试验证余弦检索语义：
最近邻排序、top_k、相似度阈值、租户隔离，以及 KbRetrievalService.search_by_text。
"""
from __future__ import annotations

from app.services.kb.pgvector_store import PGVectorStore, SegmentInput, SearchResult
from app.services.kb.retrieval_service import KbRetrievalService

DIM = 768


def _v(seed: int) -> list:
    """确定性向量：第 seed 位为 1 的 one-hot 向量，不同 seed 余弦距离可区分。"""
    v = [0.0] * DIM
    v[seed % DIM] = 1.0
    return v


def _store(db, tid):
    return PGVectorStore(db, tid)


def test_search_returns_nearest_first(db):
    s = _store(db, 100)
    s.create_collection("kb_search", DIM)
    s.insert(
        "kb_search",
        "d1",
        [SegmentInput(chunk_index=i, content=f"doc{i}", embedding=_v(i)) for i in range(5)],
    )
    results = s.search("kb_search", _v(2), top_k=3)
    assert len(results) == 3
    assert isinstance(results[0], SearchResult)
    # query=_v(2) 最近邻应为 chunk_index=2（content=doc2）
    assert results[0].content == "doc2"
    # 相似度降序
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    # 相似度范围合理（cosine ∈ [-1,1]）
    assert all(-1.0 <= r.score <= 1.0 for r in results)
    assert results[0].score > 0.99  # 自身相似度≈1


def test_search_top_k_limits(db):
    s = _store(db, 100)
    s.create_collection("kb_topk", DIM)
    s.insert(
        "kb_topk",
        "d1",
        [SegmentInput(chunk_index=i, content=f"c{i}", embedding=_v(i)) for i in range(10)],
    )
    assert len(s.search("kb_topk", _v(0), top_k=4)) == 4
    assert len(s.search("kb_topk", _v(0), top_k=100)) == 10


def test_search_score_threshold_filters(db):
    s = _store(db, 100)
    s.create_collection("kb_thr", DIM)
    s.insert(
        "kb_thr",
        "d1",
        [SegmentInput(chunk_index=i, content=f"c{i}", embedding=_v(i)) for i in range(5)],
    )
    # 高阈值只保留 query 自身（相似度≈1）
    high = s.search("kb_thr", _v(3), top_k=10, score_threshold=0.99)
    assert len(high) == 1
    assert high[0].content == "c3"
    # 低阈值保留全部
    low = s.search("kb_thr", _v(3), top_k=10, score_threshold=-1.0)
    assert len(low) == 5


def test_search_tenant_isolation(db):
    a = _store(db, 100)
    b = _store(db, 200)
    # kb_collection.name 全局唯一，故两租户用不同 collection 名；
    # 隔离在切片层的 tenant_id 过滤上验证：B 用 A 的 collection 名查询应一无所获。
    a.create_collection("kb_iso", DIM)
    a.insert("kb_iso", "d1", [SegmentInput(chunk_index=0, content="secret", embedding=_v(1))])
    # B 伪造 A 的 collection 名也搜不到 A 的切片
    assert b.search("kb_iso", _v(1), top_k=10) == []


def test_search_by_text_uses_embed_fn(db):
    calls = []

    def fake_embed(texts):
        calls.append(list(texts))
        # 单条查询固定返回 _v(2)，便于断言最近邻
        return [_v(2) for _ in texts]

    svc = KbRetrievalService(_store(db, 100), fake_embed)
    svc.store.create_collection("kb_rt", DIM)
    svc.store.insert(
        "kb_rt", "d1", [SegmentInput(chunk_index=i, content=f"t{i}", embedding=_v(i)) for i in range(4)]
    )

    res = svc.search_by_text("kb_rt", "任意查询", top_k=2)
    assert calls == [["任意查询"]]
    assert len(res) == 2
    assert res[0].content == "t2"  # 与 query=_v(2) 最近
