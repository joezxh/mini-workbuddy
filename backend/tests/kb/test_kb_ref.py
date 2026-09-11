"""kb_ref 服务 + 端点测试（P1 Task 9）。

服务层：创建/列出/获取/删除 + 租户隔离。
端点层：通过 TestClient 打 /kb 路由，依赖 get_db 用测试会话覆盖，验证
X-Tenant-Id 隔离与 404/400 行为。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.kb.kb_ref_service import KbRefService
from app.services.kb.user_id_mapper import to_as_user_id


# ------------------------------------------------------------------ #
# 服务层
# ------------------------------------------------------------------ #
def test_create_and_list(db):
    svc = KbRefService(db, 100)
    ref = svc.create_kb_ref("我的知识库", "desc", creator_id=7)
    db.flush()
    assert ref.tenant_id == 100
    assert ref.kb_id
    assert ref.as_user_id == to_as_user_id(100)
    refs = svc.list_kb_refs()
    assert len(refs) == 1
    assert refs[0].name == "我的知识库"


def test_get_and_delete(db):
    svc = KbRefService(db, 100)
    ref = svc.create_kb_ref("kb")
    db.flush()
    kb_id = ref.kb_id
    assert svc.get_kb_ref(kb_id).name == "kb"
    assert svc.delete_kb_ref(kb_id) is True
    assert svc.get_kb_ref(kb_id) is None
    assert svc.delete_kb_ref(kb_id) is False


def test_service_tenant_isolation(db):
    a = KbRefService(db, 100)
    b = KbRefService(db, 200)
    ra = a.create_kb_ref("A库")
    rb = b.create_kb_ref("B库")
    db.flush()
    # 跨租户互相不可见
    assert a.get_kb_ref(rb.kb_id) is None
    assert b.get_kb_ref(ra.kb_id) is None
    assert [r.name for r in a.list_kb_refs()] == ["A库"]
    assert [r.name for r in b.list_kb_refs()] == ["B库"]


def test_service_requires_tenant(db):
    with pytest.raises(ValueError):
        KbRefService(db, None)


# ------------------------------------------------------------------ #
# 端点层（依赖覆盖，用测试会话）
# ------------------------------------------------------------------ #
@pytest.fixture
def client(db):
    from app.services.kb.kb_app import kb_app
    from app.services.kb.kb_router import get_db as kb_get_db

    def _override():
        yield db

    kb_app.dependency_overrides[kb_get_db] = _override
    with TestClient(kb_app) as c:
        yield c
    kb_app.dependency_overrides.clear()


def test_create_and_get_endpoint(client):
    r = client.post("/kb", json={"name": "端点库", "description": "d"}, headers={"X-Tenant-Id": "100"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "端点库"
    assert body["as_user_id"] == to_as_user_id(100)
    kb_id = body["kb_id"]

    g = client.get(f"/kb/{kb_id}", headers={"X-Tenant-Id": "100"})
    assert g.status_code == 200
    assert g.json()["name"] == "端点库"


def test_list_endpoint_tenant_isolation(client):
    client.post("/kb", json={"name": "A库"}, headers={"X-Tenant-Id": "100"})
    client.post("/kb", json={"name": "B库"}, headers={"X-Tenant-Id": "200"})
    ra = client.get("/kb", headers={"X-Tenant-Id": "100"})
    rb = client.get("/kb", headers={"X-Tenant-Id": "200"})
    assert [x["name"] for x in ra.json()] == ["A库"]
    assert [x["name"] for x in rb.json()] == ["B库"]
    # 跨租户获取他人 kb → 404
    kb_a_id = ra.json()[0]["kb_id"]
    cross = client.get(f"/kb/{kb_a_id}", headers={"X-Tenant-Id": "200"})
    assert cross.status_code == 404


def test_missing_tenant_rejected(client):
    r = client.post("/kb", json={"name": "x"})
    assert r.status_code == 400


def test_delete_endpoint(client):
    r = client.post("/kb", json={"name": "del"}, headers={"X-Tenant-Id": "100"})
    kb_id = r.json()["kb_id"]
    d = client.delete(f"/kb/{kb_id}", headers={"X-Tenant-Id": "100"})
    assert d.status_code == 204
    g = client.get(f"/kb/{kb_id}", headers={"X-Tenant-Id": "100"})
    assert g.status_code == 404
