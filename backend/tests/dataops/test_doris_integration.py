"""P2 Task 4 · Doris 真实验证（需可达的 Doris / MySQL 协议实例）。

默认跳过；设置 ``DATAOPS_TEST_DORIS_URL``（如
``mysql+pymysql://root:pass@127.0.0.1:9030/testdb``，Doris 默认 9030 端口）时运行，
验证 ``DorisAdapter`` 各方法对真实引擎的行为（系统库过滤 / 列键 / 画像 / 重叠率 / 取样）。

实现说明（影响"真实验证"如何解读）：
- ``DorisAdapter`` 直接继承 ``MysqlAdapter``，所有 SQL 均为 MySQL 协议兼容语句
  （Doris 经 9030 端口的 MySQL 协议通信）；Doris 专属差异仅在于 ``list_databases`` 的
  系统库过滤集（``_DORIS_SYSTEM_DBS``），已由 ``test_dialects_mysql.py`` 的纯单测锁定。
- 因此本集成测试既可在**真实 Doris** 上运行（``DATAOPS_TEST_DORIS_URL`` 指向 Doris），
  也可在**真实 MySQL 8.0**（协议兼容、适配器代码路径一致）上做 wire 级真实验证：
  把 ``DATAOPS_TEST_DORIS_URL`` 设为 MySQL 连接串即可（CI 无 Doris 时的回退）。
- 无真实实例时整体 skip，不阻塞基线。
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, make_url, text

URL = os.environ.get("DATAOPS_TEST_DORIS_URL")
DB_NAME = make_url(URL).database if URL else None

pytestmark = pytest.mark.skipif(
    not URL, reason="未设置 DATAOPS_TEST_DORIS_URL，跳过 Doris 集成测试（需可达的 Doris/MySQL 协议实例）"
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
        dbs = get_adapter("doris").list_databases(conn)
    # Doris 专属系统库必须被过滤
    assert "information_schema" not in dbs
    assert "mysql" not in dbs
    assert "sys" not in dbs
    assert "performance_schema" not in dbs
    if DB_NAME:
        assert DB_NAME in dbs


def test_list_columns_detects_pk(engine):
    from app.ai.dataops.dialects.registry import get_adapter

    with engine.connect() as conn:
        cols = get_adapter("doris").list_columns(conn, DB_NAME, ["users"])
    users = {c.name: c for c in cols["users"]}
    assert users["id"].column_key == "PRI"
    assert users["id"].data_type == "integer"
    assert users["name"].comment == "姓名"
    assert users["email"].comment == "邮箱"


def test_profile_column_top_values(engine):
    from app.ai.dataops.dialects.registry import get_adapter

    with engine.connect() as conn:
        prof = get_adapter("doris").profile_column(conn, DB_NAME, "users", "name", 100)
    assert prof.total == 3
    names = {t["value"] for t in prof.top_values}
    assert "Alice" in names


def test_overlap_ratio(engine):
    from app.ai.dataops.dialects.registry import get_adapter
    from app.ai.dataops.dialect_base import ColRef

    with engine.connect() as conn:
        ratio = get_adapter("doris").overlap_ratio(
            conn, DB_NAME,
            ColRef("users", "id"), ColRef("orders", "user_id"),
        )
    # 1,2 都出现在 orders.user_id 中 → 命中 2/3（采样约束下至少部分命中）
    assert 0.0 <= ratio <= 1.0
    assert ratio > 0.0


def test_sample_rows(engine):
    from app.ai.dataops.dialects.registry import get_adapter

    with engine.connect() as conn:
        res = get_adapter("doris").sample_rows(conn, DB_NAME, "users", 10)
    assert res.row_count == 3
    assert "name" in res.columns
