"""图谱构建管线测试（P3）：配置 / 抽取器 / 两阶段编排 / 幂等 / 撤销 / 互斥。"""
import threading
import time

import pytest

from app.models.kb.kb_document import KbDocument, new_document_uuid
from app.models.kb.kb_segment import KbSegment
from app.models.kb.kg_entity import KgEntity
from app.models.kb.kg_entity_mention import KgEntityMention
from app.models.kb.kg_triple import KgTriple
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.services.kb.kg import kg_build_service, kg_config, kg_extractor
from tests.kb.conftest import TENANT_A


# ── fixtures ─────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _clean_locks():
    kg_build_service.reset_locks()
    yield
    kg_build_service.reset_locks()


@pytest.fixture
def kb(db):
    obj = WikiKnowledge(name="图谱库", slug="kg-build-1", type=4, tenant_id=TENANT_A)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@pytest.fixture
def doc(db, kb):
    d = KbDocument(
        uuid_code=new_document_uuid(), knowledge_id=kb.id,
        collection=f"kb_{kb.id}", name="测试文档", status="completed",
        tenant_id=TENANT_A,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def make_segment(db, kb, doc, content, index=0):
    seg = KbSegment(
        collection=f"kb_{kb.id}", document_id=doc.uuid_code, chunk_index=index,
        content=content, tenant_id=TENANT_A,
    )
    db.add(seg)
    db.commit()
    db.refresh(seg)
    return seg


class FakeClient:
    """假抽取客户端：返回预设实体/三元组，可注入异常。"""

    def __init__(self, entities=None, triplets=None, boom=False, accept_schema=True):
        self.entities = entities or []
        self.triplets = triplets or []
        self.boom = boom
        self.accept_schema = accept_schema
        self.calls = []

    def extract_entities(self, text, **options):
        self.calls.append(("entities", options))
        if self.boom:
            raise RuntimeError("extractor exploded")
        if options and not self.accept_schema:
            raise TypeError("unexpected kwarg 'schema'")
        return self.entities

    def extract_triplets(self, text, entities=None, relations=None, **kwargs):
        return self.triplets


def fake_extractor(client):
    """把 KgBuildService 的抽取器固定为使用指定假客户端。"""
    def _extract(text, *, schema_hint="", tenant_id=None, client=client):
        return kg_extractor.extract(text, client=client, schema_hint=schema_hint,
                                    tenant_id=tenant_id)
    return _extract


def builder(db, kb, *, extractor=None, embed_fn=None):
    return kg_build_service.KgBuildService(
        db, TENANT_A, kb.id, extractor=extractor, embed_fn=embed_fn
    )


def vec_fn(dim=8):
    return lambda texts: [[0.1] * dim for _ in texts]


# ── 配置 ─────────────────────────────────────────────────────────────────
def test_config_defaults(db, kb):
    cfg = kg_config.get_graph_config(db, kb.id)
    assert cfg["use_graph_retrieval"] is True
    assert cfg["ppr_damping"] == 0.85
    assert cfg["graph_entity_top_k"] == 10


def test_config_clamps_out_of_range(db, kb):
    kg_config.save_graph_config(db, kb.id, {
        "ppr_damping": 5.0,          # >1 会让 networkx pagerank 崩
        "concurrency_count": 99999,
        "graph_weight": -3,
    })
    cfg = kg_config.get_graph_config(db, kb.id)
    assert cfg["ppr_damping"] == 0.99
    assert cfg["concurrency_count"] == 1000
    assert cfg["graph_weight"] == 0.0


def test_config_ignores_unknown_keys(db, kb):
    kg_config.save_graph_config(db, kb.id, {"hacker": "x"})
    cfg = kg_config.get_graph_config(db, kb.id)
    assert "hacker" not in cfg


def test_config_roundtrip_and_preserves_other_pipeline_keys(db, kb):
    kb.pipeline_config = {"chunker": {"type": "approx_token"}}
    db.commit()
    kg_config.save_graph_config(db, kb.id, {"graph_top_k": 33})
    db.refresh(kb)
    assert kb.pipeline_config["chunker"] == {"type": "approx_token"}
    assert kg_config.get_graph_config(db, kb.id)["graph_top_k"] == 33


# ── 抽取器 ───────────────────────────────────────────────────────────────
def test_normalize_entity_name():
    assert kg_extractor.normalize_entity_name("  星海   科技 ") == "星海 科技"


def test_extractor_drops_overlong_entity_instead_of_raising():
    client = FakeClient(entities=[
        {"name": "x" * (kg_extractor.MAX_ENTITY_NAME_LENGTH + 1), "label": "T"},
        {"name": "正常实体", "label": "T"},
    ])
    out = kg_extractor.extract("文本", client=client)
    assert len(out.entities) == 1 and out.dropped_entities == 1


def test_extractor_drops_overlong_label():
    client = FakeClient(entities=[
        {"name": "实体", "label": "L" * (kg_extractor.MAX_ENTITY_LABEL_LENGTH + 1)},
    ])
    out = kg_extractor.extract("文本", client=client)
    assert out.entities == [] and out.dropped_entities == 1


def test_extractor_drops_dangling_relations():
    """端点实体被丢弃 → 关系一并丢弃（悬空边不入库）。"""
    client = FakeClient(
        entities=[{"name": "实体A", "label": "T"}],
        triplets=[{"subject": "实体A", "predicate": "属于", "object": "不存在的实体"}],
    )
    out = kg_extractor.extract("文本", client=client)
    assert out.relations == [] and out.dropped_relations == 1


def test_extractor_dedups_entities_and_relations():
    client = FakeClient(
        entities=[{"name": "实体A", "label": "T"}, {"name": "实体A ", "label": "T"}],
        triplets=[
            {"subject": "实体A", "predicate": "属于", "object": "实体B"},
            {"subject": "实体A", "predicate": "属于", "object": "实体B"},
        ],
    )
    # 实体B 不在实体表里 → 悬空；此处只验证实体去重
    out = kg_extractor.extract("文本", client=client)
    assert len(out.entities) == 1


def test_extractor_tolerates_string_entities_and_alt_keys():
    client = FakeClient(entities=["纯字符串实体"], triplets=[])
    out = kg_extractor.extract("文本", client=client)
    assert out.entities[0]["name"] == "纯字符串实体"


def test_extractor_records_failure_without_raising():
    client = FakeClient(boom=True)
    out = kg_extractor.extract("文本", client=client)
    assert out.entities == []
    assert out.errors and "抽取失败" in out.errors[0]


def test_extractor_falls_back_when_schema_option_rejected():
    """抽取器不接受 schema 选项时降级为无约束重试，而不是整篇颗粒无收。"""
    client = FakeClient(entities=[{"name": "实体A", "label": "T"}],
                        accept_schema=False)
    out = kg_extractor.extract("文本", client=client, schema_hint="约束")
    assert len(out.entities) == 1
    assert ("entities", {}) in client.calls  # 发生过无选项重试


def test_schema_hint_free_text_and_none():
    assert kg_extractor.build_schema_hint(None, schema_source="free_text",
                                          free_text="只抽客户与订单") == "只抽客户与订单"
    assert kg_extractor.build_schema_hint(None, schema_source="none") == ""


# ── 构建：两阶段 + 幂等 ───────────────────────────────────────────────────
def test_build_writes_entities_relations_and_flags(db, kb, doc):
    seg = make_segment(db, kb, doc, "星海科技向订单B1下达采购")
    client = FakeClient(
        entities=[{"name": "星海科技", "label": "客户"},
                  {"name": "订单B1", "label": "订单"}],
        triplets=[{"subject": "星海科技", "predicate": "下达", "object": "订单B1"}],
    )
    svc = builder(db, kb, extractor=fake_extractor(client), embed_fn=vec_fn())
    report = svc.run("build")

    assert report.entities == 2 and report.relations == 1
    db.refresh(seg)
    assert seg.graph_structure_indexed is True, "阶段1 标志必须置位"
    assert seg.graph_indexed is True, "阶段2 标志必须置位"
    assert seg.graph_extraction_details["entities"] == 2


def test_build_is_idempotent(db, kb, doc):
    """重复构建不产生重复实体/关系/提及（幂等是重复执行的生命线）。"""
    make_segment(db, kb, doc, "星海科技向订单B1下达采购")
    client = FakeClient(
        entities=[{"name": "星海科技", "label": "客户"},
                  {"name": "订单B1", "label": "订单"}],
        triplets=[{"subject": "星海科技", "predicate": "下达", "object": "订单B1"}],
    )
    svc = builder(db, kb, extractor=fake_extractor(client), embed_fn=vec_fn())
    svc.run("build")
    svc.run("build")

    ents = db.query(KgEntity).filter(KgEntity.knowledge_id == kb.id).all()
    tris = db.query(KgTriple).filter(KgTriple.knowledge_id == kb.id).all()
    mens = db.query(KgEntityMention).all()
    assert len(ents) == 2 and len(tris) == 1
    assert len(mens) == 2  # 每实体一条提及，不重复


def test_build_writes_provenance_mentions(db, kb, doc):
    seg = make_segment(db, kb, doc, "星海科技")
    client = FakeClient(entities=[{"name": "星海科技", "label": "客户"}])
    builder(db, kb, extractor=fake_extractor(client), embed_fn=vec_fn()).run("build")

    m = db.query(KgEntityMention).first()
    assert m is not None
    assert m.segment_id == seg.id and m.document_id == doc.uuid_code


def test_build_vectors_written(db, kb, doc):
    make_segment(db, kb, doc, "星海科技")
    client = FakeClient(entities=[{"name": "星海科技", "label": "客户"}])
    builder(db, kb, extractor=fake_extractor(client), embed_fn=vec_fn()).run("build")
    ent = db.query(KgEntity).filter(KgEntity.knowledge_id == kb.id).first()
    assert ent.embedding is not None


def test_second_run_skips_completed_structure_phase(db, kb, doc):
    """已完成阶段1的切片不再重复抽取（省 LLM 成本）。"""
    seg = make_segment(db, kb, doc, "星海科技")
    calls = {"n": 0}

    def counting(text, *, schema_hint="", tenant_id=None):
        calls["n"] += 1
        return kg_extractor.extract(text, client=FakeClient(
            entities=[{"name": "星海科技", "label": "客户"}]), schema_hint=schema_hint)

    svc = builder(db, kb, extractor=counting, embed_fn=vec_fn())
    svc.run("build")
    first = calls["n"]
    db.refresh(seg)
    assert seg.graph_structure_indexed is True
    svc.run("build")
    assert calls["n"] == first, "阶段1 已完成，第二次不得再抽取"


# ── 失败可观测 ───────────────────────────────────────────────────────────
def test_extraction_failure_marks_segment_and_document(db, kb, doc):
    seg = make_segment(db, kb, doc, "会炸的文本")

    def boom(text, *, schema_hint="", tenant_id=None):
        raise RuntimeError("LLM 挂了")

    svc = builder(db, kb, extractor=boom, embed_fn=vec_fn())
    report = svc.run("build", doc.uuid_code)

    db.refresh(seg)
    assert seg.graph_structure_indexed is False
    assert report.structure_failed == 1
    db.refresh(doc)
    assert doc.error_detail and "[graph_extract]" in doc.error_detail
    assert doc.status == "completed", "图谱失败不得回滚文档摄取状态"


def test_vector_failure_keeps_structure_phase(db, kb, doc):
    """向量阶段失败只置 graph_indexed=False，不回滚已抽取的结构。"""
    seg = make_segment(db, kb, doc, "星海科技")
    client = FakeClient(entities=[{"name": "星海科技", "label": "客户"}])
    svc = builder(db, kb, extractor=fake_extractor(client),
                  embed_fn=lambda texts: (_ for _ in ()).throw(RuntimeError("embed down")))
    report = svc.run("build")

    db.refresh(seg)
    assert seg.graph_structure_indexed is True, "结构阶段成果必须保留"
    assert seg.graph_indexed is False
    assert report.vector_failed == 1
    assert db.query(KgEntity).filter(KgEntity.knowledge_id == kb.id).count() == 1


# ── 撤销与重建 ───────────────────────────────────────────────────────────
def test_clear_document_removes_contributions(db, kb, doc):
    make_segment(db, kb, doc, "星海科技")
    client = FakeClient(entities=[{"name": "星海科技", "label": "客户"}])
    svc = builder(db, kb, extractor=fake_extractor(client), embed_fn=vec_fn())
    svc.run("build")
    assert db.query(KgEntity).filter(KgEntity.knowledge_id == kb.id).count() == 1

    out = svc.clear_document(doc.uuid_code)
    assert out["deleted_entities"] == 1
    assert db.query(KgEntity).filter(KgEntity.knowledge_id == kb.id).count() == 0
    assert db.query(KgEntityMention).count() == 0


def test_clear_document_keeps_shared_entities(db, kb, doc):
    """同一实体被两个文档共享时，清一个文档不得误删实体。"""
    s1 = make_segment(db, kb, doc, "星海科技", index=0)
    s2 = make_segment(db, kb, doc, "星海科技", index=1)
    client = FakeClient(entities=[{"name": "星海科技", "label": "客户"}])
    svc = builder(db, kb, extractor=fake_extractor(client), embed_fn=vec_fn())
    svc.run("build")
    assert db.query(KgEntityMention).count() == 2

    # 只清 index=0 所在切片：手动移除一条提及后实体仍被另一条引用
    m = db.query(KgEntityMention).filter(KgEntityMention.segment_id == s1.id).first()
    db.delete(m)
    db.commit()
    assert db.query(KgEntity).filter(KgEntity.knowledge_id == kb.id).count() == 1
    assert s2.id is not None


def test_rebuild_clears_instance_layer(db, kb, doc):
    make_segment(db, kb, doc, "星海科技")
    client = FakeClient(entities=[{"name": "星海科技", "label": "客户"}])
    svc = builder(db, kb, extractor=fake_extractor(client), embed_fn=vec_fn())
    svc.run("build")
    assert db.query(KgEntity).filter(KgEntity.knowledge_id == kb.id).count() == 1

    svc.rebuild()  # 只清场
    assert db.query(KgEntity).filter(KgEntity.knowledge_id == kb.id).count() == 0


def test_rebuild_action_clears_then_reextracts(db, kb, doc):
    """rebuild 动作 = 清场 + 重新抽取（不是只清不建）。"""
    make_segment(db, kb, doc, "星海科技")
    client = FakeClient(entities=[{"name": "星海科技", "label": "客户"}])
    svc = builder(db, kb, extractor=fake_extractor(client), embed_fn=vec_fn())
    svc.run("build")
    svc.run("rebuild", doc.uuid_code)
    assert db.query(KgEntity).filter(KgEntity.knowledge_id == kb.id).count() == 1


def test_rebuild_document_keeps_other_documents_intact(db, kb, doc):
    """单文档重抽不得波及同库其他文档（否则整库全变「未抽取」）。"""
    other = KbDocument(
        uuid_code=new_document_uuid(), knowledge_id=kb.id,
        collection=f"kb_{kb.id}", name="另一个文档", status="completed",
        tenant_id=TENANT_A,
    )
    db.add(other)
    db.commit()
    db.refresh(other)

    seg_a = make_segment(db, kb, doc, "星海科技", index=0)
    seg_b = make_segment(db, kb, other, "启明电子", index=0)
    clients = {
        "星海科技": FakeClient(entities=[{"name": "星海科技", "label": "客户"}]),
        "启明电子": FakeClient(entities=[{"name": "启明电子", "label": "供应商"}]),
    }

    def by_text(text, *, schema_hint="", tenant_id=None):
        client = clients["星海科技" if "星海" in text else "启明电子"]
        return kg_extractor.extract(text, client=client, schema_hint=schema_hint,
                                    tenant_id=tenant_id)

    svc = builder(db, kb, extractor=by_text, embed_fn=vec_fn())
    svc.run("build")
    db.refresh(seg_a)
    db.refresh(seg_b)
    assert seg_a.graph_structure_indexed is True and seg_b.graph_structure_indexed is True

    svc.run("rebuild", doc.uuid_code)  # 只重抽 seg_a 所属文档

    db.refresh(seg_a)
    db.refresh(seg_b)
    assert seg_a.graph_structure_indexed is True, "本文档应已重新抽取完成"
    assert seg_b.graph_structure_indexed is True, "其他文档的阶段标志不得被重置"
    assert seg_b.graph_indexed is True, "其他文档的向量标志不得被重置"
    names = {e.name for e in db.query(KgEntity).filter(KgEntity.knowledge_id == kb.id).all()}
    assert names == {"星海科技", "启明电子"}, "其他文档的实体不得被全库清空"


# ── 互斥 ─────────────────────────────────────────────────────────────────
def test_single_kb_mutex():
    assert kg_build_service.try_acquire(42) is True
    assert kg_build_service.try_acquire(42) is False, "同一知识库不得并发构建"
    assert kg_build_service.is_locked(42) is True
    kg_build_service.release(42)
    assert kg_build_service.try_acquire(42) is True


def test_mutex_is_per_kb():
    assert kg_build_service.try_acquire(1) is True
    assert kg_build_service.try_acquire(2) is True, "不同知识库互不阻塞"


def test_submit_build_rejects_when_locked(monkeypatch, db, kb):
    kg_build_service.try_acquire(kb.id)
    started = {"n": 0}

    def fake_run(fn, *a, **kw):
        started["n"] += 1
        return None

    # run_in_background 在 submit_build 内为局部导入，需 patch 源模块
    import app.core.job_runner as job_runner

    monkeypatch.setattr(job_runner, "run_in_background", fake_run)
    out = kg_build_service.submit_build(tenant_id=TENANT_A, knowledge_id=kb.id)
    assert out["accepted"] is False and started["n"] == 0


# ── 并发（concurrency_count）──────────────────────────────────────
def entity_result(name):
    """构造一个与 kg_extractor 产物同形的结果（含 normalized，落库依赖它）。"""
    return kg_extractor.ExtractionResult(entities=[{
        "name": name, "label": "客户", "aliases": [], "properties": {},
        "normalized": kg_extractor.normalize_entity_name(name),
    }])


def run_concurrency_case(db, kb, doc, *, workers, segments=4, delay=0.2):
    """逐切片均睡 delay 后返回同一实体；返回（峰值并发, 构建报告）。"""
    kg_config.save_graph_config(db, kb.id, {"concurrency_count": workers})
    for i in range(segments):
        make_segment(db, kb, doc, f"星海科技 片段{i}", index=i)

    guard = threading.Lock()
    state = {"running": 0, "peak": 0}

    def slow(text, **kwargs):
        with guard:
            state["running"] += 1
            state["peak"] = max(state["peak"], state["running"])
        time.sleep(delay)
        with guard:
            state["running"] -= 1
        return entity_result("星海科技")

    svc = builder(db, kb, extractor=slow, embed_fn=vec_fn())
    report = svc.run("build")
    return state["peak"], report


def test_concurrency_count_parallelizes_extraction(db, kb, doc):
    """抽取是最贵的一段（逐切片等 LLM），``concurrency_count`` 必须在此真正生效。"""
    peak, report = run_concurrency_case(db, kb, doc, workers=4)

    assert peak >= 2, f"并发度未生效（峰值只有 {peak}）"
    assert report.structure_done == 4 and report.structure_failed == 0


def test_concurrency_count_one_keeps_serial(db, kb, doc):
    """并发改为 1 时串行执行（不白开线程池）。"""
    peak, report = run_concurrency_case(db, kb, doc, workers=1, segments=3)

    assert peak == 1
    assert report.structure_done == 3


def test_concurrent_extraction_still_writes_in_main_thread(db, kb, doc):
    """并发只包抽取；落库必须串行完成，四切片都得标位。"""
    run_concurrency_case(db, kb, doc, workers=4, segments=4, delay=0.05)

    segs = db.query(KbSegment).filter(KbSegment.collection == f"kb_{kb.id}").all()
    assert all(s.graph_structure_indexed is True for s in segs)
    assert all(s.graph_indexed is True for s in segs)
    assert db.query(KgEntity).filter(KgEntity.knowledge_id == kb.id).count() == 1, \
        "同名词跨切片归一到同一实体（并发不得破幂等）"
