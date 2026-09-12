"""DataOps 新端点契约测试：POST /sources/{id}/test 与 DELETE /standards/{id}。

连通性测试通过 monkeypatch build_engine 注入假引擎，避免依赖真实数据库；
权限/错误处理（404 / tenant_required）与既有 DataOps 约定一致。
"""
from __future__ import annotations

from .conftest import build_client_routers
from app.services.dataops.data_source_service import DataSourceService
from app.services.dataops.standard_service import MetaStandardService


def test_standard_delete_and_404(client_dataops_a, db) -> None:
    obj = MetaStandardService(db, 100).create("phone", "手机号")
    db.commit()
    assert client_dataops_a.delete(
        f"/api/v1/dataops/standards/{obj.id}"
    ).status_code == 204
    assert MetaStandardService(db, 100).get(obj.id) is None

    assert client_dataops_a.delete(
        "/api/v1/dataops/standards/999999"
    ).status_code == 404


def test_source_test_not_found(client_dataops_a) -> None:
    assert client_dataops_a.post(
        "/api/v1/dataops/sources/999999/test"
    ).status_code == 404


def test_source_test_connectivity_ok(client_dataops_a, db, monkeypatch) -> None:
    src = DataSourceService(db, 100).create(
        name="src", source_type="mysql", host="h", port=3306,
        username="u", database="d",
    )
    db.commit()

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, *a, **k):
            return None

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

        def dispose(self):
            pass

    monkeypatch.setattr(
        "app.services.dataops.data_source_service.build_engine",
        lambda *a, **k: _FakeEngine(),
    )
    r = client_dataops_a.post(f"/api/v1/dataops/sources/{src.id}/test")
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def test_source_test_connectivity_fail(client_dataops_a, db, monkeypatch) -> None:
    src = DataSourceService(db, 100).create(
        name="src", source_type="mysql", host="h", port=3306, database="d",
    )
    db.commit()

    class _FakeEngine:
        def connect(self):
            raise RuntimeError("connection refused")

        def dispose(self):
            pass

    monkeypatch.setattr(
        "app.services.dataops.data_source_service.build_engine",
        lambda *a, **k: _FakeEngine(),
    )
    r = client_dataops_a.post(f"/api/v1/dataops/sources/{src.id}/test")
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is False


def test_source_test_requires_tenant(db) -> None:
    client = build_client_routers(db, None, ["app.routers.dataops.dataops"])
    assert client.post("/api/v1/dataops/sources/1/test").status_code == 400


def test_kb_rebuild_delegated(client_dataops_a, db) -> None:
    from app.services.kb.kb_ref_service import KbRefService

    ref = KbRefService(db, 100).create_kb_ref("KB-D", "desc", 1)
    r = client_dataops_a.post(f"/api/v1/dataops/knowledge-bases/{ref.kb_id}/rebuild")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kb_id"] == ref.kb_id
    assert body["reindexed_documents"] == 0
    assert body["reindexed_segments"] == 0


def test_kb_rebuild_delegated_not_found(client_dataops_a) -> None:
    assert client_dataops_a.post(
        "/api/v1/dataops/knowledge-bases/nope/rebuild"
    ).status_code == 404


def test_kb_rebuild_delegated_requires_tenant(db) -> None:
    client = build_client_routers(db, None, ["app.routers.dataops.dataops"])
    assert client.post("/api/v1/dataops/knowledge-bases/x/rebuild").status_code == 400
