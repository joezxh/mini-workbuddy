"""LLM 抽取通道回归测试。

覆盖本轮修复的三件事：
* ``extractor_type=llm`` + ``model_spec`` 真正解析到模型管理的对话模型；
* LLM 响应 → 实体/关系走与规则通道**同一套规整层**（含 ``relation_type``）；
* 模型不可用时**显式**给出降级原因（静默退回规则通道 = 前端「成功但 0 实体」）。

不发真实网络请求：模型补全一律用 ``complete=`` 注入。
"""
import json

import pytest

from app.models.ai.ai_api_key import AiApiKey, AiChatModel
from app.services.kb.kg import kg_extractor, kg_llm_extractor

TENANT_A = 100


# ── fixtures ─────────────────────────────────────────────────────────────
@pytest.fixture
def kb(db):
    from app.models.wiki.wiki_knowledge import WikiKnowledge

    obj = WikiKnowledge(name="图谱库", slug="kg-llm-1", type=4, tenant_id=TENANT_A)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@pytest.fixture
def ai_db(engine, db):
    """补建模型管理两张表（conftest 的白名单只含 kb/kg 表）。"""
    from app.db.database import Base

    Base.metadata.create_all(
        engine, tables=[AiApiKey.__table__, AiChatModel.__table__]
    )
    return db


def add_key(db, *, url="http://192.168.40.30", platform="gpustack", status=1):
    key = AiApiKey(name="本地网关", api_key="sk-test", platform=platform,
                   url=url, status=status, tenant_id=TENANT_A)
    db.add(key)
    db.commit()
    db.refresh(key)
    return key


def add_model(db, key, *, code="m-1", platform=None, type=1, status=1,
              is_default=False, sort=0, model="qwen"):
    row = AiChatModel(
        code=code, key_id=key.id, name="测试对话模型", model=model,
        platform=platform or "gpustack", status=status, type=type,
        is_default=is_default, sort=sort, tenant_id=TENANT_A,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ── 响应解析 ─────────────────────────────────────────────────────────────
def test_parse_response_plain_json():
    raw = json.dumps({
        "entities": [{"name": "星海科技", "label": "客户"}],
        "relations": [{"source": "星海科技", "target": "订单B1",
                       "relation_type": "下达"}],
    }, ensure_ascii=False)
    ents, rels = kg_llm_extractor.parse_response(raw)
    assert ents[0]["name"] == "星海科技"
    assert rels[0]["relation_type"] == "下达"


def test_parse_response_strips_fence_and_prose():
    """模型爱加 ```json 围栏、爱在 JSON 前后写解释——都要能吃下。"""
    raw = "好的，抽取结果如下：\n```json\n{\"entities\": [], \"relations\": []}\n```\n"
    ents, rels = kg_llm_extractor.parse_response(raw)
    assert ents == [] and rels == []


def test_parse_response_converts_dict_endpoints_to_text():
    raw = json.dumps({
        "entities": [{"name": "A"}, {"name": "B"}],
        "relations": [{"source": {"name": "A"}, "target": "B",
                       "relation_type": "属于"}],
    })
    _, rels = kg_llm_extractor.parse_response(raw)
    assert rels[0]["source"] == "A", "端点必须收敛成字符串，与规则通道判定一致"


@pytest.mark.parametrize("bad", ["", "抱歉，我无法抽取", "entities = [A]"])
def test_parse_response_raises_instead_of_returning_empty(bad):
    """解析失败必须抛错：返回空列表在前端与「文本确实没实体」不可区分。"""
    with pytest.raises(ValueError):
        kg_llm_extractor.parse_response(bad)


# ── prompt ───────────────────────────────────────────────────────────────
def test_build_prompt_injects_schema_hint_and_limits():
    p = kg_llm_extractor.build_prompt("正文", schema_hint="只抽客户与订单",
                                      max_entities=7, max_relations=9)
    assert "只抽客户与订单" in p
    assert "不超过 7 个" in p and "不超过 9 个" in p


def test_build_prompt_truncates_oversized_text():
    p = kg_llm_extractor.build_prompt("x" * (kg_llm_extractor.MAX_TEXT_CHARS + 999))
    assert len(p) < kg_llm_extractor.MAX_TEXT_CHARS + 2000


# ── 模型配置解析 ─────────────────────────────────────────────────────────
def test_resolve_llm_config_by_code(ai_db):
    key = add_key(ai_db)
    add_model(ai_db, key, code="chat-a")
    cfg = kg_llm_extractor.resolve_llm_config(ai_db, "chat-a")
    assert cfg["model"] == "qwen"
    assert cfg["api_key"] == "sk-test"


def test_resolve_llm_config_by_model_id_dict(ai_db):
    key = add_key(ai_db)
    row = add_model(ai_db, key, code="chat-b")
    cfg = kg_llm_extractor.resolve_llm_config(ai_db, {"model_id": row.id})
    assert cfg["model_code"] == "chat-b"


def test_resolve_llm_config_prefers_default_chat_model(ai_db):
    key = add_key(ai_db)
    add_model(ai_db, key, code="other", sort=99)
    add_model(ai_db, key, code="default-one", is_default=True, sort=0)
    cfg = kg_llm_extractor.resolve_llm_config(ai_db, None)
    assert cfg["model_code"] == "default-one", "未指定 model_spec 时取默认对话模型"


def test_resolve_llm_config_falls_back_to_sort_when_no_default(ai_db):
    """没标默认时按 sort 取最大者（与技能执行侧同一口径）。"""
    key = add_key(ai_db)
    add_model(ai_db, key, code="low", sort=1)
    add_model(ai_db, key, code="high", sort=9)
    assert kg_llm_extractor.resolve_llm_config(ai_db, None)["model_code"] == "high"


def test_resolve_llm_config_ignores_embedding_model(ai_db):
    """type=5 是向量化模型，不能被当成对话抽取模型用。"""
    key = add_key(ai_db)
    add_model(ai_db, key, code="vec", type=5, is_default=True)
    assert kg_llm_extractor.resolve_llm_config(ai_db, None) is None


def test_resolve_llm_config_rejects_disabled_model_and_key(ai_db):
    key = add_key(ai_db)
    add_model(ai_db, key, code="off", status=0, is_default=True)
    assert kg_llm_extractor.resolve_llm_config(ai_db, "off") is None

    key2 = add_key(ai_db, status=0)
    add_model(ai_db, key2, code="on", is_default=True)
    assert kg_llm_extractor.resolve_llm_config(ai_db, "on") is None, \
        "密钥被禁用不得仍被抽取链路使用"


def test_resolve_llm_config_unknown_code_returns_none(ai_db):
    add_key(ai_db)
    assert kg_llm_extractor.resolve_llm_config(ai_db, "not-exist") is None


def test_resolve_llm_config_appends_v1_for_openai_compatible(ai_db):
    """gpustack 一类 OpenAI 兼容地址必须补 /v1，否则打到错误路径。"""
    key = add_key(ai_db, url="http://192.168.40.30")
    add_model(ai_db, key, code="m", is_default=True)
    assert kg_llm_extractor.resolve_llm_config(ai_db, "m")["base_url"] \
        == "http://192.168.40.30/v1"


def test_resolve_llm_config_keeps_dashscope_url(ai_db):
    key = add_key(ai_db, url="https://dashscope.aliyuncs.com/compatible-mode",
                  platform="通义千问")
    add_model(ai_db, key, code="q", platform="通义千问", is_default=True)
    assert kg_llm_extractor.resolve_llm_config(ai_db, "q")["base_url"] \
        == "https://dashscope.aliyuncs.com/compatible-mode"


def test_resolve_llm_config_no_table_is_graceful(db):
    """无模型管理表（本用例未建表）时不抛错，返回 None 让上层降级。"""
    assert kg_llm_extractor.resolve_llm_config(db, None) is None


# ── 抽取器构造 ───────────────────────────────────────────────────────────
def test_build_llm_extractor_rule_type_returns_note(db):
    llm, note = kg_llm_extractor.build_llm_extractor(
        db, {"extractor_type": "rule", "timeout_seconds": 30}
    )
    assert llm is None and "rule" in note


def test_build_llm_extractor_reports_why_model_unavailable(ai_db):
    """模型不可用时 note 必须说清原因——这是本轮「静默降级」的正面修复。"""
    llm, note = kg_llm_extractor.build_llm_extractor(
        ai_db, {"extractor_type": "llm", "timeout_seconds": 30}
    )
    assert llm is None
    assert "默认对话模型" in note


def test_build_llm_extractor_uses_model_spec(ai_db):
    key = add_key(ai_db)
    add_model(ai_db, key, code="picked", is_default=True)
    llm, note = kg_llm_extractor.build_llm_extractor(
        ai_db, {"extractor_type": "llm", "model_spec": "picked",
                "timeout_seconds": 15}
    )
    assert llm is not None and llm.timeout_seconds == 15
    assert note == "qwen"
    assert "model=qwen" in llm.model_desc


# ── LLMExtractor（注入补全，不发网络请求）───────────────────────────────
def test_llm_extractor_end_to_end_with_injected_complete():
    seen = {}

    def fake_complete(prompt):
        seen["prompt"] = prompt
        return json.dumps({
            "entities": [{"name": "星海科技", "label": "客户"},
                         {"name": "订单B1", "label": "订单"}],
            "relations": [{"source": "星海科技", "target": "订单B1",
                           "relation_type": "下达", "text": "星海科技向订单B1下达采购"}],
        }, ensure_ascii=False)

    llm = kg_llm_extractor.LLMExtractor({"model": "m"}, complete=fake_complete)
    ents, rels = llm("星海科技向订单B1下达采购", schema_hint="只抽客户与订单")
    assert "只抽客户与订单" in seen["prompt"]
    assert len(ents) == 2 and rels[0]["relation_type"] == "下达"


def test_llm_extractor_without_model_or_complete_raises():
    llm = kg_llm_extractor.LLMExtractor({})
    with pytest.raises(ValueError):
        llm("文本")


def test_llm_extractor_parse_failure_carries_model_desc():
    """错误信息带上模型标识，排障时不必回去翻配置。"""
    llm = kg_llm_extractor.LLMExtractor(
        {"model": "qwen-plus", "provider": "openai"},
        complete=lambda p: "我不确定，无法抽取。",
    )
    with pytest.raises(ValueError) as exc:
        llm("文本")
    assert "qwen-plus" in str(exc.value)


# ── kg_extractor 双通道 ──────────────────────────────────────────────────
def test_extract_via_llm_keeps_relation_type_and_drops_dangling():
    def llm(text, *, schema_hint=""):
        return (
            [{"name": "实体A", "label": "T"}, {"name": "实体B", "label": "T"}],
            [{"source": "实体A", "target": "实体B", "relation_type": "属于"},
             {"source": "实体A", "target": "不存在的实体", "relation_type": "属于"}],
        )

    out = kg_extractor.extract("文本", llm=llm)
    assert len(out.relations) == 1, "relation_type 必须被认作谓词，否则关系全被丢弃"
    assert out.relations[0]["relation_type"] == "属于"
    assert out.dropped_relations == 1


def test_extract_llm_failure_does_not_fall_back_to_rule_channel():
    """LLM 失败绝不回落规则通道：回落会造出一堆 related_to 弱关系，比空结果更隐蔽。"""
    client_calls = []

    class SpyClient:
        def extract_entities(self, text, **options):
            client_calls.append(text)
            return [{"name": "不该出现", "label": "T"}]

        def extract_triplets(self, text, **kwargs):
            client_calls.append(text)
            return []

    def boom_llm(text, *, schema_hint=""):
        raise RuntimeError("endpoint down")

    out = kg_extractor.extract("文本", client=SpyClient(), llm=boom_llm)
    assert out.entities == [] and out.relations == []
    assert client_calls == [], "LLM 通道失败时不得调用规则通道"
    assert out.errors and "LLM 抽取失败" in out.errors[0]


def test_extract_llm_shares_normalization_with_rule_channel():
    """超长名 / 重复实体在两条通道下的处置必须一致。"""
    def llm(text, *, schema_hint=""):
        return (
            [{"name": "x" * (kg_extractor.MAX_ENTITY_NAME_LENGTH + 1)},
             {"name": "实体A"}, {"name": "实体A "}],
            [],
        )

    out = kg_extractor.extract("文本", llm=llm)
    assert len(out.entities) == 1 and out.dropped_entities == 1


# ── 构建服务接线 ─────────────────────────────────────────────────────────
def test_build_records_explicit_downgrade_when_model_missing(db, kb, monkeypatch):
    """LLM 通道不可用时，降级原因必须进构建报告，且抽取按「无 llm」执行。

    静默退回规则通道在本轮之前就这么错过去一次：前端看到「构建成功、0 实体」，
    与「文本确实没有实体」完全不可区分。
    """
    from app.models.kb.kb_document import new_document_uuid
    from app.models.kb.kb_segment import KbSegment
    from app.services.kb.kg import kg_build_service

    seg = KbSegment(collection=f"kb_{kb.id}",
                    document_id=new_document_uuid(), chunk_index=0,
                    content="星海科技向订单B1下达采购", tenant_id=TENANT_A)
    db.add(seg)
    db.commit()

    seen_kwargs = []
    real_extract = kg_extractor.extract

    def spy_extract(text, **kwargs):
        seen_kwargs.append(kwargs)
        return real_extract(text, **kwargs)

    # 未建 ai_chat_model 表 → resolve_llm_config 拿不到模型 → 通道不可用
    monkeypatch.setattr(kg_extractor, "extract", spy_extract)
    svc = kg_build_service.KgBuildService(db, TENANT_A, kb.id, embed_fn=vec_fn)
    report = svc.run("build")
    db.refresh(seg)

    assert any("LLM 抽取通道不可用" in e for e in report.errors), \
        "降级必须显式记录在报告里"
    assert seen_kwargs and all("llm" not in kw for kw in seen_kwargs), \
        "降级后按规则通道抽取（不给 llm 参数）"
    # 降级后的中文切片零产出 → 不得被标成「抽取完成」（否则配好模型也不再重跑）
    assert seg.graph_structure_indexed is False
    assert report.structure_failed == 1


def test_rule_mode_is_not_reported_as_downgrade(db, kb, monkeypatch):
    """``extractor_type=rule`` 是用户显式选的通道，不该叫「降级」。"""
    from app.models.kb.kb_document import new_document_uuid
    from app.models.kb.kb_segment import KbSegment
    from app.services.kb.kg import kg_build_service, kg_config

    kg_config.save_graph_config(db, kb.id, {"extractor_type": "rule"})
    seg = KbSegment(collection=f"kb_{kb.id}",
                    document_id=new_document_uuid(), chunk_index=0,
                    content="Oriental Bank", tenant_id=TENANT_A)
    db.add(seg)
    db.commit()

    def rule_extract(text, **kwargs):
        return kg_extractor.ExtractionResult(entities=[{
            "name": "Oriental Bank", "label": "ORG", "aliases": [],
            "properties": {}, "normalized": kg_extractor.normalize_entity_name("Oriental Bank"),
        }])

    monkeypatch.setattr(kg_extractor, "extract", rule_extract)
    svc = kg_build_service.KgBuildService(db, TENANT_A, kb.id, embed_fn=vec_fn)
    report = svc.run("build")
    db.refresh(seg)

    assert not any("LLM 抽取通道不可用" in e for e in report.errors)
    assert report.structure_done == 1 and seg.graph_structure_indexed is True


def test_llm_channel_is_passed_to_extractor(db, kb, monkeypatch):
    """``extractor_type=llm`` 必须真的把抽取器接到通道上，且 ``model_spec`` 逐层传到。"""
    from app.models.kb.kb_document import new_document_uuid
    from app.models.kb.kb_segment import KbSegment
    from app.services.kb.kg import kg_build_service, kg_config

    kg_config.save_graph_config(db, kb.id, {"extractor_type": "llm",
                                            "model_spec": "pick"})
    seg = KbSegment(collection=f"kb_{kb.id}",
                    document_id=new_document_uuid(), chunk_index=0,
                    content="星海科技", tenant_id=TENANT_A)
    db.add(seg)
    db.commit()

    got = {}
    payload = json.dumps(
        {"entities": [{"name": "星海科技", "label": "客户"}], "relations": []},
        ensure_ascii=False,
    )

    def fake_build(db_, graph_cfg, *, complete=None):
        got["spec"] = graph_cfg.get("model_spec")
        return kg_llm_extractor.LLMExtractor(complete=lambda p: payload), "qwen"

    monkeypatch.setattr(kg_llm_extractor, "build_llm_extractor", fake_build)
    real_extract = kg_extractor.extract

    def spy_extract(text, **kwargs):
        got["llm"] = kwargs.get("llm")
        return real_extract(text, **kwargs)

    monkeypatch.setattr(kg_extractor, "extract", spy_extract)
    svc = kg_build_service.KgBuildService(db, TENANT_A, kb.id, embed_fn=vec_fn)
    report = svc.run("build")

    assert got["spec"] == "pick", "model_spec 必须原样传到通道构造处"
    assert isinstance(got["llm"], kg_llm_extractor.LLMExtractor), "LLM 通道须接线到抽取"
    assert report.entities == 1
    assert not any("LLM 抽取通道不可用" in e for e in report.errors)


def test_extract_error_with_nothing_extracted_counts_as_failure(db, kb):
    """抽取报错且一无所出 → 切片归为失败，否则停在「已抽取但空」永不重试。"""
    from app.models.kb.kb_document import new_document_uuid
    from app.models.kb.kb_segment import KbSegment
    from app.services.kb.kg import kg_build_service

    seg = KbSegment(collection=f"kb_{kb.id}",
                    document_id=new_document_uuid(), chunk_index=0,
                    content="星海科技", tenant_id=TENANT_A)
    db.add(seg)
    db.commit()

    def extractor(text, **kwargs):
        return kg_extractor.ExtractionResult(errors=["LLM 抽取失败: timeout"])

    svc = kg_build_service.KgBuildService(db, TENANT_A, kb.id,
                                          extractor=extractor, embed_fn=vec_fn)
    report = svc.run("build")

    db.refresh(seg)
    assert seg.graph_structure_indexed is False, "空结果不得标记为抽取完成"
    assert report.structure_failed == 1 and report.structure_done == 0


def vec_fn(texts):
    return [[0.1] * 8 for _ in texts]
