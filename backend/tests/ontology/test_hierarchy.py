"""类层级查询与循环父类防护测试。

要求：
- `get_ancestors` / `get_descendants` / `get_hierarchy` 结果正确；
- **存在循环父类时不死循环**（改造前的 `get_hierarchy` 会在
  `root -> A -> B -> A` 这类结构下无限递归直至 RecursionError）。
"""
from __future__ import annotations

from typing import List

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.knowledge.owl_engine import HierarchyNode, WikiOwlEngine
from app.services.ontology.ontology_repository import OntologyRepository

NS = "http://example.org/ontology#"
ROOT = NS + "Root"
CHILD = NS + "Child"
GRAND = NS + "GrandChild"


def _engine(db: Session, tenant_id: int = 700) -> WikiOwlEngine:
    return WikiOwlEngine.from_store(OntologyRepository(db, tenant_id))


def _find(nodes: List[HierarchyNode], uri: str):
    for node in nodes:
        if node.uri == uri:
            return node
        found = _find(node.children, uri)
        if found is not None:
            return found
    return None


def _build_chain(engine: WikiOwlEngine) -> None:
    engine.register_class(ROOT, label="根")
    engine.register_class(CHILD, label="子", parent_uris=[ROOT])
    engine.register_class(GRAND, label="孙", parent_uris=[CHILD])


# ── 基本层级查询 ─────────────────────────────────────────────────────────────

def test_ancestors_returns_all_levels(db: Session) -> None:
    engine = _engine(db)
    _build_chain(engine)
    assert engine.get_ancestors(GRAND) == [CHILD, ROOT]
    assert engine.get_ancestors(CHILD) == [ROOT]
    assert engine.get_ancestors(ROOT) == []


def test_descendants_returns_all_levels(db: Session) -> None:
    engine = _engine(db)
    _build_chain(engine)
    assert engine.get_descendants(ROOT) == [CHILD, GRAND]
    assert engine.get_descendants(CHILD) == [GRAND]
    assert engine.get_descendants(GRAND) == []


def test_hierarchy_shape(db: Session) -> None:
    engine = _engine(db)
    _build_chain(engine)
    tree = engine.get_hierarchy()
    assert len(tree) == 1
    assert tree[0].uri == ROOT
    assert [c.uri for c in tree[0].children] == [CHILD]
    assert [c.uri for c in tree[0].children[0].children] == [GRAND]
    assert _find(tree, GRAND).label == "孙"


def test_hierarchy_includes_unregistered_parent(db: Session) -> None:
    """父类未单独注册时也作为节点出现（与改造前一致）。"""
    engine = _engine(db)
    engine.register_class(CHILD, label="子", parent_uris=[NS + "ExternalParent"])

    tree = engine.get_hierarchy()
    assert [n.uri for n in tree] == [NS + "ExternalParent"]
    assert tree[0].label == "ExternalParent"  # 无标签时回退为 URI 末段
    assert [c.uri for c in tree[0].children] == [CHILD]


def test_unregister_clears_parent_references(db: Session) -> None:
    """删除父类后，子类的 parent_uris 不再指向它（不产生悬挂引用）。"""
    engine = _engine(db)
    _build_chain(engine)
    assert engine.unregister_class(CHILD) is True

    assert engine.get_class(CHILD) is None
    assert engine.get_class(GRAND).parent_uris == []
    # CHILD 被删除后，GRAND 与 ROOT 都成为根节点（与改造前 rdflib 行为一致）
    assert {n.uri for n in engine.get_hierarchy()} == {ROOT, GRAND}


# ── 循环父类防护 ─────────────────────────────────────────────────────────────

def test_ancestors_terminates_on_cycle(db: Session) -> None:
    """A -> B -> A：祖先查询不死循环。"""
    engine = _engine(db)
    engine.register_class(NS + "A", label="A", parent_uris=[NS + "B"])
    engine.register_class(NS + "B", label="B", parent_uris=[NS + "A"])

    result = engine.get_ancestors(NS + "A")
    assert set(result) == {NS + "A", NS + "B"}


def test_descendants_terminates_on_cycle(db: Session) -> None:
    """A -> B -> A：后代查询不死循环。"""
    engine = _engine(db)
    engine.register_class(NS + "A", label="A", parent_uris=[NS + "B"])
    engine.register_class(NS + "B", label="B", parent_uris=[NS + "A"])

    result = engine.get_descendants(NS + "A")
    assert set(result) == {NS + "A", NS + "B"}


def test_hierarchy_terminates_on_cycle_between_roots(db: Session) -> None:
    """A -> B -> A：二者互为父子，无根节点，层级树为空且能正常返回。"""
    engine = _engine(db)
    engine.register_class(NS + "A", label="A", parent_uris=[NS + "B"])
    engine.register_class(NS + "B", label="B", parent_uris=[NS + "A"])

    assert engine.get_hierarchy() == []


def test_hierarchy_terminates_on_cycle_under_root(db: Session) -> None:
    """Root -> A -> B -> A：循环挂在根节点之下，必须在 A 处截断而不是无限递归。"""
    engine = _engine(db)
    engine.register_class(ROOT, label="根")
    engine.register_class(NS + "A", label="A", parent_uris=[ROOT, NS + "B"])
    engine.register_class(NS + "B", label="B", parent_uris=[NS + "A"])

    tree = engine.get_hierarchy()
    assert [n.uri for n in tree] == [ROOT]
    node_a = tree[0].children[0]
    assert node_a.uri == NS + "A"
    # B 展开后指向 A，A 已在祖先链上 → 截断为空 children
    node_b = node_a.children[0]
    assert node_b.uri == NS + "B"
    assert node_b.children[0].uri == NS + "A"
    assert node_b.children[0].children == []


def test_hierarchy_terminates_on_self_parent(db: Session) -> None:
    """自环：A -> A。"""
    engine = _engine(db)
    engine.register_class(NS + "A", label="A", parent_uris=[NS + "A"])

    assert engine.get_ancestors(NS + "A") == [NS + "A"]
    assert engine.get_hierarchy() == []


def test_hierarchy_cycle_survives_persistence(engine, db: Session) -> None:
    """循环结构落库后，新引擎实例读取时同样不死循环。"""
    from .conftest import open_session

    eng = _engine(db)
    eng.register_class(NS + "A", label="A", parent_uris=[NS + "B"])
    eng.register_class(NS + "B", label="B", parent_uris=[NS + "A"])

    other = open_session(engine)
    try:
        reloaded = _engine(other)
        assert reloaded.get_hierarchy() == []
        assert set(reloaded.get_ancestors(NS + "A")) == {NS + "A", NS + "B"}
    finally:
        other.close()


def test_api_hierarchy_with_cycle_returns_200(client_a: TestClient) -> None:
    """API 层：循环父类时 /hierarchy 仍能 200 返回（不会打挂请求）。"""
    assert client_a.post(
        "/api/v1/wiki/owl/classes",
        json={"uri": NS + "A", "label": "A", "parent_uris": [NS + "B"]},
    ).status_code == 200
    assert client_a.post(
        "/api/v1/wiki/owl/classes",
        json={"uri": NS + "B", "label": "B", "parent_uris": [NS + "A"]},
    ).status_code == 200

    resp = client_a.get("/api/v1/wiki/owl/hierarchy")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
