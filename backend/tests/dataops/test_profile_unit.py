"""P2 Task 5/6 · profile_column / overlap_ratio 单测（不依赖真实数据库）。

现有 `tests/dataops/test_dialect_postgres.py`、`tests/dataops/test_mysql_integration.py`
是**集成测试**（要真实 PG/MySQL）。本文件补一组**纯单元**测试：用 `unittest.mock.MagicMock`
替换数据库 `conn`，精确控制 `conn.execute(...)` 的返回，覆盖各分支与异常路径，
无需任何外部数据库即可在任意环境运行。

覆盖点：
- `profile_column`：数值型(min/max 分支)、非数值型(Top-10 分支)、空表(total=0)、
  未知类型(走 Top 分支)、null_rate / distinct_ratio 计算精度。
- `overlap_ratio`：正常命中比例、分母为 0 时返回 0.0、异常路径返回 0.0 **且回滚连接**
  （失败语句会把共享事务打成 aborted，污染后续语句——P2 踩坑点）。
"""
from __future__ import annotations

from typing import Any, List, Optional
from unittest.mock import MagicMock

import pytest

from app.ai.dataops.dialect_base import ColRef
from app.ai.dataops.dialects.mysql import MysqlAdapter
from app.ai.dataops.dialects.postgres import PostgresAdapter

_ADAPTERS = [PostgresAdapter(), MysqlAdapter()]


class _Result:
    """模拟 SQLAlchemy Result：同一对象可同时应答 fetchone/first/fetchall。"""

    def __init__(self, row: Optional[tuple] = None, rows: Optional[List[tuple]] = None):
        self._row = row
        self._rows = rows if rows is not None else []

    def fetchone(self):
        return self._row

    def first(self):
        return self._row

    def fetchall(self):
        return self._rows

    def keys(self):
        return []

    def fetchmany(self, n: int):
        return self._rows[:n]


def _conn(results: List[_Result]):
    """构造一个 engine=None 的假连接；execute 按 results 顺序逐次返回。"""
    conn = MagicMock()
    conn.engine = None  # 让 _quote 走纯字符串兜底，避免触碰 dialect
    conn.execute = MagicMock(side_effect=results)
    return conn


# --------------------------------------------------------------------------- #
# profile_column
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("adapter", _ADAPTERS, ids=["pg", "mysql"])
def test_profile_numeric_min_max_and_ratios(adapter):
    conn = _conn([
        _Result(row=(100, 95, 80)),        # count total/non_null/distinct
        _Result(row=("integer",)),          # _column_data_type
        _Result(row=("1", "100")),          # min/max
    ])
    p = adapter.profile_column(conn, "db", "t", "age", 1000)
    assert p.total == 100 and p.non_null == 95 and p.distinct_count == 80
    assert p.null_rate == 0.05
    assert p.distinct_ratio == round(80 / 95, 6)
    assert p.min_value == "1" and p.max_value == "100"
    assert p.top_values == []


@pytest.mark.parametrize("adapter", _ADAPTERS, ids=["pg", "mysql"])
def test_profile_string_top_values(adapter):
    conn = _conn([
        _Result(row=(10, 9, 3)),
        _Result(row=("varchar",)),
        _Result(rows=[("a", 4), ("b", 3), ("c", 2)]),
    ])
    p = adapter.profile_column(conn, "db", "t", "name", 1000)
    assert p.total == 10 and p.non_null == 9
    assert p.null_rate == 0.1
    assert p.distinct_ratio == round(3 / 9, 6)
    assert p.min_value is None and p.max_value is None
    assert p.top_values == [
        {"value": "a", "count": 4},
        {"value": "b", "count": 3},
        {"value": "c", "count": 2},
    ]


@pytest.mark.parametrize("adapter", _ADAPTERS, ids=["pg", "mysql"])
def test_profile_empty_table_no_division_by_zero(adapter):
    conn = _conn([
        _Result(row=(0, 0, 0)),
        _Result(row=("integer",)),
        _Result(row=(None, None)),
    ])
    p = adapter.profile_column(conn, "db", "t", "x", 1000)
    assert p.total == 0
    assert p.null_rate == 0.0
    assert p.distinct_ratio == 0.0
    assert p.min_value is None and p.max_value is None


@pytest.mark.parametrize("adapter", _ADAPTERS, ids=["pg", "mysql"])
def test_profile_unknown_type_falls_to_top_values(adapter):
    conn = _conn([
        _Result(row=(5, 5, 5)),
        _Result(row=None),                  # _column_data_type 无结果 → ""
        _Result(rows=[("only", 5)]),
    ])
    p = adapter.profile_column(conn, "db", "t", "weird", 1000)
    # 未知/空类型不进数值分支，走 Top-10
    assert p.min_value is None and p.max_value is None
    assert p.top_values == [{"value": "only", "count": 5}]
    assert abs(p.distinct_ratio - 1.0) < 1e-9


# --------------------------------------------------------------------------- #
# overlap_ratio
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("adapter", _ADAPTERS, ids=["pg", "mysql"])
def test_overlap_ratio_normal(adapter):
    conn = _conn([
        _Result(row=(7,)),   # matched
        _Result(row=(10,)),  # distinct total
    ])
    r = adapter.overlap_ratio(
        conn, "db", ColRef("a", "x"), ColRef("b", "y")
    )
    assert abs(r - 0.7) < 1e-9


@pytest.mark.parametrize("adapter", _ADAPTERS, ids=["pg", "mysql"])
def test_overlap_ratio_zero_denominator(adapter):
    conn = _conn([
        _Result(row=(0,)),
        _Result(row=(0,)),   # distinct total == 0 → 不除零，返回 0.0
    ])
    r = adapter.overlap_ratio(
        conn, "db", ColRef("a", "x"), ColRef("b", "y")
    )
    assert r == 0.0


@pytest.mark.parametrize("adapter", _ADAPTERS, ids=["pg", "mysql"])
def test_overlap_ratio_exception_returns_zero_and_rolls_back(adapter):
    """类型不可比/权限不足等异常：返回 0.0 而非抛出，且必须回滚连接。"""
    conn = _conn([])
    conn.execute = MagicMock(side_effect=RuntimeError("type mismatch"))
    r = adapter.overlap_ratio(
        conn, "db", ColRef("a", "x"), ColRef("b", "y")
    )
    assert r == 0.0
    conn.rollback.assert_called_once()
