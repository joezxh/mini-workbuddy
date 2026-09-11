"""P4.2 建模六表与 CQ 覆盖度测试。

TDD 说明
--------
计划示例原样固化为 `test_cq_coverage_counts_linked_types`：
2 个 CQ、其中 1 个关联了对象类型 → `cq_coverage() == 0.5`。
用例的有效性由变异测试验证（见 p4-task-2-report.md）。
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.ontology.modeling_service import ModelingError, ModelingService

from .conftest import TENANT_A, TENANT_B, engine_for, open_session


# ── 1. CQ 覆盖度 ──────────────────────────────────────────────────────────────

def test_cq_coverage_counts_linked_types(db: Session) -> None:
    """计划示例原样固化：2 个 CQ、1 个关联了对象类型 → 覆盖率 0.5。"""
    svc = ModelingService(db, TENANT_A)
    svc.add_object_type("customer", "客户")
    svc.add_cq("列出所有客户")
    svc.add_cq("客户签了哪些合同", linked_object_codes=["customer"])

    assert svc.cq_coverage() == 0.5


def test_cq_coverage_zero_when_no_cqs(db: Session) -> None:
    """无 CQ 时返回 0.0（防除零），且读路径不创建本体行。"""
    assert ModelingService(db, TENANT_A).cq_coverage() == 0.0


def test_cq_coverage_counts_only_active_cqs(db: Session) -> None:
    """archived 的 CQ 不计入覆盖度分母。"""
    svc = ModelingService(db, TENANT_A)
    svc.add_object_type("customer", "客户")
    svc.add_cq("已归档的问题", status="archived", linked_object_codes=["customer"])
    svc.add_cq("未关联的问题")

    assert svc.cq_coverage() == 0.0


# ── 2. 租户安全（子表无 tenant_id 的安全前提）────────────────────────────────

def test_cross_tenant_access_is_isolated(db: Session) -> None:
    """租户 A 的 service 对租户 B 的本体不可见、不可写。

    六张建模表不带 tenant_id（spec §5.2），跨租户安全完全依赖
    ModelingService 的「租户 → 本体 → 子表」链路，必须用测试固化。
    """
    svc_a = ModelingService(db, TENANT_A)
    svc_a.add_object_type("customer", "客户A")
    db.commit()

    svc_b = ModelingService(db, TENANT_B)
    # B 视角下 A 的对象类型等同不存在
    assert svc_b.get_object_type("customer") is None
    assert svc_b.list_object_types() == []
    assert svc_b.list_cqs() == []
    assert svc_b.cq_coverage() == 0.0

    # B 写入自己的同名 code 不冲突（不同本体行）；互不影响
    svc_b.add_object_type("customer", "客户B")
    db.commit()
    assert len(svc_a.list_object_types()) == 1
    assert len(svc_b.list_object_types()) == 1
    assert svc_a.list_object_types()[0].name == "客户A"
    assert svc_b.list_object_types()[0].name == "客户B"


# ── 3. 对象类型 ───────────────────────────────────────────────────────────────

def test_object_type_duplicate_code_rejected(db: Session) -> None:
    svc = ModelingService(db, TENANT_A)
    svc.add_object_type("customer", "客户")
    with pytest.raises(ModelingError, match="已存在"):
        svc.add_object_type("customer", "重复")


def test_object_type_parent_validation(db: Session) -> None:
    svc = ModelingService(db, TENANT_A)
    with pytest.raises(ModelingError, match="不存在"):
        svc.add_object_type("contract", "合同", parent_code="no-such-parent")

    svc.add_object_type("customer", "客户")
    svc.add_object_type("vip_customer", "VIP客户", parent_code="customer")
    vip = svc.get_object_type("vip_customer")
    assert vip is not None
    assert vip.parent_id == svc.get_object_type("customer").id


def test_object_type_status_transition(db: Session) -> None:
    """评审状态流转：suggested → accepted（可逆），非法值拒绝。"""
    svc = ModelingService(db, TENANT_A)
    svc.add_object_type("customer", "客户")

    assert svc.update_object_type_status("customer", "accepted").status == "accepted"
    assert svc.update_object_type_status("customer", "rejected").status == "rejected"
    # 可逆：改回 suggested
    assert svc.update_object_type_status("customer", "suggested").status == "suggested"

    with pytest.raises(ModelingError, match="非法的评审状态"):
        svc.update_object_type_status("customer", "bogus")


def test_object_type_illegal_source_rejected(db: Session) -> None:
    svc = ModelingService(db, TENANT_A)
    with pytest.raises(ModelingError, match="非法的来源"):
        svc.add_object_type("customer", "客户", source="magic")


# ── 4. 属性 / 关系 ────────────────────────────────────────────────────────────

def test_property_requires_existing_object_type(db: Session) -> None:
    svc = ModelingService(db, TENANT_A)
    with pytest.raises(ModelingError, match="不存在"):
        svc.add_property("ghost", "name", "名称")

    svc.add_object_type("customer", "客户")
    svc.add_property("customer", "name", "客户名称", data_type="string", required=True)
    props = svc.list_properties("customer")
    assert len(props) == 1
    assert props[0].required is True

    with pytest.raises(ModelingError, match="已存在"):
        svc.add_property("customer", "name", "重复")


def test_link_type_validates_both_ends_and_cardinality(db: Session) -> None:
    svc = ModelingService(db, TENANT_A)
    svc.add_object_type("customer", "客户")

    with pytest.raises(ModelingError, match="不存在"):
        svc.add_link_type("signs", "签订", "customer", "no-such")

    svc.add_object_type("contract", "合同")
    link = svc.add_link_type("signs", "签订", "customer", "contract", cardinality="1:N")
    assert link.cardinality == "1:N"
    assert len(svc.list_link_types()) == 1

    with pytest.raises(ModelingError, match="非法的基数"):
        svc.add_link_type("owns", "拥有", "customer", "contract", cardinality="9:9")


# ── 5. 映射 / CQ 引用校验 ─────────────────────────────────────────────────────

def test_mapping_validates_target_type_and_column(db: Session) -> None:
    svc = ModelingService(db, TENANT_A)
    svc.add_object_type("customer", "客户")

    with pytest.raises(ModelingError, match="非法的映射目标类型"):
        svc.add_mapping("customer", "index", "t_customer")
    with pytest.raises(ModelingError, match="必须提供 column_name"):
        svc.add_mapping("customer", "column", "t_customer")

    svc.add_mapping("customer", "table", "t_customer", database="dw")
    assert len(svc.list_mappings()) == 1


def test_cq_linked_codes_validated(db: Session) -> None:
    svc = ModelingService(db, TENANT_A)
    with pytest.raises(ModelingError, match="不存在"):
        svc.add_cq("问题", linked_object_codes=["ghost"])


def test_cq_empty_question_rejected(db: Session) -> None:
    svc = ModelingService(db, TENANT_A)
    with pytest.raises(ModelingError, match="question"):
        svc.add_cq("   ")


# ── 5.1 复审探针固化：校验完备性（P4.2 复审发现的缺口）────────────────────────

def test_confidence_out_of_range_rejected(db: Session) -> None:
    """confidence 必须落在 [0,1]（复审探针 B1/B2：1.5/-0.3 曾被接受入库）。"""
    svc = ModelingService(db, TENANT_A)
    with pytest.raises(ModelingError, match="confidence"):
        svc.add_object_type("bad_hi", "越界", confidence=1.5)
    with pytest.raises(ModelingError, match="confidence"):
        svc.add_object_type("bad_lo", "越界", confidence=-0.3)
    with pytest.raises(ModelingError, match="confidence"):
        svc.add_property("ghost", "p", "属性", confidence=2.0)

    # 合法边界可用
    svc.add_object_type("ok_edge", "边界", confidence=0.0, source="rule")
    assert svc.get_object_type("ok_edge").confidence == 0.0


def test_empty_code_and_name_rejected(db: Session) -> None:
    """空串/纯空白 code 与 name 必须被拒（列 nullable=False 只挡 NULL）。"""
    svc = ModelingService(db, TENANT_A)
    for code, name in (("", "空code"), ("  ", "空白code"), ("no_name", "")):
        with pytest.raises(ModelingError):
            svc.add_object_type(code, name)
    assert svc.list_object_types() == []


def test_validation_failure_leaves_no_orphan_ontology(db: Session) -> None:
    """写方法校验失败不得留下空本体行（复审探针 C1-C3 实证过 0→1）。

    `_require_ontology()` 会幂等创建本体行；其后的库依赖校验（悬空
    对象类型/跨租户引用被拒）抛 ModelingError 时，savepoint 回滚必须
    连同本体行 INSERT 一起撤销——无论调用方之后 commit 还是 rollback。
    """
    for tenant in (TENANT_A, TENANT_B):
        n_before = db.execute(
            text("SELECT count(*) FROM ontology WHERE tenant_id = :t"),
            {"t": tenant},
        ).scalar()
        svc = ModelingService(db, tenant)
        with pytest.raises(ModelingError):
            svc.update_object_type_status("ghost", "accepted")
        with pytest.raises(ModelingError):
            svc.add_property("no-such-type", "p", "属性")
        # 模拟路由层在异常之后的 commit（IM-05 模式的 rollback 之外的场景）
        db.commit()
        n_after = db.execute(
            text("SELECT count(*) FROM ontology WHERE tenant_id = :t"),
            {"t": tenant},
        ).scalar()
        assert n_before == n_after, f"租户 {tenant} 留下了孤儿本体行"


def test_cq_question_trimmed_and_linked_codes_deduped(db: Session) -> None:
    """question 存储前去空白；linked_object_codes 去重保持顺序。"""
    svc = ModelingService(db, TENANT_A)
    svc.add_object_type("customer", "客户")
    row = svc.add_cq("   有前后空格   ", linked_object_codes=["customer", "customer"])

    assert row.question == "有前后空格"
    assert row.linked_object_types == ["customer"]


# ── 6. 持久化（重启不丢）──────────────────────────────────────────────────────

def test_modeling_survives_new_engine_instance(db_target: str) -> None:
    """新建 engine + 全新会话（模拟重启）后，建模数据仍在。"""
    eng1 = engine_for(db_target, create_tables=True)
    sess1 = open_session(eng1)
    try:
        svc = ModelingService(sess1, 9101)
        svc.add_object_type("customer", "客户")
        svc.add_property("customer", "name", "客户名称")
        svc.add_cq("列出所有客户", linked_object_codes=["customer"])
        sess1.commit()
    finally:
        sess1.close()
        eng1.dispose()

    eng2 = engine_for(db_target)
    sess2 = open_session(eng2)
    try:
        svc2 = ModelingService(sess2, 9101)
        assert len(svc2.list_object_types()) == 1
        assert len(svc2.list_properties("customer")) == 1
        assert svc2.cq_coverage() == 1.0
    finally:
        sess2.close()
        eng2.dispose()
