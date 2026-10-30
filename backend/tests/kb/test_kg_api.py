"""图谱知识库路由契约测试：端点可达性 / 权限矩阵 / 类型守卫 / 租户隔离。

鉴权走真实 ``require_kb_permission``：
- 管理员直通（不查权限表）；
- 非管理员用「权限查询替身」返回指定权限集，验证读/写权限边界。
"""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_current_user, get_db
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.routers.kb.kg import router as kg_router
from tests.kb.conftest import TENANT_A, TENANT_B


def _make_kb(db, tenant_id=TENANT_A, slug="kg-api-1", kb_type=4):
    kb = WikiKnowledge(name="图谱库", slug=slug, type=kb_type, tenant_id=tenant_id)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


class _PermResult:
    def __init__(self, perms):
        self._perms = perms

    def scalars(self):
        return self

    def all(self):
        return list(self._perms)


class _SessionProxy:
    """按语句目标表分流：权限查询走替身，其余代理真实 session。"""

    def __init__(self, real, perms):
        self._real = real
        self._perms = perms

    def execute(self, stmt, *args, **kwargs):
        entity = None
        try:
            descs = stmt.column_descriptions
            entity = descs[0].get("entity") if descs else None
        except Exception:  # noqa: BLE001
            entity = None
        if getattr(entity, "__name__", "") == "SysMenu":
            return _PermResult(self._perms)
        return self._real.execute(stmt, *args, **kwargs)

    def __getattr__(self, item):
        return getattr(self._real, item)


def _client(db, perms=(), is_admin=True, tenant_id=TENANT_A):
    app = FastAPI()
    app.include_router(kg_router)
    user = SimpleNamespace(user_id=1, is_admin=is_admin, tenant_id=tenant_id)
    app.dependency_overrides[get_db] = lambda: _SessionProxy(db, perms)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture
def kb(db):
    return _make_kb(db)


def test_entities_list_empty(db, kb):
    with _client(db) as client:
        r = client.get(f"/api/v1/kb/knowledges/{kb.id}/graph/entities")
        assert r.status_code == 200
        assert r.json()["items"] == []
        assert r.json()["total"] == 0


def test_entity_crud_roundtrip(db, kb):
    with _client(db) as client:
        base = f"/api/v1/kb/knowledges/{kb.id}/graph"
        r = client.post(f"{base}/entities", json={"name": "星海科技", "type_code": "CUS"})
        assert r.status_code == 201
        eid = r.json()["id"]
        assert r.json()["status"] == "suggested"

        r = client.get(f"{base}/entities/{eid}")
        assert r.status_code == 200
        assert r.json()["name"] == "星海科技"

        r = client.put(f"{base}/entities/{eid}", json={"name": "星海科技集团"})
        assert r.status_code == 200
        assert r.json()["name"] == "星海科技集团"

        r = client.patch(f"{base}/entities/{eid}/accept")
        assert r.status_code == 200
        assert r.json()["status"] == "active"

        r = client.delete(f"{base}/entities/{eid}")
        assert r.status_code == 200
        assert client.get(f"{base}/entities").json()["total"] == 0


def test_relation_crud_and_stats(db, kb):
    with _client(db) as client:
        base = f"/api/v1/kb/knowledges/{kb.id}/graph"
        a = client.post(f"{base}/entities", json={"name": "A"}).json()["id"]
        b = client.post(f"{base}/entities", json={"name": "B"}).json()["id"]

        r = client.post(f"{base}/relations", json={
            "from_entity_id": a, "to_entity_id": b,
            "relation_code": "BELONGS", "predicate": "隶属于", "weight": 0.9,
        })
        assert r.status_code == 201
        rid = r.json()["id"]
        assert r.json()["from_entity_name"] == "A"
        assert r.json()["to_entity_name"] == "B"

        r = client.get(f"{base}/relations")
        assert r.status_code == 200
        assert r.json()["total"] == 1

        r = client.patch(f"{base}/relations/{rid}/review", json={"verdict": "accepted"})
        assert r.status_code == 200
        assert r.json()["status"] == "accepted"

        r = client.get(f"{base}/stats")
        assert r.status_code == 200
        body = r.json()
        assert body["entities"] == 2
        assert body["relations"] == 1
        assert body["by_relation"]["BELONGS"] == 1

        assert client.delete(f"{base}/relations/{rid}").status_code == 200


def test_view_permission_cannot_write(db, kb):
    with _client(db, perms=["kb:view"], is_admin=False) as client:
        base = f"/api/v1/kb/knowledges/{kb.id}/graph"
        assert client.get(f"{base}/entities").status_code == 200
        r = client.post(f"{base}/entities", json={"name": "X"})
        assert r.status_code == 403


def test_no_permission_rejected(db, kb):
    with _client(db, perms=[], is_admin=False) as client:
        base = f"/api/v1/kb/knowledges/{kb.id}/graph"
        assert client.get(f"{base}/entities").status_code == 403


def test_non_graph_knowledge_returns_422(db):
    plain = _make_kb(db, slug="kg-api-plain", kb_type=2)
    with _client(db) as client:
        r = client.get(f"/api/v1/kb/knowledges/{plain.id}/graph/entities")
        assert r.status_code == 422


def test_unknown_knowledge_returns_404(db):
    with _client(db) as client:
        r = client.get("/api/v1/kb/knowledges/999999/graph/entities")
        assert r.status_code == 404


def test_cross_tenant_knowledge_returns_404(db, kb):
    with _client(db, tenant_id=TENANT_B) as client:
        r = client.get(f"/api/v1/kb/knowledges/{kb.id}/graph/entities")
        assert r.status_code == 404
