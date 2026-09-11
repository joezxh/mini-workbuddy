"""P2 Task 4 测试：MySQL/Doris 适配器注册与纯函数。

真实 MySQL/Doris 联通测试见 ``test_mysql_integration.py``（需 Docker，env 缺省跳过）。
"""
from __future__ import annotations

import pytest

from app.ai.dataops.dialects.mysql import (
    MysqlAdapter, _build_column_type, _clamp_sample_rows, _normalize_type,
)
from app.ai.dataops.dialects.registry import get_adapter


def test_mysql_registered():
    adapter = get_adapter("mysql")
    assert isinstance(adapter, MysqlAdapter)
    assert adapter.name == "mysql"


def test_doris_registered_and_subclass():
    adapter = get_adapter("doris")
    assert isinstance(adapter, MysqlAdapter)  # Doris 复用 MySQL 实现
    assert adapter.name == "doris"


def test_pg_still_registered():
    assert get_adapter("postgresql").name == "postgresql"


def test_unknown_source_type_rejected():
    with pytest.raises(ValueError):
        get_adapter("oracle")


def test_normalize_type():
    assert _normalize_type("int") == "integer"
    assert _normalize_type("bigint") == "bigint"
    assert _normalize_type("varchar") == "varchar"
    assert _normalize_type("datetime") == "datetime"
    assert _normalize_type("double") == "double precision"
    assert _normalize_type("unknown_x") == "unknown_x"


def test_build_column_type():
    assert _build_column_type("varchar", 32, None, None, None) == "varchar(32)"
    assert _build_column_type("decimal", None, 10, 2, None) == "decimal(10,2)"
    assert _build_column_type("int", None, None, None, None) == "integer"


def test_clamp_sample_rows():
    assert _clamp_sample_rows(0) == 1000
    assert _clamp_sample_rows(50) == 100
    assert _clamp_sample_rows(2000) == 2000
    assert _clamp_sample_rows(99999) == 50000


def test_doris_list_databases_filters_system_dbs():
    """Doris 专属覆盖：SHOW DATABASES 结果剔除 Doris 系统库（无需真实实例）。

    Doris 经 MySQL 协议通信、``DorisAdapter`` 复用 ``MysqlAdapter``，唯一差异就是
    ``list_databases`` 的系统库过滤集（``_DORIS_SYSTEM_DBS``）。纯函数级锁定该行为，
    避免回归把系统库暴露进元数据扫描。
    """
    from app.ai.dataops.dialects.doris import DorisAdapter

    class _FakeConn:
        def exec_driver_sql(self, sql):  # noqa: ANN001, ANN202
            return self

        def fetchall(self):
            return [
                ("information_schema",),
                ("mysql",),
                ("sys",),
                ("performance_schema",),
                ("testdb",),
                ("doris_demo",),
            ]

    dbs = DorisAdapter().list_databases(_FakeConn())
    assert dbs == ["testdb", "doris_demo"]
