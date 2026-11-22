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
def _clean_locks(monkeypatch, engine):
    # 提交/重抽路由用生产 SessionLocal 取 PG advisory 锁（键 ns,kb_id）。
    # advisory 锁是实例级的（跨 schema/库），测试里每个新 schema 的 kb.id 恒为 1，
    # 且本文件把后台任务 stub 成 no-op → 若锁落在开发库连接上则永不释放，
    # 后续同 kb_id 用例会随连接池分配间歇性 409。
    # 把 SessionLocal 路由到测试引擎，锁随 per-test 引擎 dispose 自动释放。
    from sqlalchemy.orm import sessionmaker

    test_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr("app.db.database.SessionLocal", test_factory)
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


def test_failed_segments_returns_flat_failure_reason(db, kb):
    """前端只读平级字段就能展示原因：阶段、码、原文，不必钻两套 details 键。"""
    from app.services.kb.kg import kg_failure

    _segment(db, kb, index=0, structure=False, vector=True,
             details={"stage": "structure",
                      "error": "NoTextResponseError: 模型只返回了思考/工具块",
                      "error_code": kg_failure.MODEL_NO_TEXT})
    _segment(db, kb, index=1, structure=True, vector=False,
             details={"vector_stage": "vector",
                      "vector_error": "RuntimeError: failed to establish a new connection",
                      "vector_error_code": kg_failure.EMBEDDING_UNAVAILABLE})
    with _client(db) as c:
        items = c.get(
            f"/api/v1/kb/knowledges/{kb.id}/graph/failed-segments"
        ).json()["items"]

    by_chunk = {i["chunk_index"]: i for i in items}
    assert by_chunk[0]["stage"] == kg_failure.STAGE_STRUCTURE
    assert by_chunk[0]["error_code"] == kg_failure.MODEL_NO_TEXT
    # 结构已成功、仅向量失败的切片才报向量（否则「LLM 截断」会被看成「嵌入不可用」）
    assert by_chunk[1]["stage"] == kg_failure.STAGE_VECTOR
    assert by_chunk[1]["error_code"] == kg_failure.EMBEDDING_UNAVAILABLE
    assert by_chunk[1]["error"].startswith("RuntimeError:")


def test_failed_segments_derives_code_for_legacy_rows(db, kb):
    """旧数据只存了一句原文时也要现场求出码，不能退化成「未知原因」。"""
    from app.services.kb.kg import kg_failure

    _segment(db, kb, structure=False, vector=False,
             details={"error": "ValueError: 响应截断修复后无任何实体/关系"})
    with _client(db) as c:
        item = c.get(
            f"/api/v1/kb/knowledges/{kb.id}/graph/failed-segments"
        ).json()["items"][0]
    assert item["error_code"] == kg_failure.JSON_TRUNCATED
    assert item["stage"] == kg_failure.STAGE_STRUCTURE


def test_failed_segments_unknown_when_nothing_recorded(db, kb):
    """甚至没留痕的切片（以前向量阶段从不写 details）给 unknown，而不是猜。"""
    from app.services.kb.kg import kg_failure

    _segment(db, kb, structure=True, vector=False, details=None)
    with _client(db) as c:
        item = c.get(
            f"/api/v1/kb/knowledges/{kb.id}/graph/failed-segments"
        ).json()["items"][0]
    assert item["error_code"] == kg_failure.UNKNOWN
    assert item["stage"] == kg_failure.STAGE_VECTOR
    assert item["error"] == ""


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
