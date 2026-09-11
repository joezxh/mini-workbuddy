"""TTL 导入 → 导出 往返一致性测试。

往返口径：把「原始 TTL」和「导出 TTL」分别解析成 rdflib 图，
比较其中**有意义的三元组集合**（类声明 / rdfs:subClassOf / rdfs:label / rdfs:comment），
忽略 rdflib 序列化带来的前缀与顺序差异。
"""
from __future__ import annotations

from typing import Set, Tuple

import pytest
from fastapi.testclient import TestClient
from rdflib import BNode, Graph, RDF, RDFS, OWL, URIRef
from rdflib.compare import isomorphic
from sqlalchemy.orm import Session

from app.ai.knowledge.owl_engine import (
    DEFAULT_ONTOLOGY_NS,
    WikiOwlEngine,
)
from app.services.ontology.ontology_repository import OntologyRepository

from .conftest import TENANT_A

SAMPLE_TTL = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/ontology#> .

ex:Risk a owl:Class ;
    rdfs:label "风险" ;
    rdfs:comment "可能对目标产生影响的不确定性" .

ex:OperationalRisk a owl:Class ;
    rdfs:label "操作风险" ;
    rdfs:subClassOf ex:Risk .

ex:CreditRisk a owl:Class ;
    rdfs:label "信用风险" ;
    rdfs:subClassOf ex:Risk .
"""

TTL_WITH_RESIDUAL = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/ontology#> .

ex:Risk a owl:Class ;
    rdfs:label "风险" .

ex:hasOwner a rdf:Property ;
    rdfs:label "归属人" .
"""


# 含**空节点**（`owl:Restriction`）的真实 OWL 结构：
# 改造前 rdflib 原样保存整图，往返天然一致；持久化改造必须保持这一点。
TTL_WITH_BLANK_NODE = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/ontology#> .

ex:A a owl:Class ;
    rdfs:label "A" ;
    rdfs:subClassOf [ a owl:Restriction ;
                      owl:onProperty ex:hasPart ;
                      owl:someValuesFrom ex:B ] .

ex:B a owl:Class ;
    rdfs:label "B" .
"""

ONTOLOGY_AXIOM_URI = DEFAULT_ONTOLOGY_NS + "wiki"


def _meaningful_triples(ttl: str) -> Set[Tuple[str, str, str]]:
    """抽取用于往返比较的三元组（字符串化，忽略语言标记差异）。"""
    graph = Graph()
    graph.parse(data=ttl, format="turtle")
    triples: Set[Tuple[str, str, str]] = set()
    for subj in graph.subjects(RDF.type, OWL.Class):
        triples.add((str(subj), str(RDF.type), str(OWL.Class)))
        for predicate in (RDFS.label, RDFS.comment):
            value = graph.value(subj, predicate)
            if value is not None:
                triples.add((str(subj), str(predicate), str(value)))
        for parent in graph.objects(subj, RDFS.subClassOf):
            triples.add((str(subj), str(RDFS.subClassOf), str(parent)))
    return triples


def _engine(db: Session, tenant_id: int = TENANT_A) -> WikiOwlEngine:
    return WikiOwlEngine.from_store(OntologyRepository(db, tenant_id))


# ── 引擎层往返 ───────────────────────────────────────────────────────────────

def test_ttl_roundtrip_preserves_classes(db: Session) -> None:
    """导入 → 导出，类声明 / 标签 / 描述 / 父类 全部保持一致。"""
    engine = _engine(db)
    added = engine.import_ttl(SAMPLE_TTL)
    assert added > 0

    exported = engine.export_ttl()
    assert _meaningful_triples(exported) == _meaningful_triples(SAMPLE_TTL)


def test_ttl_roundtrip_is_idempotent(db: Session) -> None:
    """导出内容再导入：新增三元组数为 0，且 ttl_content 不重复膨胀。"""
    engine = _engine(db)
    engine.import_ttl(SAMPLE_TTL)
    first_export = engine.export_ttl()

    added = engine.import_ttl(first_export)
    assert added == 0, "重复导入同一内容不应产生新增三元组"
    assert engine.export_ttl() == first_export


def test_ttl_roundtrip_keeps_non_class_triples(db: Session) -> None:
    """非类三元组（如 rdf:Property）原样保留在导出结果中。"""
    engine = _engine(db)
    engine.import_ttl(TTL_WITH_RESIDUAL)

    exported = Graph()
    exported.parse(data=engine.export_ttl(), format="turtle")
    assert "http://example.org/ontology#hasOwner" in {
        str(s) for s in exported.subjects(RDF.type, RDF.Property)
    }


def test_ttl_roundtrip_across_engine_instances(db_target: str, db: Session) -> None:
    """导入后换新引擎实例（模拟重启）再导出，内容不丢。"""
    from .conftest import engine_for, open_session

    _engine(db).import_ttl(SAMPLE_TTL)

    restarted = engine_for(db_target)
    other = open_session(restarted)
    try:
        exported = _engine(other).export_ttl()
    finally:
        other.close()
        restarted.dispose()
    assert _meaningful_triples(exported) == _meaningful_triples(SAMPLE_TTL)


def test_import_invalid_ttl_raises_value_error(db: Session) -> None:
    """非法 TTL 抛 ValueError（路由层转成 400）。"""
    with pytest.raises(ValueError, match="TTL 解析失败"):
        _engine(db).import_ttl("this is not turtle @@@ {{{")


# ── API 层往返 ───────────────────────────────────────────────────────────────

def test_api_ttl_roundtrip(client_a: TestClient) -> None:
    """POST /import-ttl → GET /export-ttl → 再导入，新增数为 0。"""
    resp = client_a.post(
        "/api/v1/wiki/owl/import-ttl",
        files={"file": ("ontology.ttl", SAMPLE_TTL.encode("utf-8"), "text/turtle")},
    )
    assert resp.status_code == 200, resp.text

    exported = client_a.get("/api/v1/wiki/owl/export-ttl")
    assert exported.status_code == 200
    assert _meaningful_triples(exported.text) == _meaningful_triples(SAMPLE_TTL)

    reimport = client_a.post(
        "/api/v1/wiki/owl/import-ttl",
        files={"file": ("ontology.ttl", exported.text.encode("utf-8"), "text/turtle")},
    )
    assert reimport.status_code == 200, reimport.text
    assert reimport.json()["added"] == 0


def test_api_ttl_is_tenant_scoped(client_a: TestClient, client_b: TestClient) -> None:
    """TTL 导入同样受租户隔离：租户 A 导入的内容不会出现在租户 B 的导出里。"""
    resp = client_a.post(
        "/api/v1/wiki/owl/import-ttl",
        files={"file": ("ontology.ttl", SAMPLE_TTL.encode("utf-8"), "text/turtle")},
    )
    assert resp.status_code == 200, resp.text

    exported_b = client_b.get("/api/v1/wiki/owl/export-ttl").text
    assert "http://example.org/ontology#Risk" not in exported_b
    assert client_b.get("/api/v1/wiki/owl/stats").json()["class_count"] == 0


# ── 空节点（CR-01）───────────────────────────────────────────────────────────

def _graph_without_axiom(ttl: str) -> Graph:
    """解析 TTL 并去掉导出时自动附加的 `onto:wiki a owl:Ontology` 公理。"""
    graph = Graph()
    graph.parse(data=ttl, format="turtle")
    graph.remove((URIRef(ONTOLOGY_AXIOM_URI), RDF.type, OWL.Ontology))
    return graph


def test_ttl_roundtrip_preserves_blank_nodes(db: Session) -> None:
    """含 `owl:Restriction` 空节点的 OWL 导入后导出，图必须同构（往返一致）。"""
    engine = _engine(db)
    engine.import_ttl(TTL_WITH_BLANK_NODE)

    exported = engine.export_ttl()
    assert isomorphic(_graph_without_axiom(exported), _graph_without_axiom(TTL_WITH_BLANK_NODE)), (
        "空节点结构在导入→导出后必须与原文同构，实际导出:\n" + exported
    )


def test_blank_node_is_not_persisted_as_parent_uri(db: Session) -> None:
    """空节点不是 URI，不能作为父类 URI 落库（否则每次导入都多一个假父类）。"""
    engine = _engine(db)
    engine.import_ttl(TTL_WITH_BLANK_NODE)

    cls_a = engine.get_class("http://example.org/ontology#A")
    assert cls_a is not None
    assert cls_a.parent_uris == [], cls_a.parent_uris


def test_repeated_import_of_blank_node_ttl_is_idempotent(db: Session) -> None:
    """同一份含空节点的 TTL 连续导入 3 次：内容不增长、导出完全一致。"""
    engine = _engine(db)

    engine.import_ttl(TTL_WITH_BLANK_NODE)
    first_export = engine.export_ttl()

    for _ in range(2):
        added = engine.import_ttl(TTL_WITH_BLANK_NODE)
        assert added == 0, "重复导入同一内容不应产生新增三元组"

    assert engine.export_ttl() == first_export


# ── 单一真相源（R2-01 / R2-02 / R2-03，第二轮复审）────────────────────────────
# 修复前写操作只改索引、不改原文：
#   * API 注册的 label / 父类在导入含同 URI 类声明的 TTL 后从导出静默消失（R2-01）
#   * 已注销的 TTL 导入类仍留在导出与统计里（R2-02）
# 修复后 `ttl_content` 是唯一真相源，所有写操作先改原文再重建索引。

def test_registered_label_survives_ttl_import(db: Session) -> None:
    """R2-01：API 注册的 label 在导入含同 URI 类声明的 TTL 后不得从导出消失。"""
    engine = _engine(db)
    engine.register_class("http://example.org/ontology#A", label="风险")
    db.commit()

    engine.import_ttl(
        "<http://example.org/ontology#A> a <http://www.w3.org/2002/07/owl#Class> ."
    )
    db.commit()

    exported = _graph_without_axiom(engine.export_ttl())
    label = exported.value(URIRef("http://example.org/ontology#A"), RDFS.label)
    assert label is not None, (
        "API 注册的 label 被 TTL 导入吞掉（R2-01），实际导出:\n" + engine.export_ttl()
    )
    assert str(label) == "风险"


def test_registered_parent_survives_ttl_import(db: Session) -> None:
    """R2-01：API 注册的父类关系在导入含同 URI 类声明的 TTL 后不得丢失。"""
    parent = "http://example.org/ontology#Parent"
    child = "http://example.org/ontology#Child"
    engine = _engine(db)
    engine.register_class(child, parent_uris=[parent])
    db.commit()

    engine.import_ttl(f"<{child}> a <{OWL.Class}> .")
    db.commit()

    exported = _graph_without_axiom(engine.export_ttl())
    assert (URIRef(child), RDFS.subClassOf, URIRef(parent)) in exported, engine.export_ttl()


def test_unregister_removes_class_from_export(db: Session) -> None:
    """R2-02：注销「TTL 导入进来的类」后，导出与索引/统计不再自相矛盾。"""
    x = "http://example.org/ontology#X"
    y = "http://example.org/ontology#Y"
    engine = _engine(db)
    engine.import_ttl(
        f"<{x}> a <{OWL.Class}> . <{y}> a <{OWL.Class}> . <{y}> <{RDFS.subClassOf}> <{x}> ."
    )
    db.commit()

    assert engine.unregister_class(x) is True
    db.commit()

    exported = _graph_without_axiom(engine.export_ttl())
    assert (URIRef(x), RDF.type, OWL.Class) not in exported, engine.export_ttl()
    assert (URIRef(y), RDFS.subClassOf, URIRef(x)) not in exported
    assert x not in {c.uri for c in engine.list_classes()}, "索引说删了导出还在（R2-02）"
    assert engine.stats()["class_count"] == 1


def _ttl_with_restriction(cls_name: str) -> str:
    """生成一个「类 subClassOf 匿名限制」的 TTL，各份之间结构相同、主体不同。"""
    return (
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        "@prefix ex: <http://example.org/ontology#> .\n\n"
        f"ex:{cls_name} rdfs:subClassOf [\n"
        "    a owl:Restriction ;\n"
        "    owl:onProperty ex:hasOwner ;\n"
        "    owl:someValuesFrom ex:User\n"
        "] .\n"
    )


def test_same_structure_blank_nodes_from_two_imports_stay_distinct(db: Session) -> None:
    """R2-03：两次导入「结构相同、主体不同」的匿名限制，不得合并成一个空节点。

    修复前用 `to_canonical_graph` 的规范化标签做集合并集：结构相同的空节点
    获得相同标签 → 两个独立限制被并成一个，两个类的父类指向同一空节点。
    """
    a = "http://example.org/ontology#WithRestrictionA"
    b = "http://example.org/ontology#WithRestrictionB"
    engine = _engine(db)
    engine.import_ttl(_ttl_with_restriction("WithRestrictionA"))
    engine.import_ttl(_ttl_with_restriction("WithRestrictionB"))
    db.commit()

    exported = _graph_without_axiom(engine.export_ttl())
    bn_a = exported.value(URIRef(a), RDFS.subClassOf)
    bn_b = exported.value(URIRef(b), RDFS.subClassOf)
    assert isinstance(bn_a, BNode) and isinstance(bn_b, BNode), engine.export_ttl()
    assert bn_a != bn_b, "两个结构相同的匿名限制被合并成了一个（R2-03）"
    # 每个限制自身的内容都完整保留
    for bn in (bn_a, bn_b):
        assert (bn, OWL.onProperty, URIRef("http://example.org/ontology#hasOwner")) in exported
        assert (bn, OWL.someValuesFrom, URIRef("http://example.org/ontology#User")) in exported
