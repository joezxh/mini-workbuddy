"""探测脚本：映射覆盖率的计算必须可离线验证（不连库，喂 fixture 行）。

行形状与脚本内 SQL 的输出一致：每行代表一个**已采纳元素**（对象或属性），
`covered` 表示它是否已完成物理绑定。聚合口径 = 对象与属性合并计数。
"""
from scripts.twin_mapping_probe import summarize


def test_summarize_aggregates_objects_and_attributes():
    rows = [
        {"code": "sales_ontology", "version": 1, "kind": "object", "covered": True},
        {"code": "sales_ontology", "version": 1, "kind": "object", "covered": False},
        {"code": "sales_ontology", "version": 1, "kind": "attribute", "covered": True},
        {"code": "sales_ontology", "version": 1, "kind": "attribute", "covered": False},
    ]
    assert summarize(rows) == [{
        "ontology_code": "sales_ontology", "version": 1,
        "objects": 2, "mapped_objects": 1, "attributes": 2, "mapped_attributes": 1,
        "mapping_rate": 0.5,
    }]


def test_summarize_reports_zero_when_nothing_mapped():
    # demo 本体当前实况：有对象但一个都没绑上表
    rows = [{"code": "hr_ontology", "version": 1, "kind": "object", "covered": False}]
    out = summarize(rows)
    assert out[0]["objects"] == 1 and out[0]["mapped_objects"] == 0
    assert out[0]["mapping_rate"] == 0.0


def test_summarize_splits_versions_and_sorts_output():
    rows = [
        {"code": "b_kb", "version": 2, "kind": "object", "covered": True},
        {"code": "a_dev", "version": 1, "kind": "attribute", "covered": True},
    ]
    out = summarize(rows)
    assert [(x["ontology_code"], x["version"]) for x in out] == [("a_dev", 1), ("b_kb", 2)]
