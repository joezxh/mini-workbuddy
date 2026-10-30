"""图谱知识库端到端冒烟：经**真实创建链路**建库，再跑通图谱实例全流程。

覆盖计划 Task 9 Step 1：
建 type=4 知识库 → 建实体 → 查实体 → 评审 → 建关系 → 查统计 → 跨租户隔离。
"""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_current_user, get_db
from app.routers.kb.kg import router as kg_router
from app.routers.kb.knowledge_mgnt import router as kb_admin_router
from tests.kb.conftest import TENANT_A, TENANT_B


class _PermResult:
    def __init__(self, perms):
        self._perms = perms

    def scalars(self):
        return self

    def all(self):
        return list(self._perms)


class _SessionProxy:
    """权限查询走替身，其余代理真实 session（系统权限表不在 kb 测试 schema 内）。"""

    def __init__(self, real, perms=()):
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


def _client(db, tenant_id=TENANT_A, is_admin=True, perms=()):
    app = FastAPI()
    app.include_router(kb_admin_router)
    app.include_router(kg_router)
    user = SimpleNamespace(user_id=1, is_admin=is_admin, tenant_id=tenant_id)
    app.dependency_overrides[get_db] = lambda: _SessionProxy(db, perms)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture
def created_kb(db):
    """经真实创建链路建一个 type=4 知识库，返回其 id。"""
    with _client(db) as client:
        r = client.post("/api/v1/kb/knowledges", json={
            "name": "图谱E2E库",
            "description": "端到端冒烟",
            "type": 4,
            "kb_format": "graph",
            "category_id": None,
        })
        assert r.status_code == 201, r.text
        return r.json()


def test_create_graph_kb_enforces_constraints(created_kb):
    """type=4 建库后：形态固定 graph、索引恒 high_quality、恒不启用多模态、无外部类型。"""
    assert created_kb["type"] == 4
    assert created_kb["kb_format"] == "graph"
    assert created_kb["index_mode"] == "high_quality"
    assert created_kb["multimodal_enabled"] is False
    assert created_kb.get("external_type") in (None, "")


def test_created_kb_is_tenant_owned(db, created_kb):
    """新建知识库必须落 tenant_id：生产租户拦截器按 tenant_id 过滤，
    tenant_id 为 NULL 的库对任何租户都不可见（建了也看不到）。"""
    from app.models.wiki.wiki_knowledge import WikiKnowledge

    kb = db.get(WikiKnowledge, created_kb["id"])
    assert kb is not None
    assert kb.tenant_id == TENANT_A


def test_graph_kb_full_flow(db, created_kb):
    kid = created_kb["id"]
    with _client(db) as client:
        base = f"/api/v1/kb/knowledges/{kid}/graph"

        # 建实体
        r = client.post(f"{base}/entities", json={
            "name": "星海科技", "type_code": "CUS", "aliases": ["Xinghai"],
        })
        assert r.status_code == 201, r.text
        a_id = r.json()["id"]

        r = client.post(f"{base}/entities", json={"name": "订单B1", "type_code": "ORD"})
        assert r.status_code == 201
        b_id = r.json()["id"]

        # 查实体 + 关键词过滤
        r = client.get(f"{base}/entities", params={"keyword": "星海"})
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["aliases"] == ["Xinghai"]

        # 评审实体
        r = client.patch(f"{base}/entities/{a_id}/accept")
        assert r.status_code == 200
        assert r.json()["status"] == "active"

        # 建关系
        r = client.post(f"{base}/relations", json={
            "from_entity_id": a_id, "to_entity_id": b_id,
            "relation_code": "PLACES", "predicate": "下达", "weight": 0.92,
        })
        assert r.status_code == 201, r.text
        rel_id = r.json()["id"]
        assert r.json()["from_entity_name"] == "星海科技"

        # 统计
        r = client.get(f"{base}/stats")
        assert r.status_code == 200
        body = r.json()
        assert body["entities"] == 2
        assert body["relations"] == 1
        assert body["by_type"]["CUS"] == 1
        assert body["by_relation"]["PLACES"] == 1

        # 幂等：重复建同键实体不增行
        client.post(f"{base}/entities", json={"name": "星海科技", "type_code": "CUS"})
        assert client.get(f"{base}/stats").json()["entities"] == 2

        # 关系评审
        r = client.patch(f"{base}/relations/{rel_id}/review", json={"verdict": "accepted"})
        assert r.status_code == 200
        assert r.json()["status"] == "accepted"


def test_graph_kb_cross_tenant_read_isolated(db, created_kb):
    kid = created_kb["id"]
    with _client(db) as client:
        client.post(
            f"/api/v1/kb/knowledges/{kid}/graph/entities",
            json={"name": "租户A实体", "type_code": "X"},
        )
    with _client(db, tenant_id=TENANT_B) as client:
        r = client.get(f"/api/v1/kb/knowledges/{kid}/graph/entities")
        assert r.status_code == 404
