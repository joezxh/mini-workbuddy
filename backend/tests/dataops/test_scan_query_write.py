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


# ── 三级作用域（PG 族：物理库→schema→表）──────────────────────
def test_scope_helpers():
    svc = MetaScanService
    assert svc._has_schema("postgresql") is True
    assert svc._has_schema("kingbase") is True
    assert svc._has_schema("mysql") is False
    assert svc._has_schema("bogus") is False
    assert svc._resolve_scope("demo", "kev_db") == "demo"   # 传了 schema 以 schema 限定
    assert svc._resolve_scope(None, "public") == "public"   # 旧语义兼容


def test_remote_browse_three_level(scannable, db):
    """导入向导链路：列物理库→按库重连列 schema→按 schema 列表（回归：早期版本库名被当 schema 恒查空）。"""
    source_id, probe = scannable
    svc = MetaScanService(db, TENANT_A)
    assert TEST_DB_NAME in svc.list_remote_databases(source_id)
    assert probe in svc.list_remote_schemas(source_id, TEST_DB_NAME)
    tables = svc.list_remote_tables(source_id, TEST_DB_NAME, schema=probe)
    assert any(x["name"] == "orders" for x in tables)
    # 旧参数形态（不传 schema，database 直接当作用域）仍可用
    assert any(x["name"] == "orders" for x in svc.list_remote_tables(source_id, probe))


def test_import_tables_with_schema(scannable, db):
    """三级导入：meta_table.database=schema、db_name=物理库（跨库同名 schema 靠
    db_name 区分，回归：早期仅按 schema 过滤导致混库）。"""
    from app.models.dataops.meta import MetaTable
    from sqlalchemy import select

    source_id, probe = scannable
    svc = MetaScanService(db, TENANT_A)
    r = svc.import_tables(source_id, TEST_DB_NAME, ["orders"], schema=probe)
    assert r["imported"] == 1 and not r["failed"]
    row = db.execute(
        select(MetaTable).where(
            MetaTable.source_id == source_id,
            MetaTable.database == probe,
            MetaTable.table_name == "orders",
        )
    ).scalar_one()
    assert row.table_comment == "订单表"
    assert row.column_count == 3
    # 第一级物理库单独存 db_name，供前端按库过滤
    assert row.db_name == TEST_DB_NAME


def test_tables_route_filters_by_db_name(scannable, db, client_a):
    """回归（用户报障）：选数据源/库/schema 后，左侧元数据表须按
    物理库(db_name)+schema(database) 双条件过滤；早期仅按 schema 过滤，
    跨物理库同名 schema 会串库。"""
    source_id, probe = scannable
    MetaScanService(db, TENANT_A).start_scan(source_id, probe, connect_database=TEST_DB_NAME)
    url = f"/api/v1/dataops/sources/{source_id}/tables"
    # 正确物理库：命中 orders，且回带 db_name
    ok = client_a.get(url, params={"database": probe, "db_name": TEST_DB_NAME}).json()
    assert any(x["table_name"] == "orders" for x in ok)
    assert ok[0]["db_name"] == TEST_DB_NAME
    # 错误物理库：即使 schema 同名也应过滤为空（证明 db 维度生效）
    empty = client_a.get(url, params={"database": probe, "db_name": "not_exist_db"}).json()
    assert empty == []


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
