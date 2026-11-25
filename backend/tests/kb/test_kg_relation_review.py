"""关系 LLM 二次复核（证据复核 pass）回归测试。

覆盖：
* 复核提示词组装与响应解析（supported/weak/unsupported + 解析失败隔离）；
* ``run_review`` 批量复核落库（verdict/note/reviewed_at），单条失败不影响整批；
* ``review-batch`` 手动触发端点 + 关系列表/详情透出复核字段；
* 构建完成后自动复核（LLM 通道可用时），复核结果进构建报告；
* 复核相关配置键（review_enabled / review_batch_size）。
"""
import json

import pytest

from app.models.kb.kg_entity import KgEntity
from app.models.kb.kg_triple import KgTriple
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.services.kb.kg import kg_config, kg_relation_reviewer

TENANT_A = 100


# ── fixtures ─────────────────────────────────────────────────────────────
@pytest.fixture
def kb(db):
    obj = WikiKnowledge(name="图谱库", slug="kg-review-1", type=4, tenant_id=TENANT_A)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@pytest.fixture
def triple(db, kb):
    a = KgEntity(knowledge_id=kb.id, collection=f"kb_{kb.id}", name="启明电子",
                 entity_key="供应商:启明电子", type_code="供应商", tenant_id=TENANT_A)
    b = KgEntity(knowledge_id=kb.id, collection=f"kb_{kb.id}", name="智联数码",
                 entity_key="产品:智联数码", type_code="产品", tenant_id=TENANT_A)
    db.add_all([a, b])
    db.flush()
    t = KgTriple(knowledge_id=kb.id, collection=f"kb_{kb.id}",
                 from_entity_id=a.id, to_entity_id=b.id,
                 relation_code="生产", weight=0.9,
                 evidence={"text": "启明电子生产智联数码系列产品"},
                 tenant_id=TENANT_A)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _mk_triple(db, kb, src, dst, code, evidence):
    a = KgEntity(knowledge_id=kb.id, collection=f"kb_{kb.id}", name=src,
                 entity_key=f"{code}:{src}", type_code="T", tenant_id=TENANT_A)
    b = KgEntity(knowledge_id=kb.id, collection=f"kb_{kb.id}", name=dst,
                 entity_key=f"{code}:{dst}", type_code="T", tenant_id=TENANT_A)
    db.add_all([a, b])
    db.flush()
    t = KgTriple(knowledge_id=kb.id, collection=f"kb_{kb.id}",
                 from_entity_id=a.id, to_entity_id=b.id,
                 relation_code=code, evidence={"text": evidence} if evidence else None,
                 tenant_id=TENANT_A)
    db.add(t)
    db.flush()
    return t


# ── 提示词与解析 ─────────────────────────────────────────────────────────
def test_build_review_prompt_contains_relation_and_evidence():
    p = kg_relation_reviewer.build_review_prompt(
        source="启明电子", relation="生产", target="智联数码",
        evidence="启明电子生产智联数码系列产品",
    )
    assert "启明电子" in p and "智联数码" in p and "生产" in p
    assert "启明电子生产智联数码系列产品" in p
    for v in ("supported", "weak", "unsupported"):
        assert v in p, "判定词表必须写进提示词"


def test_parse_review_response_verdicts():
    raw = json.dumps({"verdict": "supported", "reason": "原文明确陈述", "confidence": 0.9})
    assert kg_relation_reviewer.parse_review_response(raw) == ("supported", "原文明确陈述", 0.9)

    fenced = "```json\n" + json.dumps({"verdict": "unsupported", "reason": "无关"}) + "\n```"
    assert kg_relation_reviewer.parse_review_response(fenced) == ("unsupported", "无关", 0.2), \
        "缺 confidence 时按判定推导默认值（unsupported=0.2）"

    verdict, note, conf = kg_relation_reviewer.parse_review_response("模型胡言乱语")
    assert verdict == kg_relation_reviewer.VERDICT_FAILED
    assert note
    assert conf is None, "解析失败不给置信度（weight 不回填）"


def test_parse_review_response_invalid_verdict_is_failed():
    verdict, _, conf = kg_relation_reviewer.parse_review_response(
        json.dumps({"verdict": "yes", "reason": "x"})
    )
    assert verdict == kg_relation_reviewer.VERDICT_FAILED
    assert conf is None


def test_parse_review_response_confidence_clamped():
    """confidence 越界/非法 → 钳制或回退判定默认值。"""
    verdict, _, conf = kg_relation_reviewer.parse_review_response(
        json.dumps({"verdict": "supported", "reason": "x", "confidence": 1.7})
    )
    assert (verdict, conf) == ("supported", 1.0)
    verdict, _, conf = kg_relation_reviewer.parse_review_response(
        json.dumps({"verdict": "weak", "reason": "x", "confidence": "abc"})
    )
    assert (verdict, conf) == ("weak", 0.5)


# ── run_review 批量复核 ──────────────────────────────────────────────────
def test_run_review_records_verdicts(db, kb, triple):
    t2 = _mk_triple(db, kb, "华创制造", "天枢服务器", "生产",
                    "支撑该关系的原文片段")  # 占位文本 → 模型判 unsupported
    t3 = _mk_triple(db, kb, "A", "B", "采购", "依据三")

    def complete(prompt):
        if "启明电子" in prompt:
            return json.dumps({"verdict": "supported", "reason": "原文明确陈述"})
        if "华创制造" in prompt:
            return json.dumps({"verdict": "unsupported", "reason": "依据是提示词占位文本"})
        raise RuntimeError("boom")

    summary = kg_relation_reviewer.run_review(
        db, tenant_id=TENANT_A, knowledge_id=kb.id, complete=complete,
    )
    db.refresh(triple)
    db.refresh(t2)
    db.refresh(t3)
    assert triple.review_verdict == "supported"
    assert triple.review_note == "原文明确陈述"
    assert triple.reviewed_at is not None
    assert triple.weight == 0.8, "复核置信度回填 weight（supported 默认 0.8）"
    assert t2.review_verdict == "unsupported"
    assert t2.weight == 0.2
    assert t3.review_verdict == kg_relation_reviewer.VERDICT_FAILED, \
        "单条 LLM 调用失败要落 review_failed，不影响整批"
    assert t3.weight == 0, "复核失败不回填 weight（保持列默认值 0）"
    assert summary["reviewed"] == 3
    assert summary["supported"] == 1 and summary["unsupported"] == 1


def test_run_review_skip_reviewed_incremental(db, kb, triple):
    """增量复核（skip_reviewed=True）不覆盖已有结论——修复构建自动复核
    反复覆盖全量结论的次序问题。"""
    def complete(prompt):
        return json.dumps({"verdict": "weak", "reason": "间接支撑"})

    first = kg_relation_reviewer.run_review(
        db, tenant_id=TENANT_A, knowledge_id=kb.id, complete=complete)
    assert first["reviewed"] == 1
    db.refresh(triple)
    assert triple.review_verdict == "weak"

    second = kg_relation_reviewer.run_review(
        db, tenant_id=TENANT_A, knowledge_id=kb.id, complete=complete,
        skip_reviewed=True,
    )
    assert second["reviewed"] == 0, "已复核关系必须跳过（增量构建不覆盖）"
    db.refresh(triple)
    assert triple.review_verdict == "weak"


def test_run_review_respects_status_and_ids(db, kb, triple):
    triple.status = "accepted"
    db.commit()
    calls = []

    def complete(prompt):
        calls.append(prompt)
        return json.dumps({"verdict": "weak", "reason": "间接支撑"})

    summary = kg_relation_reviewer.run_review(
        db, tenant_id=TENANT_A, knowledge_id=kb.id, complete=complete,
        status="suggested",
    )
    db.refresh(triple)
    assert summary["reviewed"] == 0, "accepted 默认不在复核范围"
    assert triple.review_verdict is None
    summary2 = kg_relation_reviewer.run_review(
        db, tenant_id=TENANT_A, knowledge_id=kb.id, complete=complete,
        relation_ids=[triple.id],
    )
    assert summary2["reviewed"] == 1
    db.refresh(triple)
    assert triple.review_verdict == "weak"


def test_model_has_review_columns(triple):
    assert triple.review_verdict is None
    assert triple.review_note is None
    assert triple.reviewed_at is None


# ── 构建后自动复核 ────────────────────────────────────────────────────────
def test_build_auto_reviews_relations(db, kb, monkeypatch):
    """LLM 通道可用时，构建完成后自动跑一轮复核（抽取响应被复用为复核输入时
    判定 review_failed，恰好证明复核真的对新建关系跑过并落库）。"""
    from app.models.kb.kb_document import new_document_uuid
    from app.models.kb.kb_segment import KbSegment
    from app.services.kb.kg import kg_build_service, kg_llm_extractor

    payload = json.dumps(
        {"entities": [{"name": "A", "label": "T"}, {"name": "B", "label": "T"}],
         "relations": [{"source": "A", "relation_type": "属于",
                        "target": "B", "text": "A属于B"}]},
        ensure_ascii=False,
    )
    monkeypatch.setattr(
        kg_llm_extractor, "build_llm_extractor",
        lambda db_, cfg, *, complete=None: (
            kg_llm_extractor.LLMExtractor(complete=lambda p: payload), "qwen"),
    )
    seg = KbSegment(collection=f"kb_{kb.id}", document_id=new_document_uuid(),
                    chunk_index=0, content="A属于B", tenant_id=TENANT_A)
    db.add(seg)
    db.commit()

    svc = kg_build_service.KgBuildService(
        db, TENANT_A, kb.id, embed_fn=lambda texts: [[0.1] * 8 for _ in texts])
    svc.run("build")

    tri = db.query(KgTriple).filter(KgTriple.knowledge_id == kb.id).one()
    assert tri.review_verdict == kg_relation_reviewer.VERDICT_FAILED, \
        "构建完成后必须自动跑过一轮复核（本例复核输入是抽取 JSON，判 review_failed）"
    assert tri.reviewed_at is not None


# ── API：review-batch + 序列化透出 ───────────────────────────────────────
def test_review_batch_endpoint(db, kb, triple, monkeypatch):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.deps import get_current_user, get_db
    from app.routers.kb.kg import router as kg_router
    from app.services.kb.kg import kg_llm_extractor

    monkeypatch.setattr(
        kg_llm_extractor, "build_llm_extractor",
        lambda db_, cfg, *, complete=None: (
            kg_llm_extractor.LLMExtractor(complete=lambda p: json.dumps(
                {"verdict": "supported", "reason": "原文支撑"})), "fake"),
    )

    app = FastAPI()
    app.include_router(kg_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        user_id=1, is_admin=True, tenant_id=TENANT_A)
    client = TestClient(app)

    r = client.post(f"/api/v1/kb/knowledges/{kb.id}/graph/relations/review-batch",
                    json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reviewed"] >= 1
    db.refresh(triple)
    assert triple.review_verdict == "supported"

    # 列表与详情透出复核字段
    r = client.get(f"/api/v1/kb/knowledges/{kb.id}/graph/relations")
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["review_verdict"] == "supported"
    assert item["review_note"] == "原文支撑"


# ── 配置 ─────────────────────────────────────────────────────────────────
def test_review_config_keys(db, kb):
    cfg = kg_config.get_graph_config(db, kb.id)
    assert cfg["relation_review_enabled"] is True
    assert cfg["review_batch_size"] >= 100
    kg_config.save_graph_config(db, kb.id, {"relation_review_enabled": False})
    assert kg_config.get_graph_config(db, kb.id)["relation_review_enabled"] is False
