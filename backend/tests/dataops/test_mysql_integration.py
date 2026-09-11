"""P2 Task 4 真实 MySQL 集成测试（需 Docker）。

默认跳过；设置 ``DATAOPS_TEST_MYSQL_URL``（如
``mysql+pymysql://root:testpass@127.0.0.1:3307/testdb``）时运行，验证
``MysqlAdapter`` 各方法对真实 MySQL 的行为（系统库过滤 / 列键 / 画像 / 重叠率）。
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

URL = os.environ.get("DATAOPS_TEST_MYSQL_URL")

pytestmark = pytest.mark.skipif(
    not URL, reason="未设置 DATAOPS_TEST_MYSQL_URL，跳过 MySQL 集成测试（需 Docker）"
)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(URL, pool_pre_ping=True)
    with eng.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS orders"))
        conn.execute(text("DROP TABLE IF EXISTS users"))
        conn.execute(text(
            "CREATE TABLE users ("
            " id INT PRIMARY KEY, name VARCHAR(32) COMMENT '姓名', email VARCHAR(64) COMMENT '邮箱'"
            ") COMMENT='用户表'"
        ))
        conn.execute(text(
            "CREATE TABLE orders ("
            " id INT PRIMARY KEY, user_id INT COMMENT '用户ID', amount DECIMAL(10,2)"
            ") COMMENT='订单表'"
        ))
        conn.execute(text("INSERT INTO users (id, name, email) VALUES "
                          "(1,'Alice','a@x.com'),(2,'Bob','b@x.com'),(3,'Alice','a2@x.com')"))
        conn.execute(text("INSERT INTO orders (id, user_id, amount) VALUES "
                          "(1,1,9.9),(2,1,19.9),(3,2,5.0)"))
        conn.execute(text("COMMIT"))
    yield eng
    eng.dispose()


def test_list_databases_excludes_system(engine):
    from app.ai.dataops.dialects.registry import get_adapter

    with engine.connect() as conn:
        dbs = get_adapter("mysql").list_databases(conn)
    assert "information_schema" not in dbs
    assert "mysql" not in dbs
    assert "testdb" in dbs


def test_list_columns_detects_pk(engine):
    from app.ai.dataops.dialects.registry import get_adapter

    with engine.connect() as conn:
        cols = get_adapter("mysql").list_columns(conn, "testdb", ["users"])
    users = {c.name: c for c in cols["users"]}
    assert users["id"].column_key == "PRI"
    assert users["id"].data_type == "integer"
    assert users["name"].comment == "姓名"
    assert users["email"].comment == "邮箱"


def test_profile_column_top_values(engine):
    from app.ai.dataops.dialects.registry import get_adapter

    with engine.connect() as conn:
        prof = get_adapter("mysql").profile_column(conn, "testdb", "users", "name", 100)
    assert prof.total == 3
    names = {t["value"] for t in prof.top_values}
    assert "Alice" in names


def test_overlap_ratio(engine):
    from app.ai.dataops.dialects.registry import get_adapter
    from app.ai.dataops.dialect_base import ColRef

    with engine.connect() as conn:
        ratio = get_adapter("mysql").overlap_ratio(
            conn, "testdb",
            ColRef("users", "id"), ColRef("orders", "user_id"),
        )
    # 1,2 都出现在 orders.user_id 中 → 命中 2/3（采样约束下至少部分命中）
    assert 0.0 <= ratio <= 1.0
    assert ratio > 0.0


def test_sample_rows(engine):
    from app.ai.dataops.dialects.registry import get_adapter

    with engine.connect() as conn:
        res = get_adapter("mysql").sample_rows(conn, "testdb", "users", 10)
    assert res.row_count == 3
    assert "name" in res.columns
