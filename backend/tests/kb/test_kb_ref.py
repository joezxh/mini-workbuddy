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
    """D1：端点测试改打主应用路由 /api/v1/kb（依赖覆盖 db + 登录用户）。"""
    from fastapi import FastAPI

    from app.deps import get_current_user, get_db
    from app.routers.kb.kb import router as kb_router

    app = FastAPI()
    app.include_router(kb_router)

    def _override_db():
        yield db

    def _override_user():
        user = type("U", (), {})()
        user.tenant_id = 100
        user.user_id = 7
        user.username = "tester"
        # 管理员直通（Phase 3 T3 权限点），避免测试依赖 sys_menu 等系统表
        user.is_admin = True
        return user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


BASE = "/api/v1/kb/kb-refs"


def test_create_and_get_endpoint(client):
    r = client.post(BASE, json={"name": "端点库", "description": "d"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "端点库"
    assert body["as_user_id"] == to_as_user_id(100)  # 租户来自登录用户
    kb_id = body["kb_id"]

    g = client.get(f"{BASE}/{kb_id}")
    assert g.status_code == 200
    assert g.json()["name"] == "端点库"


def test_list_endpoint_tenant_isolation(client, db):
    client.post(BASE, json={"name": "A库"})  # 登录用户租户=100
    # 另一租户的库用服务层直接创建（同一测试 schema）
    from app.services.kb.kb_ref_service import KbRefService

    KbRefService(db, 200).create_kb_ref("B库")
    db.flush()
    listed = client.get(BASE)
    assert [x["name"] for x in listed.json()] == ["A库"]  # 仅本租户可见


def test_delete_endpoint(client):
    r = client.post(BASE, json={"name": "del"})
    kb_id = r.json()["kb_id"]
    d = client.delete(f"{BASE}/{kb_id}")
    assert d.status_code == 200
    g = client.get(f"{BASE}/{kb_id}")
    assert g.status_code == 404
