"""本体持久化与租户隔离测试。

TDD 说明
--------
本文件第一条用例 `test_tenant_b_cannot_see_tenant_a_classes` 是**先写的失败测试**：
改造前 `get_owl_engine()` 返回进程级单例，租户 B 能看到租户 A 注册的类，
该用例在改造前必须失败（用于暴露「跨租户可见」缺陷）。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ── 1. 租户隔离（缺陷暴露用例）────────────────────────────────────────────────

def test_tenant_b_cannot_see_tenant_a_classes(
    client_a: TestClient, client_b: TestClient
) -> None:
    """租户 A 注册一个 OWL 类后，租户 B 的列表必须为空。"""
    resp = client_a.post(
        "/api/v1/wiki/owl/classes",
        json={"uri": "http://example.org/ontology#Risk", "label": "风险"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["uri"] == "http://example.org/ontology#Risk"

    resp_b = client_b.get("/api/v1/wiki/owl/classes")
    assert resp_b.status_code == 200, resp_b.text
    assert resp_b.json() == [], "租户 B 不应看到租户 A 的本体类"


def test_tenant_a_cannot_see_tenant_b_classes(
    client_a: TestClient, client_b: TestClient
) -> None:
    """反向隔离：租户 B 注册的类对租户 A 同样不可见。"""
    resp = client_b.post(
        "/api/v1/wiki/owl/classes",
        json={"uri": "http://example.org/ontology#Control", "label": "控制措施"},
    )
    assert resp.status_code == 200, resp.text

    resp_a = client_a.get("/api/v1/wiki/owl/classes")
    assert resp_a.status_code == 200, resp_a.text
    assert resp_a.json() == [], "租户 A 不应看到租户 B 的本体类"


def test_same_tenant_sees_own_classes(client_a: TestClient) -> None:
    """同租户内注册的类可见（隔离不能做成全空）。"""
    for uri, label in [
        ("http://example.org/ontology#Risk", "风险"),
        ("http://example.org/ontology#Control", "控制措施"),
    ]:
        resp = client_a.post(
            "/api/v1/wiki/owl/classes", json={"uri": uri, "label": label}
        )
        assert resp.status_code == 200, resp.text

    listed = client_a.get("/api/v1/wiki/owl/classes").json()
    assert {c["uri"] for c in listed} == {
        "http://example.org/ontology#Risk",
        "http://example.org/ontology#Control",
    }


# ── 2. 持久化（重启/新实例不丢）──────────────────────────────────────────────


def test_classes_survive_new_engine_instance(db_target: str) -> None:
    """新建引擎实例（模拟重启）后，已注册的类仍在。

    两次访问之间用 `engine_for()` **重建 engine**（新连接池、新连接），
    确保数据来自数据库而非任何进程内缓存。
    """
    from app.ai.knowledge.owl_engine import WikiOwlEngine
    from app.services.ontology.ontology_repository import OntologyRepository

    from .conftest import engine_for, open_session

    uri = "http://example.org/ontology#Asset"

    # 第一次「进程」：注册
    eng1 = engine_for(db_target, create_tables=True)
    sess1 = open_session(eng1)
    try:
        WikiOwlEngine.from_store(OntologyRepository(sess1, 9001)).register_class(
            uri, label="资产", comment="企业资产"
        )
        sess1.commit()
    finally:
        sess1.close()
        eng1.dispose()

    # 第二次「进程」：全新 engine + 全新会话，数据应仍在
    eng2 = engine_for(db_target)
    sess2 = open_session(eng2)
    try:
        engine2 = WikiOwlEngine.from_store(OntologyRepository(sess2, 9001))
        classes = engine2.list_classes()
        assert [c.uri for c in classes] == [uri]
        assert classes[0].label == "资产"
        assert classes[0].comment == "企业资产"
    finally:
        sess2.close()
        eng2.dispose()


def test_classes_survive_across_sessions(engine, db) -> None:
    """同一文件库、不同会话之间数据可见。"""
    from app.ai.knowledge.owl_engine import WikiOwlEngine
    from app.services.ontology.ontology_repository import OntologyRepository

    from .conftest import open_session

    uri = "http://example.org/ontology#Incident"
    WikiOwlEngine.from_store(OntologyRepository(db, 9002)).register_class(
        uri, label="事件"
    )
    db.commit()

    other = open_session(engine)
    try:
        engine2 = WikiOwlEngine.from_store(OntologyRepository(other, 9002))
        assert [c.uri for c in engine2.list_classes()] == [uri]
    finally:
        other.close()


def test_tenant_id_none_is_logged_as_shared_partition(db, caplog) -> None:
    """`tenant_id=None` 落到 NULL 分区（多个无租户用户共享）。

    评审 IM-07：简报未授权改成 400，因此保留 NULL 分区语义，
    但必须**显式告警**而不是静默共享。本用例把该行为与告警固化下来。
    """
    from app.ai.knowledge.owl_engine import WikiOwlEngine
    from app.services.ontology.ontology_repository import OntologyRepository

    uri = "http://example.org/ontology#Shared"
    with caplog.at_level("WARNING"):
        engine = WikiOwlEngine.from_store(OntologyRepository(db, None))

    assert any("NULL 租户分区" in r.getMessage() for r in caplog.records), [
        r.getMessage() for r in caplog.records
    ]

    engine.register_class(uri, label="共享类")
    db.commit()
    assert [c.uri for c in WikiOwlEngine.from_store(OntologyRepository(db, None)).list_classes()] == [uri]


def test_unregister_clears_annotation_references(db) -> None:
    """注销类后，指向该类的文章标注必须一并清理（评审 IM-04）。

    改造前 `unregister_class` 会删除所有 `<target> a <uri>` 三元组；
    只清理 `parent_uris` 会留下悬挂引用：`get_articles_by_class(uri)`
    仍返回指向已删除类的文章。
    """
    from app.ai.knowledge.owl_engine import WikiOwlEngine
    from app.services.ontology.ontology_repository import OntologyRepository

    uri = "http://example.org/ontology#Risk"
    engine = WikiOwlEngine.from_store(OntologyRepository(db, 9004))
    engine.register_class(uri, label="风险")
    engine.annotate_article("wiki://article-1", [uri])
    engine.annotate_article("wiki://article-2", [uri, "http://example.org/ontology#Other"])
    db.commit()

    assert sorted(engine.get_articles_by_class(uri)) == ["wiki://article-1", "wiki://article-2"]

    assert engine.unregister_class(uri) is True
    db.commit()

    assert engine.get_articles_by_class(uri) == [], "类已删除，不应再有指向它的标注"
    # 标注行里引用的其它类不能被误删
    assert engine.get_article_classes("wiki://article-2") == [
        "http://example.org/ontology#Other"
    ]


def test_unregister_is_persisted(engine, db) -> None:
    """删除操作同样持久化：新实例里类已消失。"""
    from app.ai.knowledge.owl_engine import WikiOwlEngine
    from app.services.ontology.ontology_repository import OntologyRepository

    from .conftest import open_session

    uri = "http://example.org/ontology#Temp"
    eng = WikiOwlEngine.from_store(OntologyRepository(db, 9003))
    eng.register_class(uri, label="临时")
    db.commit()
    assert eng.unregister_class(uri) is True
    db.commit()

    other = open_session(engine)
    try:
        assert WikiOwlEngine.from_store(
            OntologyRepository(other, 9003)
        ).list_classes() == []
    finally:
        other.close()
