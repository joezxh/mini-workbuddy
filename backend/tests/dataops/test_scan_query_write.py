"""P2 Task 7/9/10 集成测试：扫描 / 只读查询 / 写审批（真实 PG 探针库）。

约定：探针 schema(``probe_scan_<uuid>``) 建在测试库 minworkbuddy_test 中，
DataSource 指向该测试库，扫描 database 参数传探针 schema（PG 语义：库=库，
schema=namespace）。凭据用 .env 的 DB_* 直连，密码经 DataSourceService 加密落库。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, text

from app.ai.dataops.dialects.registry import get_adapter
from app.config import settings
from app.services.dataops.data_source_service import DataSourceService
from app.services.dataops.query_service import ReadonlyQueryService
from app.services.dataops.scan_service import MetaScanService
from app.services.dataops.write_request_service import DataWriteRequestService
from tests.dataops.conftest import TENANT_A, TEST_DB_NAME, TEST_DB_URL


@pytest.fixture
def scannable(db):
    probe = "probe_scan_" + uuid.uuid4().hex[:8]
    eng = create_engine(TEST_DB_URL)
    with eng.begin() as c:
        c.execute(text(f'CREATE SCHEMA "{probe}"'))
        c.execute(
            text(
                f'CREATE TABLE "{probe}".orders ('
                f' id integer PRIMARY KEY,'
                f' amount numeric(12,2),'
                f' cname varchar(64))'
            )
        )
        c.execute(text(f"COMMENT ON TABLE \"{probe}\".orders IS '订单表'"))
        c.execute(text(f"COMMENT ON COLUMN \"{probe}\".orders.cname IS '客户名'"))
        c.execute(
            text(f"INSERT INTO \"{probe}\".orders (id, amount, cname) VALUES (1,100.50,'甲'),(2,200.00,'乙')")
        )
    svc = DataSourceService(db, TENANT_A)
    ds = svc.create(
        name="src", source_type="postgresql", host=settings.DB_HOST, port=settings.DB_PORT,
        username=settings.DB_USER, password=settings.DB_PASSWORD, database=TEST_DB_NAME,
    )
    db.commit()
    yield ds.id, probe
    admin = create_engine(TEST_DB_URL)
    try:
        with admin.begin() as c2:
            c2.execute(text("SET LOCAL lock_timeout = '5s'"))
            c2.execute(text(f'DROP SCHEMA IF EXISTS "{probe}" CASCADE'))
    finally:
        admin.dispose()


def test_scan_writes_metadata(scannable, db):
    source_id, probe = scannable
    job = MetaScanService(db, TENANT_A).start_scan(source_id, probe)
    assert job.status == "succeeded"
    assert job.stats_json["table_count"] == 1
    assert job.stats_json["column_count"] == 3
    assert job.progress == 100.0


def test_scan_powers_adapters(scannable, db):
    source_id, probe = scannable
    MetaScanService(db, TENANT_A).start_scan(source_id, probe)
    adapter = get_adapter("postgresql")
    eng = create_engine(TEST_DB_URL)
    with eng.connect() as conn:
        tables = adapter.list_tables(conn, probe)
        assert any(t.name == "orders" and t.comment == "订单表" for t in tables)
        cols = adapter.list_columns(conn, probe, ["orders"])["orders"]
        cname = [c for c in cols if c.name == "cname"][0]
        assert cname.comment == "客户名"
    eng.dispose()


def test_readonly_query(scannable, db):
    source_id, probe = scannable
    r = ReadonlyQueryService(db, TENANT_A).run(source_id, f'SELECT * FROM "{probe}".orders ORDER BY id')
    assert r["row_count"] == 2
    assert "amount" in r["columns"]
    assert r["truncated"] is False


def test_readonly_query_rejects_write(scannable, db):
    source_id, probe = scannable
    with pytest.raises(ValueError):
        ReadonlyQueryService(db, TENANT_A).run(
            source_id, f'UPDATE "{probe}".orders SET amount=0'
        )


def test_write_request_flow(scannable, db):
    source_id, probe = scannable
    svc = DataWriteRequestService(db, TENANT_A)
    req = svc.create_request(
        source_id, f'UPDATE "{probe}".orders SET amount=0 WHERE id=1'
    )
    db.commit()
    assert req.statement_type == "update" and req.status == "pending"

    # 只读查询不可作为写申请
    with pytest.raises(ValueError):
        svc.create_request(source_id, f'SELECT * FROM "{probe}".orders')

    approved = svc.approve(req.id)
    db.commit()
    assert approved.status == "approved" and approved.token

    executed = svc.execute(req.id, approved.token)
    db.commit()
    assert executed.status == "executed" and executed.token_consumed is True
    assert executed.result_json["affected_rows"] == 1

    # 令牌不可重放
    with pytest.raises(ValueError):
        svc.execute(req.id, approved.token)


def test_token_mismatch_rejected(scannable, db):
    source_id, probe = scannable
    svc = DataWriteRequestService(db, TENANT_A)
    req = svc.create_request(source_id, f'DELETE FROM "{probe}".orders WHERE id=2')
    db.commit()
    svc.approve(req.id)
    db.commit()
    with pytest.raises(ValueError):
        svc.execute(req.id, "wrong-token")
