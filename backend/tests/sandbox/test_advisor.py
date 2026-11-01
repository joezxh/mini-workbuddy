"""Task 7：AI 顾问（S20）——确定性证据三法 + LLM 解释降级 + 零写路径（A8）。"""
import inspect
from pathlib import Path

import pytest

from app.models.ontology.ontology import MetaOntology
from app.models.sandbox.sandbox import (
    SandboxBranch, SandboxElement, SandboxEntity, SandboxObservation, SandboxScene,
)
from app.services.sandbox.sandbox_advisor_service import SandboxAdvisorService
from tests.sandbox.conftest import TENANT_A

ADVISOR_SRC = Path(inspect.getfile(SandboxAdvisorService))


def _ent(branch_id, scene_id, code, obj, props, risk, masked=False):
    return SandboxEntity(tenant_id=TENANT_A, scene_id=scene_id, branch_id=branch_id,
                         entity_code=code, object_code=obj, props_json=props,
                         risk_score=risk, masked=masked, origin="clone")


@pytest.fixture
def world(db):
    """场景 + 基线分支 + 3 实体 + 2 accepted 因果边/规则 + engine 观察若干（供三证据法取数）。"""
    on = MetaOntology(tenant_id=TENANT_A, code="O_ADV", name="供应链", status="published",
                      current_version=1)
    db.add(on)
    db.flush()
    scene = SandboxScene(tenant_id=TENANT_A, ontology_id=on.id, ontology_version=1,
                         name="断供传导", exec_mode="auto", tick_max=12, status="running")
    db.add(scene)
    db.flush()
    br = SandboxBranch(tenant_id=TENANT_A, scene_id=scene.id, name="基线分支", tick_now=3)
    db.add(br)
    db.flush()
    db.add_all([
        _ent(br.id, scene.id, "SUP006", "Supplier", {"supply_cut": "1"}, 0.9),
        _ent(br.id, scene.id, "FAC007", "Factory", {"capacity": "62.0000"}, 0.5),
        _ent(br.id, scene.id, "ORD012", "Order", {"delay": "1"}, 0.3),
    ])
    db.add_all([
        SandboxElement(tenant_id=TENANT_A, scene_id=scene.id, kind="causal_edge", code="CE-1",
                       label="断供→减产", from_ref="SUP006", to_ref="FAC007.capacity",
                       status="accepted", origin="human"),
        SandboxElement(tenant_id=TENANT_A, scene_id=scene.id, kind="causal_edge", code="CE-2",
                       label="减产→延迟", from_ref="FAC007", to_ref="ORD012.delay",
                       status="accepted", origin="human"),
    ])
    db.add_all([
        SandboxObservation(tenant_id=TENANT_A, scene_id=scene.id, branch_id=br.id, tick=1,
                           kind="edge_fired", severity="warn", title="CE-1 命中",
                           detail_json={"element_code": "CE-1", "from": "SUP006", "to": "FAC007.capacity"},
                           source="engine"),
        SandboxObservation(tenant_id=TENANT_A, scene_id=scene.id, branch_id=br.id, tick=2,
                           kind="kpi_point", severity="info", title="Tick2 KPI",
                           detail_json={"health": "0.4333", "controllability": "0.0000"}, source="engine"),
    ])
    db.commit()
    return {"scene_id": scene.id, "branch_id": br.id}


@pytest.fixture
def svc(db):
    return SandboxAdvisorService(db, TENANT_A)


def test_ask_degrades_without_llm(db, svc, world, monkeypatch):
    monkeypatch.setattr("app.services.sandbox.sandbox_advisor_service.llm_json",
                        lambda p, model_id=None: (_ for _ in ()).throw(RuntimeError("down")))
    r = svc.ask(world["scene_id"], world["branch_id"], "风险如何从 SUP006 传到 ORD012")
    assert r["degraded"] is True and r["answer"]
    assert r["cited_evidence"] == []


def test_ask_cites_trace_only_real_entities(db, svc, world, monkeypatch):
    monkeypatch.setattr("app.services.sandbox.sandbox_advisor_service.llm_json",
                        lambda p, model_id=None: {"answer": "SUP006→FAC007→ORD012",
                                                  "cited_evidence": [1, 2, 3, 9]})
    r = svc.ask(world["scene_id"], world["branch_id"], "风险如何传导")
    assert r["degraded"] is False
    assert set(r["cited_evidence"]) <= {1, 2, 3}
    # 证据世界须只引用真实存在的实体（不编造）
    ev = svc._evidence_world(world["scene_id"], world["branch_id"])
    for code in ("SUP006", "FAC007", "ORD012"):
        assert code in ev


def test_advisor_has_no_write_methods():
    """A8/隔离面：顾问服务源码不得含任何 DB 写语义。"""
    src = ADVISOR_SRC.read_text(encoding="utf-8")
    for forbidden in ("db.add", "db.delete", "db.execute(update", "db.execute(delete",
                      "self.db.query("):
        assert forbidden not in src, f"顾问源码出现写路径: {forbidden}"
