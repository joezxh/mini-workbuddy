"""本体驱动检索过滤测试（P4.3 / P4 Task 7）。

验证：后代类扩展（父类过滤覆盖子类、环路/悬空安全、deprecated 排除）、
按 class_uris 过滤 kb_segment 结果不越界、租户隔离、混合检索联动，
以及 OntologyDrivenRetriever 组合入口。
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from app.db.database import Base
from app.models.ontology.ontology import Ontology, OntologyClass
from app.services.kb.pgvector_store import PGVectorStore, SegmentInput
from app.services.ontology.search_filter import (
    OntologyDrivenRetriever,
    expand_with_descendants,
)

from tests.ontology.conftest import TEST_DB_URL, TENANT_A, TENANT_B

DIM = 768
LOAN = "http://onto/finance#Loan"
MORTGAGE = "http://onto/finance#Mortgage"
CONSUMER = "http://onto/finance#ConsumerLoan"
DEPOSIT = "http://onto/finance#Deposit"


def _v(seed: int) -> list:
    vec = [0.0] * DIM
    vec[seed % DIM] = 1.0
    return vec


def _fake_embed(texts):
    """确定性伪 embed：按字符/二元组哈希落桶，同字词越多越相似。"""
    out = []
    for t in texts:
        vec = [0.0] * DIM
        chars = [c for c in t if not c.isspace()]
        for c in chars:
            vec[ord(c) % DIM] += 1.0
        for a, b in zip(chars, chars[1:]):
            vec[(ord(a) * 131 + ord(b)) % DIM] += 0.5
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        out.append([x / norm for x in vec])
    return out


@pytest.fixture
def kb_engine(engine):
    """ontology 测试 schema 内补建 kb 三表 + pg_trgm 扩展（DB 级，幂等）。"""
    from app.models.kb.kb_collection import KbCollection
    from app.models.kb.kb_ref import KbRef
    from app.models.kb.kb_segment import KbSegment

    Base.metadata.create_all(
        engine,
        tables=[KbCollection.__table__, KbSegment.__table__, KbRef.__table__],
    )
    admin = create_engine(TEST_DB_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    finally:
        admin.dispose()
    return engine


@pytest.fixture
def ontology_id(db):
    o = Ontology(tenant_id=TENANT_A, code="fin", name="金融本体")
    db.add(o)
    db.flush()

    def add_cls(uri, label, parents, status="active"):
        db.add(
            OntologyClass(
                tenant_id=TENANT_A,
                ontology_id=o.id,
                uri=uri,
                label=label,
                parent_uris=parents,
                status=status,
            )
        )

    add_cls(LOAN, "贷款", [])
    add_cls(MORTGAGE, "房贷", [LOAN])
    add_cls(CONSUMER, "消费贷", [LOAN])
    add_cls(DEPOSIT, "存款", [])
    db.flush()
    return o.id


@pytest.fixture
def seg_store(db, kb_engine, ontology_id):
    store = PGVectorStore(db, TENANT_A)
    store.create_collection("kb_onto", DIM)
    store.insert(
        "kb_onto",
        "d1",
        [
            SegmentInput(chunk_index=0, content="房贷利率调整通知", embedding=_v(1), class_uris=[MORTGAGE]),
            SegmentInput(chunk_index=1, content="消费贷审批流程", embedding=_v(2), class_uris=[CONSUMER]),
            SegmentInput(chunk_index=2, content="存款利率表", embedding=_v(3), class_uris=[DEPOSIT]),
            SegmentInput(chunk_index=3, content="无类属文本", embedding=_v(4), class_uris=[]),
            SegmentInput(chunk_index=4, content="空类属文本", embedding=_v(5), class_uris=None),
        ],
    )
    db.flush()
    return store


# ── 后代扩展 ────────────────────────────────────────────────────────────────
def test_expand_includes_all_descendants(db, ontology_id):
    assert set(expand_with_descendants(db, TENANT_A, ontology_id, [LOAN])) == {
        LOAN,
        MORTGAGE,
        CONSUMER,
    }
    # 选叶子类只命中自身
    assert expand_with_descendants(db, TENANT_A, ontology_id, [MORTGAGE]) == [MORTGAGE]
    # 空选区 = 不过滤
    assert expand_with_descendants(db, TENANT_A, ontology_id, None) is None
    assert expand_with_descendants(db, TENANT_A, ontology_id, []) is None


def test_expand_safe_on_cycles(db, ontology_id):
    x, y = "http://onto/x#X", "http://onto/x#Y"
    db.add(OntologyClass(tenant_id=TENANT_A, ontology_id=ontology_id, uri=x, parent_uris=[y]))
    db.add(OntologyClass(tenant_id=TENANT_A, ontology_id=ontology_id, uri=y, parent_uris=[x]))
    db.flush()
    # 互相引用的脏数据不得死循环（深度上限 + visited 兜底）
    assert set(expand_with_descendants(db, TENANT_A, ontology_id, [x])) == {x, y}


def test_expand_excludes_deprecated(db, ontology_id):
    old = "http://onto/f#Old"
    db.add(
        OntologyClass(
            tenant_id=TENANT_A,
            ontology_id=ontology_id,
            uri=old,
            parent_uris=[LOAN],
            status="deprecated",
        )
    )
    db.flush()
    assert old not in expand_with_descendants(db, TENANT_A, ontology_id, [LOAN])


# ── 检索过滤 ────────────────────────────────────────────────────────────────
def test_filter_by_parent_class_hits_descendants(seg_store, ontology_id, db):
    scope = expand_with_descendants(db, TENANT_A, ontology_id, [LOAN])
    hits = seg_store.search("kb_onto", _v(1), top_k=10, class_uris=scope)
    # 命中房贷 + 消费贷（Loan 后代），不含存款/无类/空类切片 —— 不越界
    assert {r.chunk_index for r in hits} == {0, 1}


def test_filter_leaf_class(seg_store, ontology_id, db):
    scope = expand_with_descendants(db, TENANT_A, ontology_id, [DEPOSIT])
    hits = seg_store.search("kb_onto", _v(1), top_k=10, class_uris=scope)
    assert {r.chunk_index for r in hits} == {2}


def test_tenant_b_cannot_search_others_segments(db, kb_engine, ontology_id, seg_store):
    b = PGVectorStore(db, TENANT_B)
    scope = expand_with_descendants(db, TENANT_A, ontology_id, [LOAN])
    assert b.search("kb_onto", _v(1), top_k=10, class_uris=scope) == []
    assert b.hybrid_search("kb_onto", _v(1), "房贷", top_k=10, class_uris=scope) == []


def test_hybrid_with_class_filter(seg_store, ontology_id, db):
    scope = expand_with_descendants(db, TENANT_A, ontology_id, [LOAN])
    hits = seg_store.hybrid_search("kb_onto", _v(1), "房贷", top_k=10, class_uris=scope)
    # 关键词命中房贷（chunk 0），向量召回含全部 Loan 后代；存款/无类/空类绝不越界
    assert {r.chunk_index for r in hits} == {0, 1}
    assert hits[0].chunk_index == 0  # 关键词+向量双命中者排第一


# ── 组合入口 ────────────────────────────────────────────────────────────────
def test_retriever_composes_scope(db, seg_store, ontology_id):
    from app.services.kb.retrieval_service import KbRetrievalService

    retriever = OntologyDrivenRetriever(
        db, KbRetrievalService(seg_store, _fake_embed)
    )
    hits = retriever.search_by_text(
        "kb_onto", "房贷利率", TENANT_A, ontology_id=ontology_id, class_uris=[LOAN]
    )
    assert hits and hits[0].chunk_index == 0

    hy = retriever.search_by_text(
        "kb_onto", "房贷利率", TENANT_A, ontology_id=ontology_id,
        class_uris=[LOAN], hybrid=True,
    )
    assert hy and hy[0].chunk_index == 0

    # 不选类 = 不过滤，能拿到全部 5 条候选
    all_hits = retriever.search_by_text("kb_onto", "利率", TENANT_A, top_k=10)
    assert len(all_hits) == 5

    # 传了 class_uris 缺 ontology_id 必须显式报错
    with pytest.raises(ValueError):
        retriever.resolve_scope(TENANT_A, None, [LOAN])
