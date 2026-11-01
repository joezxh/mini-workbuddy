"""Task 6：行动门禁六步求值 + stepwise 两段式确认测试（A3/A4/A5）。"""
from datetime import datetime

import pytest
from sqlalchemy import select

from app.core.api_error import ApiError
from app.models.ontology.ontology import MetaOntology
from app.models.sandbox.action_template import SandboxActionTemplate
from app.models.sandbox.sandbox import SandboxAction, SandboxBranch, SandboxEntity, SandboxScene
from app.services.sandbox.sandbox_action_service import SandboxActionService
from types import SimpleNamespace
from tests.sandbox.conftest import TENANT_A


def _build(db, exec_mode, *, permission=True, extra_disabled=False):
    import uuid
    on = MetaOntology(tenant_id=TENANT_A, code=f"O_{exec_mode}_{uuid.uuid4().hex[:6]}", name="供应链",
                      status="published", current_version=1)
    db.add(on)
    db.flush()
    scene = SandboxScene(tenant_id=TENANT_A, ontology_id=on.id, ontology_version=1,
                         name="断供", exec_mode=exec_mode, tick_max=12, status="running")
    db.add(scene)
    db.flush()
    br = SandboxBranch(tenant_id=TENANT_A, scene_id=scene.id, name="基线", tick_now=0)
    db.add(br)
    db.flush()
    db.add_all([
        SandboxEntity(tenant_id=TENANT_A, scene_id=scene.id, branch_id=br.id, entity_code="SUP006",
                      object_code="Supplier", props_json={"supply_cut": "0", "risk_score": "0.1"},
                      risk_score=0.1, masked=False, origin="clone"),
        SandboxEntity(tenant_id=TENANT_A, scene_id=scene.id, branch_id=br.id, entity_code="MASK001",
                      object_code="Supplier", props_json={"mobile": "***"},
                      risk_score=0.0, masked=True, origin="clone"),
    ])
    if extra_disabled:
        db.add(SandboxActionTemplate(code="ghost_disabled", name="停用模板", status="disabled",
                                     param_schema_json={"type": "object"}, effect_spec_json={"writes": []}))
    db.commit()
    svc = SandboxActionService(db, TENANT_A, user_id=1, has_act_permission=permission)
    return SimpleNamespace(svc=svc, scene_id=scene.id, branch_id=br.id, db=db)


@pytest.fixture
def svc_auto(db):
    return _build(db, "auto")


@pytest.fixture
def svc_step(db):
    return _build(db, "stepwise")


@pytest.fixture
def svc_replay(db):
    return _build(db, "replay")


def _cur(db, branch_id, code):
    return db.execute(select(SandboxEntity).where(
        SandboxEntity.branch_id == branch_id, SandboxEntity.entity_code == code,
        SandboxEntity.checkpoint_id.is_(None))).scalar_one()


def _derived_count(db, branch_id):
    return len(db.execute(select(SandboxEntity.id).where(
        SandboxEntity.branch_id == branch_id, SandboxEntity.origin == "derived",
        SandboxEntity.checkpoint_id.is_(None))).scalars().all())


def _act_count(db):
    return len(db.execute(select(SandboxAction.id).where(
        SandboxAction.tenant_id == TENANT_A)).scalars().all())


def _apply(ns, target="SUP006", code="supply_cut", params=None):
    return ns.svc.apply_action(ns.scene_id, ns.branch_id, template_code=code,
                               target_entity_code=target, params=params or {"ratio": 100})


def test_gate_replay_denied_audited(svc_replay):
    ns = svc_replay
    r = _apply(ns)
    assert r["gate_result"] == "denied" and r["reason"] == "MODE_READONLY" and r["action_id"]
    # 世界无变化
    assert _cur(ns.db, ns.branch_id, "SUP006").props_json["supply_cut"] == "0"
    assert _derived_count(ns.db, ns.branch_id) == 0
    assert ns.db.get(SandboxBranch, ns.branch_id).tick_now == 0


def test_gate_masked_target(svc_auto):
    r = _apply(svc_auto, target="MASK001")
    assert r["gate_result"] == "denied" and r["reason"] == "MASKED_TARGET"
    row = svc_auto.db.execute(select(SandboxAction).where(
        SandboxAction.id == r["action_id"])).scalar_one()
    assert row.gate_result == "denied" and row.gate_reason == "MASKED_TARGET"


def test_gate_template_disabled_no_audit(db):
    ns = _build(db, "auto", extra_disabled=True)
    before = _act_count(db)
    with pytest.raises(ApiError) as exc:
        _apply(ns, code="ghost_disabled")
    assert exc.value.http_status == 400
    assert _act_count(db) == before           # 第 4 步非法请求不入留痕（A5）


def test_stepwise_pending_then_confirm(svc_step):
    ns = svc_step
    r = _apply(ns)
    assert r["gate_result"] == "pending" and r["confirm_token"]
    # 未确认前世界不变（A4）
    assert _cur(ns.db, ns.branch_id, "SUP006").props_json["supply_cut"] == "0"
    assert _derived_count(ns.db, ns.branch_id) == 0
    assert ns.db.get(SandboxBranch, ns.branch_id).tick_now == 0
    out = ns.svc.confirm_action(ns.scene_id, r["action_id"], token=r["confirm_token"])
    assert out["gate_result"] == "allowed" and out["tick_after"] == 1
    assert _derived_count(ns.db, ns.branch_id) >= 1            # SimEvent 已写
    assert _cur(ns.db, ns.branch_id, "SUP006").risk_score == pytest.approx(0.9)


def test_stepwise_confirm_expired(svc_step):
    ns = svc_step
    r = _apply(ns)
    act = ns.db.get(SandboxAction, r["action_id"])
    act.created_at = datetime(2000, 1, 1)      # 远早于 now-300s → 超时
    ns.db.commit()
    with pytest.raises(ApiError) as exc:
        ns.svc.confirm_action(ns.scene_id, r["action_id"], token=r["confirm_token"])
    assert exc.value.code == "CONFIRM_EXPIRED"
    assert ns.db.get(SandboxAction, r["action_id"]).gate_result == "pending"
    assert _derived_count(ns.db, ns.branch_id) == 0            # 超时不生效


def test_auto_writes_world_and_advances(svc_auto):
    ns = svc_auto
    r = _apply(ns)
    assert r["gate_result"] == "allowed" and r["tick_after"] == 1
    assert _cur(ns.db, ns.branch_id, "SUP006").props_json["supply_cut"] == "1.0000"
    assert _cur(ns.db, ns.branch_id, "SUP006").risk_score == pytest.approx(0.9)
    assert _derived_count(ns.db, ns.branch_id) >= 1


def test_denied_always_returns_action_id(db):
    replay = _build(db, "replay")
    noperm = _build(db, "auto", permission=False)
    masked = _build(db, "auto")
    r1 = _apply(replay)
    r2 = _apply(noperm)
    r3 = _apply(masked, target="MASK001")
    assert r1["reason"] == "MODE_READONLY"
    assert r2["reason"] == "NO_ACTION_PERMISSION"
    assert r3["reason"] == "MASKED_TARGET"
    assert all(x["action_id"] for x in (r1, r2, r3))            # 三种 denied 均审计闭环
