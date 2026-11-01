"""孪生 P0 前置探测：已发布快照内的对象与属性是否完成物理映射。

背景（spec §8.2 假设 A1 / §8.3 U1）：查询编译第 3 步要求
对象→``meta_table_standard``→``MetaTable``、属性→``meta_column_standard``→``MetaColumn``
均已绑定；迁移 0009 的 demo 本体只写了模式层，未写映射层。本脚本量化缺口。

探测靶面必须是**编译第 1/3 步真正读的东西**：
``onto_ontology_version.snapshot_json``（发布时冻结，只存 id）+ 实表的 accepted 绑定，
故 SQL 直接展开快照的 ``objects[]``（按 ``id``）与 ``properties[]``（按 ``standard_id``），
而不是遍历 ``onto_ontology_build_item``——构建期元素未必进入任何已发布快照。

两个易错列名（实测，写错即 SQL 报错）：``meta_table_standard.object_standard_id``
（**不是** ``object_id``）；``meta_table`` 的 schema 列名是 ``database``（**无** ``schema_name`` 列）。

必须用 ``EXISTS`` 而不是 ``LEFT JOIN`` 判覆盖：一个对象可绑多表
（``uq_meta_table_standard_table`` 只在 ``table_id`` 上唯一）、一个标准项可绑多列，
LEFT JOIN 会把一个快照元素放大成多行，分母与分子一起虚高（实测 11 条属性被数成 13）。

用法（须在 backend/ 下执行）：
       python scripts/twin_mapping_probe.py            # 全部租户
       python scripts/twin_mapping_probe.py --tenant 1 # 指定租户
       python -m scripts.twin_mapping_probe            # 等价（包路径导入）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

SQL_OBJECT_COVERAGE = text(
    """
    SELECT ont.code        AS code,
           v.version       AS version,
           'object'        AS kind,
           EXISTS (SELECT 1 FROM meta_table_standard ts
                   WHERE ts.object_standard_id = o.id AND ts.status = 'accepted') AS covered
    FROM onto_ontology_version v
    JOIN onto_ontology ont ON ont.id = v.ontology_id
    CROSS JOIN LATERAL jsonb_array_elements(v.snapshot_json -> 'objects') AS s(item)
    JOIN meta_object_standard o ON o.id = (s.item ->> 'id')::bigint
    WHERE v.tenant_id = :tid AND v.version > 0
      AND (s.item ->> 'review_status') = 'accepted'
    """
)

SQL_ATTRIBUTE_COVERAGE = text(
    """
    SELECT ont.code        AS code,
           v.version       AS version,
           'attribute'     AS kind,
           EXISTS (SELECT 1 FROM meta_column_standard cs
                   WHERE cs.standard_id = st.id AND cs.status = 'accepted') AS covered
    FROM onto_ontology_version v
    JOIN onto_ontology ont ON ont.id = v.ontology_id
    CROSS JOIN LATERAL jsonb_array_elements(v.snapshot_json -> 'properties') AS p(item)
    JOIN meta_standard st ON st.id = (p.item ->> 'standard_id')::bigint
    WHERE v.tenant_id = :tid AND v.version > 0
      AND (p.item ->> 'review_status') = 'accepted'
    """
)


def summarize(rows: List[Dict]) -> List[Dict]:
    """按 (本体 code, 版本) 聚合对象/属性覆盖率。纯函数，便于单测。

    :param rows: 每行 `{code, version, kind('object'|'attribute'), covered(bool)}`
    :return: 按 (ontology_code, version) 升序的聚合结果；`mapping_rate` 为对象与
        属性合并后的覆盖率（分母为 0 时记 0.0，不抛）
    """
    buckets: Dict[tuple, Dict] = {}
    for r in rows:
        k = (r["code"], int(r["version"]))
        b = buckets.setdefault(k, {"ontology_code": r["code"], "version": k[1],
                                   "objects": 0, "mapped_objects": 0,
                                   "attributes": 0, "mapped_attributes": 0})
        kind, covered = r["kind"], bool(r["covered"])
        b[kind + "s"] += 1                     # objects / attributes
        if covered:
            b["mapped_" + kind + "s"] += 1      # mapped_objects / mapped_attributes
    for b in buckets.values():
        total = b["objects"] + b["attributes"]
        done = b["mapped_objects"] + b["mapped_attributes"]
        b["mapping_rate"] = round(done / total, 3) if total else 0.0
    return sorted(buckets.values(), key=lambda x: (x["ontology_code"], x["version"]))


def probe(db: Session, tenant_id: int) -> List[Dict]:
    """合并两次查询的原始行后聚合（列名由第一条 SQL 的别名决定）。"""
    rows = [dict(r) for r in db.execute(SQL_OBJECT_COVERAGE, {"tid": tenant_id}).mappings()]
    rows += [dict(r) for r in db.execute(SQL_ATTRIBUTE_COVERAGE, {"tid": tenant_id}).mappings()]
    return summarize(rows)


def main() -> None:
    # 支持 `python scripts/twin_mapping_probe.py` 直接执行：脚本目录不是仓库根，
    # 需把 backend/ 挂上 sys.path 才能 import `app`（沿用 scripts/apply_ddl.py:17 的写法）。
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from app.db.database import SessionLocal

    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", type=int, required=False)
    args = ap.parse_args()

    db: Session = SessionLocal()
    try:
        tids = [args.tenant] if args.tenant else [
            # 注意：`sys_tenant` 的主键叫 `tenant_id`（**不是** `id`）
            t[0] for t in db.execute(text("SELECT tenant_id FROM sys_tenant")).all()
        ]
        report = {tid: probe(db, tid) for tid in tids}
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
