"""图谱构建管理端点 / 配置端点 / 失败清单端点契约测试（P3）。

覆盖：
* ``/graph-build/submit``：动作分发 + 单库互斥 409 + 非法动作 422
* ``/graph-build/status``：五态状态机（未构建/构建中/就绪/部分失败/降级）
* ``/graph/failed-segments``：失败切片清单
* ``/graph/config`：读写 + 越界钳制
* ``/graph/documents/rebuild``：单文档重抽
"""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_current_user, get_db
from app.models.kb.kb_document import KbDocument, new_document_uuid
from app.models.kb.kb_segment import KbSegment
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.routers.kb.kg import build_router, router as kg_router
from app.services.kb.kg import kg_build_service
from tests.kb.conftest import TENANT_A, TENANT_B
from tests.kb.test_kg_api import _SessionProxy


def _client(db, perms=(), is_admin=True, tenant_id=TENANT_A):
    app = FastAPI()
    app.include_router(kg_router)
    app.include_router(build_router)
    user = SimpleNamespace(user_id=1, is_admin=is_admin, tenant_id=tenant_id)
    app.dependency_overrides[get_db] = lambda: _SessionProxy(db, perms)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_locks():
    kg_build_service.reset_locks()
    yield
    kg_build_service.reset_locks()


@pytest.fixture
def kb(db):
    obj = WikiKnowledge(name="图谱库", slug="kg-bapi-1", type=4, tenant_id=TENANT_A)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def _segment(db, kb, *, index=0, structure=None, vector=None, details=None,
             document_id=None):
    doc_uuid = document_id or new_document_uuid()
    seg = KbSegment(
        collection=f"kb_{kb.id}", document_id=doc_uuid, chunk_index=index,
        content="内容", tenant_id=TENANT_A,
        graph_structure_indexed=structure,
        graph_indexed=vector,
        graph_extraction_details=details,
    )
    db.add(seg)
    db.commit()
    db.refresh(seg)
    return seg


# ── 提交构建 ─────────────────────────────────────────────────────────────
def test_submit_build_accepted(monkeypatch, db, kb):
    import app.core.job_runner as job_runner

    started = {}
    monkeypatch.setattr(
        job_runner, "run_in_background",
        lambda fn, *a, **kw: started.setdefault("fn", fn),
    )
    with _client(db) as c:
        r = c.post(f"/api/v1/kb/knowledges/{kb.id}/graph-build/submit",
                   json={"action": "build"})
    assert r.status_code == 200 and r.json()["accepted"] is True
    assert started.get("fn") is not None


def test_submit_build_conflict_returns_409(db, kb):
    kg_build_service.try_acquire(kb.id)
    with _client(db) as c:
        r = c.post(f"/api/v1/kb/knowledges/{kb.id}/graph-build/submit",
                   json={"action": "build"})
    assert r.status_code == 409


def test_submit_unknown_action_422(db, kb):
    with _client(db) as c:
        r = c.post(f"/api/v1/kb/knowledges/{kb.id}/graph-build/submit",
                   json={"action": "explode"})
    assert r.status_code == 422


def test_submit_requires_admin_permission(db, kb):
    with _client(db, perms=("kb:view",), is_admin=False) as c:
        r = c.post(f"/api/v1/kb/knowledges/{kb.id}/graph-build/submit",
                   json={"action": "build"})
    assert r.status_code == 403


# ── 构建状态 ─────────────────────────────────────────────────────────────
def test_status_not_built(db, kb):
    with _client(db) as c:
        r = c.get(f"/api/v1/kb/knowledges/{kb.id}/graph-build/status")
    body = r.json()
    assert r.status_code == 200
    assert body["state"] == "not_built"
    assert body["segments"] == 0


def test_status_pending_and_ready(db, kb):
    _segment(db, kb, structure=None, vector=None)
    with _client(db) as c:
        body = c.get(f"/api/v1/kb/knowledges/{kb.id}/graph-build/status").json()
    assert body["state"] == "pending"
    assert body["segments"] == 1 and body["structure_done"] == 0

    seg = db.query(KbSegment).first()
    seg.graph_structure_indexed = True
    seg.graph_indexed = True
    db.commit()
    with _client(db) as c:
        body = c.get(f"/api/v1/kb/knowledges/{kb.id}/graph-build/status").json()
    assert body["state"] == "ready"
    assert body["structure_done"] == 1 and body["vector_done"] == 1


def test_status_partial_failed(db, kb):
    _segment(db, kb, structure=False, vector=False,
             details={"error": "LLM 挂了"})
    with _client(db) as c:
        body = c.get(f"/api/v1/kb/knowledges/{kb.id}/graph-build/status").json()
    assert body["state"] == "partial_failed"
    assert body["failed"] == 1


def test_status_running_when_locked(db, kb):
    kg_build_service.try_acquire(kb.id)
    with _client(db) as c:
        body = c.get(f"/api/v1/kb/knowledges/{kb.id}/graph-build/status").json()
    assert body["state"] == "running" and body["running"] is True


def test_status_is_tenant_scoped(db, kb):
    _segment(db, kb, structure=True, vector=True)
    with _client(db, tenant_id=TENANT_B) as c:
        body = c.get(f"/api/v1/kb/knowledges/{kb.id}/graph-build/status").json()
    assert body["segments"] == 0, "不得看到他人租户的切片统计"


# ── 失败清单 ─────────────────────────────────────────────────────────────
def test_failed_segments_lists_only_failures(db, kb):
    _segment(db, kb, index=0, structure=False, vector=False,
             details={"error": "boom"})
    _segment(db, kb, index=1, structure=True, vector=True)
    with _client(db) as c:
        r = c.get(f"/api/v1/kb/knowledges/{kb.id}/graph/failed-segments")
    body = r.json()
    assert r.status_code == 200
    assert len(body["items"]) == 1
    assert body["items"][0]["details"]["error"] == "boom"


# ── 配置 ─────────────────────────────────────────────────────────────────
def test_config_get_returns_defaults(db, kb):
    with _client(db) as c:
        r = c.get(f"/api/v1/kb/knowledges/{kb.id}/graph/config")
    assert r.status_code == 200
    assert r.json()["ppr_damping"] == 0.85


def test_config_put_persists_and_clamps(db, kb):
    with _client(db) as c:
        r = c.put(f"/api/v1/kb/knowledges/{kb.id}/graph/config",
                  json={"graph_top_k": 42, "ppr_damping": 9})
    assert r.status_code == 200
    body = r.json()
    assert body["graph_top_k"] == 42
    assert body["ppr_damping"] == 0.99, "越界值必须钳制而非报错"


def test_config_put_requires_admin(db, kb):
    with _client(db, perms=("kb:view",), is_admin=False) as c:
        r = c.put(f"/api/v1/kb/knowledges/{kb.id}/graph/config",
                  json={"graph_top_k": 42})
    assert r.status_code == 403


def test_config_does_not_touch_other_pipeline_keys(db, kb):
    kb.pipeline_config = {"chunker": {"type": "approx_token"}}
    db.commit()
    with _client(db) as c:
        c.put(f"/api/v1/kb/knowledges/{kb.id}/graph/config",
              json={"graph_top_k": 7})
    db.refresh(kb)
    assert kb.pipeline_config["chunker"] == {"type": "approx_token"}
    assert kb.pipeline_config["graph"]["graph_top_k"] == 7


# ── 单文档重抽 ───────────────────────────────────────────────────────────
def test_rebuild_document_submits(monkeypatch, db, kb):
    import app.core.job_runner as job_runner

    _segment(db, kb, document_id="doc-x")
    monkeypatch.setattr(job_runner, "run_in_background",
                        lambda fn, *a, **kw: None)
    with _client(db) as c:
        r = c.post(f"/api/v1/kb/knowledges/{kb.id}/graph/documents/rebuild",
                   json={"document_uuid": "doc-x"})
    assert r.status_code == 200 and r.json()["accepted"] is True


def test_rebuild_document_without_segments_409(db, kb):
    """摄取失败的文档没有切片：必须拒绝，否则后台空转却回 200 骗前端。"""
    with _client(db) as c:
        r = c.post(f"/api/v1/kb/knowledges/{kb.id}/graph/documents/rebuild",
                   json={"document_uuid": "no-such-segment"})
    assert r.status_code == 409
    assert "没有可抽取的切片" in r.json()["detail"]


def test_rebuild_document_conflict_409(db, kb):
    _segment(db, kb, document_id="doc-y")
    kg_build_service.try_acquire(kb.id)
    with _client(db) as c:
        r = c.post(f"/api/v1/kb/knowledges/{kb.id}/graph/documents/rebuild",
                   json={"document_uuid": "doc-y"})
    assert r.status_code == 409
