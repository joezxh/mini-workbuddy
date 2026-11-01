"""Task 5：确定性 Tick 引擎测试（A1 可复现 / 传播 / 检查点上限 / 派生 / 回放 / 对比 / A5/A6）。"""
import json

import pytest
from sqlalchemy import select

from app.core.api_error import ApiError
from app.models.ontology.ontology import MetaOntology
from app.models.sandbox.sandbox import (
    SandboxBranch, SandboxCheckpoint, SandboxElement, SandboxEntity,
    SandboxObservation, SandboxScene,
)
from app.services.sandbox.sandbox_engine_service import SandboxEngineService
from tests.sandbox.conftest import TENANT_A


def _ent(branch_id, scene_id, code, obj, props, risk, cp=None):
    return SandboxEntity(tenant_id=TENANT_A, scene_id=scene_id, branch_id=branch_id,
                         checkpoint_id=cp, entity_code=code, object_code=obj,
                         props_json=props, risk_score=risk, masked=False, origin="clone")


@pytest.fixture
def world(db):
    """3 实体（SUP006 断供/FAC007 产能/LOG008）+ 2 accepted 元素 + 基线分支/检查点 seq=0。"""
    on = MetaOntology(tenant_id=TENANT_A, code="O_ENG", name="供应链", status="published",
                      current_version=1)
    db.add(on)
    db.flush()
    scene = SandboxScene(tenant_id=TENANT_A, ontology_id=on.id, ontology_version=1,
                         name="断供传导", exec_mode="auto", tick_max=12, status="running")
    db.add(scene)
    db.flush()
    br = SandboxBranch(tenant_id=TENANT_A, scene_id=scene.id, name="基线分支", tick_now=0)
    db.add(br)
    db.flush()
    cur = [
        _ent(br.id, scene.id, "SUP006", "Supplier", {"supply_cut": "1"}, 0.5),
        _ent(br.id, scene.id, "FAC007", "Factory", {"capacity": "100.0000"}, 0.5),
        _ent(br.id, scene.id, "LOG008", "Logistics", {"on_time": "0.9"}, 0.2),
    ]
    db.add_all(cur)
    # 基线检查点 seq=0 + 其快照行（供 replay 复位）
    base = SandboxCheckpoint(tenant_id=TENANT_A, scene_id=scene.id, branch_id=br.id,
                             tick=0, seq=0, label="基线快照")
    db.add(base)
    db.flush()
    db.add_all([
        _ent(br.id, scene.id, "SUP006", "Supplier", {"supply_cut": "1"}, 0.5, cp=base.id),
        _ent(br.id, scene.id, "FAC007", "Factory", {"capacity": "100.0000"}, 0.5, cp=base.id),
        _ent(br.id, scene.id, "LOG008", "Logistics", {"on_time": "0.9"}, 0.2, cp=base.id),
    ])
    ce = SandboxElement(
        tenant_id=TENANT_A, scene_id=scene.id, kind="causal_edge", code="CE-1",
        label="断供→减产", from_ref="SUP006", to_ref="FAC007.capacity", status="accepted",
        origin="human",
        condition_expr_json={"op": "eq", "a": {"op": "prop", "entity": "SUP006", "key": "supply_cut"},
                             "b": {"op": "num", "v": "1"}},
        effect_expr_json={"op": "mul", "a": {"op": "prop", "entity": "FAC007", "key": "capacity"},
                          "b": {"op": "num", "v": "0.62"}})
    rule = SandboxElement(
        tenant_id=TENANT_A, scene_id=scene.id, kind="rule", code="R-1", label="断供告警",
        status="accepted", origin="human",
        condition_expr_json={"op": "ge", "a": {"op": "prop", "entity": "SUP006", "key": "supply_cut"},
                             "b": {"op": "num", "v": "1"}})
    db.add_all([ce, rule])
    db.commit()
    return {"scene_id": scene.id, "branch_id": br.id, "baseline_cp": base.id}


def _fac_capacity(db, branch_id):
    r = db.execute(select(SandboxEntity).where(
        SandboxEntity.branch_id == branch_id, SandboxEntity.entity_code == "FAC007",
        SandboxEntity.checkpoint_id.is_(None))).scalar_one()
    return r.props_json["capacity"]


def _obs_fp(db, branch_id):
    rows = db.execute(select(SandboxObservation).where(
        SandboxObservation.branch_id == branch_id).order_by(
        SandboxObservation.tick, SandboxObservation.id)).scalars().all()
    return [(o.kind, o.tick, o.title, json.dumps(o.detail_json, sort_keys=True)) for o in rows]


def _count_kind(db, branch_id, kind):
    return len(db.execute(select(SandboxObservation.id).where(
        SandboxObservation.branch_id == branch_id,
        SandboxObservation.kind == kind)).scalars().all())


def test_supply_cut_propagation(db, world):
    eng = SandboxEngineService(db, TENANT_A)
    res = eng.advance(world["scene_id"], world["branch_id"], 3)
    assert res["tick_after"] == 3
    # Decimal 量化 4 位：100 →62.0000 →38.4400 →23.8328
    assert _fac_capacity(db, world["branch_id"]) == "23.8328"
    assert _count_kind(db, world["branch_id"], "edge_fired") == 3
    assert _count_kind(db, world["branch_id"], "rule_fired") == 3
    assert _count_kind(db, world["branch_id"], "kpi_point") == 3
    assert _count_kind(db, world["branch_id"], "risk_point") == 3


def test_run_tick_deterministic(db, world):
    eng = SandboxEngineService(db, TENANT_A)
    eng.advance(world["scene_id"], world["branch_id"], 3)
    fp1 = _obs_fp(db, world["branch_id"])
    cap1 = _fac_capacity(db, world["branch_id"])
    # 回放复位到 0 再推进 3：逐 Tick observation 序列与实体终态完全一致（A1）
    eng.replay_to(world["scene_id"], world["branch_id"], 0)
    eng.advance(world["scene_id"], world["branch_id"], 3)
    fp2 = _obs_fp(db, world["branch_id"])
    assert fp1 == fp2
    assert _fac_capacity(db, world["branch_id"]) == cap1 == "23.8328"


def test_checkpoint_limit_and_derive(db, world):
    eng = SandboxEngineService(db, TENANT_A)
    sid, bid = world["scene_id"], world["branch_id"]
    for i in range(4):                    # 基线占 1 格 → 再存 4 个成功（合计 5）
        eng.save_checkpoint(sid, bid, f"T快照{i}")
    with pytest.raises(ApiError) as exc:  # 第 6 个（合计）被拒
        eng.save_checkpoint(sid, bid, "超限")
    assert exc.value.code == "CHECKPOINT_LIMIT"
    before = len(db.execute(select(SandboxEntity).where(
        SandboxEntity.branch_id == bid, SandboxEntity.checkpoint_id.is_(None))).scalars().all())
    tick0 = db.get(SandboxBranch, bid).tick_now
    d = eng.derive_branch(sid, world["baseline_cp"], "平行分支B")
    assert d["branch_id"] != bid and d["restored_entities"] == 3
    after = len(db.execute(select(SandboxEntity).where(
        SandboxEntity.branch_id == bid, SandboxEntity.checkpoint_id.is_(None))).scalars().all())
    assert after == before and db.get(SandboxBranch, bid).tick_now == tick0  # 原分支不变（A5）


def test_delete_checkpoint_with_dependent_branch_rejected(db, world):
    eng = SandboxEngineService(db, TENANT_A)
    eng.derive_branch(world["scene_id"], world["baseline_cp"], "依赖分支")
    with pytest.raises(ApiError) as exc:
        eng.delete_checkpoint(world["baseline_cp"])
    assert exc.value.http_status == 400


def test_compare_series_from_observations(db, world):
    eng = SandboxEngineService(db, TENANT_A)
    sid = world["scene_id"]
    b1 = world["branch_id"]
    eng.advance(sid, b1, 2)
    d = eng.derive_branch(sid, world["baseline_cp"], "分支二")
    eng.advance(sid, d["branch_id"], 2)
    cmp = eng.compare(sid, [b1, d["branch_id"]])
    assert len(cmp["branches"]) == 2
    assert len(cmp["series"]) == 2                     # tick 1,2
    # series 的 health 直接来自 kpi_point observation（引擎产出，非前端计算，A6）
    kpi = db.execute(select(SandboxObservation).where(
        SandboxObservation.branch_id == b1, SandboxObservation.kind == "kpi_point",
        SandboxObservation.tick == 1)).scalar_one()
    assert cmp["series"][0]["values"][b1]["health"] == kpi.detail_json["health"]
