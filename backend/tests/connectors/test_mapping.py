"""P3 Task 2~5 测试：字段映射（纯函数，无网络/DB）。"""
from __future__ import annotations

from app.connectors.mapping import FieldMapItem, apply_field_map, extract_path


def test_extract_path_nested():
    assert extract_path({"a": {"b": {"c": 1}}}, "a.b.c") == 1
    assert extract_path({"a": {"b": 1}}, "a.x") is None
    assert extract_path([1, 2], None) == [1, 2]


def test_apply_field_map_basic():
    recs = [{"data": {"user": {"name": "Alice", "age": "30"}}}]
    fm = [
        FieldMapItem(target="name", source="data.user.name"),
        FieldMapItem(target="age", source="data.user.age", transform="int"),
    ]
    out = apply_field_map(recs, fm)
    assert out == [{"name": "Alice", "age": 30}]


def test_apply_field_map_default():
    recs = [{"x": 1}]
    fm = [FieldMapItem(target="y", source="missing", default="N/A")]
    out = apply_field_map(recs, fm)
    assert out == [{"y": "N/A"}]


def test_apply_field_map_transforms():
    recs = [{"s": "  Hello  ", "n": "42", "b": "true", "d": "2024-01-02"}]
    fm = [
        FieldMapItem(target="s", source="s", transform="trim"),
        FieldMapItem(target="n", source="n", transform="int"),
        FieldMapItem(target="b", source="b", transform="bool"),
        FieldMapItem(target="d", source="d", transform="date_iso"),
    ]
    out = apply_field_map(recs, fm)
    assert out[0]["s"] == "Hello"
    assert out[0]["n"] == 42
    assert out[0]["b"] is True
    assert out[0]["d"] == "2024-01-02T00:00:00"


def test_apply_field_map_unknown_transform_raises():
    recs = [{"a": 1}]
    fm = [FieldMapItem(target="a", source="a", transform="eval_me")]
    try:
        apply_field_map(recs, fm)
        assert False, "应当抛出 ValueError"
    except ValueError:
        pass


def test_apply_field_map_passthrough_when_none():
    recs = [{"a": 1}]
    assert apply_field_map(recs, None) == recs
