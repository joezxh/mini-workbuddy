"""Task 5：P2 元数据 → 本体候选生成测试。

分层口径以 P2 计划 Task 12 的参数化示例为权威：
`0.90 → accepted`、`0.70 → suggested`、`0.50 → 丢弃`
（分界线即 `rule_engine.CONF_AUTO_ACCEPT=0.85` / `CONF_SUGGEST_MIN=0.65`，
P4 与 P2 共用，不得各自定义——`test_thresholds_are_single_sourced` 固化）。
"""
from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.services.dataops.rule_engine import CONF_AUTO_ACCEPT, CONF_SUGGEST_MIN
from app.services.ontology.modeling_service import (
    ColumnPairOverlap,
    MetaColumnRef,
    MetaTableRef,
    ModelingService,
)

from .conftest import TENANT_A, TENANT_B


def _tables() -> List[MetaTableRef]:
    return [
        MetaTableRef(source_id="s1", database="dw", table_name="t_customer", comment="客户表"),
        MetaTableRef(source_id="s1", database="dw", table_name="t_contract", comment="合同表"),
    ]


def _columns() -> List[MetaColumnRef]:
    return [
        MetaColumnRef("s1", "dw", "t_customer", "cust_name", "string", "客户名称", confidence=0.90),
        MetaColumnRef("s1", "dw", "t_customer", "cust_id", "string", "客户编号", confidence=0.70),
        MetaColumnRef("s1", "dw", "t_customer", "low_conf", "string", "低置信", confidence=0.50),
        MetaColumnRef("s1", "dw", "t_contract", "amount", "decimal", "金额", confidence=None),
    ]


def _pairs() -> List[ColumnPairOverlap]:
    return [
        ColumnPairOverlap("t_customer", "cust_id", "t_contract", "cust_id", 0.92),
        ColumnPairOverlap("t_customer", "cust_name", "t_contract", "cust_name", 0.70),
        ColumnPairOverlap("t_customer", "cust_id", "t_contract", "amount", 0.30),
    ]


# ── 1. 联动全链路（spec §8：meta_table → 候选 → 人工接受 → 落库）─────────────

def test_full_chain_table_candidate_then_human_accept(db: Session) -> None:
    svc = ModelingService(db, TENANT_A)
    report = svc.generate_candidates(tables=_tables(), columns=[], column_pairs=[])

    assert report.created["object_type"] == 2, report
    assert report.created["mapping"] == 2, report

    codes = {r.code for r in svc.list_object_types(status="suggested")}
    assert codes == {"t_customer", "t_contract"}, "表候选默认 suggested（人工评审）"

    # 人工接受
    svc.update_object_type_status("t_customer", "accepted")
    accepted = {r.code for r in svc.list_object_types(status="accepted")}
    assert accepted == {"t_customer"}

    # 候选可追溯：evidence 记录 P2 侧来源
    row = svc.get_object_type("t_customer")
    assert row.evidence_json["origin"] == "p2_meta_scan"
    assert row.evidence_json["table_name"] == "t_customer"
    assert row.evidence_json["source_id"] == "s1"


def test_table_mapping_generated_with_evidence(db: Session) -> None:
    """表候选顺带生成 table 级映射（可追溯 P2 的 source/database）。"""
    svc = ModelingService(db, TENANT_A)
    svc.generate_candidates(tables=_tables(), columns=[], column_pairs=[])

    mappings = svc.list_mappings()
    assert len(mappings) == 2
    by_table = {m.table_name: m for m in mappings}
    assert by_table["t_customer"].target_type == "table"
    assert by_table["t_customer"].source_id == "s1"
    assert by_table["t_customer"].database == "dw"


# ── 2. 列置信度分层（与 P2 计划示例对齐）─────────────────────────────────────

def test_column_confidence_tiers(db: Session) -> None:
    svc = ModelingService(db, TENANT_A)
    report = svc.generate_candidates(
        # amount 列挂在 t_contract，两张表都要在输入里
        tables=[
            MetaTableRef("s1", "dw", "t_customer"),
            MetaTableRef("s1", "dw", "t_contract"),
        ],
        columns=_columns()
        + [
            MetaColumnRef("s1", "dw", "t_customer", "edge_hi", confidence=CONF_AUTO_ACCEPT),
            MetaColumnRef("s1", "dw", "t_customer", "edge_lo", confidence=CONF_SUGGEST_MIN),
        ],
        column_pairs=[],
    )

    props = {p.code: p.status for p in svc.list_properties("t_customer")}
    assert props["cust_name"] == "accepted"   # 0.90 ≥ 0.85 → 自动接受
    assert props["cust_id"] == "suggested"    # 0.70 ∈ [0.65, 0.85)
    assert props["edge_hi"] == "accepted"     # 0.85 边界（含）→ accepted
    assert props["edge_lo"] == "suggested"    # 0.65 边界（含）→ suggested
    assert "low_conf" not in props            # 0.50 < 0.65 → 不生成

    # amount（confidence=None）挂在 t_contract 上：未评分 → suggested 人工兜底
    contract_props = {p.code: p.status for p in svc.list_properties("t_contract")}
    assert contract_props.get("amount") == "suggested"

    assert report.created["property"] == 5
    assert report.skipped["property"] == 1


# ── 3. 关系候选 ───────────────────────────────────────────────────────────────

def test_link_type_from_column_pairs(db: Session) -> None:
    """高重叠列对 → 关系候选；同表对多列对合并 evidence；低于阈值丢弃。"""
    svc = ModelingService(db, TENANT_A)
    report = svc.generate_candidates(tables=_tables(), columns=[], column_pairs=_pairs())

    links = svc.list_link_types()
    assert len(links) == 1, "同表对的两条合格列对合并为一个关系候选"
    link = links[0]
    assert link.code == "rel_t_customer__t_contract"
    assert link.cardinality == "N:M"
    assert link.source == "rule"
    assert link.status == "suggested"
    assert link.confidence == 0.92  # 取列对最大重叠度
    pairs = link.evidence_json["pairs"]
    assert len(pairs) == 2, "0.92 与 0.70 合并；0.30 低于阈值丢弃"
    assert {p["overlap_ratio"] for p in pairs} == {0.92, 0.70}
    assert report.created["link_type"] == 1
    assert report.skipped["link_type"] == 1


def test_link_type_skips_unknown_tables(db: Session) -> None:
    """列对引用的表不在输入/库中 → 跳过而不是报错。"""
    svc = ModelingService(db, TENANT_A)
    report = svc.generate_candidates(
        tables=_tables(),
        columns=[],
        column_pairs=[ColumnPairOverlap("t_customer", "cust_id", "t_ghost", "id", 0.99)],
    )
    assert svc.list_link_types() == []
    assert report.skipped["link_type"] == 1


# ── 4. 幂等 ───────────────────────────────────────────────────────────────────

def test_generate_candidates_is_idempotent(db: Session) -> None:
    svc = ModelingService(db, TENANT_A)
    first = svc.generate_candidates(
        tables=_tables(), columns=_columns(), column_pairs=_pairs()
    )
    second = svc.generate_candidates(
        tables=_tables(), columns=_columns(), column_pairs=_pairs()
    )

    assert first.created.get("object_type", 0) == 2
    # 第二次全部跳过（created 键可能不出现，用 .get 语义）
    assert second.created.get("object_type", 0) == 0
    assert second.created.get("property", 0) == 0
    assert second.created.get("mapping", 0) == 0
    assert second.created.get("link_type", 0) == 0
    assert second.skipped.get("object_type", 0) == 2

    assert len(svc.list_object_types()) == 2
    assert len(svc.list_mappings()) == 2
    assert len(svc.list_link_types()) == 1


# ── 5. 租户隔离 ───────────────────────────────────────────────────────────────

def test_generate_candidates_tenant_isolated(db: Session) -> None:
    """同一批元数据在不同租户各自生成候选，互不冲突、互不可见。"""
    ModelingService(db, TENANT_A).generate_candidates(
        tables=_tables(), columns=[], column_pairs=[]
    )
    db.commit()

    svc_b = ModelingService(db, TENANT_B)
    report = svc_b.generate_candidates(tables=_tables(), columns=[], column_pairs=[])
    assert report.created["object_type"] == 2, "B 从零生成，不受 A 影响"
    assert svc_b.list_object_types(status="suggested") != []
    assert ModelingService(db, TENANT_A).list_object_types() != []


# ── 6. 阈值单一来源（计划约束：不得重新定义）─────────────────────────────────

def test_thresholds_are_single_sourced() -> None:
    """modeling_service 必须引用 rule_engine 常量本身，而非复刻数值。"""
    import app.services.ontology.modeling_service as ms

    assert ms.CONF_AUTO_ACCEPT is CONF_AUTO_ACCEPT
    assert ms.CONF_SUGGEST_MIN is CONF_SUGGEST_MIN
    assert (CONF_AUTO_ACCEPT, CONF_SUGGEST_MIN) == (0.85, 0.65)
