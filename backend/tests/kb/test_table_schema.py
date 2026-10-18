"""表格列定义（schema）自动生成 + 导入格式校验（spec §10.2 / §10.5）。

覆盖：无定义→按表头自动定义并落库；已有定义→缺列/多列/类型不符拒绝导入。
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.services.kb.rag.content_service import parse_table, parse_table_bytes
from app.services.kb.table_schema import (
    TableSchemaMismatch,
    coerce_value,
    embedding_fields,
    get_schema_fields,
    infer_fields,
    resolve_import_schema,
    set_schema_fields,
    validate_rows,
)

FIELDS = [
    {"name": "商品", "type": "string", "enabled": True, "embedding": True, "filterable": False},
    {"name": "价格", "type": "number", "enabled": True, "embedding": False, "filterable": True},
]


# ── 取值规范化 ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "value,ftype,expected",
    [
        (9, "number", 9),
        ("9.5", "number", 9.5),
        ("1,234", "number", 1234),
        ("是", "boolean", True),
        ("false", "boolean", False),
        (True, "boolean", True),
        (None, "number", ""),
        ("  ", "string", ""),
        (dt.date(2026, 1, 2), "string", "2026-01-02"),
        (12, "string", "12"),
    ],
)
def test_coerce_value(value, ftype, expected):
    assert coerce_value(value, ftype) == expected


def test_coerce_value_type_error():
    with pytest.raises(ValueError):
        coerce_value("abc", "number")
    with pytest.raises(ValueError):
        coerce_value("maybe", "boolean")


# ── 解析 ──────────────────────────────────────────────────────────────────

def test_parse_table_returns_headers_in_order():
    columns, rows = parse_table("b,a\n2,1\n".encode(), "t.csv")
    assert columns == ["b", "a"]
    assert rows == [{"b": "2", "a": "1"}]


def test_parse_table_rejects_unsupported_type():
    with pytest.raises(ValueError, match="不支持的表格文件类型"):
        parse_table(b"x", "t.pdf")


def test_parse_table_bytes_still_returns_rows():
    assert parse_table_bytes("desc,price\n防水低价,9\n".encode(), "t.csv")[0]["desc"] == "防水低价"


# ── 推断 ──────────────────────────────────────────────────────────────────

def test_infer_fields_marks_all_columns_as_embedding_by_default():
    """未指定向量化字段时，**默认所有字段**组合为向量化内容。"""
    fields = infer_fields(["空列", "商品", "价格"], [{"空列": None, "商品": "A", "价格": "9"}])
    assert [f["name"] for f in fields] == ["空列", "商品", "价格"]
    assert [f["name"] for f in fields if f["embedding"]] == ["空列", "商品", "价格"]
    assert next(f for f in fields if f["name"] == "价格")["type"] == "number"
    assert next(f for f in fields if f["name"] == "商品")["type"] == "string"


def test_infer_fields_respects_explicit_embed_fields():
    """显式指定字段组合（1~N 个）时，仅这些字段为向量化字段，其余可过滤。"""
    fields = infer_fields(
        ["商品", "价格", "库存"],
        [{"商品": "A", "价格": "9", "库存": "3"}],
        embed_fields=["商品", "库存"],
    )
    assert [f["name"] for f in fields if f["embedding"]] == ["商品", "库存"]
    assert [f["name"] for f in fields if f["filterable"]] == ["价格"]


def test_infer_fields_keeps_legacy_single_embed_field():
    """兼容旧参数 ``embed_field``（单字段组合）。"""
    fields = infer_fields(
        ["商品", "价格"], [{"商品": "A", "价格": "9"}], embed_field="价格",
    )
    assert [f["name"] for f in fields if f["embedding"]] == ["价格"]


# ── 校验 ──────────────────────────────────────────────────────────────────

def test_validate_rows_normalizes_values():
    rows = validate_rows(FIELDS, [{"商品": "A", "价格": "9"}, {"商品": "B", "价格": "10.5"}])
    assert rows[0]["价格"] == 9 and isinstance(rows[0]["价格"], int)
    assert rows[1]["价格"] == 10.5


def test_validate_rows_column_order_insensitive():
    rows = validate_rows(FIELDS, [{"价格": "9", "商品": "A"}], columns=["价格", "商品"])
    assert rows[0] == {"商品": "A", "价格": 9}


def test_validate_rows_missing_and_extra_columns():
    with pytest.raises(TableSchemaMismatch) as ei:
        validate_rows(FIELDS, [{"商品": "A", "库存": "3"}], columns=["商品", "库存"])
    assert ei.value.code == "table_schema_mismatch"
    assert ei.value.extra["missing"] == ["价格"]
    assert ei.value.extra["extra"] == ["库存"]


def test_validate_rows_cell_type_mismatch():
    with pytest.raises(TableSchemaMismatch) as ei:
        validate_rows(FIELDS, [{"商品": "A", "价格": "九块九"}])
    assert ei.value.code == "table_cell_type_mismatch"
    assert ei.value.extra == {"row": 1, "column": "价格", "expected": "number"}


def test_validate_rows_requires_definition():
    with pytest.raises(TableSchemaMismatch) as ei:
        validate_rows([], [{"a": 1}])
    assert ei.value.code == "table_schema_empty"


# ── 落库：自动定义 / 已有定义校验 ──────────────────────────────────────────

def test_resolve_import_schema_auto_creates_and_persists(db):
    result = resolve_import_schema(
        db, "kb_9", ["商品", "价格"], [{"商品": "A", "价格": "9"}],
    )
    assert result["created"] is True
    # 自动生成时默认**所有字段**组合为向量化内容
    assert result["embed_fields"] == ["商品", "价格"]
    assert result["embed_field"] == "商品"
    assert list(result["rows"][0]) == ["商品", "价格"]
    stored = get_schema_fields(db, "kb_9")
    assert [f["name"] for f in stored] == ["商品", "价格"]
    assert [f["name"] for f in stored if f["embedding"]] == ["商品", "价格"]


def test_resolve_import_schema_validates_existing_definition(db):
    resolve_import_schema(db, "kb_10", ["商品", "价格"], [{"商品": "A", "价格": "9"}])
    # 列序变化可过
    ok = resolve_import_schema(db, "kb_10", ["价格", "商品"], [{"商品": "B", "价格": "10"}])
    assert ok["created"] is False and ok["rows"][0]["价格"] == 10
    # 缺列 → 拒绝
    with pytest.raises(TableSchemaMismatch) as ei:
        resolve_import_schema(db, "kb_10", ["商品"], [{"商品": "B"}])
    assert ei.value.code == "table_schema_mismatch"
    assert ei.value.extra["missing"] == ["价格"]


def test_resolve_import_schema_persist_false_does_not_write(db):
    result = resolve_import_schema(
        db, "kb_11", ["商品"], [{"商品": "A"}], persist=False,
    )
    assert result["created"] is True
    assert get_schema_fields(db, "kb_11") == []


# ── 手工维护定义 ──────────────────────────────────────────────────────────

def test_set_schema_fields_requires_single_embedded_column(db):
    with pytest.raises(TableSchemaMismatch) as ei:
        set_schema_fields(db, "kb_12", [{"name": "a", "embedding": False}])
    assert ei.value.code == "table_schema_embed_required"


def test_set_schema_fields_dedupes_and_normalizes(db):
    """去重 + 类型白名单；向量化字段**允许多选**（不再截断为第一个）。"""
    fields = set_schema_fields(db, "kb_13", [
        {"name": " a ", "type": "unknown", "embedding": True},
        {"name": "a", "embedding": True},
        {"name": "b", "type": "number", "embedding": True},
    ])
    assert [f["name"] for f in fields] == ["a", "b"]
    assert fields[0]["type"] == "string"
    assert [f["name"] for f in fields if f["embedding"]] == ["a", "b"]


def test_embedding_fields_returns_combination_in_order(db):
    """``embedding_fields`` 按字段定义顺序返回向量化字段组合。"""
    fields = set_schema_fields(db, "kb_14", [
        {"name": "商品", "type": "string", "embedding": True},
        {"name": "价格", "type": "number", "embedding": False},
        {"name": "品牌", "type": "string", "embedding": True},
    ])
    assert embedding_fields(fields) == ["商品", "品牌"]