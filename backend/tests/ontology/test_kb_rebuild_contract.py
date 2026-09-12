"""KB 向量索引重建契约测试（对齐 app/services/kb/kb_router.py 的 POST /kb/{kb_id}/rebuild）。

验证：重建经 RAG Service 入口（KbIngestService）触发、租户隔离、tenant_required、未知 kb 404。
用例仅覆盖「无切片可重建」这类不依赖 embedding 后端的路径，保证可不联网运行。
"""
from __future__ import annotations

from .conftest import TENANT_A, TENANT_B
from app.services.kb.kb_ref_service import KbRefService


def test_rebuild_empty_kb(client_kb, db) -> None:
    ref = KbRefService(db, TENANT_A).create_kb_ref("测试KB", "desc", 1)
    r = client_kb.post(f"/kb/{ref.kb_id}/rebuild", headers={"X-Tenant-Id": str(TENANT_A)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kb_id"] == ref.kb_id
    assert body["reindexed_segments"] == 0
    assert body["reindexed_documents"] == 0


def test_rebuild_unknown_kb_404(client_kb) -> None:
    r = client_kb.post("/kb/nope/rebuild", headers={"X-Tenant-Id": str(TENANT_A)})
    assert r.status_code == 404, r.text


def test_rebuild_requires_tenant(client_kb) -> None:
    r = client_kb.post("/kb/anything/rebuild")
    assert r.status_code == 400 and r.json()["detail"] == "缺少租户标识 X-Tenant-Id"


def test_rebuild_tenant_isolation(client_kb, db) -> None:
    ref = KbRefService(db, TENANT_A).create_kb_ref("KB-A", None, 1)
    r = client_kb.post(f"/kb/{ref.kb_id}/rebuild", headers={"X-Tenant-Id": str(TENANT_B)})
    assert r.status_code == 404, r.text
