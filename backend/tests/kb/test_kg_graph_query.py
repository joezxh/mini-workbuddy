"""图谱查询与 CDM 校验测试（P5/P6）：子图 / 路径 / 邻接 / 类型分布 / 校验 / 导出。"""
import pytest

from app.models.dataops.standard_cdm import (
    MetaObjectRelation,
    MetaObjectStandard,
)
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.services.kb.kg.kg_cdm_check import run_cdm_check
from tests.kb.conftest import TENANT_A


@pytest.fixture
def kb(db):
    obj = WikiKnowledge(name="图谱库", slug="kg-q-1", type=4, tenant_id=TENANT_A)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@pytest.fixture
def svc(db, kb):
    from app.services.kb.kg.kg_service import KgService

    return KgService(db, tenant_id=TENANT_A, knowledge_id=kb.id)


@pytest.fixture
def chain(svc):
    """A -(下达)-> B -(属于)-> C 三点链。"""
    a = svc.create_entity(name="星海科技", type_code="CUS")
    b = svc.create_entity(name="订单B1", type_code="ORD")
    c = svc.create_entity(name="产品P1", type_code="PRD")
    svc.create_triple(from_entity_id=a.id, to_entity_id=b.id, relation_code="PLACES")
    svc.create_triple(from_entity_id=b.id, to_entity_id=c.id, relation_code="OWNS")
    return a, b, c


# ── 子图 ─────────────────────────────────────────────────────────────────
def test_subgraph_depth1_returns_direct_neighbours(svc, chain):
    a, b, c = chain
    sub = svc.subgraph([b.id], depth=1)
    ids = {n["id"] for n in sub["nodes"]}
    assert ids == {a.id, b.id, c.id}
    assert len(sub["edges"]) == 2


def test_subgraph_depth0_is_clamped_to_1(svc, chain):
    a, _b, _c = chain
    sub = svc.subgraph([a.id], depth=0)
    assert len(sub["edges"]) == 1, "depth=0 必须被钳制为 1"


def test_subgraph_depth_capped_at_3(svc, chain):
    a, _b, _c = chain
    sub = svc.subgraph([a.id], depth=99)
    assert len(sub["edges"]) <= 2


def test_subgraph_empty_seeds(svc, chain):
    assert svc.subgraph([]) == {"nodes": [], "edges": []}


def test_subgraph_node_shape_matches_standard_graph(svc, chain):
    """节点字段与标准中心 graph() 对齐（id/name/code），前端图组件可共用。"""
    a, _b, _c = chain
    sub = svc.subgraph([a.id], depth=1)
    node = next(n for n in sub["nodes"] if n["id"] == a.id)
    assert {"id", "name", "code"} <= set(node.keys())
    edge = sub["edges"][0]
    assert {"id", "from", "to", "relation_type"} <= set(edge.keys())


def test_subgraph_respects_limit(svc, chain):
    a, _b, _c = chain
    sub = svc.subgraph([a.id], depth=2, limit=1)
    assert len(sub["nodes"]) <= 1


def test_neighbors_of_entity(svc, chain):
    a, b, c = chain
    sub = svc.neighbors(b.id, depth=1)
    assert {n["id"] for n in sub["nodes"]} == {a.id, b.id, c.id}


# ── 路径 ─────────────────────────────────────────────────────────────────
def test_paths_finds_two_hop_route(svc, chain):
    a, b, c = chain
    paths = svc.paths(a.id, c.id, max_depth=2)
    assert paths, "两跳路径必须被找到"
    assert len(paths[0]["nodes"]) == 3
    assert len(paths[0]["edges"]) == 2


def test_paths_direct_edge(svc, chain):
    a, b, _c = chain
    paths = svc.paths(a.id, b.id, max_depth=1)
    assert paths and len(paths[0]["edges"]) == 1


def test_paths_returns_empty_when_unreachable(svc, chain):
    a, _b, _c = chain
    other = svc.create_entity(name="孤立实体", type_code="X")
    assert svc.paths(a.id, other.id, max_depth=3) == []


def test_paths_same_entity_is_empty(svc, chain):
    a, _b, _c = chain
    assert svc.paths(a.id, a.id) == []


def test_paths_depth_limit_respected(svc, chain):
    a, _b, c = chain
    assert svc.paths(a.id, c.id, max_depth=1) == [], "跳数不足时不得返回路径"


# ── 类型分布 ─────────────────────────────────────────────────────────────
def test_labels_distribution(svc, chain):
    items = svc.labels()
    by_code = {i["code"]: i["count"] for i in items}
    assert by_code == {"CUS": 1, "ORD": 1, "PRD": 1}

# ── CDM 双向校验（P6）────────────────────────────────────────────────────
def _cdm(db, *, code="PLACES", from_code="CUS", to_code="ORD", cardinality="1:N"):
    fo = MetaObjectStandard(code=from_code, name=from_code, tenant_id=TENANT_A)
    to = MetaObjectStandard(code=to_code, name=to_code, tenant_id=TENANT_A)
    db.add_all([fo, to])
    db.commit()
    db.refresh(fo)
    db.refresh(to)
    rel = MetaObjectRelation(
        code=code, name=code, from_object_id=fo.id, to_object_id=to.id,
        relation_type=cardinality, tenant_id=TENANT_A,
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


def test_cdm_check_hit(db, kb, svc, chain):
    _cdm(db)
    out = run_cdm_check(db, kb.id, TENANT_A)
    assert out["hit"] == 1
    assert out["missing"] == 0
    assert out["conflict"] == 0
    assert out["items"][0]["verdict"] == "hit"


def test_cdm_check_missing(db, kb, svc):
    _cdm(db, code="MISSING_REL", from_code="NOPE_A", to_code="NOPE_B")
    out = run_cdm_check(db, kb.id, TENANT_A)
    assert out["missing"] == 1
    assert out["items"][0]["verdict"] == "missing"


def test_cdm_check_conflict_on_cardinality(db, kb, svc):
    """标准声明 1:1，但图谱出现两条同类型边 -> conflict。"""
    _cdm(db, code="PLACES", from_code="CUS", to_code="ORD", cardinality="1:1")
    a = svc.create_entity(name="客户A", type_code="CUS")
    b1 = svc.create_entity(name="订单1", type_code="ORD")
    b2 = svc.create_entity(name="订单2", type_code="ORD")
    svc.create_triple(from_entity_id=a.id, to_entity_id=b1.id, relation_code="PLACES")
    svc.create_triple(from_entity_id=a.id, to_entity_id=b2.id, relation_code="PLACES")

    out = run_cdm_check(db, kb.id, TENANT_A)
    assert out["conflict"] == 1
    item = next(i for i in out["items"] if i["verdict"] == "conflict")
    assert "1:1" in item["detail"]


def test_cdm_check_flags_relation_not_covered_by_standard(db, kb, svc, chain):
    """标准未覆盖的边单列为 uncovered 诊断（不污染 conflict 的 spec 语义）。"""
    _cdm(db, code="PLACES", from_code="CUS", to_code="ORD")
    svc.create_triple(
        from_entity_id=chain[0].id, to_entity_id=chain[2].id,
        relation_code="DRIFTED",
    )
    out = run_cdm_check(db, kb.id, TENANT_A)
    assert out["conflict"] == 0, "未覆盖不等于违反约束"
    codes = [u["relation_code"] for u in out["uncovered"]]
    assert "DRIFTED" in codes
    assert "OWNS" in codes



def test_cdm_check_uses_existing_verdict_vocabulary(db, kb, svc, chain):
    """结论词表沿用既有 hit/missing/conflict，不发明新词。"""
    _cdm(db)
    out = run_cdm_check(db, kb.id, TENANT_A)
    verdicts = {i["verdict"] for i in out["items"]}
    assert verdicts <= {"hit", "missing", "conflict"}


def test_entity_mentions_returns_segment_provenance(db, kb, svc):
    """实体溯源：返回提及该实体的切片（chunk_index / 文档 / 正文）。"""
    from app.models.kb.kb_document import KbDocument, new_document_uuid
    from app.models.kb.kb_segment import KbSegment
    from app.models.kb.kg_entity_mention import KgEntityMention

    doc = KbDocument(
        uuid_code=new_document_uuid(), knowledge_id=kb.id,
        collection=f"kb_{kb.id}", name="溯源文档", status="completed",
        tenant_id=TENANT_A,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    seg = KbSegment(
        collection=f"kb_{kb.id}", document_id=doc.uuid_code, chunk_index=2,
        content="星海科技下单内容", tenant_id=TENANT_A,
    )
    db.add(seg)
    db.commit()
    db.refresh(seg)

    e = svc.create_entity(name="星海科技", type_code="CUS")
    db.add(KgEntityMention(
        tenant_id=TENANT_A, kg_entity_id=e.id, segment_id=seg.id,
        document_id=doc.uuid_code,
    ))
    db.commit()

    out = svc.entity_mentions(e.id)
    assert len(out) == 1
    assert out[0]["chunk_index"] == 2
    assert out[0]["document_id"] == doc.uuid_code
    assert "星海科技" in out[0]["content"]

