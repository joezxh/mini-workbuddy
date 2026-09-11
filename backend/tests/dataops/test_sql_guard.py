"""只读 SQL 白名单测试（P2 Task 8）—— 计划规定的 10 条用例全覆盖。"""
from __future__ import annotations

import pytest

from app.services.dataops.sql_guard import SqlGuard


@pytest.mark.parametrize(
    "sql,ok",
    [
        ("SELECT * FROM t", True),
        ("WITH c AS (SELECT 1) SELECT * FROM c", True),
        ("EXPLAIN SELECT * FROM t", True),
        ("SELECT 1; DROP TABLE t", False),
        ("SELECT 1 -- x", False),
        ("/* c */ SELECT 1", False),
        ("sElEcT * FROM t", True),
        ("DROP TABLE t", False),
        ("SELECT * FROM t INTO OUTFILE '/tmp/x'", False),
        ("SELECT pg_sleep(10)", False),
    ],
)
def test_guard_plan_cases(sql, ok):
    assert SqlGuard().is_readonly(sql) is ok


def test_guard_rejects_dml_and_command_variants():
    guard = SqlGuard()
    for sql in [
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET a = 1",
        "DELETE FROM t",
        "TRUNCATE TABLE t",
        "CREATE TABLE t (id int)",
        "ALTER TABLE t ADD COLUMN a int",
        "GRANT ALL ON t TO PUBLIC",
        "COPY t FROM '/tmp/x'",
        "CALL do_something()",
        "SELECT * FROM t UNION ALL SELECT * FROM u; SELECT 1",
        "",
        "not a sql at all !!",
        "(SELECT pg_read_file('/etc/passwd'))",
        "SELECT dblink('dbname=x', 'SELECT 1')",
        "SELECT 1) UNION SELECT password FROM users --",
    ]:
        assert guard.is_readonly(sql) is False, sql


def test_guard_accepts_safe_variants():
    guard = SqlGuard()
    for sql in [
        "SELECT a, b FROM t WHERE a > 1 ORDER BY a LIMIT 10",
        "SELECT count(*) FROM t GROUP BY a HAVING count(*) > 1",
        "  SELECT 1  ",
        "(SELECT 1) UNION (SELECT 2)",
        "WITH x AS (SELECT 1), y AS (SELECT 2) SELECT * FROM x JOIN y ON true",
    ]:
        assert guard.is_readonly(sql) is True, sql
