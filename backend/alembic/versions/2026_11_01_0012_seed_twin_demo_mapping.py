"""seed twin demo mapping（孪生 P0 演示口径：物理表 + 绑定 + 重发布快照）

探测结论（spec 2026-11-01-digital-twin-app-design §8.3 U1 / 计划 Task 0）：
迁移 0009 的 demo 本体只写模式层，版本快照硬编码
``"properties": []`` / ``"mappings": {"table": [], "column": []}``，
故全部 ``(租户, 本体, 版本)`` 的 ``mapping_rate`` 实测为 0.0 ——
孪生查询编译第 3 步（物理绑定解析）必然 ``QUERY_MAPPING_MISSING``。
本迁移为 ``sales_ontology`` 补齐最小可演示闭环：

1. 物理层：schema ``twin_demo`` + 客户/订单/产品三张表 + 样例行；
2. 资产层：``meta_data_source``（指向应用自身库；连接参数取 ``DB_*`` 环境变量，
   密码经 Fernet 落 ``password_enc``）+ ``meta_table`` / ``meta_column`` 录入；
3. 模式层：``meta_standard`` 属性项 + ``meta_object_standard_attribute``（全 accepted）；
4. 映射层：``meta_table_standard`` / ``meta_column_standard``（全 accepted）；
5. 关系层：为 ``sales_rel_order_of_customer`` 补 ``via_attribute_ids``
   （0009 留空，缺连接键则跨对象 JOIN 无键可用）；
6. 发布层：**追加**一个版本快照（properties/mappings 非空）并 bump
   ``current_version``——不改写历史快照（孪生运行期的快照不可变语义依赖它）。

只补 ``sales_ontology``（3 个 accepted 对象 + 1 条 accepted 关系，落在 P0 的
「≤2 对象 / ≤1 跳」编译限制内）；``supply_chain_ontology`` / ``hr_ontology`` 维持 P0 范围外。

两个易错点（实测）：``meta_table`` 的 schema 列叫 ``database``（**无** ``schema_name``），
物理库名另存 ``db_name``；``meta_object_standard_attribute`` 的 FK 指向
``meta_standard`` 是 RESTRICT，downgrade 必须先删引用行再删标准项。

前置条件：``DATAOPS_ENCRYPTION_KEY`` 必须已配置，否则 ``encrypt_secret`` 显式拒绝
（不降级为明文存储，见 app/ai/dataops/crypto.py:18）。

幂等：逐 ``sys_tenant``；该租户下已存在 ``name='twin-demo'`` 的数据源即整体跳过。
清理定位：版本行按 ``change_note``、数据源按 ``name``、标准项按显式 code 列表。

Revision ID: 2026_11_01_0012_seed_twin_demo_mapping
Revises: 2026_11_01_0011_add_sandbox_tables
Create Date: 2026-11-01 00:12:00.000000
"""
from __future__ import annotations

import json
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2026_11_01_0012_seed_twin_demo_mapping"
down_revision: Union[str, None] = "2026_11_01_0011_add_sandbox_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── 稳定标记（downgrade 与幂等判定都靠它们，不要改字面量）──────────────────
_MARK = "twin-demo-mapping"          # 同时作为数据源 name 与版本 change_note
_ONTOLOGY_CODE = "sales_ontology"
_SCHEMA = "twin_demo"

# 标准项：(code, name, security_level, mask_rule)
# mask_rule 非空即视为「脱敏已覆盖」（发布门禁 5 与编译敏感闸同一口径，
# 判定只看真假值，不解析字符串），故 demo 用可读名字占位即可。
_STANDARDS = [
    ("t_a_customer_code", "客户编码", "L0", None),
    ("t_a_customer_name", "客户名称", "L1", None),
    ("t_a_customer_phone", "客户联系电话", "L2", "keep_first3_last4"),
    ("t_a_region", "所属区域", "L0", None),
    ("t_a_order_code", "订单编码", "L0", None),
    ("t_a_order_amount", "订单金额", "L1", None),
    ("t_a_order_date", "下单日期", "L0", None),
    ("t_a_product_code", "产品编码", "L0", None),
    ("t_a_product_name", "产品名称", "L1", None),
    ("t_a_product_price", "产品单价", "L1", None),
]

# 物理表：表名 → (建表 DDL, [(列名, 标准 code, pii_level, data_type), ...], [样例行元组, ...])
_TABLES: list[tuple[str, str, list[tuple[str, str, str, str]], list[tuple]]] = [
    (
        "demo_customer",
        f'CREATE TABLE IF NOT EXISTS "{_SCHEMA}"."demo_customer" ('
        "customer_code text PRIMARY KEY, customer_name text, "
        "customer_phone text, customer_region text)",
        [("customer_code", "t_a_customer_code", "L0", "text"),
         ("customer_name", "t_a_customer_name", "L1", "text"),
         ("customer_phone", "t_a_customer_phone", "L2", "text"),
         ("customer_region", "t_a_region", "L0", "text")],
        [("C001", "华东电子", "13800001234", "EAST"),
         ("C002", "南方物流", "13900005678", "SOUTH")],
    ),
    (
        "demo_order",
        f'CREATE TABLE IF NOT EXISTS "{_SCHEMA}"."demo_order" ('
        "order_code text PRIMARY KEY, customer_code text, "
        "order_amount numeric(14,2), order_date date)",
        [("order_code", "t_a_order_code", "L0", "text"),
         ("customer_code", "t_a_customer_code", "L0", "text"),
         ("order_amount", "t_a_order_amount", "L1", "numeric"),
         ("order_date", "t_a_order_date", "L0", "date")],
        [("O1001", "C001", 128000, "2026-10-12"),
         ("O1002", "C002", 46000, "2026-10-18")],
    ),
    (
        "demo_product",
        f'CREATE TABLE IF NOT EXISTS "{_SCHEMA}"."demo_product" ('
        "product_code text PRIMARY KEY, product_name text, unit_price numeric(12,2))",
        [("product_code", "t_a_product_code", "L0", "text"),
         ("product_name", "t_a_product_name", "L1", "text"),
         ("unit_price", "t_a_product_price", "L1", "numeric")],
        [("P77", "边缘网关", 3200), ("P78", "工业网关", 5100)],
    ),
]

# 对象 code（0009 已 seed）→ 物理表名
_OBJECT_TABLE = {
    "sales_obj_customer": "demo_customer",
    "sales_obj_order": "demo_order",
    "sales_obj_product": "demo_product",
}

# 对象 code → 该对象的属性标准项 code（顺序即 sort_order）
_OBJECT_ATTRS = {
    "sales_obj_customer": ["t_a_customer_code", "t_a_customer_name",
                           "t_a_customer_phone", "t_a_region"],
    "sales_obj_order": ["t_a_order_code", "t_a_customer_code",
                        "t_a_order_amount", "t_a_order_date"],
    "sales_obj_product": ["t_a_product_code", "t_a_product_name", "t_a_product_price"],
}

# 关系 code → 两端共用的连接键标准项 code
_RELATION_VIA = {"sales_rel_order_of_customer": "t_a_customer_code"}


def _quoted(values) -> str:
    """拼显式 IN 列表（值全部来自本模块常量，无外部输入）。"""
    return ", ".join("'{}'".format(v) for v in values)


def _existing(bind, tid: int) -> bool:
    return bind.execute(
        sa.text("SELECT 1 FROM meta_data_source WHERE tenant_id = :t AND name = :n"),
        {"t": tid, "n": _MARK},
    ).first() is not None


def _create_physical(bind) -> None:
    """① 物理层：schema + 三张 demo 表 + 样例行（IF NOT EXISTS，可重复执行）。"""
    bind.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{_SCHEMA}"'))
    for name, ddl, _cols, rows in _TABLES:
        bind.execute(sa.text(ddl))
        if rows:
            values = ", ".join(
                "(" + ", ".join(
                    "NULL" if v is None else (f"'{v}'" if isinstance(v, str) else str(v))
                    for v in r
                ) + ")"
                for r in rows
            )
            bind.execute(sa.text(f'INSERT INTO "{_SCHEMA}"."{name}" VALUES {values} '
                                 f"ON CONFLICT DO NOTHING"))


def _insert_source(bind, tid: int) -> int:
    """② 资产层：数据源指向应用自身库（连接参数与 alembic/env.py 同源）。"""
    from app.ai.dataops.crypto import encrypt_secret

    db_name = os.getenv("DB_NAME", "minworkbuddy")
    return bind.execute(
        sa.text(
            "INSERT INTO meta_data_source (tenant_id, name, source_type, external_type, "
            "host, port, username, password_enc, database, charset, status) "
            "VALUES (:t, :n, 'postgresql', 'rdbms', :h, :p, :u, :pw, :db, 'utf8', 'online') "
            "RETURNING id"
        ),
        {
            "t": tid, "n": _MARK,
            "h": os.getenv("DB_HOST", "localhost"),
            "p": int(os.getenv("DB_PORT", "5432")),
            "u": os.getenv("DB_USER", "postgres"),
            "pw": encrypt_secret(os.getenv("DB_PASSWORD", "")),
            "db": db_name,
        },
    ).scalar_one()


def _insert_assets(bind, tid: int, dsid: int) -> tuple[dict, dict]:
    """② 资产层：meta_table / meta_column 录入（database 存 schema，db_name 存物理库）。"""
    db_name = os.getenv("DB_NAME", "minworkbuddy")
    table_ids: dict[str, int] = {}
    column_ids: dict[tuple[str, str], int] = {}
    for name, _ddl, cols, _rows in _TABLES:
        tid_ = bind.execute(
            sa.text("INSERT INTO meta_table (tenant_id, source_id, db_name, database, table_name, "
                    "table_type, column_count) VALUES (:t, :s, :db, :sc, :n, 'BASE TABLE', :cc) "
                    "RETURNING id"),
            {"t": tid, "s": dsid, "db": db_name, "sc": _SCHEMA, "n": name, "cc": len(cols)},
        ).scalar_one()
        table_ids[name] = int(tid_)
        for ordinal, (cname, _std, pii, dtype) in enumerate(cols, start=1):
            cid = bind.execute(
                sa.text("INSERT INTO meta_column (tenant_id, table_id, column_name, ordinal, "
                        "data_type, pii_level) VALUES (:t, :tb, :n, :o, :dt, :p) RETURNING id"),
                {"t": tid, "tb": tid_, "n": cname, "o": ordinal, "dt": dtype, "p": pii},
            ).scalar_one()
            column_ids[(name, cname)] = int(cid)
    return table_ids, column_ids


def _insert_standards(bind, tid: int) -> dict:
    """③ 模式层：meta_standard 属性项（published，review_status=accepted）。"""
    std_ids: dict[str, int] = {}
    for code, name, level, mask in _STANDARDS:
        sid = bind.execute(
            sa.text("INSERT INTO meta_standard (tenant_id, code, name, status, security_level, "
                    "mask_rule, review_status) "
                    "VALUES (:t, :c, :n, 'published', :l, :m, 'accepted') RETURNING id"),
            {"t": tid, "c": code, "n": name, "l": level, "m": mask},
        ).scalar_one()
        std_ids[code] = int(sid)
    return std_ids


def _object_ids(bind, tid: int) -> dict | None:
    """取 0009 seed 的 accepted 对象 id；任一缺失说明该租户未 seed demo 本体 → 跳过。"""
    ids: dict[str, int] = {}
    for code in _OBJECT_TABLE:
        row = bind.execute(
            sa.text("SELECT id FROM meta_object_standard "
                    "WHERE tenant_id = :t AND code = :c AND review_status = 'accepted'"),
            {"t": tid, "c": code},
        ).first()
        if row is None:
            return None
        ids[code] = int(row[0])
    return ids


def _insert_attributes(bind, tid: int, obj_ids: dict, std_ids: dict) -> list[dict]:
    """③ 模式层：对象↔属性 引用（全 accepted），返回快照 properties 行。"""
    props: list[dict] = []
    for obj_code, attr_codes in _OBJECT_ATTRS.items():
        for sort_order, std_code in enumerate(attr_codes):
            sid = std_ids[std_code]
            pid = bind.execute(
                sa.text("INSERT INTO meta_object_standard_attribute "
                        "(tenant_id, object_id, standard_id, required, sort_order, review_status) "
                        "VALUES (:t, :o, :s, false, :so, 'accepted') RETURNING id"),
                {"t": tid, "o": obj_ids[obj_code], "s": sid, "so": sort_order},
            ).scalar_one()
            props.append({"id": int(pid), "object_id": obj_ids[obj_code],
                          "standard_id": sid, "required": False,
                          "review_status": "accepted"})
    return props


def _insert_mappings(bind, tid: int, obj_ids: dict, std_ids: dict,
                     table_ids: dict, column_ids: dict) -> tuple[list[dict], list[dict]]:
    """④ 映射层：表/列绑定（全 accepted、source=human），返回快照 mappings 两组行。"""
    table_rows: list[dict] = []
    for obj_code, table_name in _OBJECT_TABLE.items():
        tb = table_ids[table_name]
        mid = bind.execute(
            sa.text("INSERT INTO meta_table_standard (tenant_id, table_id, object_standard_id, "
                    "status, source) VALUES (:t, :tb, :o, 'accepted', 'human') RETURNING id"),
            {"t": tid, "tb": tb, "o": obj_ids[obj_code]},
        ).scalar_one()
        table_rows.append({"id": int(mid), "table_id": tb,
                           "object_standard_id": obj_ids[obj_code], "source": "human"})

    column_rows: list[dict] = []
    for name, _ddl, cols, _rows in _TABLES:
        for cname, std_code, _pii, _dt in cols:
            cid = column_ids[(name, cname)]
            sid = std_ids[std_code]
            mid = bind.execute(
                sa.text("INSERT INTO meta_column_standard (tenant_id, column_id, standard_id, "
                        "status, source) VALUES (:t, :c, :s, 'accepted', 'human') RETURNING id"),
                {"t": tid, "c": cid, "s": sid},
            ).scalar_one()
            column_rows.append({"id": int(mid), "column_id": cid,
                                "standard_id": sid, "source": "human"})
    return table_rows, column_rows


def _fill_relation_keys(bind, tid: int, std_ids: dict) -> None:
    """⑤ 关系层：补 JOIN 连接键（快照只冻结关系 id，编译回查实表的 via_attribute_ids）。"""
    for rel_code, std_code in _RELATION_VIA.items():
        bind.execute(
            sa.text("UPDATE meta_object_relation SET via_attribute_ids = CAST(:v AS jsonb) "
                    "WHERE tenant_id = :t AND code = :c"),
            {"t": tid, "c": rel_code, "v": json.dumps([std_ids[std_code]])},
        )


def _republish_snapshot(bind, tid: int, props: list[dict],
                        table_rows: list[dict], column_rows: list[dict]) -> None:
    """⑥ 发布层：以 current_version 快照为基追加新版本（只补 properties/mappings）。"""
    ont = bind.execute(
        sa.text("SELECT id, current_version FROM onto_ontology WHERE tenant_id = :t AND code = :c"),
        {"t": tid, "c": _ONTOLOGY_CODE},
    ).first()
    if ont is None:
        return
    ontology_id, cv = int(ont[0]), int(ont[1] or 0)
    base = bind.execute(
        sa.text("SELECT snapshot_json FROM onto_ontology_version "
                "WHERE tenant_id = :t AND ontology_id = :o AND version = :v"),
        {"t": tid, "o": ontology_id, "v": cv},
    ).scalar()
    if base is None:                      # 无 current 版本快照（draft 本体）→ 不重发布
        return

    snap = dict(base)
    snap["properties"] = props
    snap["mappings"] = {"table": table_rows, "column": column_rows}
    nv = cv + 1
    diff = {
        "added": {"objects": [], "relations": [], "properties": len(props)},
        "removed": {"objects": [], "relations": []},
        "changed": [], "regressions": [],
    }
    gate = {"passed": True, "checks": [], "blocked_reasons": [], "exemptions": []}
    bind.execute(
        sa.text("INSERT INTO onto_ontology_version "
                "(tenant_id, ontology_id, version, snapshot_json, diff_json, gate_json, change_note) "
                "VALUES (:t, :o, :v, CAST(:snap AS jsonb), CAST(:diff AS jsonb), CAST(:gate AS jsonb), :note)"),
        {
            "t": tid, "o": ontology_id, "v": nv,
            "snap": json.dumps(snap, ensure_ascii=False),
            "diff": json.dumps(diff), "gate": json.dumps(gate), "note": _MARK,
        },
    )
    bind.execute(
        sa.text("UPDATE onto_ontology SET current_version = :v WHERE id = :o"),
        {"v": nv, "o": ontology_id},
    )


def upgrade() -> None:
    bind = op.get_bind()
    tenant_ids = bind.execute(sa.text("SELECT tenant_id FROM sys_tenant")).scalars().all()
    for tid in tenant_ids:
        if _existing(bind, tid):
            continue
        obj_ids = _object_ids(bind, tid)
        if obj_ids is None:               # 该租户没有 seed 过 demo 本体（0009 未覆盖）→ 跳过
            continue
        _create_physical(bind)
        dsid = _insert_source(bind, tid)
        table_ids, column_ids = _insert_assets(bind, tid, dsid)
        std_ids = _insert_standards(bind, tid)
        props = _insert_attributes(bind, tid, obj_ids, std_ids)
        table_rows, column_rows = _insert_mappings(bind, tid, obj_ids, std_ids, table_ids, column_ids)
        _fill_relation_keys(bind, tid, std_ids)
        _republish_snapshot(bind, tid, props, table_rows, column_rows)


def downgrade() -> None:
    """逆序清理：版本行 → current_version 回退 → 列/表绑定 → 属性引用 → 标准项 → 资产 → 物理层。

    注意 ``DROP SCHEMA ... CASCADE`` 只删本迁移建的 ``twin_demo``，不碰业务 schema。
    """
    bind = op.get_bind()
    std_in = _quoted(c for c, *_ in _STANDARDS)
    obj_in = _quoted(_OBJECT_TABLE)
    rel_in = _quoted(_RELATION_VIA)

    # ⑥ 发布层：只删带标记的版本行，然后把 current_version 回退到剩余最大版本
    bind.execute(sa.text("DELETE FROM onto_ontology_version WHERE change_note = :m"), {"m": _MARK})
    bind.execute(
        sa.text(
            "UPDATE onto_ontology o SET current_version = COALESCE("
            "(SELECT max(v.version) FROM onto_ontology_version v WHERE v.ontology_id = o.id), 0) "
            "WHERE o.code = :c"
        ),
        {"c": _ONTOLOGY_CODE},
    )
    # ⑤ 关系层：连接键还原为 0009 的 NULL
    bind.execute(
        sa.text(f"UPDATE meta_object_relation SET via_attribute_ids = NULL WHERE code IN ({rel_in})")
    )
    # ④ 映射层
    bind.execute(
        sa.text("DELETE FROM meta_column_standard WHERE standard_id IN "
                f"(SELECT id FROM meta_standard WHERE code IN ({std_in}))")
    )
    bind.execute(
        sa.text("DELETE FROM meta_table_standard WHERE object_standard_id IN "
                f"(SELECT id FROM meta_object_standard WHERE code IN ({obj_in}))")
    )
    # ③ 模式层（meta_standard 被属性引用 RESTRICT，必须先删引用）
    bind.execute(
        sa.text("DELETE FROM meta_object_standard_attribute WHERE standard_id IN "
                f"(SELECT id FROM meta_standard WHERE code IN ({std_in}))")
    )
    bind.execute(sa.text(f"DELETE FROM meta_standard WHERE code IN ({std_in})"))
    # ② 资产层（列 → 表 → 数据源）
    bind.execute(
        sa.text("DELETE FROM meta_column WHERE table_id IN "
                "(SELECT id FROM meta_table WHERE database = :sc)"),
        {"sc": _SCHEMA},
    )
    bind.execute(sa.text("DELETE FROM meta_table WHERE database = :sc"), {"sc": _SCHEMA})
    bind.execute(sa.text("DELETE FROM meta_data_source WHERE name = :m"), {"m": _MARK})
    # ① 物理层
    bind.execute(sa.text(f'DROP SCHEMA IF EXISTS "{_SCHEMA}" CASCADE'))
