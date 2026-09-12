"""本体治理契约测试（对齐 app/routers/ontology/ontology.py）。

覆盖本体 CRUD、类层级 CRUD、TTL 导入/导出、对象类型与空列表端点；
租户隔离与 tenant_required 与连接器保持一致。
"""
from __future__ import annotations

from .conftest import build_client_routers

SAMPLE_TTL = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/ontology#> .

ex:Risk a owl:Class ;
    rdfs:label "风险" ;
    rdfs:comment "风险描述" .
"""


def _make_ontology(client) -> dict:
    return client.post(
        "/api/v1/ontology",
        json={"code": "default", "name": "默认本体", "namespace": "http://x/#"},
    ).json()


def test_list_empty(client_ontology_a) -> None:
    assert client_ontology_a.get("/api/v1/ontology").json() == []


def test_create_and_get(client_ontology_a) -> None:
    o = _make_ontology(client_ontology_a)
    assert o["code"] == "default"
    got = client_ontology_a.get(f"/api/v1/ontology/{o['id']}").json()
    assert got["id"] == o["id"]
    assert len(client_ontology_a.get("/api/v1/ontology").json()) == 1


def test_classes_crud(client_ontology_a) -> None:
    o = _make_ontology(client_ontology_a)
    assert client_ontology_a.get(f"/api/v1/ontology/{o['id']}/classes").json() == []

    c = client_ontology_a.post(
        f"/api/v1/ontology/{o['id']}/classes",
        json={"name": "风险", "comment": "风险描述"},
    ).json()
    assert c["label"] == "风险" and c["uri"]

    listed = client_ontology_a.get(f"/api/v1/ontology/{o['id']}/classes").json()
    assert len(listed) == 1 and listed[0]["id"] == c["id"]

    u = client_ontology_a.put(
        f"/api/v1/ontology/{o['id']}/classes/{c['id']}", json={"comment": "更新"}
    ).json()
    assert u["comment"] == "更新"

    assert client_ontology_a.delete(
        f"/api/v1/ontology/{o['id']}/classes/{c['id']}"
    ).status_code == 204
    assert client_ontology_a.get(f"/api/v1/ontology/{o['id']}/classes").json() == []


def test_export_returns_turtle(client_ontology_a) -> None:
    o = _make_ontology(client_ontology_a)
    client_ontology_a.post(
        f"/api/v1/ontology/{o['id']}/classes", json={"name": "风险"}
    )
    r = client_ontology_a.get(f"/api/v1/ontology/{o['id']}/export")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/turtle")
    assert "风险" in r.text


def test_import_ttl(client_ontology_a) -> None:
    o = _make_ontology(client_ontology_a)
    r = client_ontology_a.post(
        f"/api/v1/ontology/{o['id']}/import",
        files={"file": ("o.ttl", SAMPLE_TTL.encode("utf-8"), "text/turtle")},
    )
    assert r.status_code == 200, r.text
    uris = {
        c["uri"]
        for c in client_ontology_a.get(f"/api/v1/ontology/{o['id']}/classes").json()
    }
    assert "http://example.org/ontology#Risk" in uris


def test_object_types_and_empty_lists(client_ontology_a) -> None:
    o = _make_ontology(client_ontology_a)
    assert client_ontology_a.get(f"/api/v1/ontology/{o['id']}/object-types").json() == []
    ot = client_ontology_a.post(
        f"/api/v1/ontology/{o['id']}/object-types", json={"name": "客户"}
    ).json()
    assert ot["name"] == "客户"
    assert len(client_ontology_a.get(f"/api/v1/ontology/{o['id']}/object-types").json()) == 1

    assert client_ontology_a.get(f"/api/v1/ontology/{o['id']}/relations").json() == []
    assert client_ontology_a.get(f"/api/v1/ontology/{o['id']}/cqs").json() == []
    assert client_ontology_a.get(f"/api/v1/ontology/{o['id']}/review").json() == []
    assert client_ontology_a.get(f"/api/v1/ontology/{o['id']}/versions").json() == []


def test_tenant_isolation(client_ontology_a, client_ontology_b) -> None:
    o = _make_ontology(client_ontology_a)
    assert client_ontology_b.get(f"/api/v1/ontology/{o['id']}").status_code == 404


def test_requires_tenant(db) -> None:
    client = build_client_routers(db, None, ["app.routers.ontology.ontology"])
    assert client.get("/api/v1/ontology").status_code == 400
