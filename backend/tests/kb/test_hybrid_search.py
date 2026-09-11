"""中文混合检索测试（P1 Task 5：pg_trgm + RRF）。

验证 hybrid_search 在纯向量召回之外，能通过 pg_trgm 关键词召回补回向量漏掉的
中文相关切片（召回 ≥ 纯向量），以及向量/关键词单侧路径与租户隔离。
依赖测试库已启用 pg_trgm 扩展 + content 列 GIN trigram 索引（tests/kb/conftest.py）。
"""
from __future__ import annotations

from app.services.kb.pgvector_store import PGVectorStore, SegmentInput

DIM = 768


def _v(seed: int) -> list:
    """确定性 one-hot 向量，第 seed 位为 1；不同 seed 余弦相似度可区分。"""
    vec = [0.0] * DIM
    vec[seed % DIM] = 1.0
    return vec


def _store(db, tid):
    return PGVectorStore(db, tid)


def test_hybrid_recall_ge_vector(db):
    s = _store(db, 100)
    s.create_collection("kb_hy", DIM)
    s.insert(
        "kb_hy",
        "d1",
        [
            # 向量命中项（查询向量 one-hot@5）
            SegmentInput(chunk_index=0, content="无关内容一", embedding=_v(5)),
            # 关键词命中项（含查询文本「梯度下降优化」子串，但向量与查询向量无关）
            SegmentInput(chunk_index=1, content="本文讲解梯度下降优化算法的收敛性分析", embedding=_v(9)),
            SegmentInput(chunk_index=2, content="随机填充文本", embedding=_v(2)),
        ],
    )
    q_emb = _v(5)
    q_text = "梯度下降优化"

    vec_only = s.search("kb_hy", q_emb, top_k=1)
    assert vec_only[0].content == "无关内容一"

    hy = s.hybrid_search("kb_hy", q_emb, q_text, top_k=5)
    hy_contents = [r.content for r in hy]
    kw_hit = "本文讲解梯度下降优化算法的收敛性分析"
    # 混合检索召回到了纯向量 top_k=1 漏掉的关键词命中项 → 召回 ≥ 纯向量
    assert kw_hit in hy_contents
    assert kw_hit not in [r.content for r in vec_only]


def test_hybrid_keyword_only(db):
    s = _store(db, 100)
    s.create_collection("kb_hy2", DIM)
    s.insert(
        "kb_hy2",
        "d1",
        [
            SegmentInput(chunk_index=0, content="无关内容一", embedding=_v(5)),
            SegmentInput(chunk_index=1, content="本文讲解梯度下降优化算法的收敛性分析", embedding=_v(9)),
        ],
    )
    # query_embedding=None → 仅走 pg_trgm 关键词召回
    res = s.hybrid_search("kb_hy2", None, "梯度下降优化", top_k=5)
    assert len(res) == 1
    assert res[0].content == "本文讲解梯度下降优化算法的收敛性分析"


def test_hybrid_vector_only_equals_vector_search(db):
    s = _store(db, 100)
    s.create_collection("kb_hy3", DIM)
    s.insert(
        "kb_hy3",
        "d1",
        [
            SegmentInput(chunk_index=0, content="a", embedding=_v(5)),
            SegmentInput(chunk_index=1, content="b", embedding=_v(9)),
        ],
    )
    vec = s.search("kb_hy3", _v(5), top_k=10)
    hy = s.hybrid_search("kb_hy3", _v(5), "", top_k=10)
    # 单侧向量召回：混合检索退化成向量召回，排序应一致
    assert [r.content for r in hy] == [r.content for r in vec]


def test_hybrid_tenant_isolation(db):
    a = _store(db, 100)
    a.create_collection("kb_hy4", DIM)
    a.insert("kb_hy4", "d1", [SegmentInput(chunk_index=0, content="本文讲解梯度下降优化", embedding=_v(9))])
    b = _store(db, 200)
    # B 跨租户用 A 的 collection 名做混合检索，一无所获
    assert b.hybrid_search("kb_hy4", None, "梯度下降优化", top_k=5) == []
