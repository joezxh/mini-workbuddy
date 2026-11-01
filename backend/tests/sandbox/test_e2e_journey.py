"""Task 8：端到端旅程（spec §6 五旅程合体）+ A1–A8 验收断言 CI 化（动态面）。

静态隔离扫描见 test_isolation_static.py（A7）。本文件覆盖 A1/A2/A3/A4/A5/A6/A8。
"""
import hashlib
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text

from app.core.api_error import ApiError
from app.models.ontology.ontology import MetaOntology
from app.models.sandbox.sandbox import (
    SandboxAction, SandboxBranch, SandboxCheckpoint, SandboxEntity,
    SandboxObservation, SandboxScene,
)
from app.services.sandbox.sandbox_action_service import SandboxActionService
from app.services.sandbox.sandbox_advisor_service import SandboxAdvisorService
from app.services.sandbox.sandbox_element_service import SandboxElementService
from app.services.sandbox.sandbox_engine_service import SandboxEngineService
from tests.sandbox.conftest import TENANT_A

# AST 节点辅助（受控文法：prop/num + 比较返回 bool）
_P = lambda e, k: {"op": "prop", "entity": e, "key": k}  # noqa: E731
_N = lambda v: {"op": "num", "v": v}  # noqa: E731
_CMP = lambda o, a, b: {"op": o, "a": a, "b": b}  # noqa: E731

_ELEMENTS = [
    {"kind": "causal_edge", "code": "CE-001", "label": "断供→减产", "from_ref": "SUP006",
     "to_ref": "FAC007.capacity",
     "condition_expr_json": _CMP("eq", _P("SUP006", "supply_cut"), _N("1")),
     "effect_expr_json": {"op": "mul", "a": _P("FAC007", "capacity"), "b": _N("0.62")}},
    {"kind": "causal_edge", "code": "CE-002", "label": "减产→风险", "from_ref": "FAC007",
     "to_ref": "ORD012.risk_score",
     "condition_expr_json": _CMP("lt", _P("FAC007", "capacity"), _N("50")),
     "effect_expr_json": _N("0.9")},
    {"kind": "rule", "code": "R-001", "label": "断供告警",
     "condition_expr_json": _CMP("ge", _P("SUP006", "supply_cut"), _N("1"))},
    {"kind": "goal", "code": "G-01", "label": "交付保障",
     "condition_expr_json": _CMP("lt", _P("ORD012", "risk_score"), _N("0.5"))},
]


def _ent(branch_id, scene_id, code, obj, props, risk, masked=False):
    return SandboxEntity(tenant_id=TENANT_A, scene_id=scene_id, branch_id=branch_id,
                         entity_code=code, object_code=obj, props_json=props,
                         risk_score=risk, masked=masked, origin="clone")


def bootstrap(db, exec_mode="auto", *, with_masked=False):
    """造可跑场景 + 基线分支 + 3 实体（+可选 masked）；元素由调用方按 S13/S15 配。"""
    on = MetaOntology(tenant_id=TENANT_A, code=f"O_J_{exec_mode}", name="供应链",
                      status="published", current_version=1)
    db.add(on)
    db.flush()
    scene = SandboxScene(tenant_id=TENANT_A, ontology_id=on.id, ontology_version=1,
                         name="断供传导", exec_mode=exec_mode, tick_max=12, status="running")
    db.add(scene)
    db.flush()
    br = SandboxBranch(tenant_id=TENANT_A, scene_id=scene.id, name="基线分支", tick_now=0)
    db.add(br)
    db.flush()
    rows = [
        _ent(br.id, scene.id, "SUP006", "Supplier", {"supply_cut": "0"}, 0.1),
        _ent(br.id, scene.id, "FAC007", "Factory", {"capacity": "100.0000"}, 0.5),
        _ent(br.id, scene.id, "ORD012", "Order", {}, 0.1),
    ]
    if with_masked:
        rows.append(_ent(br.id, scene.id, "MASK999", "Supplier", {"mobile": "***"}, 0.0, masked=True))
    db.add_all(rows)
    db.commit()
    return SimpleNamespace(
        scene_id=scene.id, branch_id=br.id, db=db,
        eng=SandboxEngineService(db, TENANT_A),
        elem=SandboxElementService(db, TENANT_A),
        act=SandboxActionService(db, TENANT_A, user_id=1),
        adv=SandboxAdvisorService(db, TENANT_A))


def _add_accepted(ns, payload):
    e = ns.elem.upsert_element(ns.scene_id, payload, origin="human", creator_id=1)
    return ns.elem.review_element(e["id"], "accept")


def _load_elements(ns):
    for p in _ELEMENTS:
        _add_accepted(ns, p)


def _cur_props(db, branch_id, code):
    r = db.execute(select(SandboxEntity).where(
        SandboxEntity.branch_id == branch_id, SandboxEntity.entity_code == code,
        SandboxEntity.checkpoint_id.is_(None))).scalar_one()
    return r.props_json, float(r.risk_score)


def _obs_codes(db, branch_id, kind):
    return {o.detail_json.get("element_code") or o.detail_json.get("goal_code")
            for o in db.execute(select(SandboxObservation).where(
                SandboxObservation.branch_id == branch_id,
                SandboxObservation.kind == kind)).scalars().all()}


def _fp(db, branch_id):
    rows = db.execute(select(SandboxObservation).where(
        SandboxObservation.branch_id == branch_id).order_by(
        SandboxObservation.tick, SandboxObservation.id)).scalars().all()
    blob = json.dumps([(o.kind, o.tick, o.title, o.detail_json) for o in rows],
                      sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


# ------------------------------------------------------------------- 旅程 2+4+5 合体

def test_journey_supply_cut_full_chain(db):
    ns = bootstrap(db, "auto", with_masked=True)
    _load_elements(ns)
    # 仅 accepted 参与引擎（D3/A8：人审采纳后 load_accepted 命中）
    assert {x["code"] for x in ns.elem.load_accepted(ns.scene_id)} == {"CE-001", "CE-002", "R-001", "G-01"}

    # S17 断供 SUP006 → auto 放行，改写生效并推进
    r = ns.act.apply_action(ns.scene_id, ns.branch_id, template_code="supply_cut",
                            target_entity_code="SUP006", params={"ratio": 100})
    assert r["gate_result"] == "allowed" and r["tick_after"] == 1
    props, _ = _cur_props(db, ns.branch_id, "SUP006")
    assert props["supply_cut"] == "1.0000"

    # S8 再推进 4 Tick（累计 5）
    ns.eng.advance(ns.scene_id, ns.branch_id, 4)
    assert db.get(SandboxBranch, ns.branch_id).tick_now == 5
    fac_props, _ = _cur_props(db, ns.branch_id, "FAC007")
    assert float(fac_props["capacity"]) < 100.0                           # 产能下降
    assert _obs_codes(db, ns.branch_id, "edge_fired") >= {"CE-001", "CE-002"}
    assert "R-001" in _obs_codes(db, ns.branch_id, "rule_fired")
    assert "G-01" in _obs_codes(db, ns.branch_id, "goal_eval")

    # S21 健康度单调不增（风险累积）
    kpis = ns.eng.list_kpis(ns.scene_id, ns.branch_id)
    health = [float(k["detail_json"]["health"]) for k in kpis if k["kind"] == "kpi_point"]
    assert health and all(health[i] >= health[i + 1] for i in range(len(health) - 1))

    # S18 审计含 allowed 行动行
    audit = ns.act.list_actions(ns.scene_id, branch_id=ns.branch_id, result="allowed")
    assert any(a["gate_result"] == "allowed" for a in audit)

    # 异常路径：masked 目标被拒并审计
    masked = ns.act.apply_action(ns.scene_id, ns.branch_id, template_code="supply_cut",
                                 target_entity_code="MASK999", params={"ratio": 100})
    assert masked["gate_result"] == "denied" and masked["reason"] == "MASKED_TARGET"
    # 推进超窗口 → 400
    with pytest.raises(ApiError) as exc:
        ns.eng.advance(ns.scene_id, ns.branch_id, 8)             # 5+8 > tick_max 12
    assert exc.value.http_status == 400


# ------------------------------------------------------------------- A1 可复现回放

def test_acceptance_a1_replay_identity(db):
    ns = bootstrap(db, "auto")
    _load_elements(ns)
    ns.eng.save_checkpoint(ns.scene_id, ns.branch_id, "基线")     # seq=0 供 replay 复位
    ns.act.apply_action(ns.scene_id, ns.branch_id, template_code="supply_cut",
                        target_entity_code="SUP006", params={"ratio": 100})
    ns.eng.advance(ns.scene_id, ns.branch_id, 5)                 # 累计 6 Tick
    fp1 = _fp(db, ns.branch_id)
    ns.eng.replay_to(ns.scene_id, ns.branch_id, 0)
    ns.act.apply_action(ns.scene_id, ns.branch_id, template_code="supply_cut",
                        target_entity_code="SUP006", params={"ratio": 100})
    ns.eng.advance(ns.scene_id, ns.branch_id, 5)
    assert _fp(db, ns.branch_id) == fp1                          # 逐 Tick 指纹一致


# ------------------------------------------------------------------- A2 不写生产域

def _prod_snapshot(db):
    from app.db.database import Base
    out = {}
    for t in Base.metadata.sorted_tables:
        name = t.name
        if name.startswith("onto_sandbox") or name == "onto_action_template":
            continue
        if name.startswith("meta_") or name.startswith("onto_ontology"):
            row = db.execute(text(
                f'SELECT count(*), coalesce(md5(string_agg(x::text, \'|\' ORDER BY x::text)),\'\') '
                f'FROM "{name}" x')).one()
            out[name] = (row[0], row[1])
    return out


def test_acceptance_a2_no_production_writes(db):
    from app.services.sandbox.sandbox_clone_service import SandboxCloneService
    from app.services.sandbox.sandbox_scene_service import SandboxSceneService
    from tests.sandbox.test_scene_clone import _seed_published_ontology

    oid = _seed_published_ontology(db)
    before = _prod_snapshot(db)

    recorded = []

    def fake_fetcher(source_id, sql, limit):
        recorded.append(sql)
        return {"columns": ["supp_name", "mobile"],
                "rows": [["甲厂", "***"], ["乙厂", "***"]],
                "row_count": 2, "truncated": False}

    res = SandboxSceneService(db, TENANT_A).create_scene(
        ontology_id=oid, name="断供", clone_scope={"object_codes": ["Supplier"]})
    sid = res["scene_id"]
    db.get(SandboxScene, sid).status = "draft"
    db.commit()
    SandboxCloneService(db, TENANT_A, fetcher=fake_fetcher).clone_scene(sid)

    # 沙箱内推演（只写 onto_sandbox_*）
    br = db.execute(select(SandboxBranch).where(SandboxBranch.scene_id == sid)).scalar_one()
    db.add_all([
        _ent(br.id, sid, "SUP006", "Supplier", {"supply_cut": "1"}, 0.5),
        _ent(br.id, sid, "FAC007", "Factory", {"capacity": "100.0000"}, 0.5),
    ])
    db.commit()
    eng = SandboxEngineService(db, TENANT_A)
    _add_accepted(SimpleNamespace(scene_id=sid, elem=SandboxElementService(db, TENANT_A)),
                  _ELEMENTS[0])
    eng.advance(sid, br.id, 2)

    after = _prod_snapshot(db)
    assert before == after                                       # 生产域逐表 count+md5 无变化
    assert recorded and all(s.upper().lstrip().startswith("SELECT") for s in recorded)


# ------------------------------------------------------------------- A3 脱敏目标被拒

def test_acceptance_a3_masked_denied_audited(db):
    ns = bootstrap(db, "auto", with_masked=True)
    r = ns.act.apply_action(ns.scene_id, ns.branch_id, template_code="supply_cut",
                            target_entity_code="MASK999", params={"ratio": 100})
    assert r["gate_result"] == "denied" and r["reason"] == "MASKED_TARGET"
    row = db.get(SandboxAction, r["action_id"])
    assert row.gate_result == "denied" and row.gate_reason == "MASKED_TARGET"
    props, _ = _cur_props(db, ns.branch_id, "MASK999")
    assert props == {"mobile": "***"}                            # 世界未被篡改


# ------------------------------------------------------------------- A4 未确认不改世界

def test_acceptance_a4_stepwise_pending_no_world_change(db):
    ns = bootstrap(db, "stepwise")
    _load_elements(ns)
    r = ns.act.apply_action(ns.scene_id, ns.branch_id, template_code="supply_cut",
                            target_entity_code="SUP006", params={"ratio": 100})
    assert r["gate_result"] == "pending"
    props, _ = _cur_props(db, ns.branch_id, "SUP006")
    assert props["supply_cut"] == "0"                            # 未确认前不改世界
    assert db.get(SandboxBranch, ns.branch_id).tick_now == 0
    out = ns.act.confirm_action(ns.scene_id, r["action_id"], token=r["confirm_token"])
    assert out["gate_result"] == "allowed"
    assert _cur_props(db, ns.branch_id, "SUP006")[0]["supply_cut"] == "1.0000"


# ------------------------------------------------------------------- A5 检查点上限 + 依赖保护

def test_acceptance_a5_checkpoint_limit_and_dependency(db):
    ns = bootstrap(db, "auto")
    for i in range(5):
        ns.eng.save_checkpoint(ns.scene_id, ns.branch_id, f"CP{i}")
    with pytest.raises(ApiError) as exc:
        ns.eng.save_checkpoint(ns.scene_id, ns.branch_id, "超限")
    assert exc.value.code == "CHECKPOINT_LIMIT"

    cp = db.execute(select(SandboxCheckpoint).where(
        SandboxCheckpoint.scene_id == ns.scene_id)).scalars().first()
    ns.eng.derive_branch(ns.scene_id, cp.id, "派生分支")
    with pytest.raises(ApiError) as exc2:                        # 有派生依赖不可删
        ns.eng.delete_checkpoint(cp.id)
    assert exc2.value.http_status == 400


# ------------------------------------------------------------------- A6 对比聚合自观察

def test_acceptance_a6_compare_from_observations(db):
    ns = bootstrap(db, "auto")
    _load_elements(ns)
    ns.eng.save_checkpoint(ns.scene_id, ns.branch_id, "基线")
    base = db.execute(select(SandboxCheckpoint).where(
        SandboxCheckpoint.scene_id == ns.scene_id, SandboxCheckpoint.seq == 0)).scalar_one()
    ns.act.apply_action(ns.scene_id, ns.branch_id, template_code="supply_cut",
                        target_entity_code="SUP006", params={"ratio": 100})   # 干预分支
    ns.eng.advance(ns.scene_id, ns.branch_id, 2)
    d = ns.eng.derive_branch(ns.scene_id, base.id, "未干预分支")
    ns.eng.advance(ns.scene_id, d["branch_id"], 3)                            # 对照分支
    cmp = ns.eng.compare(ns.scene_id, [ns.branch_id, d["branch_id"]])
    assert len(cmp["branches"]) == 2
    # 每分支终值 health 直接取自 kpi_point 观察（引擎无额外计算，A6）
    for row in cmp["diff_table"]:
        last = db.get(SandboxBranch, row["branch_id"]).tick_now
        obs = db.execute(select(SandboxObservation).where(
            SandboxObservation.branch_id == row["branch_id"],
            SandboxObservation.kind == "kpi_point",
            SandboxObservation.tick == last)).scalar_one()
        assert row["branch_a_final"] == obs.detail_json["health"]


# ------------------------------------------------------------------- A8 顾问只读 + D3

def test_acceptance_a8_advisor_readonly_and_d3(db, monkeypatch):
    monkeypatch.setattr("app.services.sandbox.sandbox_advisor_service.llm_json",
                        lambda p, model_id=None: (_ for _ in ()).throw(RuntimeError("down")))
    ns = bootstrap(db, "auto")
    _load_elements(ns)
    ns.act.apply_action(ns.scene_id, ns.branch_id, template_code="supply_cut",
                        target_entity_code="SUP006", params={"ratio": 100})
    ns.eng.advance(ns.scene_id, ns.branch_id, 2)
    answer = ns.adv.ask(ns.scene_id, ns.branch_id, "风险如何传导")
    assert answer["degraded"] is True
    for code in ("SUP006", "FAC007", "ORD012"):
        assert code in answer["answer"]                          # 只引用真实实体（可溯源）
    # D3：llm 候选未经人审不进引擎
    llm = ns.elem.upsert_element(ns.scene_id, {"kind": "rule", "code": "R-LLM", "label": "LLM 候选",
                                               "condition_expr_json": _CMP("ge", _P("SUP006", "supply_cut"), _N("1"))},
                                 origin="llm")
    assert llm["status"] == "suggested" and llm["origin"] == "llm"
    assert "R-LLM" not in {x["code"] for x in ns.elem.load_accepted(ns.scene_id)}
