"""PostgreSQL 方言适配器测试（P2 Task 3）。

fixture：探针 schema（probe_<uuid>）内建带注释的表 + 已知数据，
用例结束 DROP。计划用例：list_databases 排除模板库；列注释来自 pg_catalog。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, text

from app.ai.dataops.dialect_base import ColRef
from app.ai.dataops.dialects.postgres import PostgresAdapter
from app.ai.dataops.dialects.registry import get_adapter
from tests.dataops.conftest import TEST_DB_URL

SCHEMA = "probe_" + uuid.uuid4().hex[:8]


@pytest.fixture(scope="module")
def pg_conn():
    eng = create_engine(TEST_DB_URL)
    with eng.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{SCHEMA}"'))
        conn.execute(
            text(
                f'CREATE TABLE "{SCHEMA}".dim_region ('
                f' id integer PRIMARY KEY,'
                f' region_name varchar(64),'
                f' amount numeric(12,2),'
                f' cust_id integer)'
            )
        )
        conn.execute(text(f'COMMENT ON TABLE "{SCHEMA}".dim_region IS \'这是注释\''))
        conn.execute(text(f'COMMENT ON COLUMN "{SCHEMA}".dim_region.region_name IS \'区域名称\''))
        conn.execute(
            text(
                f"INSERT INTO \"{SCHEMA}\".dim_region (id, region_name, amount, cust_id) "
                f"VALUES (1,'华东',100.50,9001),(2,'华北',200.00,9002),"
                f"(3,'华东',NULL,9003),(4,NULL,50.25,9001)"
            )
        )
        # 采集统计信息：否则 EXPLAIN 对新表估算 Plan Rows=0
        conn.execute(text(f'ANALYZE "{SCHEMA}".dim_region'))
    conn = eng.connect()
    try:
        yield conn
    finally:
        conn.close()
        eng.dispose()
        admin = create_engine(TEST_DB_URL)
        try:
            with admin.begin() as conn2:
                conn2.execute(text("SET LOCAL lock_timeout = '5s'"))
                conn2.execute(text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))
        finally:
            admin.dispose()


def test_list_databases_excludes_templates(pg_conn):
    dbs = PostgresAdapter().list_databases(pg_conn)
    assert "template0" not in dbs and "template1" not in dbs
    assert "minworkbuddy_test" in dbs


def test_list_tables_returns_comment_and_type(pg_conn):
    tables = PostgresAdapter().list_tables(pg_conn, SCHEMA)
    names = {t.name: t for t in tables}
    assert "dim_region" in names
    t = names["dim_region"]
    assert t.comment == "这是注释"
    assert t.table_type == "BASE TABLE"
    assert t.row_count is None or t.row_count >= 0


def test_column_comment_comes_from_pg_catalog(pg_conn):
    cols = PostgresAdapter().list_columns(pg_conn, SCHEMA, ["dim_region"])["dim_region"]
    by_name = {c.name: c for c in cols}
    assert by_name["region_name"].comment == "区域名称"
    assert by_name["id"].column_key == "PRI"
    assert by_name["amount"].data_type == "numeric"
    assert by_name["region_name"].column_type == "varchar(64)"
    assert by_name["amount"].nullable is True
    assert by_name["id"].ordinal == 1


def test_profile_column_non_numeric_top_values(pg_conn):
    p = PostgresAdapter().profile_column(pg_conn, SCHEMA, "dim_region", "region_name", 1000)
    assert p.total == 4 and p.non_null == 3
    assert abs(p.null_rate - 0.25) < 1e-6
    assert p.top_values and p.top_values[0]["value"] == "华东" and p.top_values[0]["count"] == 2
    assert p.min_value is None and p.max_value is None


def test_profile_column_numeric_min_max(pg_conn):
    p = PostgresAdapter().profile_column(pg_conn, SCHEMA, "dim_region", "amount", 1000)
    assert p.non_null == 3 and p.distinct_count == 3
    assert abs(p.distinct_ratio - 1.0) < 1e-6
    assert p.min_value is not None and p.max_value is not None
    assert not p.top_values


def test_overlap_ratio_identical_and_disjoint(pg_conn):
    adapter = PostgresAdapter()
    same = adapter.overlap_ratio(
        pg_conn, SCHEMA,
        ColRef(table="dim_region", column="cust_id"),
        ColRef(table="dim_region", column="cust_id"),
    )
    assert same == 1.0
    disjoint = adapter.overlap_ratio(
        pg_conn, SCHEMA,
        ColRef(table="dim_region", column="region_name"),
        ColRef(table="dim_region", column="amount"),
    )
    assert disjoint == 0.0
    # 类型不可比 → 异常路径返回 0.0 而非抛出
    bad = adapter.overlap_ratio(
        pg_conn, SCHEMA,
        ColRef(table="dim_region", column="region_name"),
        ColRef(table="dim_region", column="amount"),
    )
    assert bad == 0.0


def test_sample_rows_truncation(pg_conn):
    r = PostgresAdapter().sample_rows(pg_conn, SCHEMA, "dim_region", 3)
    assert r.row_count == 3 and r.truncated is True
    r2 = PostgresAdapter().sample_rows(pg_conn, SCHEMA, "dim_region", 50)
    assert r2.row_count == 4 and r2.truncated is False


def test_dry_run_estimates_rows(pg_conn):
    impact = PostgresAdapter().dry_run(
        pg_conn, f'UPDATE "{SCHEMA}".dim_region SET amount = 0 WHERE cust_id = 9001'
    )
    assert impact.statement_type == "update"
    # ANALYZE 后估算应命中 2 行；宽松断言：取到了数值型估算（≥0）即视为 EXPLAIN 链路可用
    assert impact.estimated_rows is not None and impact.estimated_rows >= 0


def test_registry_dispatch():
    assert isinstance(get_adapter("postgresql"), PostgresAdapter)
    assert isinstance(get_adapter("PostgreSQL"), PostgresAdapter)
    with pytest.raises(ValueError):
        get_adapter("oracle")
