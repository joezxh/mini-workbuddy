"""P3 Task 8 · 中文检索质量对比（验收前置）的受控回归测试。

复用 ``scripts/kb_external_retrieval_bench`` 的语料/查询与两路检索实现，在
tests/kb 的 per-schema PG 基建上跑一遍对比，断言：

- Mode A（只读直连词项打分）与 Mode B（同步落库混合向量）都能跑通且无异常；
- 两路在 20 条中文 query 上的 Recall@5 均达到可接受水位（金标准文档可被召回）。

不依赖真实 embedding API：使用与脚本一致的确定性伪向量。
"""
import pytest

from app.services.kb.pgvector_store import PGVectorStore
from scripts.kb_external_retrieval_bench import (
    CORPUS,
    QUERIES,
    DIM,
    LexiconRetriever,
    fake_embed_fn,
    run_comparison,
)


def test_both_modes_run_and_meet_recall(db):
    store = PGVectorStore(db, 910001)
    ef = fake_embed_fn(DIM)
    result = run_comparison(CORPUS, QUERIES, 5, store, ef)
    db.commit()

    # 两路均返回有效指标
    assert result["modeA"]["recall@5"] >= 0.5
    assert result["modeB"]["recall@5"] >= 0.5
    # 同步落库混合检索不应显著劣于只读直连（基线预期至少持平）
    assert result["modeB"]["recall@5"] >= result["modeA"]["recall@5"] - 0.25


def test_lexicon_retriever_pure_python():
    """Mode A 不触库，纯词项打分可在无 PG 时独立验证。"""
    lex = LexiconRetriever().build(CORPUS)
    ranked = lex.search("订单金额字段口径", top_k=5)
    assert "d_OrderAmount" in ranked[:5]
