"""Task 6：版本快照与评审记录测试。

边界固化：**回滚不在本阶段**——`test_no_rollback_api` 断言本服务不存在任何
回滚/恢复接口；未来引入回滚（P4.4 评估）时必须显式修改该用例。
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.services.ontology.modeling_service import ModelingService
from app.services.ontology.review_service import OntologyReviewService

from .conftest import TENANT_A, TENANT_B


def _svc(db: Session, tenant_id: int = TENANT_A) -> OntologyReviewService:
    return OntologyReviewService(db, tenant_id)


def test_snapshot_version_increments(db: Session) -> None:
    """连续创建快照：v1 → v2 递增。"""
    svc = ModelingService(db, TENANT_A)
    svc.add_object_type("customer", "客户")
    db.commit()

    review = _svc(db)
    v1 = review.create_snapshot(change_note="初始快照")
    assert v1.version == "v1"
    v2 = review.create_snapshot(change_note="加入属性后")
    assert v2.version == "v2"


def test_snapshot_body_is_complete_frozen_view(db: Session) -> None:
    """快照包含六类实体 + CQ 覆盖度 + OWL 类计数（冻结视图完整性）。"""
    svc = ModelingService(db, TENANT_A)
    svc.add_object_type("customer", "客户")
    svc.add_property("customer", "name", "客户名称")
    svc.add_cq("列出所有客户", linked_object_codes=["customer"])
    db.commit()

    snap = _svc(db).create_snapshot()
    body = snap.snapshot_json
    assert [ot["code"] for ot in body["object_types"]] == ["customer"]
    assert [p["code"] for p in body["properties"]] == ["name"]
    assert body["cqs"][0]["question"] == "列出所有客户"
    assert body["cq_coverage"] == 1.0
    assert body["owl_class_count"] == 0
    # 父引用以 code 冻结（可读、diff 可比），而非内部 id
    svc.add_object_type("vip_customer", "VIP客户", parent_code="customer")
    db.commit()
    snap2 = _svc(db).create_snapshot()
    vip = next(ot for ot in snap2.snapshot_json["object_types"] if ot["code"] == "vip_customer")
    assert vip["parent_code"] == "customer"


def test_snapshot_requires_existing_ontology(db: Session) -> None:
    """空本体（从未有写操作）→ 拒绝快照而非创建空本体行。"""
    with pytest.raises(ValueError, match="本体不存在"):
        _svc(db, TENANT_B).create_snapshot()
    # 且没有因这次失败创建本体行
    from sqlalchemy import text

    n = db.execute(
        text("SELECT count(*) FROM ontology WHERE tenant_id = :t"), {"t": TENANT_B}
    ).scalar()
    assert n == 0


def test_diff_snapshots_traces_changes(db: Session) -> None:
    """变更可追溯：对象类型的 added / status_changed 在 diff 中可见。"""
    svc = ModelingService(db, TENANT_A)
    svc.add_object_type("customer", "客户", status="suggested")
    db.commit()
    review = _svc(db)
    review.create_snapshot(change_note="候选落定")

    svc.add_object_type("contract", "合同")            # added
    svc.update_object_type_status("customer", "accepted")  # status_changed
    db.commit()
    review.create_snapshot(change_note="评审通过")

    diff = review.diff_snapshots("v1", "v2").to_dict()
    added = {c["key"] for c in diff["changes"]["object_types"]["added"]}
    assert added == {"contract"}
    changed = diff["changes"]["object_types"]["status_changed"]
    assert any(c["key"] == "customer" and c["from"] == "suggested" and c["to"] == "accepted"
               for c in changed)


def test_list_and_get_snapshots(db: Session) -> None:
    svc = ModelingService(db, TENANT_A)
    svc.add_object_type("customer", "客户")
    db.commit()
    review = _svc(db)
    review.create_snapshot()
    review.create_snapshot()

    rows = review.list_snapshots()
    assert [r[1] for r in rows] == ["v2", "v1"]  # 倒序

    full = review.get_snapshot("v1")
    assert full is not None and full.snapshot_json["object_types"] != []
    assert review.get_snapshot("v999") is None


def test_snapshot_tenant_isolated(db: Session) -> None:
    """快照按租户隔离：B 的快照链不含 A 的内容。"""
    ModelingService(db, TENANT_A).add_object_type("customer", "客户A")
    db.commit()
    _svc(db, TENANT_A).create_snapshot()

    review_b = _svc(db, TENANT_B)
    assert review_b.list_snapshots() == []
    with pytest.raises(ValueError, match="本体不存在"):
        review_b.create_snapshot()


def test_no_rollback_api(db: Session) -> None:
    """回滚不在本阶段（P4 计划 Task 6 明确）：不得存在回滚/恢复接口。

    未来引入回滚时，本用例必须被**显式修改**（连同设计评审），
    而不是静默通过。
    """
    import app.services.ontology.review_service as review_module

    svc = _svc(db)
    for banned in ("rollback", "rollback_to_version", "restore", "restore_snapshot"):
        assert not hasattr(review_module, banned), f"review_service 不应有 {banned}"
        assert not hasattr(svc, banned), f"OntologyReviewService 不应有 {banned}"
