"""本体领域 CRUD API 与引用完整性（真实 PG + per-schema 隔离）。"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.ontology.conftest import TENANT_A, TENANT_B


BASE = "/api/v1/dataops"


def _create(client: TestClient, code: str, name: str, **extra) -> dict:
    resp = client.post(f"{BASE}/domains", json={"code": code, "name": name, **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_domain_crud_lifecycle(client_a: TestClient) -> None:
    created = _create(client_a, "hr", "HR人力资源", sort_order=3)
    did = created["id"]
    assert created["status"] == "active"
    assert created["reference_count"] == 0

    listing = client_a.get(f"{BASE}/domains", params={"status": "active", "keyword": "HR"})
    assert listing.status_code == 200
    assert [d["id"] for d in listing.json()] == [did]

    updated = client_a.put(f"{BASE}/domains/{did}", json={"name": "人力资源", "sort_order": 1})
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "人力资源"

    toggled = client_a.put(f"{BASE}/domains/{did}/toggle", json={"status": "disabled"})
    assert toggled.status_code == 200, toggled.text
    assert toggled.json()["status"] == "disabled"
    assert client_a.get(f"{BASE}/domains", params={"status": "active"}).json() == []

    deleted = client_a.delete(f"{BASE}/domains/{did}")
    assert deleted.status_code == 204
    assert client_a.get(f"{BASE}/domains").json() == []


def test_domain_code_duplicate_and_tenant_isolation(client_a: TestClient, client_b: TestClient) -> None:
    d = _create(client_a, "supply_chain", "供应链管理")
    dup = client_a.post(f"{BASE}/domains", json={"code": "supply_chain", "name": "重复"})
    assert dup.status_code == 409
    assert dup.json()["code"] == "DOMAIN_CODE_DUPLICATED"

    # 另一租户看不到 A 的领域，也允许同 code
    assert client_b.get(f"{BASE}/domains").json() == []
    other = _create(client_b, "supply_chain", "B 的供应链")
    assert other["id"] != d["id"]
    # 跨租户修改 A 的领域应视为不存在
    cross = client_b.put(f"{BASE}/domains/{d['id']}", json={"name": "篡改"})
    assert cross.status_code == 404


def test_ontology_domain_filter_and_detach(client_a: TestClient, db: Session) -> None:
    from app.models.ontology.domain import OntoDomain
    from app.models.ontology.ontology import MetaOntology

    domain = OntoDomain(tenant_id=TENANT_A, code="finance", name="财务", status="active")
    db.add(domain)
    db.flush()
    onto = MetaOntology(tenant_id=TENANT_A, code="fin-onto", name="财务本体",
                        status="draft", current_version=0, domain_id=domain.id)
    db.add(onto)
    db.flush()

    listed = client_a.get(f"{BASE}/ontologies", params={"domain_id": domain.id})
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1 and items[0]["domain_id"] == domain.id
    assert items[0]["domain_name"] == "财务"

    detail = client_a.get(f"{BASE}/ontologies/{onto.id}")
    assert detail.json()["domain_name"] == "财务"

    # 停用领域后不能被新本体引用
    client_a.put(f"{BASE}/domains/{domain.id}/toggle", json={"status": "disabled"})
    blocked = client_a.post(f"{BASE}/ontologies", json={
        "code": "fin-onto-2", "name": "财务本体2", "domain_id": domain.id,
    })
    assert blocked.status_code in (400, 404)
