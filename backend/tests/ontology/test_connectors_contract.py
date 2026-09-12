"""外部知识库连接器契约测试（对齐 app/routers/connectors/connector.py）。

租户隔离、tenant_required、同步开关落日志等行为与 DataOps 约定一致。
"""
from __future__ import annotations

from .conftest import TENANT_A, TENANT_B, build_client_routers


def test_list_empty(client_connectors_a) -> None:
    assert client_connectors_a.get("/api/v1/connectors").json() == []


def test_params_config_notion(client_connectors_a) -> None:
    r = client_connectors_a.get(
        "/api/v1/connectors/params-config", params={"type": "notion"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["type"] == "notion"
    assert isinstance(body["options"], list) and body["options"]


def test_create_and_list(client_connectors_a) -> None:
    r = client_connectors_a.post(
        "/api/v1/connectors",
        json={
            "name": "Notion 生产", "connector_type": "notion",
            "token": "secret-xxx", "sync_enabled": True, "kb_dataset": "kb-1",
        },
    )
    assert r.status_code == 201, r.text
    inst = r.json()
    assert inst["name"] == "Notion 生产"
    assert inst["connector_type"] == "notion"
    assert inst["sync_enabled"] is True
    assert inst["kb_dataset"] == "kb-1"
    listed = client_connectors_a.get("/api/v1/connectors").json()
    assert len(listed) == 1 and listed[0]["id"] == inst["id"]


def test_tenant_isolation(client_connectors_a, client_connectors_b) -> None:
    client_connectors_a.post(
        "/api/v1/connectors", json={"name": "A", "connector_type": "web"}
    )
    assert client_connectors_b.get("/api/v1/connectors").json() == []


def test_update(client_connectors_a) -> None:
    inst = client_connectors_a.post(
        "/api/v1/connectors", json={"name": "A", "connector_type": "web"}
    ).json()
    r = client_connectors_a.put(
        f"/api/v1/connectors/{inst['id']}",
        json={"name": "A2", "sync_interval_min": 30},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "A2"
    assert body["sync_interval_min"] == 30


def test_sync_toggle_creates_log(client_connectors_a) -> None:
    inst = client_connectors_a.post(
        "/api/v1/connectors", json={"name": "A", "connector_type": "web"}
    ).json()
    r = client_connectors_a.post(
        f"/api/v1/connectors/{inst['id']}/sync", json={"enabled": True}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sync_enabled"] is True and body["job_id"]
    logs = client_connectors_a.get(
        "/api/v1/connectors/sync-jobs", params={"instance_id": inst["id"]}
    ).json()
    assert len(logs) == 1 and logs[0]["instance_id"] == inst["id"]


def test_delete(client_connectors_a) -> None:
    inst = client_connectors_a.post(
        "/api/v1/connectors", json={"name": "A", "connector_type": "web"}
    ).json()
    assert client_connectors_a.delete(f"/api/v1/connectors/{inst['id']}").status_code == 204
    assert client_connectors_a.get("/api/v1/connectors").json() == []


def test_requires_tenant(db) -> None:
    client = build_client_routers(db, None, ["app.routers.connectors.connector"])
    r = client.get("/api/v1/connectors")
    assert r.status_code == 400 and r.json()["detail"] == "tenant_required"


def test_cross_tenant_not_found(client_connectors_a, client_connectors_b) -> None:
    inst = client_connectors_a.post(
        "/api/v1/connectors", json={"name": "A", "connector_type": "web"}
    ).json()
    assert client_connectors_b.get(f"/api/v1/connectors/{inst['id']}").status_code == 404


def test_tenant_a_is_constant() -> None:
    assert TENANT_A != TENANT_B
