"""PostgreSQL 方言契约测试（评审 IM-01 / IM-03）。

本任务的验收标准是「持久化到 PostgreSQL」，因此测试必须跑在真实 PostgreSQL 上。
这个文件把「确实是 PostgreSQL」以及「JSONB 语义正确」固化为断言：

* 连接串必须是 PostgreSQL（防止有人把测试退回 SQLite 后声称通过）；
* `parent_uris` / `class_uris` 在 PG 上的真实类型必须是 `jsonb`；
* `.contains()` 必须编译成 `@>` 而不是 `LIKE`（`JSON().with_variant(JSONB)` 的坑）。
"""
from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Engine

from app.models.ontology.ontology import OntologyAnnotation, OntologyClass

from .conftest import IS_POSTGRES, TEST_DB_URL

pytestmark = pytest.mark.skipif(
    not IS_POSTGRES,
    reason="MINWORKBUDDY_TEST_DB_URL 被显式覆盖为非 PostgreSQL，跳过方言契约检查",
)


def test_tests_run_against_postgresql() -> None:
    """验收数据库必须是 PostgreSQL（不是 SQLite）。"""
    assert IS_POSTGRES, f"测试必须跑在 PostgreSQL 上，当前连接串为 {TEST_DB_URL}"


def test_json_list_columns_are_real_jsonb(engine: Engine) -> None:
    """`parent_uris` / `class_uris` 在 PG 上必须是 jsonb 列。"""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name, column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND ((table_name = 'ontology_class' AND column_name = 'parent_uris') "
                "OR (table_name = 'ontology_annotation' AND column_name = 'class_uris'))"
            )
        ).all()
    types = {(row[0], row[1]): row[2] for row in rows}
    assert types == {
        ("ontology_class", "parent_uris"): "jsonb",
        ("ontology_annotation", "class_uris"): "jsonb",
    }, types


def test_contains_operator_compiles_to_jsonb_containment() -> None:
    """`.contains()` 必须编译成 JSONB 的 `@>`（不是 `LIKE`） —— 评审 IM-03。"""
    for column in (OntologyClass.parent_uris, OntologyAnnotation.class_uris):
        stmt = select(column).where(column.contains(["http://example.org/ontology#X"]))
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        assert "@>" in sql, f"期望 JSONB @> 运算符，实际: {sql}"
        assert "LIKE" not in sql, f"退化成了 LIKE 匹配，实际: {sql}"


def test_jsonb_containment_query_actually_runs(engine: Engine) -> None:
    """真实执行一条 `@>` 查询：类型变体错误会在这一步暴露为 DataError。"""
    with engine.connect() as conn:
        rows = conn.execute(
            select(OntologyClass.uri).where(
                OntologyClass.parent_uris.contains(["http://example.org/ontology#Risk"])
            )
        ).all()
    assert rows == []
