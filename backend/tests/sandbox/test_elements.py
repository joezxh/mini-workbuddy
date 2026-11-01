"""Task 4：配置元素与 D3 审阅测试（S13–S15）。

D3 防线（spec §0-V2 / §3.6 / §4.2 S15）：``origin='llm'`` 只能 ``status='suggested'``
（数据库级 CHECK 兜底）；人审采纳 = 把候选**转为 human 署名的 accepted 元素**
（而非把 llm 行直接置 accepted，否则违反 CHECK），仅 accepted 参与引擎求值。
"""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.api_error import ApiError
from app.models.ontology.ontology import MetaOntology
from app.models.sandbox.sandbox import SandboxElement, SandboxScene
from app.services.sandbox.sandbox_element_service import SandboxElementService
from tests.sandbox.conftest import TENANT_A


@pytest.fixture
def sc(db):
    """建一个 running 场景（元素需合法 scene_id FK）。"""
    on = MetaOntology(tenant_id=TENANT_A, code="O_EL", name="供应链",
                      status="published", current_version=1)
    db.add(on)
    db.flush()
    s = SandboxScene(tenant_id=TENANT_A, ontology_id=on.id, ontology_version=1,
                     name="断供传导", status="running")
    db.add(s)
    db.commit()
    return s.id


@pytest.fixture
def svc(db):
    return SandboxElementService(db, TENANT_A)


def test_llm_origin_forced_suggested(svc, sc):
    e = svc.upsert_element(sc, {"kind": "causal_edge", "code": "CE-1",
                                "label": "断供→减产", "from_ref": "SUP006",
                                "to_ref": "FAC007"}, origin="llm")
    assert e["status"] == "suggested"           # V2：llm 永不自动采纳
    assert e["origin"] == "llm"


def test_human_candidate_then_accept(svc, sc):
    e = svc.upsert_element(sc, {"kind": "rule", "code": "R-1", "label": "库存红线"},
                           origin="human")
    assert svc.load_accepted(sc) == []          # 新建默认 suggested，未生效
    svc.review_element(e["id"], "accept")
    assert [x["code"] for x in svc.load_accepted(sc)] == ["R-1"]


def test_adopt_llm_flips_origin_to_human(svc, sc):
    e = svc.upsert_element(sc, {"kind": "goal", "code": "G-1", "label": "保供 95%"},
                           origin="llm")
    assert e["origin"] == "llm" and e["status"] == "suggested"
    out = svc.review_element(e["id"], "accept")   # D3 采纳执行点：转 human
    assert out["origin"] == "human" and out["status"] == "accepted"
    assert [x["code"] for x in svc.load_accepted(sc)] == ["G-1"]
    # 数据库 CHECK 未被违反：不存在 origin='llm' 且 status<>'suggested' 的行
    row = svc.db.get(SandboxElement, e["id"])
    assert not (row.origin == "llm" and row.status != "suggested")


def test_review_non_suggested_rejected_400(svc, sc):
    e = svc.upsert_element(sc, {"kind": "rule", "code": "R-9", "label": "重复审阅"},
                           origin="human")
    svc.review_element(e["id"], "accept")
    with pytest.raises(ApiError) as exc:
        svc.review_element(e["id"], "accept")     # 已是 accepted → 重复审阅 400
    assert exc.value.http_status == 400


def test_upsert_overwrites_non_empty_fields(svc, sc):
    svc.upsert_element(sc, {"kind": "rule", "code": "R-1", "label": "旧名"}, origin="human")
    e2 = svc.upsert_element(sc, {"kind": "rule", "code": "R-1", "label": "新名"},
                            origin="human")
    rows = svc.db.execute(select(SandboxElement).where(
        SandboxElement.scene_id == sc, SandboxElement.code == "R-1")).scalars().all()
    assert len(rows) == 1                          # 覆盖而非新增
    assert e2["label"] == "新名"


def test_load_accepted_sorted(svc, sc):
    for code in ("R-2", "R-1", "R-10"):
        e = svc.upsert_element(sc, {"kind": "rule", "code": code, "label": code},
                               origin="human")
        svc.review_element(e["id"], "accept")
    # 固定序 (kind, code) 字符串元组排序：R-1 < R-10 < R-2（A1 前提）
    assert [x["code"] for x in svc.load_accepted(sc)] == ["R-1", "R-10", "R-2"]


def test_draft_rejects_bad_ast(svc, sc, monkeypatch):
    fake = {"elements": [
        {"kind": "causal_edge", "code": "CE-BAD", "label": "坏",
         "effect_expr_json": {"op": "system", "cmd": "x"}},
        {"kind": "causal_edge", "code": "CE-OK", "label": "好",
         "condition_expr_json": {"op": "eq",
                                 "a": {"op": "prop", "entity": "SUP006", "key": "supply_cut"},
                                 "b": {"op": "num", "v": "1"}}}]}
    monkeypatch.setattr("app.services.sandbox.sandbox_element_service.llm_json",
                        lambda p, model_id=None: fake)
    out = svc.draft_llm(sc)
    assert [x["code"] for x in out] == ["CE-OK"]           # 坏 AST 条被拒
    assert all(x["origin"] == "llm" and x["status"] == "suggested" for x in out)


def test_draft_degrades_empty_on_llm_failure(svc, sc, monkeypatch):
    def boom(p, model_id=None):
        raise RuntimeError("LLM 配置缺失")
    monkeypatch.setattr("app.services.sandbox.sandbox_element_service.llm_json", boom)
    assert svc.draft_llm(sc) == []                          # 降级不抛
