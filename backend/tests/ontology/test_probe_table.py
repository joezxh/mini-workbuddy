"""E-探活：表级可读性探活（单表 + 批量限 20，AF-06）。不连真库，monkeypatch get_adapter。"""
import pytest

from app.core.api_error import ApiError
from app.services.dataops import scan_service as ss_mod


def _source(db, tenant=100, name="s"):
    from app.models.dataops.data_source import DataSource

    ds = DataSource(tenant_id=tenant, name=name, source_type="mysql",
                    external_type="rdbms", host="h", port=3306)
    db.add(ds)
    db.flush()
    return ds


def _table(db, source_id, name="t1", tenant=100):
    from app.models.dataops.meta import MetaTable

    mt = MetaTable(tenant_id=tenant, source_id=source_id, db_name="d",
                   database="d", table_name=name)
    db.add(mt)
    db.flush()
    return mt


class FakeAdapter:
    def __init__(self, connect_ok=True, probe_ok=True, probe_raises=False):
        self.connect_ok, self.probe_ok, self.probe_raises = connect_ok, probe_ok, probe_raises

    def test_connect(self, ds):
        return (True, None) if self.connect_ok else (False, "ConnectionRefusedError: refused")

    def open(self, ds, connect_database=None):
        raise AssertionError("probe_table must not call open directly")

    def probe_table(self, ds, database, table_name):
        if self.probe_raises:
            raise RuntimeError("boom")
        return (True, None) if self.probe_ok else (False, "ProgrammingError: table missing")


def test_probe_ok(db, monkeypatch):
    ds = _source(db)
    t = _table(db, ds.id)
    monkeypatch.setattr(ss_mod, "get_adapter", lambda st: FakeAdapter())
    from app.services.dataops.scan_service import MetaScanService

    ok, code, err = MetaScanService(db, 100).test_table(t.id)
    assert (ok, code, err) == (True, None, None)


def test_probe_unreachable(db, monkeypatch):
    ds = _source(db)
    t = _table(db, ds.id)
    monkeypatch.setattr(ss_mod, "get_adapter", lambda st: FakeAdapter(connect_ok=False))
    from app.services.dataops.scan_service import MetaScanService

    ok, code, err = MetaScanService(db, 100).test_table(t.id)
    assert (ok, code) == (False, "SOURCE_UNREACHABLE")
    assert err and "refused" in err


def test_probe_not_readable(db, monkeypatch):
    ds = _source(db)
    t = _table(db, ds.id)
    monkeypatch.setattr(ss_mod, "get_adapter", lambda st: FakeAdapter(probe_ok=False))
    from app.services.dataops.scan_service import MetaScanService

    ok, code, err = MetaScanService(db, 100).test_table(t.id)
    assert (ok, code) == (False, "TABLE_NOT_READABLE")
    assert err and "missing" in err


def test_probe_adapter_crash_counts_as_not_readable(db, monkeypatch):
    ds = _source(db)
    t = _table(db, ds.id)
    monkeypatch.setattr(ss_mod, "get_adapter", lambda st: FakeAdapter(probe_raises=True))
    from app.services.dataops.scan_service import MetaScanService

    ok, code, err = MetaScanService(db, 100).test_table(t.id)
    assert (ok, code) == (False, "TABLE_NOT_READABLE")


def test_probe_wrong_source_or_cross_tenant_404(db, monkeypatch):
    from app.services.dataops.scan_service import MetaScanService

    ds_a = _source(db, name="A")
    ds_b = _source(db, name="B")
    t = _table(db, ds_a.id)
    svc = MetaScanService(db, 100)
    monkeypatch.setattr(ss_mod, "get_adapter", lambda st: FakeAdapter())
    with pytest.raises(ApiError) as ei:
        svc.test_table(t.id, source_id=ds_b.id)
    assert ei.value.http_status == 404
    with pytest.raises(ApiError):
        svc.test_table(999999, source_id=ds_a.id)


def test_route_single(client_a, db, monkeypatch):
    ds = _source(db)
    t = _table(db, ds.id)
    monkeypatch.setattr(ss_mod, "get_adapter", lambda st: FakeAdapter())
    r = client_a.post(f"/api/v1/dataops/sources/{ds.id}/tables/{t.id}/test")
    assert r.status_code == 200
    assert r.json() == {"table_id": t.id, "ok": True, "code": None}


def test_route_unreachable_502(client_a, db, monkeypatch):
    ds = _source(db)
    t = _table(db, ds.id)
    monkeypatch.setattr(ss_mod, "get_adapter", lambda st: FakeAdapter(connect_ok=False))
    r = client_a.post(f"/api/v1/dataops/sources/{ds.id}/tables/{t.id}/test")
    assert r.status_code == 502
    assert r.json()["code"] == "SOURCE_UNREACHABLE"


def test_batch_limit_21(client_a, db):
    ds = _source(db)
    ids = [_table(db, ds.id, f"t{i}").id for i in range(21)]
    r = client_a.post(f"/api/v1/dataops/sources/{ds.id}/tables/test-batch",
                      json={"table_ids": ids})
    assert r.status_code == 400


def test_batch_route(client_a, db, monkeypatch):
    ds = _source(db)
    t_ok = _table(db, ds.id, "ok1")
    t_bad = _table(db, ds.id, "bad1")

    class ByName(FakeAdapter):
        def probe_table(self, ds, database, table_name):
            return (False, "ProgrammingError: x") if table_name == "bad1" else (True, None)

    monkeypatch.setattr(ss_mod, "get_adapter", lambda st: ByName())
    r = client_a.post(f"/api/v1/dataops/sources/{ds.id}/tables/test-batch",
                      json={"table_ids": [t_ok.id, t_bad.id, 999999]})
    assert r.status_code == 200
    results = {x["table_id"]: x for x in r.json()["results"]}
    assert results[t_ok.id]["ok"] is True
    assert results[t_bad.id] == {"table_id": t_bad.id, "ok": False, "code": "TABLE_NOT_READABLE"}
    assert results[999999]["ok"] is False and results[999999]["code"] == "TABLE_NOT_FOUND"
