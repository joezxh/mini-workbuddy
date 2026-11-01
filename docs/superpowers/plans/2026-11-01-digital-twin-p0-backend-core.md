# 孪生应用 P0 · 后端取数内核 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付孪生应用 P0 的后端能力：本体查询一等公民、查询编译与敏感闸、页面级批量取数（含出口脱敏与角色安全缓存）、卡片/页面/组件编排、发布只读页与权限申请闭环。

**Architecture:** 四层职责——语义层 `onto_ontology_query` 声明"查什么"；编排层 `twin_*` 只做绑定；执行层复用唯一取数口 `ReadonlyQueryService` + `SqlGuard`（仅扩展 `params` 形参）；出口层复用纯函数 `masking.apply_masking`。查询期直连源库，不落库任何业务数据（遵守上游决策 D2）。

**Tech Stack:** Python 3 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL(JSONB) · sqlglot 30.18.0 · pytest

**Spec:** `docs/superpowers/specs/2026-11-01-digital-twin-app-design.md`（本计划实现其 §3 数据模型、§4 关键闭环、§6.1 端点 Q1–Q5/T1–T12、§7.3 的 P0-1/P0-2/P0-3/P0-4/P0-7/P0-8/P0-11；前端 P0-5/P0-6/P0-9/P0-10 属 Plan 2）

## Global Constraints

- **不新增任何第三方依赖**（后端与前端均不引新包）。
- 查询编译产物必须是**单语句、无注释** SQL：`SqlGuard` 对 `--`、`/*`、`*/` 零容忍（`app/services/dataops/sql_guard.py:25`，校验点 `:102`）。
- 所有新端点只抛 `ApiError(code, message, http_status, detail)`（`app/core/api_error.py:22`），响应体固定 `{code, message, detail?}`；**不改动**既有 dataops 端点的 `HTTPException` 契约。
- 服务层构造一律要求租户：沿用现有写法，`tenant_id is None` 直接 `raise ValueError`（对照 `query_service.py:34-35`）。
- 命名纪律：**模块**= `widget_key`（palette 类型），**组件**= `widget_id`（已放置实例），不得都叫 `module`；`scene` 在本计划中仅指**等距视觉场景模板**，禁止引用沙盘域的 `onto_sandbox_scene` 类型。
- 权限判定统一走 `build_user_context(db, user) -> Optional[ToolUserContext]`（`app/ai/tool_manager/tool_context.py:173`，聚合 `role_codes` 与 `permissions`，异常降级为最小权限）。**不启用** `AuditLogRoute` 的 `openapi_extra={"permissions": ...}` 分支——全仓库当前零处使用，其 403 路径未经运行验证。
- 表名前缀：本体域 `onto_ontology_*`、孪生域 `twin_*`；模型类名本体域 `Meta*`、孪生域 `Twin*`。
- Alembic 当前 head：`2026_11_01_0011_add_sandbox_tables`；本计划新迁移 `down_revision` 必须指向它。
- 测试需要本地 PostgreSQL（库 `minworkbuddy_test` 由夹具自建），所有命令在 `backend/` 目录用仓库 venv 执行：`.\.venv\Scripts\python.exe -m pytest ...`。
- 结果缓存键**必须包含角色签名**（`(tenant_id, query_id, param_hash, role_sig)`）。这是安全不变量：漏掉角色会让豁免用户的未脱敏结果命中到非豁免用户。

## 前置发现（影响任务设计，已实测）

1. **seed 的三条 demo 本体没有物理映射**：`alembic/versions/2026_11_01_0009_seed_demo_ontologies.py` 只写 `meta_object_standard` / `meta_object_relation` / `onto_ontology_build_item` / `onto_ontology_version`，**没有** `meta_table_standard` / `meta_column_standard` 插入。因此直连编译在第 3 步（物理绑定解析）必然失败——Task 0 不是可选项。
2. **参数占位符会被方言改写**：`sqlglot ... .sql(dialect='postgres')` 把 `:p_1` 渲染成 `%(p_1)s`，而 SQLAlchemy `text()` 只认 `:p_1`。实测 `SqlGuard.is_readonly` 对两种写法均返回 `True`。结论：按方言渲染后**归一回 `:name`** 再存 `compiled_sql`（Task 3 固化该纯函数与往返测试）。
3. **脱敏入口吃 dict、取数口吐 list**：`apply_masking(rows: List[Dict], masking: MaskingConfig, user)`（`masking.py:97`）要求行是字典，而 `ReadonlyQueryService.run` 返回 `rows: [list]`。孪生取数出口必须先 `zip(columns, row)` 成 records、脱敏后按**字典行**返回前端（Task 7 定死该契约）。
4. **router 是声明式清单**：新 router 加到 `app/core/router_registry.py` 的 `ROUTER_SPECs`（`:89-217`），不改 `main.py`；本体子 router 由 `app/routers/dataops/dataops.py:1353-1355` 以 `router.include_router(ontology_router)` 挂载，故 Q1–Q5 的实际前缀是 `/api/v1/dataops/...`。
5. **两个列名陷阱（探测与夹具均踩过）**：`sys_tenant` 的主键列叫 `tenant_id`（**不是** `id`）；Fernet 加密入口在 `app/ai/dataops/crypto.py` 的 `encrypt_secret`（**不存在** `app/core/crypto.py`）。

## File Structure（Plan 1 全量）

```
backend/app/models/ontology/query.py            🆕 MetaOntologyQuery（onto_ontology_query）
backend/app/models/twin/__init__.py             🆕 导出 6 个 Twin* 模型（供 create_all 注册）
backend/app/models/twin/card.py                 🆕 TwinCard, TwinPage
backend/app/models/twin/widget.py               🆕 TwinWidget
backend/app/models/twin/publish.py              🆕 TwinPublish, TwinCardShare
backend/app/models/twin/access.py               🆕 TwinAccessRequest
backend/app/core/cache.py                       🆕 TTLCache（自 audit_logger 私有 _TTLCache 上提）
backend/app/services/ontology/ontology_query_service.py  🆕 编译 7 步 + preview
backend/app/services/twin/__init__.py           🆕
backend/app/services/twin/twin_service.py       🆕 卡片/页面/组件 CRUD + 布局 + 形状配对校验
backend/app/services/twin/twin_data_service.py  🆕 批量取数 + 闸门 + 缓存 + 出口脱敏 + 四态
backend/app/services/twin/twin_publish_service.py 🆕 发布登记 + 只读页取数鉴权
backend/app/services/twin/twin_access_service.py  🆕 申请/审批/共享
backend/app/routers/twin/__init__.py            🆕
backend/app/routers/twin/twin.py                🆕 /api/v1/twins/* 与 /api/v1/twin-p/*
backend/app/routers/ontology/ontology.py        ✏️ 追加 Q1–Q5 端点
backend/app/services/dataops/query_service.py   ✏️ run() 增加 params 形参（默认 None，行为不变）
backend/app/services/dataops/sql_placeholder.py 🆕 normalize_placeholders() 纯函数
backend/app/services/ontology/ontology_publish_service.py ✏️ 抽出 _sensitive_covered()
backend/app/middleware/audit_logger.py          ✏️ 改用 app.core.cache.TTLCache
backend/app/core/api_error.py                   ✏️ 追加 QUERY_*/TWIN_* 错误码
backend/alembic/versions/2026_11_01_0012_seed_twin_demo_mapping.py 🆕（Task 0b，探测结论要求）
backend/alembic/versions/2026_11_01_0013_add_twin_tables.py 🆕（Task 1，down_revision 接 0012）
backend/scripts/twin_mapping_probe.py           🆕 映射覆盖率探测
backend/tests/twin/conftest.py                  🆕 仿 tests/ontology/conftest.py
backend/tests/twin/test_*.py                    🆕
docs/sql/init.sql · docs/sql/menu_knowledge_governance.sql ✏️ sys_menu 2407 行（原定 2406 已被占用）
docs/superpowers/specs/2026-10-31-ontology-capability-design.md   ✏️ 规格关账 4 处（Task 11）
docs/superpowers/specs/2026-11-01-simulation-sandbox-design.md    ✏️ 规格关账 1 处（Task 11）
docs/superpowers/specs/2026-10-31-minworkbuddy-ontology-capability-design.md ✏️ 旧草案标记（Task 11）
```

---

### Task 0: 映射覆盖率探测（决策闸，决定 P0 演示口径）

**Files:**
- Create: `backend/scripts/twin_mapping_probe.py`
- Create: `backend/tests/twin/test_mapping_probe.py`

**Interfaces:**
- Consumes: 库表 `onto_ontology`、`onto_ontology_version`、`meta_object_standard`、`meta_table_standard`、`meta_column_standard`
- Produces: `probe(tenant_id: int) -> list[dict]`，每项 `{ontology_code, version, objects, mapped_objects, mapping_rate, sensitive_columns, covered_columns}`；以及结论文档行（写入 spec §8.3 U1）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/twin/test_mapping_probe.py`：

```python
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
```

- [ ] **Step 2: 跑到失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/twin/test_mapping_probe.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.twin_mapping_probe'`

- [ ] **Step 3: 写探测脚本**

创建 `backend/scripts/twin_mapping_probe.py`：

```python
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
```

- [ ] **Step 4: 跑到通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/twin/test_mapping_probe.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 在开发库上跑一次真实探测并记录结论**

Run: `cd backend; .\.venv\Scripts\python.exe scripts/twin_mapping_probe.py`
Expected: 输出每个租户每本体的 `mapping_rate`（`python -m scripts.twin_mapping_probe` 等价）。

**实测结论（2026-11-01 开发库，已写回 spec §8.3 U1）**：14 条 `(租户, 本体, 版本)` 组合的
`mapping_rate` **全部 0.0**；`objects` 为 10（supply_chain）或 3（sales），`attributes` 恒为 0。
经直查确认这不是探测口径遗漏：`meta_object_standard_attribute` 库内共 368 行 accepted，
但均属非 demo 本体；sales_ontology v3 快照的 `properties` 确为空数组——根因是 0009 的
快照硬编码 `"properties": []` / `"mappings": {"table": [], "column": []}`。
→ P0 演示口径确定走 **Task 0b**（新增 `2026_11_01_0012_seed_twin_demo_mapping.py`），
补齐物理表、表/列绑定、模式层属性与重发布版本，仅针对 `sales_ontology`。

- [ ] **Step 6: 提交**

```bash
git add backend/scripts/twin_mapping_probe.py backend/tests/twin/test_mapping_probe.py docs/superpowers/specs/2026-11-01-digital-twin-app-design.md
git commit -m "feat(twin): add ontology mapping-coverage probe for P0 demo gate"
```

---

### Task 0b: demo 物理映射 seed（Alembic `0012_seed_twin_demo_mapping`）

**存因**：Task 0 实测 14 条 `(租户, 本体, 版本)` 组合的 `mapping_rate` 全为 0.0，
且已发布快照的 `properties` 恒为空（根因在 0009 硬编码 `"properties": []`）——
P0 演示链路的编译第 3 步（物理绑定解析）必然 `QUERY_MAPPING_MISSING`。
本任务补齐最小可演示闭环，否则 Task 4/7 的端点在真实环境只能空跑。

**代价（已得到用户确认）**：生产库升级也会多出 `twin_demo` schema、三张假业务表
与一份重发布版本。缓解：全部行带稳定标记（数据源 `name`、版本 `change_note`、
标准项 `t_a_` 前缀），downgrade 可完整清除。

**Files:**
- Create: `backend/alembic/versions/2026_11_01_0012_seed_twin_demo_mapping.py`

**Interfaces:**
- Consumes: 0009 seed 的 `meta_object_standard`（`sales_obj_customer` / `sales_obj_order` / `sales_obj_product`，均 accepted）、`meta_object_relation`（`sales_rel_order_of_customer`）、`onto_ontology_version` 的 `current_version` 快照
- Produces: 一个 `meta_data_source(name='twin-demo')`、`meta_table(database='twin_demo')` 三行、10 个 `t_a_*` 标准项、11 条 accepted 属性引用、3 条表绑定 + 11 条列绑定、`sales_ontology` 的 `current_version + 1` 版本快照（`properties` / `mappings` 非空）。Task 4 编译第 3 步与 Task 7 取数在演示环境据此可跑通

- [ ] **Step 1: 写迁移（六层顺序固定）**

常量规格即设计本体（实现已落地于 `backend/alembic/versions/2026_11_01_0012_seed_twin_demo_mapping.py`，
后续修改以该文件为准；下面的值必须逐字一致，探测与验证都依赖它们）：

```python
_MARK = "twin-demo-mapping"          # 同时作为数据源 name 与版本 change_note
_ONTOLOGY_CODE = "sales_ontology"
_SCHEMA = "twin_demo"

# 标准项：(code, name, security_level, mask_rule)——mask_rule 非空即视为脱敏已覆盖
# （发布门禁 5 与编译敏感闸同一口径，只看真假值、不解析字符串）
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

# 物理表：表名 → (DDL, [(列名, 标准 code, pii_level, data_type), ...], [样例行])
#   demo_customer(customer_code PK, customer_name, customer_phone, customer_region)  2 行
#   demo_order   (order_code PK, customer_code, order_amount numeric(14,2), order_date date)  2 行
#   demo_product (product_code PK, product_name, unit_price numeric(12,2))  2 行
#   样例行含 11 位手机号，用于演示出口脱敏

# 对象 code → 表名（三张表分别绑三个 accepted 对象）
_OBJECT_TABLE = {"sales_obj_customer": "demo_customer",
                 "sales_obj_order": "demo_order",
                 "sales_obj_product": "demo_product"}

# 对象 → 属性（4 + 4 + 3 = 11 条；t_a_customer_code 复用给订单的 customer_code，即 JOIN 键）
_OBJECT_ATTRS = {"sales_obj_customer": ["t_a_customer_code", "t_a_customer_name",
                                        "t_a_customer_phone", "t_a_region"],
                 "sales_obj_order": ["t_a_order_code", "t_a_customer_code",
                                     "t_a_order_amount", "t_a_order_date"],
                 "sales_obj_product": ["t_a_product_code", "t_a_product_name",
                                       "t_a_product_price"]}

# 关系 → 连接键（0009 把 via_attribute_ids 留空，缺键则跨对象 JOIN 无法生成）
_RELATION_VIA = {"sales_rel_order_of_customer": "t_a_customer_code"}
```

六个写入函数与必须对齐的列名（逐字段形状以 `ontology_publish_service.build_snapshot:175-206` 为真源）：

```python
_create_physical(bind)      # CREATE SCHEMA IF NOT EXISTS + 三表 + 样例行（ON CONFLICT DO NOTHING）
_insert_source(bind, tid)   # meta_data_source：host/port/username/database 取 DB_* 环境变量
                            # （与 alembic/env.py:30-34 同源，不硬编码凭据），
                            # password_enc = encrypt_secret(os.getenv("DB_PASSWORD", ""))
                            # ——入口在 app/ai/dataops/crypto.py，不是 app/core/crypto.py
_insert_assets(bind, tid, dsid)
    # meta_table (tenant_id, source_id, db_name, database, table_name, table_type, column_count)
    #   database = 物理 schema 名 'twin_demo'；db_name = 物理库名（两个列必须分开写）
    # meta_column (tenant_id, table_id, column_name, ordinal, data_type, pii_level)
_insert_standards(bind, tid)  # meta_standard (…, status='published', security_level, mask_rule, review_status='accepted')
_object_ids(bind, tid)        # 任一 sales_obj_* 不存在 → 返回 None → 整租户跳过（幂等安全）
_insert_attributes(bind, tid, obj_ids, std_ids)
    # meta_object_standard_attribute (tenant_id, object_id, standard_id, required, sort_order, review_status)
    # 返回快照行：{"id", "object_id", "standard_id", "required", "review_status"}
_insert_mappings(bind, tid, …)
    # meta_table_standard (tenant_id, table_id, object_standard_id, status='accepted', source='human')
    #   写入列名是 object_standard_id（不是 object_id）；唯一约束只在 table_id 上
    # meta_column_standard (tenant_id, column_id, standard_id, status='accepted', source='human')
    # 返回两行列表：table → {"id","table_id","object_standard_id","source"}
    #           column → {"id","column_id","standard_id","source"}
_fill_relation_keys(bind, tid, std_ids)  # UPDATE meta_object_relation SET via_attribute_ids = CAST(:v AS jsonb)
_republish_snapshot(bind, tid, props, table_rows, column_rows)
    # 读 current_version 快照 → dict(base) 只补 properties/mappings → 插 version+1 行
    # → UPDATE onto_ontology SET current_version = version+1
    # **绝不 UPDATE 历史快照的 snapshot_json**（Task 8 的发布不可变语义依赖它）
    # 插入必用 CAST(:snap AS jsonb)（PG JSONB，无 server_default 兼容写法）
```

upgrade 逐 `sys_tenant`（主键列是 `tenant_id`，不是 `id`），先查 `_existing()` 再写；
只有「无标记数据源且已有 demo 对象行」的租户才写入。downgrade 必须按外键逆序：
版本行→回退 `current_version`（`COALESCE(max(version),0)`）→ `via_attribute_ids` 置 NULL
→ `meta_column_standard` → `meta_table_standard` → `meta_object_standard_attribute`
→ `meta_standard`（被属性引用 RESTRICT，必须后删）→ `meta_column` → `meta_table`
→ `meta_data_source` → `DROP SCHEMA twin_demo CASCADE`。

- [ ] **Step 2: 应用迁移**

Run: `cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head`
Expected: 输出含 `Running upgrade 2026_11_01_0011_add_sandbox_tables -> 2026_11_01_0012_seed_twin_demo_mapping`，无 Traceback。
前置条件：`DATAOPS_ENCRYPTION_KEY` 已配置（未配置时 `encrypt_secret` 直接抛 RuntimeError，绝不降级为明文存储）。

- [ ] **Step 3: 探测复跑（本任务的硬门闸）**

Run: `cd backend; .\.venv\Scripts\python.exe scripts/twin_mapping_probe.py --tenant 1`
Expected（实测值，必须逐字对上）：

```
sales_ontology  v3  obj 3/3   attr 0/0    rate 1.0
sales_ontology  v4  obj 3/3   attr 11/11  rate 1.0     ← current_version，演示口径
supply_chain_ontology v1 obj 0/10 attr 0/0 rate 0.0    ← P0 范围外，有意保持
```

注意：`v3` 的 rate 会从 0.0 变 1.0——因为表绑定按 `object_standard_id` 判、不分版本，
而 v3 快照 `properties` 为空（分母 0）。**判读只看 `current_version` 那一行**。

- [ ] **Step 4: 回滚往返与残留核查**

Run: `\.venv\Scripts\python.exe -m alembic downgrade -1` 后 `alembic current`
Expected: 回到 `2026_11_01_0011_add_sandbox_tables`；残留十项均为空（实测）：
`onto_ontology_version WHERE change_note='twin-demo-mapping'`=0、`current_version`=3、
`t_a_*` 标准项=0、`name='twin-demo'` 数据源=0、schema `twin_demo`=0、
`meta_table WHERE database='twin_demo'`=0、列/表绑定=0、属性引用=0、`via_attribute_ids IS NULL`=true。
再 `alembic upgrade head`：七租户各重建一份 v4（`change_note` 行=7），样例行可查（`SELECT count(*) FROM twin_demo.demo_order`=2）。

失败排查序：1）`A value is required for bind parameter` → 某 `bind.execute(text(...))` 漏传参数字典
（本次实跑就在 downgrade 这里失败过一次）；2）`duplicate key value violates uq_meta_table_standard_table`
→ `_existing()` 判定被绕过（同一租户跑了第二遍 seed）；3）`invalid key: not a Fernet token`
→ 拿错了 `DATAOPS_ENCRYPTION_KEY`；4）探测 `attr 13/13` 而不是 `11/11` → 探测 SQL 退回了 `LEFT JOIN`。

- [ ] **Step 5: 提交**

```bash
git add backend/alembic/versions/2026_11_01_0012_seed_twin_demo_mapping.py
git commit -m "feat(twin): seed demo physical mapping so sales ontology is queryable"
```

---

### Task 1: 数据模型 7 张表 + Alembic 迁移 + 测试夹具

**Files:**
- Create: `backend/app/models/ontology/query.py`
- Create: `backend/app/models/twin/__init__.py`、`card.py`、`widget.py`、`publish.py`、`access.py`
- Create: `backend/alembic/versions/2026_11_01_0013_add_twin_tables.py`
- Create: `backend/tests/twin/conftest.py`
- Test: `backend/tests/twin/test_models_twin.py`

**Interfaces:**
- Consumes: `app.db.database.Base`、`app.models.tenant_mixin.TenantMixin`、`onto_ontology.id`、`onto_ontology_query.id`
- Produces: 模型类 `MetaOntologyQuery`、`TwinCard`、`TwinPage`、`TwinWidget`、`TwinPublish`、`TwinCardShare`、`TwinAccessRequest`（表名 `onto_ontology_query`、`twin_card`、`twin_page`、`twin_widget`、`twin_publish`、`twin_card_share`、`twin_access_request`）；夹具 `db`、`client_a`、`client_b`、`TENANT_A`、`TENANT_B`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/twin/test_models_twin.py`：

```python
"""7 张新表可建、约束生效、默认值符合 spec §3。"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.ontology.query import MetaOntologyQuery
from app.models.twin import TwinAccessRequest, TwinCard, TwinCardShare, TwinPage, TwinPublish, TwinWidget
from tests.twin.conftest import TENANT_A


def test_tablenames_match_spec():
    assert MetaOntologyQuery.__tablename__ == "onto_ontology_query"
    assert {TwinCard.__tablename__, TwinPage.__tablename__, TwinWidget.__tablename__,
            TwinPublish.__tablename__, TwinCardShare.__tablename__,
            TwinAccessRequest.__tablename__} == {
        "twin_card", "twin_page", "twin_widget", "twin_publish", "twin_card_share", "twin_access_request"}


def test_query_draft_version_forces_disabled(db, ontology_factory):
    """spec §3.1：version=0 的草稿态必须 status=disabled（与 onto_ontology_publish 同律）。"""
    q = MetaOntologyQuery(tenant_id=TENANT_A, ontology_id=ontology_factory(), version=0,
                          code="q1", name="草稿查询", result_shape="kpi", spec_json={},
                          status="disabled")
    db.add(q)
    db.commit()
    assert q.status == "disabled"


def test_query_code_unique_per_version(db, ontology_factory):
    """uq_onto_query_code：同 (tenant, ontology, version) 下 code 唯一。"""
    oid = ontology_factory()
    db.add(MetaOntologyQuery(tenant_id=TENANT_A, ontology_id=oid, version=1, code="dup",
                             name="n", result_shape="kpi", spec_json={}, status="enabled"))
    db.commit()
    with pytest.raises(IntegrityError):
        db.add(MetaOntologyQuery(tenant_id=TENANT_A, ontology_id=oid, version=1, code="dup",
                                 name="n2", result_shape="kpi", spec_json={}, status="enabled"))
        db.commit()


def test_query_code_unique_across_version(db, ontology_factory):
    """版本维在唯一键里：同 code 换版本不冲突（重发布后查询逐版本留痕）。"""
    oid = ontology_factory()
    for ver in (1, 2):
        db.add(MetaOntologyQuery(tenant_id=TENANT_A, ontology_id=oid, version=ver, code="same",
                                 name="n", result_shape="kpi", spec_json={}, status="enabled"))
    db.commit()
    assert db.query(MetaOntologyQuery).filter_by(ontology_id=oid, code="same").count() == 2


def test_widget_shape_check_rejects_unknown_result_shape(db, ontology_factory):
    """CHECK 约束：result_shape 取值域固定。"""
    from sqlalchemy.exc import DatabaseError
    db.add(MetaOntologyQuery(tenant_id=TENANT_A, ontology_id=ontology_factory(), version=1,
                             code="bad", name="n", result_shape="pie", spec_json={}, status="enabled"))
    with pytest.raises((DatabaseError, IntegrityError)):
        db.commit()
```

- [ ] **Step 2: 创建 `backend/tests/twin/conftest.py`**

以 `backend/tests/ontology/conftest.py` 为模板复制（**逐行照抄** `_test_db_url`/`IS_POSTGRES`/`_ENGINES`/`dispose_all_engines`/`_encryption_key`/`_test_database`/`schema_name`/`db_target`/`engine`/`db`/`_fake_user`/`build_client`/`client_a`/`client_b`），并做三处改动：

```python
# 改动 1：_tables() 里的 import 清单在 ontology 版基础上追加孪生模型（import 即注册元数据）
    import app.models.ontology.asset_tag  # noqa: F401
    import app.models.ontology.ontology  # noqa: F401
    import app.models.ontology.query  # noqa: F401  ← 新增
    import app.models.twin  # noqa: F401            ← 新增（包 __init__ 已 import 六个模型）

# 改动 2：build_client() 默认只挂 dataops 父 router（含本体子 router）；孪生 router 到
# Task 6 才创立，所以用 with_twin 开关 + 函数内延迟 import。Task 1 的用例不请求 twin 端点，
# 开关恒为 False，不会触发 import，因此无需额外的就绪标志位。
def build_client(db: Session, tenant_id: Optional[int], *, with_twin: bool = False) -> TestClient:
    from app.routers.dataops.dataops import router as dataops_router

    app = FastAPI()
    app.include_router(dataops_router)
    if with_twin:
        from app.routers.twin.twin import router as twin_router
        app.include_router(twin_router)

    from app.core.api_error import register_api_error_handler
    register_api_error_handler(app)

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: _fake_user(tenant_id)
    return TestClient(app)


@pytest.fixture
def twin_client_a(db: Session) -> TestClient:
    """带 /api/v1/twins/* 与 /twin-p/* 的客户端（Task 6 起使用）。"""
    return build_client(db, TENANT_A, with_twin=True)


@pytest.fixture
def twin_client_b(db: Session) -> TestClient:
    return build_client(db, TENANT_B, with_twin=True)

# 改动 3：追加本体工厂夹具（Task 1 测试与后续编译测试共用）
@pytest.fixture
def ontology_factory(db: Session):
    """创建一个 current_version=1 的本体，返回其 id。"""
    from sqlalchemy import text

    def _make() -> int:
        oid = db.execute(
            text("INSERT INTO onto_ontology (tenant_id, code, name, status, current_version) "
                 "VALUES (:t, gen_random_uuid()::text, '演示本体', 'published', 1) "
                 "RETURNING id"),
            {"t": TENANT_A},
        ).scalar_one()
        db.commit()
        return int(oid)

    return _make
```

**改动 4：同步修 `backend/tests/ontology/conftest.py::_tables()`（与 Step 2 同批提交）**

该函数返回 `Base.metadata.sorted_tables`（只看已 import 的模型），新表不 import 就不会建。
所以在 `tests/ontology/conftest.py:68` 的 `import app.models.ontology.ontology` 之后追加两行：

```python
    import app.models.ontology.query  # noqa: F401  ← 新增：onto_ontology_query
    import app.models.twin  # noqa: F401            ← 新增：twin_* 六表（Task 4 的 bound_widget 需要）
```

> 不改这里，Task 4 的 `bound_widget` 夹具会 `relation "twin_card" does not exist`。

- [ ] **Step 3: 跑到失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/twin/test_models_twin.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.twin'`

- [ ] **Step 4: 写 `backend/app/models/ontology/query.py`**

```python
"""本体查询定义（onto_ontology_query）：跨端复用的一等公民查询，spec 孪生方案 §3.1。

决策 T2：查询定义属语义层，落 onto_ 域而非 twin_ 域，使探索/智能体/孪生共用同一条查询。
约束沿用现状：TenantMixin 租户隔离、状态用 String + comment、显式 CHECK/UQ/Index。
"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, ForeignKey, Index, Integer,
    String, Text, TIMESTAMP, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin

_RESULT_SHAPES = ("kpi", "trend", "bar", "donut", "table", "entity_set", "graph")


class MetaOntologyQuery(Base, TenantMixin):
    """已保存的本体查询（编译产物钉版本，不存数据）。"""

    __tablename__ = "onto_ontology_query"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger, ForeignKey("onto_ontology.id", ondelete="CASCADE"), nullable=False, comment="所属本体",
    )
    version = Column(Integer, nullable=False, server_default="0", comment="钉住的发布版本；0=草稿，禁止编译")
    code = Column(String(64), nullable=False, comment="本体+版本内唯一")
    name = Column(String(200), nullable=False, comment="查询名称")
    description = Column(Text, nullable=True, comment="说明")
    result_shape = Column(
        String(16), nullable=False,
        comment="结果形状: kpi|trend|bar|donut|table|entity_set|graph ← 组件配对契约",
    )
    spec_json = Column(JSONB, nullable=False, comment="声明式查询: {objects[], attributes[], agg, group_by[], filters[], time_window, limit}；attributes 为标准项 code")
    params_json = Column(JSONB, nullable=True, comment="参数声明: [{name,type,default,control}]；编译期追写生成占位符 [{name,type,source:'compiled'}]")
    compiled_sql = Column(Text, nullable=True, comment="编译产物：无注释单语句模板，含 :p_xxx 占位符")
    sql_sha256 = Column(String(64), nullable=True, comment="编译产物摘要（锚点沿用 meta_data_write_request 做法）")
    source_id = Column(BigInteger, nullable=True, comment="编译期确定的直连数据源（meta_data_source.id）；运行期不再重复解析快照")
    mask_rules_json = Column(JSONB, nullable=True, comment="出口脱敏配置，直接可 MaskingConfig.model_validate：{enabled, rules:[{field,strategy,keep_prefix,keep_suffix,exempt_roles}]}")
    verify_status = Column(String(16), nullable=False, server_default="pending", comment="pending|verified|failed")
    verify_detail_json = Column(JSONB, nullable=True, comment="{columns[], row_count, elapsed_ms, blocked_columns[]}")
    status = Column(String(16), nullable=False, server_default="disabled", comment="enabled|disabled")
    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "ontology_id", "version", "code", name="uq_onto_query_code"),
        CheckConstraint(
            "result_shape IN ('kpi','trend','bar','donut','table','entity_set','graph')",
            name="ck_onto_query_shape",
        ),
        CheckConstraint("status IN ('enabled','disabled')", name="ck_onto_query_status"),
        CheckConstraint("verify_status IN ('pending','verified','failed')", name="ck_onto_query_verify"),
        Index("idx_onto_query_ontology", "ontology_id", "version", "status"),
    )
```

- [ ] **Step 5: 写孪生模型 4 个文件 + `__init__.py`**

`backend/app/models/twin/card.py`：

```python
"""孪生卡片与页面（spec §3.2 / §3.3）。卡片钉「本体+版本」，页面持有刷新策略。"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, ForeignKey, Index, Integer,
    String, Text, TIMESTAMP, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class TwinCard(Base, TenantMixin):
    """孪生卡片：一个孪生应用的顶层容器。"""

    __tablename__ = "twin_card"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name = Column(String(200), nullable=False, comment="卡片名")
    icon = Column(String(32), nullable=True, comment="图标字符")
    description = Column(Text, nullable=True, comment="说明")
    source_template_key = Column(String(64), nullable=True, comment="模板中心来源，可空")
    ontology_id = Column(BigInteger, ForeignKey("onto_ontology.id", ondelete="CASCADE"), nullable=False, comment="钉住的本体")
    ontology_version = Column(Integer, nullable=False, server_default="0", comment="钉住的版本；0=未发布本体")
    scene_key = Column(String(64), nullable=True, comment="等距视觉场景模板 key（非沙盘 onto_sandbox_scene）")
    scene_config_json = Column(JSONB, nullable=True, comment="P1 场景编辑器写入")
    runtime_state = Column(String(16), nullable=False, server_default="draft", comment="draft|live|paused")
    owner_id = Column(BigInteger, nullable=False, comment="归属用户")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "owner_id", "name", name="uq_twin_card_name"),
        CheckConstraint("runtime_state IN ('draft','live','paused')", name="ck_twin_card_state"),
        Index("idx_twin_card_owner", "tenant_id", "owner_id", "runtime_state"),
    )


class TwinPage(Base, TenantMixin):
    """卡片内的页面（对应原型顶部页面 Tab）。"""

    __tablename__ = "twin_page"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    card_id = Column(BigInteger, ForeignKey("twin_card.id", ondelete="CASCADE"), nullable=False, comment="所属卡片")
    name = Column(String(200), nullable=False, comment="页面名")
    sort_order = Column(Integer, nullable=False, server_default="0", comment="Tab 顺序")
    refresh_json = Column(JSONB, nullable=True, comment="{mode: interval|manual|off, interval_seconds: 10|30|0}")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("card_id", "name", name="uq_twin_page_name"),
        Index("idx_twin_page_card", "card_id", "sort_order"),
    )
```

`backend/app/models/twin/widget.py`：

```python
"""画布组件实例（spec §3.4）。query_id 用 SET NULL：删定义不打碎画面，打回「待绑定」空态。"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, ForeignKey, Index, Integer,
    String, TIMESTAMP, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin

WIDGET_KEYS = ("kpi", "trend", "bar", "donut", "alert_table", "graph", "scene2d", "scene3d")


class TwinWidget(Base, TenantMixin):
    __tablename__ = "twin_widget"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    page_id = Column(BigInteger, ForeignKey("twin_page.id", ondelete="CASCADE"), nullable=False, comment="所属页面")
    widget_key = Column(String(32), nullable=False, comment="模块类型（palette 项），非实例")
    title = Column(String(200), nullable=False, comment="组件标题")
    query_id = Column(
        BigInteger, ForeignKey("onto_ontology_query.id", ondelete="SET NULL"), nullable=True,
        comment="绑定的本体查询；NULL = 原型「待绑定」空态",
    )
    param_values_json = Column(JSONB, nullable=True, comment="参数实值 {name: value}")
    display_json = Column(JSONB, nullable=True, comment="{series_map, thresholds, columns, span}")
    grid_json = Column(JSONB, nullable=False, server_default='{"x":0,"y":0,"w":6,"h":4}', comment="12 列栅格位")
    refresh_json = Column(JSONB, nullable=True, comment="覆盖页面级刷新")
    sort_order = Column(Integer, nullable=False, server_default="0", comment="同 (y) 内次序")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        CheckConstraint(
            "widget_key IN ('kpi','trend','bar','donut','alert_table','graph','scene2d','scene3d')",
            name="ck_twin_widget_key",
        ),
        Index("idx_twin_widget_page", "page_id", "sort_order"),
        Index("idx_twin_widget_query", "query_id"),
    )
```

`backend/app/models/twin/publish.py`：

```python
"""发布登记与卡片共享（spec §3.5 / §3.6）。

与 onto_ontology_publish 刻意分离：那张登记「本体→对外契约(skill|http|mcp)」，
本表登记「孪生页→只读路由」，混用会逼 ck_onto_publish_target 加 page 值并污染语义。
"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, ForeignKey, Index, Integer,
    String, TIMESTAMP, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class TwinPublish(Base, TenantMixin):
    """页面发布为独立只读页。"""

    __tablename__ = "twin_publish"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    card_id = Column(BigInteger, ForeignKey("twin_card.id", ondelete="CASCADE"), nullable=False, comment="卡片")
    page_id = Column(BigInteger, ForeignKey("twin_page.id", ondelete="CASCADE"), nullable=False, comment="页面")
    slug = Column(String(32), nullable=False, comment="随机不可猜串（禁止用自增 id 派生，防枚举）")
    access = Column(String(16), nullable=False, server_default="org", comment="org|role（public 留 P1）")
    role_codes_json = Column(JSONB, nullable=True, comment="access=role 时生效的角色码数组")
    snapshot_json = Column(JSONB, nullable=True, comment="发布时冻结的页面+组件配置")
    version = Column(Integer, nullable=False, server_default="1", comment="发布版本号，重复发布 +1")
    status = Column(String(16), nullable=False, server_default="enabled", comment="enabled|disabled")
    published_by = Column(BigInteger, nullable=False, comment="发布人")
    published_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="发布时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_twin_publish_slug"),
        CheckConstraint("access IN ('org','role')", name="ck_twin_publish_access"),
        CheckConstraint("status IN ('enabled','disabled')", name="ck_twin_publish_status"),
        Index("idx_twin_publish_page", "page_id", "status"),
    )


class TwinCardShare(Base, TenantMixin):
    """卡片可见性授予（驱动原型「共享给我的（只读）」）。"""

    __tablename__ = "twin_card_share"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    card_id = Column(BigInteger, ForeignKey("twin_card.id", ondelete="CASCADE"), nullable=False, comment="卡片")
    grantee_type = Column(String(16), nullable=False, comment="user|role")
    grantee_id = Column(BigInteger, nullable=True, comment="grantee_type=user 时的用户 id")
    grantee_code = Column(String(64), nullable=True, comment="grantee_type=role 时的角色码")
    perm = Column(String(16), nullable=False, server_default="read", comment="read|edit")
    source = Column(String(16), nullable=False, server_default="manual", comment="manual|request")
    expires_at = Column(TIMESTAMP, nullable=True, comment="过期时间；NULL=长期")
    granted_by = Column(BigInteger, nullable=False, comment="授予人")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        CheckConstraint("grantee_type IN ('user','role')", name="ck_twin_share_type"),
        CheckConstraint("perm IN ('read','edit')", name="ck_twin_share_perm"),
        CheckConstraint("source IN ('manual','request')", name="ck_twin_share_source"),
        Index("idx_twin_share_card", "card_id", "grantee_type"),
    )
```

`backend/app/models/twin/access.py`：

```python
"""权限申请单（spec §3.7）。形态取自 meta_data_write_request 的申请/审批/过期三段。

与写请求单的差异：批准产物是写入 twin_card_share，**不发一次性令牌**。
"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, ForeignKey, Index, String,
    Text, TIMESTAMP, func, text,
)

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class TwinAccessRequest(Base, TenantMixin):
    __tablename__ = "twin_access_request"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    card_id = Column(BigInteger, ForeignKey("twin_card.id", ondelete="CASCADE"), nullable=False, comment="目标卡片")
    applicant_id = Column(BigInteger, nullable=False, comment="申请人")
    reason = Column(Text, nullable=True, comment="申请理由")
    required_role_code = Column(String(64), nullable=True, comment="卡片声明的所需角色（原型「安防管理员」）")
    status = Column(String(16), nullable=False, server_default="pending", comment="pending|approved|rejected|expired")
    approver_id = Column(BigInteger, nullable=True, comment="审批人")
    reviewed_at = Column(TIMESTAMP, nullable=True, comment="审批时刻")
    expires_at = Column(TIMESTAMP, nullable=True, comment="审批通过后的授予有效期")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        CheckConstraint("status IN ('pending','approved','rejected','expired')", name="ck_twin_access_status"),
        # 每人每卡只允许**一张在途**申请：用部分唯一索引（WHERE status='pending'）。
        # 若把 status 也放进整列唯一约束，同一人对同一卡的「历史 rejected + 新的 pending」
        # 或「续期后的第二条 approved」都会撞键，Task 9 的续期路径直接报 IntegrityError。
        Index("uq_twin_access_pending", "tenant_id", "card_id", "applicant_id",
              unique=True, postgresql_where=text("status = 'pending'")),
        Index("idx_twin_access_card", "card_id", "status"),
    )
```

`backend/app/models/twin/__init__.py`：

```python
"""孪生域模型（import 即注册到 Base.metadata，供 create_all 与迁移使用）。"""
from app.models.twin.access import TwinAccessRequest  # noqa: F401
from app.models.twin.card import TwinCard, TwinPage  # noqa: F401
from app.models.twin.publish import TwinCardShare, TwinPublish  # noqa: F401
from app.models.twin.widget import WIDGET_KEYS, TwinWidget  # noqa: F401

__all__ = [
    "TwinAccessRequest", "TwinCard", "TwinCardShare", "TwinPage",
    "TwinPublish", "TwinWidget", "WIDGET_KEYS",
]
```

- [ ] **Step 6: 写 Alembic 迁移**

创建 `backend/alembic/versions/2026_11_01_0013_add_twin_tables.py`。结构照抄同目录 `2026_11_01_0011_add_sandbox_tables.py`（同一 `sa.Column` 风格 + `_AUDIT_TS` 常量用法）：

```python
"""add twin tables

Revision ID: 2026_11_01_0013_add_twin_tables
Revises: 2026_11_01_0012_seed_twin_demo_mapping
Create Date: 2026-11-01 00:13:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2026_11_01_0013_add_twin_tables"
down_revision: Union[str, None] = "2026_11_01_0012_seed_twin_demo_mapping"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AUDIT_TS = [
    sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("now()")),
]


def upgrade() -> None:
    op.create_table(
        "onto_ontology_query",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("ontology_id", sa.BigInteger(), sa.ForeignKey("onto_ontology.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("result_shape", sa.String(16), nullable=False),
        sa.Column("spec_json", postgresql.JSONB(), nullable=False),
        sa.Column("params_json", postgresql.JSONB(), nullable=True),
        sa.Column("compiled_sql", sa.Text(), nullable=True),
        sa.Column("sql_sha256", sa.String(64), nullable=True),
        sa.Column("source_id", sa.BigInteger(), nullable=True),
        sa.Column("mask_rules_json", postgresql.JSONB(), nullable=True),
        sa.Column("verify_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("verify_detail_json", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="disabled"),
        sa.Column("creator_id", sa.BigInteger(), nullable=True),
        *_AUDIT_TS,
        sa.UniqueConstraint("tenant_id", "ontology_id", "version", "code", name="uq_onto_query_code"),
        sa.CheckConstraint("result_shape IN ('kpi','trend','bar','donut','table','entity_set','graph')", name="ck_onto_query_shape"),
        sa.CheckConstraint("status IN ('enabled','disabled')", name="ck_onto_query_status"),
        sa.CheckConstraint("verify_status IN ('pending','verified','failed')", name="ck_onto_query_verify"),
    )
    op.create_index("idx_onto_query_ontology", "onto_ontology_query", ["ontology_id", "version", "status"])

    op.create_table(
        "twin_card",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("icon", sa.String(32), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_template_key", sa.String(64), nullable=True),
        sa.Column("ontology_id", sa.BigInteger(), sa.ForeignKey("onto_ontology.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ontology_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scene_key", sa.String(64), nullable=True),
        sa.Column("scene_config_json", postgresql.JSONB(), nullable=True),
        sa.Column("runtime_state", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        *_AUDIT_TS,
        sa.UniqueConstraint("tenant_id", "owner_id", "name", name="uq_twin_card_name"),
        sa.CheckConstraint("runtime_state IN ('draft','live','paused')", name="ck_twin_card_state"),
    )
    op.create_index("idx_twin_card_owner", "twin_card", ["tenant_id", "owner_id", "runtime_state"])

    op.create_table(
        "twin_page",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("card_id", sa.BigInteger(), sa.ForeignKey("twin_card.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("refresh_json", postgresql.JSONB(), nullable=True),
        *_AUDIT_TS,
        sa.UniqueConstraint("card_id", "name", name="uq_twin_page_name"),
    )
    op.create_index("idx_twin_page_card", "twin_page", ["card_id", "sort_order"])

    op.create_table(
        "twin_widget",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("page_id", sa.BigInteger(), sa.ForeignKey("twin_page.id", ondelete="CASCADE"), nullable=False),
        sa.Column("widget_key", sa.String(32), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("query_id", sa.BigInteger(), sa.ForeignKey("onto_ontology_query.id", ondelete="SET NULL"), nullable=True),
        sa.Column("param_values_json", postgresql.JSONB(), nullable=True),
        sa.Column("display_json", postgresql.JSONB(), nullable=True),
        sa.Column("grid_json", postgresql.JSONB(), nullable=False, server_default='{"x":0,"y":0,"w":6,"h":4}'),
        sa.Column("refresh_json", postgresql.JSONB(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_AUDIT_TS,
        sa.CheckConstraint("widget_key IN ('kpi','trend','bar','donut','alert_table','graph','scene2d','scene3d')", name="ck_twin_widget_key"),
    )
    op.create_index("idx_twin_widget_page", "twin_widget", ["page_id", "sort_order"])
    op.create_index("idx_twin_widget_query", "twin_widget", ["query_id"])

    op.create_table(
        "twin_publish",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("card_id", sa.BigInteger(), sa.ForeignKey("twin_card.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_id", sa.BigInteger(), sa.ForeignKey("twin_page.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(32), nullable=False),
        sa.Column("access", sa.String(16), nullable=False, server_default="org"),
        sa.Column("role_codes_json", postgresql.JSONB(), nullable=True),
        sa.Column("snapshot_json", postgresql.JSONB(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(16), nullable=False, server_default="enabled"),
        sa.Column("published_by", sa.BigInteger(), nullable=False),
        sa.Column("published_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_twin_publish_slug"),
        sa.CheckConstraint("access IN ('org','role')", name="ck_twin_publish_access"),
        sa.CheckConstraint("status IN ('enabled','disabled')", name="ck_twin_publish_status"),
    )
    op.create_index("idx_twin_publish_page", "twin_publish", ["page_id", "status"])

    op.create_table(
        "twin_card_share",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("card_id", sa.BigInteger(), sa.ForeignKey("twin_card.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grantee_type", sa.String(16), nullable=False),
        sa.Column("grantee_id", sa.BigInteger(), nullable=True),
        sa.Column("grantee_code", sa.String(64), nullable=True),
        sa.Column("perm", sa.String(16), nullable=False, server_default="read"),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("expires_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("granted_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("grantee_type IN ('user','role')", name="ck_twin_share_type"),
        sa.CheckConstraint("perm IN ('read','edit')", name="ck_twin_share_perm"),
        sa.CheckConstraint("source IN ('manual','request')", name="ck_twin_share_source"),
    )
    op.create_index("idx_twin_share_card", "twin_card_share", ["card_id", "grantee_type"])

    op.create_table(
        "twin_access_request",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("card_id", sa.BigInteger(), sa.ForeignKey("twin_card.id", ondelete="CASCADE"), nullable=False),
        sa.Column("applicant_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("required_role_code", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("approver_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('pending','approved','rejected','expired')", name="ck_twin_access_status"),
    )
    op.create_index(
        "uq_twin_access_pending", "twin_access_request",
        ["tenant_id", "card_id", "applicant_id"],
        unique=True, postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index("idx_twin_access_card", "twin_access_request", ["card_id", "status"])


def downgrade() -> None:
    # 逆序 drop：twin_* 先删，onto_ontology_query 最后（被 twin_widget 引用）
    for tbl in (
        "twin_access_request", "twin_card_share", "twin_publish",
        "twin_widget", "twin_page", "twin_card", "onto_ontology_query",
    ):
        op.drop_table(tbl)
```

> **注意**：`downgrade` 内不得留 `pass`——必须真 drop（本仓库既有迁移均如此），否则回滚演练会静默失败。
>
> **计划缺陷修正（执行时实测，2026-11-01）**：`grid_json` 的默认值原写为
> `sa.text("'{\"x\":0,...}'::jsonb")`，但 `text()` 会把 JSON 里的 `:0`/`:6`/`:4` 当成**绑定参数**吞掉，
> 生成的 DDL 是 `DEFAULT '{"x"NULL,"y"NULL,...}'::jsonb`，PG 报
> `psycopg2.errors.InvalidTextRepresentation: Token "NULL" is invalid`，`upgrade head` 直接在
> `CREATE TABLE twin_widget` 处失败。正确写法是与 ORM 模型同形的**纯字符串** `server_default='{"x":0,...}'`
> （SQLAlchemy 会把它渲染成带引量的字面量，PG 隐式 coercion 到 jsonb）。

- [ ] **Step 7: 跑测试到通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/twin/test_models_twin.py -v`
Expected: PASS（5 passed）

> **计划缺陷修正（执行时实测，2026-11-01）**：原 Step 1 的 `test_query_code_unique_per_version`
> 写成 `for code in ("dup", "dup")` 并在循环内 `commit()`——第二次循环就会抛未捕获的
> `IntegrityError`，用例直接报错而不是验证唯一键。已改为「先插一条并提交，再插重复 code 期待报错」，
> 并补一条 `test_query_code_unique_across_version` 证明 `version` 确实在唯一键里（重发布留痕的前提）。

- [ ] **Step 8: 验证迁移可用（含回滚）**

Run: `.\.venv\Scripts\python.exe -m alembic upgrade head`
Expected: 无异常，输出含 `Running upgrade 2026_11_01_0012_seed_twin_demo_mapping -> 2026_11_01_0013_add_twin_tables`

Run: `.\.venv\Scripts\python.exe -m alembic downgrade -1` 然后 `.\.venv\Scripts\python.exe -m alembic upgrade head`
Expected: 两个方向均无异常（`downgrade -1` 只跑本任务的 0013 → drop 7 张表，**不会**连带清掉
0012 的 `twin_demo` schema 与 seed 行；若回退到 0012 之前（`downgrade -2` 或 `downgrade base`）则会，
测完务必 `alembic upgrade head` 复原，否则 Task 4/7 的演示链路没数据）

> 实测（2026-11-01）：`upgrade head` → `current = 2026_11_01_0013_add_twin_tables (head)`；
> `downgrade -1` → `2026_11_01_0012_seed_twin_demo_mapping`；再 `upgrade head` 回 head，双向无异常。

- [ ] **Step 9: 提交**

```bash
git add backend/app/models/ontology/query.py backend/app/models/twin backend/alembic/versions/2026_11_01_0013_add_twin_tables.py backend/tests/twin
git commit -m "feat(twin): add twin domain models, onto_ontology_query and alembic 0013"
```

---

### Task 2: 抽出 `_sensitive_covered()`（行为不变重构，供孪生与门禁 5 同源）

**Files:**
- Modify: `backend/app/services/ontology/ontology_publish_service.py:348-390`
- Test: `backend/tests/ontology/test_sensitive_covered_parity.py`

**Interfaces:**
- Consumes: 现有 `_gate5_mask_coverage` 内的判定逻辑
- Produces: 模块级纯函数 `is_sensitive(pii: Optional[str]) -> bool` 与 `sensitive_covered(pii: Optional[str], mask_rule: Optional[str], security_level_override: Optional[str], exempt: bool) -> bool`（Task 4 的编译敏感闸必须调用它，不得重写判断）

- [ ] **Step 1: 写失败测试（锁死同源语义）**

创建 `backend/tests/ontology/test_sensitive_covered_parity.py`：

```python
"""脱敏覆盖判定的真值表——发布门禁 5 与孪生编译共用（spec §4.1 第 4 步、§8.1 事实行）。

覆盖成立 = 非敏感 | 已豁免 | mask_rule 非空 | override 降级至 L1 以下
"""
import pytest

from app.services.ontology.ontology_publish_service import _SENSITIVE_PII, sensitive_covered


@pytest.mark.parametrize("pii,mask,ovr,exempt,expected", [
    ("L0", None, None, False, True),    # 非敏感
    (None,  None, None, False, True),   # 未标 pii_level 视为非敏感
    ("L2", None, None, False, False),   # 敏感且无 mask_rule → 未覆盖
    ("L3", "phone", None, False, True),  # 有 mask_rule → 覆盖
    ("L2", None, "L1", False, True),    # 显式降级 → 覆盖
    ("L2", None, "L2", False, False),   # 降级到仍敏感 → 不算覆盖
    ("L2", None, None, True, True),     # 豁免清单命中 → 覆盖
])
def test_truth_table(pii, mask, ovr, exempt, expected):
    assert sensitive_covered(pii, mask, ovr, exempt) is expected


def test_sensitive_set_is_L2_L3():
    assert _SENSITIVE_PII == {"L2", "L3"}
```

- [ ] **Step 2: 跑到失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ontology/test_sensitive_covered_parity.py -v`
Expected: FAIL — `ImportError: cannot import name 'sensitive_covered'`

- [ ] **Step 3: 在 `ontology_publish_service.py` 中新增模块级纯函数**

插入到 `_SENSITIVE_PII = {"L2", "L3"}`（`:54`）之后、`_iso()`（`:57`）之前：

```python
def is_sensitive(pii: Optional[str]) -> bool:
    """列是否属敏感（L2/L3）。"""
    return pii in _SENSITIVE_PII


def sensitive_covered(
    pii: Optional[str],
    mask_rule: Optional[str],
    security_level_override: Optional[str],
    exempt: bool = False,
) -> bool:
    """敏感列是否已有脱敏覆盖。

    唯一真源：发布门禁 5（``_gate5_mask_coverage``）与孪生查询编译的敏感闸
    （``OntologyQueryService``）共用本函数。任何一处私自改写判定都会破坏
    「发布能过 == 孪生能查」这条不变量，禁止复制第二份逻辑。

    覆盖成立（返回 True）当且仅当：
      非敏感 | 已登记豁免 | 已绑定标准且 mask_rule 非空 | override 显式降级至 L1 以下
    """
    if not is_sensitive(pii):
        return True
    if exempt:
        return True
    if mask_rule:
        return True
    if security_level_override and security_level_override not in _SENSITIVE_PII:
        return True
    return False
```

- [ ] **Step 4: 把 `_gate5_mask_coverage` 循环体改为调用它（行为不变）**

将 `:369-383` 的 for 循环替换为：

```python
        for cm in column_maps:
            pii = pii_map.get(cm["column_id"])
            ovr = (override_map.get(cm["column_id"]) or {}).get("security_level_override")
            if sensitive_covered(pii, mask_map.get(cm["standard_id"]), ovr,
                                 exempt=cm["column_id"] in exempt_set):
                continue
            missing.append(f"column:{cm['column_id']} pii={pii}")
```

并把同文件 `:385` 的 `pii_map.get(c['column_id']) in _SENSITIVE_PII` 改为 `is_sensitive(pii_map.get(c['column_id']))`（计数语义不变）。

- [ ] **Step 5: 跑新旧两套测试到全绿**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ontology -v -k "publish or gate or mask or sensitive"`
Expected: PASS，且**既有门禁测试无任何修改即通过**（证明重构未改行为；若既有测试红，说明 §Step 4 的替换不等价，必须回退重做，禁止改测试来迁就实现）

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/ontology/ontology_publish_service.py backend/tests/ontology/test_sensitive_covered_parity.py
git commit -m "refactor(ontology): extract sensitive_covered() as single source for gate 5"
```

---

### Task 3: `ReadonlyQueryService.run` 支持绑定参数 + 占位符归一

**Files:**
- Modify: `backend/app/services/dataops/query_service.py:41-63`
- Create: `backend/app/services/dataops/sql_placeholder.py`
- Test: `backend/tests/dataops/test_query_params.py`

**Interfaces:**
- Consumes: 既有 `run(source_id, sql, limit)`（3 个调用方：`routers/dataops/dataops.py:596`、`ai/tools/dataops_tools.py:183`、`services/kb/table_sync_service.py:68`）
- Produces: `run(source_id, sql, limit=100, params: Optional[dict] = None, params_declared: Optional[list] = None) -> dict`（签名向后兼容，两个新形参默认 None 时行为逐字节不变）；`normalize_placeholders(sql: str) -> str`；`declared_names(params_json: list) -> list[str]`；`validate_params(declared: list, values: dict) -> dict`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/dataops/test_query_params.py`：

```python
"""参数化的三条硬约束：方言渲染归一、越界拒绝、无参数时行为不变（spec §4.2、W15）。"""
import pytest

from app.services.dataops.sql_placeholder import MAX_PARAMS, normalize_placeholders, validate_params


def test_normalize_postgres_style_to_named():
    # sqlglot postgres 方言把 :p_1 渲染成 %(p_1)s，而 SQLAlchemy text() 要 :name
    assert normalize_placeholders(
        "SELECT a FROM t WHERE a = %(p_1)s AND b > %(p_2)s"
    ) == "SELECT a FROM t WHERE a = :p_1 AND b > :p_2"


def test_normalize_keeps_plain_sql_untouched():
    s = "SELECT a FROM t WHERE a = 1"
    assert normalize_placeholders(s) == s


def test_normalize_does_not_touch_percent_arithmetic():
    # 50 % 2 之类的取模不得被误改写（只有 %(name)s 形态才替换）
    assert normalize_placeholders("SELECT 50 % 2 AS m, 1 = ANY(%(p_1)s) AS f") == \
        "SELECT 50 % 2 AS m, 1 = ANY(:p_1) AS f"


def test_validate_params_rejects_unknown_name_and_count():
    declared = [{"name": "p_1", "type": "int", "default": 0}]
    with pytest.raises(ValueError, match="未声明"):
        validate_params(declared, {"p_9": 1})
    with pytest.raises(ValueError, match="参数个数"):
        validate_params([], {f"p_{i}": i for i in range(MAX_PARAMS + 1)})


def test_validate_params_type_mismatch():
    declared = [{"name": "p_1", "type": "int", "default": 0}]
    with pytest.raises(ValueError, match="类型"):
        validate_params(declared, {"p_1": "abc"})


def test_validate_params_int_accepts_bool_rejects_float():
    # bool 是 int 子类但进 SQL 语义不同，显式拒绝，避免 True→1 静默改写
    declared = [{"name": "p_1", "type": "int", "default": 0}]
    with pytest.raises(ValueError, match="类型"):
        validate_params(declared, {"p_1": True})
    assert validate_params(declared, {"p_1": 7}) == {"p_1": 7}
```

- [ ] **Step 2: 跑到失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/dataops/test_query_params.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.dataops.sql_placeholder'`

- [ ] **Step 3: 创建 `backend/app/services/dataops/sql_placeholder.py`**

```python
"""SQL 占位符归一与参数校验（孪生编译链路专用，spec §4.1 第 5~6 步）。

为什么需要归一：sqlglot 按 postgres 方言渲染时会把命名参数写成 psycopg2 风格
``%(p_1)s``，而 SQLAlchemy ``text()`` 的绑定标记是 ``:p_1``（由它再转成驱动风格）。
实测 SqlGuard 对两种写法均判定为只读，故统一以 ``:name`` 落库存储。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

MAX_PARAMS = 20
"""单条查询绑定参数上限（超出即拒绝，防慢查询拼装）。"""

_DRIVER_STYLE = re.compile(r"%\((\w+)\)s")
_TYPE_CHECKS = {
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "str": lambda v: isinstance(v, str),
    "date": lambda v: isinstance(v, str) and len(v) == 10,
    "bool": lambda v: isinstance(v, bool),
}


def normalize_placeholders(sql: str) -> str:
    """把驱动风格 ``%(name)s`` 归一为 SQLAlchemy ``:name``。"""
    return _DRIVER_STYLE.sub(r":\1", sql)


def declared_names(params_json: List[Dict[str, Any]]) -> List[str]:
    return [str(p.get("name", "")).strip() for p in (params_json or []) if p.get("name")]


def validate_params(declared: List[Dict[str, Any]], values: Dict[str, Any]) -> Dict[str, Any]:
    """校验绑定参数：只允许声明过的名字、个数受上限、类型必须匹配。

    :raises ValueError: 未声明参数、参数越界或类型不符
    """
    names = declared_names(declared)
    if len(values) > MAX_PARAMS:
        raise ValueError(f"参数个数超过上限 {MAX_PARAMS}")
    out: Dict[str, Any] = {}
    for key, val in values.items():
        if key not in names:
            raise ValueError(f"未声明的参数: {key}")
        spec = next((p for p in declared if p.get("name") == key), {})
        expected = str(spec.get("type", "str"))
        check = _TYPE_CHECKS.get(expected)
        if check is None:
            raise ValueError(f"不支持的参数类型声明: {expected}")
        if not check(val):
            raise ValueError(f"参数 {key} 类型不符，期望 {expected}")
        out[key] = val
    return out
```

- [ ] **Step 4: 跑到通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/dataops/test_query_params.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: 写 run() 参数化测试（含等价性）**

追加到 `backend/tests/dataops/test_query_params.py`：

> **计划缺陷修正（执行时实测，2026-11-01）**：原写的两条用例直接不可用，已按下述重写：
> 1. `CREATE TABLE p_t` 经 `db` 连接建在本用例的**随机 schema** 里，而 `run()` 会按 DataSource
>    另起一个引擎（`build_engine` 不传 `config`，`dbSchema`/search_path 不生效），那个连接默认
>    search_path 看不到 `p_t` → 未限定名的 SQL 必报 `relation "p_t" does not exist`。
>    正解：表名用 `"{schema_name}".p_t` 全限定。
> 2. 注入串那条写成了 `assert out2["rows"] == []`，但类型校验会**先抛 `ValueError`**，语句得
>    不到返回值 → 用例直接报错。正解：用 `pytest.raises(ValueError, match="类型")`。
> 3. 新增两条补置：`params` 有值但 `params_declared` 缺位也必须拒（白名单只来自声明），
>    以及 `params=None` 的逐字节等价用例（W15 的正面证据）。
> 4. 夹具 `tenant_factory` / `source_factory` 在 `tests/dataops/conftest.py` 中原本**不存在**，
>    已按该文件既有风格补两个工厂（`source_factory` 用 `DataSourceService.create` 指向本机
>    `minworkbuddy_test`，密码自动 Fernet 落库）。

```python
from sqlalchemy import text

from app.services.dataops.query_service import ReadonlyQueryService


def test_run_binds_params_against_real_pg(db, tenant_factory, source_factory):
    """params 走绑定而非字面量拼接：注入串不得生效。"""
    tid = tenant_factory()
    sid = source_factory(tid)  # 指向本机 minworkbuddy_test 库的 DataSource
    db.execute(text("CREATE TABLE IF NOT EXISTS p_t (a int, b text)"))
    db.execute(text("INSERT INTO p_t VALUES (7, 'x')"))
    db.commit()

    svc = ReadonlyQueryService(db, tid)
    out = svc.run(sid, "SELECT a FROM p_t WHERE a = :p_1", params={"p_1": 7})
    assert out["rows"] == [[7]] and out["row_count"] == 1

    out2 = svc.run(sid, "SELECT a FROM p_t WHERE a = :p_1", params={"p_1": "7 OR 1=1"})
    assert out2["rows"] == []  # 类型不符先抛，故不会走到执行


def test_run_rejects_unknown_placeholder_before_guard(db, tenant_factory, source_factory):
    tid = tenant_factory()
    sid = source_factory(tid)
    svc = ReadonlyQueryService(db, tid)
    with pytest.raises(ValueError, match="未声明"):
        svc.run(sid, "SELECT 1 FROM dual WHERE x = :p_1",
                params={"p_2": 1}, params_declared=[{"name": "p_1", "type": "int"}])
```

> 若夹具尚无 `tenant_factory` / `source_factory`，在 `backend/tests/dataops/conftest.py` 内按该文件既有夹具风格补两个工厂（`source_factory` 建 `DataSource` 行并用 `DataSourceService` 加密密码指向本机 PG 测试库）。

- [ ] **Step 6: 改 `query_service.py`（向后兼容）**

把 `run` 改为（仅三处变化：签名、`bindparams`、占位符校验；其余逐行保持）：

```python
    def run(
        self,
        source_id: int,
        sql: str,
        limit: int = 100,
        params: Optional[dict] = None,
        params_declared: Optional[list] = None,
    ) -> dict:
        """执行只读查询，返回列/行/截断标记。

        :param params: 绑定参数（``:name`` 占位符实值）；为 None 时行为与扩展前完全一致
        :param params_declared: 参数声明（[{name,type,default}]），提供时先做校验
        """
        if limit < 1:
            limit = 1
        elif limit > 5000:
            limit = 5000

        # 参数校验前置：未声明/越界/类型不符一律拒绝（spec §4.2）
        if params:
            from app.services.dataops.sql_placeholder import validate_params
            params = validate_params(params_declared or [], params)

        ds = self._ds.get_or_404(source_id)  # 租户隔离校验
        dialect = _dialect_of(ds.source_type)
        if not self._guard.is_readonly(sql, dialect):
            raise ValueError("仅允许单条只读查询（SELECT/CTE/UNION/EXPLAIN 查询），且不含注释与危险函数")

        password = self._ds.reveal_password(ds.id)
        engine = build_engine(
            ds.source_type, ds.host, ds.port, ds.username, password, ds.database
        )
        try:
            with engine.connect() as conn:
                stmt = text(sql)
                if params:
                    stmt = stmt.bindparams(**params)
                result = conn.execute(stmt)
                columns = list(result.keys())
                rows = [list(r) for r in result.fetchmany(limit + 1)]
        finally:
            engine.dispose()
```

- [ ] **Step 7: 等价回归（W15）**

Run: `.\.venv\Scripts\python.exe -m pytest tests/dataops tests/kb/test_table_sync_and_reprocess.py tests/ai -v -k "query or sync or dataops"`
Expected: 既有测试全绿，且**未新增任何 `params` 实参**（`git diff` 里这 3 个调用方文件必须无改动——用 `git status` 确认它们未被修改）

> **计划缺陷修正（执行时实测，2026-11-01）**：路径 `tests/kb/test_table_sync.py` **不存在**
> （实名 `tests/kb/test_table_sync_and_reprocess.py`）。pytest 对不存在的收集路径直接以用法错误退出，
> 既不跑也不报错在摘要里——实测输出是「3 warnings in 0.01s」且 **0 collected**，看上去像全绿但一条也没跑。
> 这类“空绿灯”比红灯更危险：收集范里必须核对末尾的 passed/skipped 计数非零。
> 实测（修正路径后）：135 passed / 10 skipped / 36 deselected。

- [ ] **Step 8: 提交**

```bash
git add backend/app/services/dataops/query_service.py backend/app/services/dataops/sql_placeholder.py backend/tests/dataops
git commit -m "feat(dataops): optional bind params for ReadonlyQueryService with placeholder normalization"
```

---

### Task 4: `OntologyQueryService` 编译 7 步 + Q1–Q5 端点

**Files:**
- Create: `backend/app/services/ontology/ontology_query_service.py`
- Modify: `backend/app/routers/ontology/ontology.py`（文件末尾追加端点）、`backend/app/core/api_error.py`（追加错误码）
- Test: `backend/tests/ontology/test_query_compile.py`

**Interfaces:**
- Consumes: `onto_ontology_version.snapshot_json`、`OntologyAgentService._accepted()` 口径、`meta_table_standard`/`meta_column_standard`/`meta_object_relation`、Task 2 的 `sensitive_covered()`、Task 3 的 `normalize_placeholders()`、`SqlGuard.is_readonly()`
- Produces: `OntologyQueryService(db, tenant_id)` 方法 `create(...) -> dict`、`get(qid) -> dict`、`list_for_ontology(ontology_id, shape=None, kw=None) -> list[dict]`、`compile_query(qid) -> dict`、`preview(qid, params=None) -> dict`、`update(qid, patch) -> dict`、`delete(qid) -> dict`、`bindings(qid) -> list[dict]`；模块级纯函数 `shape_result(shape: str, records: list[dict], columns: list[str]) -> dict`（Task 7 必须复用它做形状归一）；错误码常量 `QUERY_NOT_FOUND`、`QUERY_DRAFT_FORBIDDEN`、`QUERY_MAPPING_MISSING`、`QUERY_ELEMENTS_UNREVIEWED`、`QUERY_JOIN_AMBIGUOUS`、`QUERY_SENSITIVE_UNCOVERED`、`QUERY_SHAPE_MISMATCH`、`QUERY_COMPILE_FAILED`、`WIDGET_IN_USE`

- [ ] **Step 1: 追加错误码常量**

在 `backend/app/core/api_error.py` 的常量区**末尾**追加（现有最后一行是 `CONFIRM_EXPIRED`，`:82`；**不要**插在 `ASSISTANT_BUILD_EMPTY:71` 之后，那会拆散「推演沙盘沙箱域」注释块）。响应体由 `register_api_error_handler` 固定输出顶层 `{code, message, detail?}`：

```python
# --- 孪生应用 P0（spec 2026-11-01-digital-twin-app-design §4.6）---
QUERY_NOT_FOUND = "QUERY_NOT_FOUND"
QUERY_DRAFT_FORBIDDEN = "QUERY_DRAFT_FORBIDDEN"          # version=0 草稿态禁止编译
QUERY_ELEMENTS_UNREVIEWED = "QUERY_ELEMENTS_UNREVIEWED"  # 引用了非 accepted 元素
QUERY_MAPPING_MISSING = "QUERY_MAPPING_MISSING"          # 对象未绑表 / 属性未绑列
QUERY_JOIN_AMBIGUOUS = "QUERY_JOIN_AMBIGUOUS"            # 跨对象路径不唯一
QUERY_TOO_MANY_OBJECTS = "QUERY_TOO_MANY_OBJECTS"        # P0 硬限制：>2 对象或 >1 跳
QUERY_SENSITIVE_UNCOVERED = "QUERY_SENSITIVE_UNCOVERED"  # 敏感列缺脱敏覆盖
QUERY_SHAPE_MISMATCH = "QUERY_SHAPE_MISMATCH"            # result_shape 与 widget_key 不配对
QUERY_COMPILE_FAILED = "QUERY_COMPILE_FAILED"
WIDGET_IN_USE = "WIDGET_IN_USE"
TWIN_CARD_NOT_FOUND = "TWIN_CARD_NOT_FOUND"
TWIN_PAGE_NOT_FOUND = "TWIN_PAGE_NOT_FOUND"
TWIN_WIDGET_NOT_FOUND = "TWIN_WIDGET_NOT_FOUND"
TWIN_NOT_PUBLISHED = "TWIN_NOT_PUBLISHED"
TWIN_ACCESS_REQUIRED = "TWIN_ACCESS_REQUIRED"
TWIN_REQUEST_NOT_FOUND = "TWIN_REQUEST_NOT_FOUND"
TWIN_REQUEST_NOT_PENDING = "TWIN_REQUEST_NOT_PENDING"
```

- [ ] **Step 2: 写失败测试（覆盖 6 类失败路径 + 1 条成功编译）**

创建 `backend/tests/ontology/test_query_compile.py`：

```python
"""查询编译 7 步的失败路径必须逐类可判定（spec §4.1、§7.4、W10）。"""
import pytest

from app.core.api_error import (
    QUERY_COMPILE_FAILED, QUERY_DRAFT_FORBIDDEN, QUERY_JOIN_AMBIGUOUS,
    QUERY_MAPPING_MISSING, QUERY_SENSITIVE_UNCOVERED, QUERY_ELEMENTS_UNREVIEWED,
    QUERY_TOO_MANY_OBJECTS,
)
from app.services.ontology.ontology_query_service import OntologyQueryService

# spec_json 的 attributes 是**标准项 code**（meta_standard.code），不是属性主键
SHAPE_OK = {"objects": ["o_dev"], "attributes": ["a_oee"], "agg": None,
            "group_by": [], "filters": [], "time_window": None, "limit": 100}


def _svc(db):
    from tests.ontology.conftest import TENANT_A
    return OntologyQueryService(db, TENANT_A)


def test_draft_version_cannot_compile(db, seeded_ontology):
    svc = _svc(db)
    q = svc.create(ontology_id=seeded_ontology["id"], version=0, code="q_draft",
                   name="草稿", result_shape="kpi", spec_json=SHAPE_OK)
    with pytest.raises(Exception) as ei:
        svc.compile_query(q["id"])
    assert ei.value.code == QUERY_DRAFT_FORBIDDEN


def test_unreviewed_element_rejected(db, seeded_ontology):
    """② 只认 accepted：引用快照内 review_status != accepted 的属性即拒。"""
    svc = _svc(db)
    spec = {**SHAPE_OK, "attributes": ["a_pending"]}
    with pytest.raises(Exception) as ei:
        svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_unrev",
                   name="n", result_shape="kpi", spec_json=spec)
    assert ei.value.code == QUERY_ELEMENTS_UNREVIEWED
    assert ei.value.detail["elements"] == ["a_pending"]


def test_missing_table_binding_reports_offenders(db, seeded_ontology):
    """③ 对象已采纳但未绑物理表 → 回传 offender 列表（前端直接列出待映射对象）。"""
    svc = _svc(db)
    spec = {**SHAPE_OK, "objects": ["o_nomap"], "attributes": ["a_linecode"]}
    with pytest.raises(Exception) as ei:
        svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_nomap",
                   name="n", result_shape="kpi", spec_json=spec)
    assert ei.value.code == QUERY_MAPPING_MISSING
    assert "o_nomap" in ei.value.detail["objects"]


def test_attribute_without_column_binding_rejected(db, seeded_ontology):
    """③′ 属性在该对象表上无 accepted 列绑定 → 同样 fail-closed，不默默丢列。"""
    svc = _svc(db)
    spec = {**SHAPE_OK, "attributes": ["a_linecode"]}  # a_linecode 只绑在 o_line 上
    with pytest.raises(Exception) as ei:
        svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_nocol",
                   name="n", result_shape="kpi", spec_json=spec)
    assert ei.value.code == QUERY_MAPPING_MISSING
    assert ei.value.detail["attributes"] == ["a_linecode"]


def test_too_many_objects_blocked(db, seeded_ontology):
    svc = _svc(db)
    spec = {**SHAPE_OK, "objects": ["o_dev", "o_line", "o_site"]}
    with pytest.raises(Exception) as ei:
        svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_many",
                   name="n", result_shape="kpi", spec_json=spec)
    assert ei.value.code == QUERY_TOO_MANY_OBJECTS


def test_ambiguous_join_returns_candidates(db, seeded_ontology):
    """③′ o_dev↔o_site 在夹具里有两条关系：不指定 join 则不猜，回传候选。"""
    svc = _svc(db)
    spec = {**SHAPE_OK, "objects": ["o_dev", "o_site"],
            "attributes": ["a_oee", "a_devcode"]}
    with pytest.raises(Exception) as ei:
        svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_join",
                   name="n", result_shape="table", spec_json=spec)
    assert ei.value.code == QUERY_JOIN_AMBIGUOUS
    assert sorted(ei.value.detail["candidates"]) == ["r_dev_site_a", "r_dev_site_b"]


def test_sensitive_column_without_mask_rule_blocked(db, seeded_ontology):
    """④ 敏感闸：L2 列且标准无 mask_rule → 拒绝并回传 blocked_columns。"""
    svc = _svc(db)
    spec = {**SHAPE_OK, "attributes": ["a_idcard"]}
    with pytest.raises(Exception) as ei:
        svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_pii",
                   name="n", result_shape="table", spec_json=spec)
    assert ei.value.code == QUERY_SENSITIVE_UNCOVERED
    assert ei.value.detail["blocked_columns"] == ["a_idcard"]


def test_happy_path_compiles_comment_free_single_statement(db, seeded_ontology):
    svc = _svc(db)
    q = svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_ok",
                   name="OEE", result_shape="kpi", spec_json=SHAPE_OK)
    out = svc.compile_query(q["id"])
    assert out["verify_status"] == "verified"
    sql = out["compiled_sql"]
    assert "--" not in sql and "/*" not in sql and sql.count(";") <= 1
    assert sql.startswith("SELECT ")
    assert out["sql_sha256"] and len(out["sql_sha256"]) == 64
    # 执行目标在编译期定死，运行期不再重复解析快照
    assert out["source_id"] == seeded_ontology["source_id"]
    assert seeded_ontology["table"].lower() in sql.lower()


def test_join_path_projects_both_sides(db, seeded_ontology):
    """③′ 成功分支：1 跳 JOIN，ON 由关系的 via 属性解析到两侧列名。"""
    svc = _svc(db)
    spec = {**SHAPE_OK, "objects": ["o_dev", "o_line"],
            "attributes": ["a_oee", "a_linecode"], "result_shape": "table"}
    out = svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_j",
                     name="n", result_shape="table", spec_json=spec)
    sql = out["compiled_sql"].lower()
    assert " join " in sql and " on " in sql
    assert sql.count("demo_device_stat") == 1 and "demo_line_stat" in sql


def test_filters_compile_to_placeholders_never_literals(db, seeded_ontology):
    """⑤⑥ 过滤值一律落 :p_n 占位符，并追写进 params_json 供执行期校验。"""
    svc = _svc(db)
    spec = {**SHAPE_OK, "filters": [{"attribute": "a_oee", "op": "gt", "value": 0.5}]}
    out = svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_f",
                     name="n", result_shape="kpi", spec_json=spec)
    assert ":p_1" in out["compiled_sql"]
    assert "0.5" not in out["compiled_sql"]
    assert out["params_json"][0]["name"] == "p_1"
    assert out["params_json"][0]["type"] == "float"


def test_illegal_agg_operator_fails_closed(db, seeded_ontology):
    svc = _svc(db)
    spec = {**SHAPE_OK, "agg": {"op": "drop table", "attribute": "a_oee"}}
    with pytest.raises(Exception) as ei:
        svc.create(ontology_id=seeded_ontology["id"], version=1, code="q_agg",
                   name="n", result_shape="kpi", spec_json=spec)
    assert ei.value.code == QUERY_COMPILE_FAILED


def test_unsupported_dialect_rejected_without_db():
    """⑤ 非 PG 族直接拒编译（§10 U6），而不是编出一句只能跑错的 SQL。"""
    from app.services.ontology.ontology_query_service import _require_supported_dialect

    assert _require_supported_dialect("postgresql") == "postgres"
    for st in ("mysql", "doris"):
        with pytest.raises(Exception) as ei:
            _require_supported_dialect(st)
        assert ei.value.code == QUERY_COMPILE_FAILED
```

- [ ] **Step 3: 写 `seeded_ontology` 夹具**

追加到 `backend/tests/ontology/conftest.py` 末尾（沿用该文件既有 `TENANT_A`/`TEST_DB_NAME`/`db`/`schema_name` 夹具）：

真实快照形状已从代码实测得到（`ontology_publish_service.build_snapshot:175-212`），必须逐字段对齐，
否则编译第 1/3 步在测试里读到的是空快照，所有用例会因错误原因失败：

| 快照键 | 来由 | 包含的字段 |
|---|---|---|
| `objects[]` | `MetaObjectStandard` | `id` `code` `name` `domain` `aliases` `source` `review_status` `confidence` |
| `relations[]` | `MetaObjectRelation` | `id` `code` `name` `from_object_id` `to_object_id` `relation_type` `source` `review_status`（**只有 id，无 code、无连接键**） |
| `properties[]` | `MetaObjectStandardAttribute` | `id` `object_id` `standard_id` `required` `review_status`（**无 `code`，属性以标准项 id 表达**） |
| `mappings.table[]` | `MetaTableStandard` | `id` `table_id` `object_standard_id` `source` |
| `mappings.column[]` | `MetaColumnStandard` | `id` `column_id` `standard_id` `source` |
| `cq[]` | `MetaOntologyCq` | `id` `question` `category` `verify_status` `version` |

推论：快照**只冻结 id**，物理表/列名必须回查实表（与发布门禁 5 一致地读 `MetaColumn.pii_level`），
关系的连接键 `via_attribute_ids` 也不在快照里，同样回查 `MetaObjectRelation`。

```python
@pytest.fixture
def seeded_ontology(db: Session, schema_name: str) -> dict:
    """最小可编译本体：真实形状的版本快照 + accepted 映射 + 三张可查的 demo 表。

    设该夹具的三个硬约束：
    1. demo 表建在**本测试的随机 schema**（db 连接的 search_path 已指向它），
       而 MetaTable.database 也写该 schema——编译产物因此带限定名，
       能被 ReadonlyQueryService 另建的引擎（默认 search_path）直接看到；
    2. DataSource 密码必须用 ``encrypt_secret`` 写 ``password_enc``，
       因为建连走 ``DataSourceService.reveal_password`` 会解密（Fernet 密钥由
       本文件 autouse 夹具 ``_encryption_key`` 注入）；
    3. 一个对象一张表、一个列一个标准项：``uq_meta_table_standard_table`` 与
       ``uq_meta_column_standard_column`` 都是单列 UNIQUE，所以 o_site 有自己的
       demo_site_stat、a_pending 占自己的 note 列，共用会撞 UniqueViolation。
    """
    import json

    from sqlalchemy import text

    from app.config import settings
    from app.ai.dataops.crypto import encrypt_secret
    from tests.ontology.conftest import TENANT_A, TEST_DB_NAME

    tid = TENANT_A
    ex = lambda s, p=None: db.execute(text(s), p or {})  # noqa: E731

    # ---------- 1. 三张真实可查的 demo 表（落在本测试 schema） ----------
    ex(f'CREATE TABLE "{schema_name}".demo_device_stat '
       f'(dev_code text, oee numeric, id_card text, ts_posted timestamp, note text)')
    ex(f'CREATE TABLE "{schema_name}".demo_line_stat (line_code text, dev_code text)')
    # o_site 必须有自己的物理表：uq_meta_table_standard_table 是 UNIQUE(table_id)，
    # 一张表只能绑一个对象标准，「多个对象共用同一张表」在真实系统里根本建不出来。
    ex(f'CREATE TABLE "{schema_name}".demo_site_stat (site_code text, dev_code text)')
    ex(f'INSERT INTO "{schema_name}".demo_device_stat '
       f'(dev_code, oee, id_card, ts_posted, note) VALUES (\'D1\', 0.85, \'310101199001011234\', now(), NULL)')
    ex(f'INSERT INTO "{schema_name}".demo_line_stat VALUES (\'L1\', \'D1\')')
    ex(f'INSERT INTO "{schema_name}".demo_site_stat VALUES (\'S1\', \'D1\')')

    dsid = ex(
        "INSERT INTO meta_data_source (tenant_id, name, source_type, external_type, host, port, "
        "username, password_enc, database, status) "
        "VALUES (:t,'twin-demo','postgresql','rdbms',:h,:p,:u,:pw,:db,'online') RETURNING id",
        {"t": tid, "h": settings.DB_HOST, "p": int(settings.DB_PORT), "u": settings.DB_USER,
         "pw": encrypt_secret(str(settings.DB_PASSWORD)), "db": TEST_DB_NAME},
    ).scalar_one()

    def table(name: str) -> int:
        return ex(
            "INSERT INTO meta_table (tenant_id, source_id, db_name, database, table_name) "
            "VALUES (:t,:s,:db,:sc,:n) RETURNING id",
            {"t": tid, "s": dsid, "db": TEST_DB_NAME, "sc": schema_name, "n": name},
        ).scalar_one()

    tb_dev, tb_line = table("demo_device_stat"), table("demo_line_stat")
    tb_site = table("demo_site_stat")

    def column(table_id: int, name: str, ordinal: int, pii: str) -> int:
        return ex(
            "INSERT INTO meta_column (tenant_id, table_id, column_name, ordinal, pii_level) "
            "VALUES (:t,:tb,:n,:o,:p) RETURNING id",
            {"t": tid, "tb": table_id, "n": name, "o": ordinal, "p": pii},
        ).scalar_one()

    c_dev_code = column(tb_dev, "dev_code", 1, "L0")
    c_oee = column(tb_dev, "oee", 2, "L1")
    c_id_card = column(tb_dev, "id_card", 3, "L2")     # 敏感且标准无 mask_rule → 触发敏感闸
    column(tb_dev, "ts_posted", 4, "L0")
    c_note = column(tb_dev, "note", 5, "L0")
    c_line_code = column(tb_line, "line_code", 1, "L0")
    c_line_dev = column(tb_line, "dev_code", 2, "L0")  # 与 dev 侧同名，是 JOIN 的连接键
    c_site_dev = column(tb_site, "dev_code", 2, "L0")  # o_site 侧的 JOIN 连接键

    # ---------- 2. 模式层：对象 / 标准项 ----------
    def obj(code: str, name: str, review: str = "accepted") -> int:
        return ex(
            "INSERT INTO meta_object_standard (tenant_id, code, name, status, review_status, source) "
            "VALUES (:t,:c,:n,'published',:r,'human') RETURNING id",
            {"t": tid, "c": code, "n": name, "r": review},
        ).scalar_one()

    def std(code: str, name: str, mask: str = "keep_first2", level: str = "L1") -> int:
        return ex(
            "INSERT INTO meta_standard (tenant_id, code, name, status, security_level, mask_rule) "
            "VALUES (:t,:c,:n,'published',:l,:m) RETURNING id",
            {"t": tid, "c": code, "n": name, "l": level, "m": mask},
        ).scalar_one()

    dev, line, site = obj("o_dev", "设备"), obj("o_line", "产线"), obj("o_site", "园区")
    obj("o_nomap", "未映射对象")                        # accepted 但未绑表 → ③ 失败路径
    a_oee = std("a_oee", "设备OEE")
    a_idcard = std("a_idcard", "身份证号", mask=None)      # 无脱敏规则 → ④ 敏感闸拦截
    a_devcode = std("a_devcode", "设备编码")
    a_linecode = std("a_linecode", "产线编码")
    a_pending = std("a_pending", "待采纳属性")

    # ---------- 3. 对象↔属性（快照里的 properties） ----------
    prop_rows = []

    def prop(object_id: int, standard_id: int, review: str = "accepted") -> None:
        pid = ex(
            "INSERT INTO meta_object_standard_attribute (tenant_id, object_id, standard_id, "
            "required, sort_order, review_status) "
            "VALUES (:t,:o,:s,false,0,:r) RETURNING id",
            {"t": tid, "o": object_id, "s": standard_id, "r": review},
        ).scalar_one()
        prop_rows.append({"id": int(pid), "object_id": int(object_id),
                          "standard_id": int(standard_id), "required": False,
                          "review_status": review})

    prop(dev, a_devcode)
    prop(dev, a_oee)
    prop(dev, a_idcard)
    prop(dev, a_pending, review="suggested")            # ② 未采纳路径
    prop(line, a_linecode)
    prop(line, a_devcode)
    prop(site, a_devcode)

    # ---------- 4. 物理映射（status=accepted） ----------
    table_map_rows = []

    def bind_table(object_id: int, table_id: int) -> None:
        mid = ex(
            "INSERT INTO meta_table_standard (tenant_id, table_id, object_standard_id, status, source) "
            "VALUES (:t,:tb,:o,'accepted','human') RETURNING id",
            {"t": tid, "tb": table_id, "o": object_id},
        ).scalar_one()
        table_map_rows.append({"id": int(mid), "table_id": int(table_id),
                              "object_standard_id": int(object_id), "source": "human"})

    column_map_rows = []

    def bind_column(column_id: int, standard_id: int) -> None:
        mid = ex(
            "INSERT INTO meta_column_standard (tenant_id, column_id, standard_id, status, source) "
            "VALUES (:t,:c,:s,'accepted','human') RETURNING id",
            {"t": tid, "c": column_id, "s": standard_id},
        ).scalar_one()
        column_map_rows.append({"id": int(mid), "column_id": int(column_id),
                               "standard_id": int(standard_id), "source": "human"})

    bind_table(dev, tb_dev)          # o_nomap 故意不绑
    bind_table(line, tb_line)
    bind_table(site, tb_site)
    bind_column(c_dev_code, a_devcode)
    bind_column(c_oee, a_oee)
    bind_column(c_id_card, a_idcard)
    bind_column(c_line_code, a_linecode)
    bind_column(c_line_dev, a_devcode)
    bind_column(c_site_dev, a_devcode)
    bind_column(c_note, a_pending)  # 列侧已绑，但属性 review_status=suggested
    # uq_meta_column_standard_column 是 UNIQUE(column_id)：一个物理列只能绑一个标准项，
    # 故 a_pending 必须占自己的 note 列，不能搭 c_dev_code 的车。

    # ---------- 5. 关系：o_dev→o_line 唯一路径；o_dev↔o_site 两条→歧义 ----------
    rel_rows = []

    def relation(code: str, from_id: int, to_id: int, via: list, review: str = "accepted") -> int:
        rid = ex(
            "INSERT INTO meta_object_relation (tenant_id, code, name, from_object_id, to_object_id, "
            "relation_type, via_attribute_ids, status, source, review_status) "
            "VALUES (:t,:c,:n,:f,:to,'N:1',CAST(:v AS jsonb),'published','human',:r) RETURNING id",
            {"t": tid, "c": code, "n": code, "f": from_id, "to": to_id,
             "v": json.dumps([int(x) for x in via]), "r": review},
        ).scalar_one()
        rel_rows.append({"id": int(rid), "code": code, "name": code,
                         "from_object_id": int(from_id), "to_object_id": int(to_id),
                         "relation_type": "N:1", "source": "human", "review_status": review})
        return int(rid)

    relation("r_dev_line", dev, line, [a_devcode])
    relation("r_dev_site_a", dev, site, [a_devcode])
    relation("r_dev_site_b", site, dev, [a_devcode])   # 同一对对象的第二条路径
    db.commit()

    # ---------- 6. 版本快照（逐字段对齐 build_snapshot 输出） ----------
    snap = {
        "objects": [
            {"id": dev, "code": "o_dev", "name": "设备", "domain": None, "aliases": [],
             "source": "human", "review_status": "accepted", "confidence": None},
            {"id": line, "code": "o_line", "name": "产线", "domain": None, "aliases": [],
             "source": "human", "review_status": "accepted", "confidence": None},
            {"id": site, "code": "o_site", "name": "园区", "domain": None, "aliases": [],
             "source": "human", "review_status": "accepted", "confidence": None},
            {"id": ex("SELECT id FROM meta_object_standard WHERE tenant_id=:t AND code='o_nomap'",
                      {"t": tid}).scalar_one(),
             "code": "o_nomap", "name": "未映射对象", "domain": None, "aliases": [],
             "source": "human", "review_status": "accepted", "confidence": None},
        ],
        "relations": rel_rows,
        "properties": prop_rows,
        "mappings": {"table": table_map_rows, "column": column_map_rows},
        "cq": [],
    }
    oid = ex(
        "INSERT INTO onto_ontology (tenant_id, code, name, status, current_version) "
        "VALUES (:t,'twin_demo','孪生演示本体','published',1) RETURNING id", {"t": tid}
    ).scalar_one()
    vid = ex(
        "INSERT INTO onto_ontology_version (tenant_id, ontology_id, version, snapshot_json) "
        "VALUES (:t,:o,1,CAST(:s AS jsonb)) RETURNING id",
        {"t": tid, "o": oid, "s": json.dumps(snap, ensure_ascii=False)},
    ).scalar_one()
    db.commit()

    return {
        "id": int(oid), "version": int(vid), "source_id": int(dsid),
        "schema": schema_name, "table": "demo_device_stat", "table_line": "demo_line_stat",
        "table_site": "demo_site_stat",
        "objects": {"o_dev": dev, "o_line": line, "o_site": site},
        "attributes": {"a_oee": a_oee, "a_idcard": a_idcard,
                       "a_devcode": a_devcode, "a_linecode": a_linecode},
    }
```

> 该夹具的列名/取值域已逐表比对 `backend/app/models/dataops/{meta,standard,standard_cdm,data_source}.py`：
> `meta_table` 无 `schema_name` 列（PG 族用 `database` 存 schema）；`meta_table_standard.object_standard_id`；
> `meta_data_source.status` 取值域是 `unknown|online|offline`（无 `active`）且 `external_type` 有 CHECK。
> 若仍报 NOT NULL，**按报错补列，不得放宽模型约束**。

- [ ] **Step 4: 跑到失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ontology/test_query_compile.py -v`
Expected: FAIL — 12 个用例均 `ModuleNotFoundError: No module named 'app.services.ontology.ontology_query_service'`（夹具先行报错属正常，补上服务后应只剩导入错误消失后的断言失败）

- [ ] **Step 5: 写编译服务**

创建 `backend/app/services/ontology/ontology_query_service.py`：

```python
"""本体查询编译（spec 孪生方案 §4.1：7 步，全程 fail-closed）。

安全边界：
- 只读快照输入（``onto_ontology_version.snapshot_json``），绝不跟随 ``onto_ontology.current_version``；
- 只认快照内逐行 ``review_status='accepted'`` 的元素（**比发布更严**：发布按
  ``onto_ontology_build_item.status`` 整批放行，本模块按元素结论，宁可拒绝也不放行未采纳元素）；
- 敏感列复用 ``sensitive_covered()``，与发布门禁 5 同一真源；
- 产物为无注释单语句 + ``:p_n`` 绑定参数，执行仍走 ``ReadonlyQueryService`` 单一取数口。

版本快照是唯一真源，形状由 ``OntologyPublishService.build_snapshot``
（``ontology_publish_service.py:175-212``）决定，解析必须按下列实测事实写：

- ``objects[]`` = ``{id, code, name, domain, aliases, source, review_status, confidence}``；
- ``relations[]`` = ``{id, code, name, from_object_id, to_object_id, relation_type, source,
  review_status}``——**只有对象 id、没有连接键**，``via_attribute_ids`` 要回查 ``meta_object_relation``；
- ``properties[]`` = ``{id, object_id, standard_id, required, review_status}``——**没有属性 code**，
  属性身份 = 标准项 ``meta_standard.code``，需回查取名；
- ``mappings.table[]`` / ``mappings.column[]`` 已由 build_snapshot 按 ``status='accepted'`` 过滤
  （``:141-166``），故编译期**不再查** ``meta_table_standard``/``meta_column_standard``，
  只按 ``table_id``/``column_id`` 回查 ``meta_table``/``meta_column`` 取物理名。

两个易错列名（实测）：``meta_table`` 的 schema 在 ``database`` 列（**无** ``schema_name`` 列）；
投影一律 ``AS`` 成标准项 code，使结果集键、脱敏 ``field`` 与 ``spec_json`` 引用三者同源。
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

import sqlglot
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.api_error import (
    ApiError, ONTOLOGY_NOT_FOUND, QUERY_COMPILE_FAILED, QUERY_DRAFT_FORBIDDEN,
    QUERY_ELEMENTS_UNREVIEWED, QUERY_JOIN_AMBIGUOUS, QUERY_MAPPING_MISSING,
    QUERY_NOT_FOUND, QUERY_SENSITIVE_UNCOVERED, QUERY_TOO_MANY_OBJECTS, WIDGET_IN_USE,
)
from app.models.dataops.data_source import DataSource
from app.models.dataops.meta import MetaColumn, MetaTable
from app.models.dataops.standard import MetaStandard
from app.models.dataops.standard_cdm import MetaObjectRelation
from app.models.ontology.ontology import MetaOntology, MetaOntologyVersion
from app.models.ontology.query import MetaOntologyQuery
from app.services.dataops.query_service import ReadonlyQueryService, _dialect_of
from app.services.dataops.sql_guard import SqlGuard
from app.services.dataops.sql_placeholder import normalize_placeholders
from app.services.ontology.ontology_publish_service import is_sensitive, sensitive_covered

SHAPES = ("kpi", "trend", "bar", "donut", "table", "entity_set", "graph")
AGG_OPS = ("sum", "avg", "min", "max", "count")
FILTER_OPS = {"eq": "=", "ne": "<>", "gt": ">", "ge": ">=", "lt": "<", "le": "<=",
              "in": "IN", "like": "LIKE"}
MAX_OBJECTS = 2      # P0 硬限制（对象 ≤2 ⇒ JOIN ≤1 跳，无需单独的 MAX_JOINS）
MAX_LIMIT = 5000
SUPPORTED_DIALECTS = ("postgres",)   # §10 U6：P0 只支持 PG 族（时间窗用 PG 的 INTERVAL 语法）


class OntologyQueryService:
    """查询定义的创建、编译、预览与生命周期。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("OntologyQueryService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id
        self._guard = SqlGuard()

    # ------------------------------------------------------------------ CRUD

    def create(self, *, ontology_id: int, version: int, code: str, name: str,
               result_shape: str, spec_json: dict, params_json: Optional[list] = None,
               description: Optional[str] = None) -> dict:
        if result_shape not in SHAPES:
            raise ApiError(QUERY_COMPILE_FAILED, f"非法 result_shape: {result_shape}", 400,
                           {"result_shape": result_shape})
        self._ontology_or_404(ontology_id)
        row = MetaOntologyQuery(
            tenant_id=self.tenant_id, ontology_id=ontology_id, version=version, code=code,
            name=name, description=description, result_shape=result_shape, spec_json=spec_json,
            params_json=params_json or [],
            status="disabled" if int(version or 0) == 0 else "enabled",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        # 创建即尝试编译：失败信息直接回给调用方（前端绑定抽屉据此提示）
        # 例外：version=0 的草稿不自动编译——草稿必须存得下来（spec §3.1），
        # 编译是显式动作，否则 create 会当场抛 QUERY_DRAFT_FORBIDDEN 而无处保存。
        if int(version or 0) != 0:
            self.compile_query(row.id)
        return self.get(row.id)

    def get(self, qid: int) -> dict:
        return self._serialize(self._row_or_404(qid))

    def list_for_ontology(self, ontology_id: int, shape: Optional[str] = None,
                          kw: Optional[str] = None, verified_only: bool = False) -> List[dict]:
        stmt = select(MetaOntologyQuery).where(
            MetaOntologyQuery.tenant_id == self.tenant_id,
            MetaOntologyQuery.ontology_id == ontology_id,
        )
        if shape:
            stmt = stmt.where(MetaOntologyQuery.result_shape == shape)
        if kw:
            stmt = stmt.where(MetaOntologyQuery.name.ilike(f"%{kw}%"))
        if verified_only:
            stmt = stmt.where(MetaOntologyQuery.verify_status == "verified")
        rows = self.db.execute(stmt.order_by(MetaOntologyQuery.code)).scalars().all()
        return [self._serialize(r) for r in rows]

    def update(self, qid: int, patch: dict) -> dict:
        row = self._row_or_404(qid)
        for f in ("name", "description", "spec_json", "params_json", "result_shape"):
            if f in patch:
                setattr(row, f, patch[f])
        row.verify_status = "pending"
        self.db.commit()
        if int(row.version or 0) != 0:   # 同上：草稿改动不触发自动编译
            self.compile_query(qid)
        return self.get(qid)

    def bindings(self, qid: int) -> List[dict]:
        from app.models.twin import TwinWidget
        self._row_or_404(qid)
        rows = self.db.execute(
            select(TwinWidget.id, TwinWidget.title).where(
                TwinWidget.tenant_id == self.tenant_id, TwinWidget.query_id == qid
            )
        ).all()
        return [{"widget_id": int(w), "title": t} for w, t in rows]

    def delete(self, qid: int) -> dict:
        row = self._row_or_404(qid)
        used = self.bindings(qid)
        if used:
            raise ApiError(
                WIDGET_IN_USE, f"该查询被 {len(used)} 个组件绑定中，请先解绑", 409,
                {"widgets": used},
            )
        self.db.delete(row)
        self.db.commit()
        return {"deleted": True, "id": qid}

    # -------------------------------------------------------------- 编译 7 步

    def compile_query(self, qid: int) -> dict:
        """①~⑥ 全量重编译；任一步失败先回写 failed 再原样抛出（fail-closed）。"""
        row = self._row_or_404(qid)
        try:
            sql, source_id, params_json, mask_rules, projection = self._compile(row)
        except ApiError as exc:
            detail: Dict[str, Any] = {"blocked_code": exc.code}
            if isinstance(exc.detail, dict):
                detail.update(exc.detail)
            row.compiled_sql = None
            row.sql_sha256 = None
            row.verify_status = "failed"
            row.verify_detail_json = detail
            self.db.commit()
            raise
        row.compiled_sql = sql
        row.sql_sha256 = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        row.source_id = source_id
        row.params_json = params_json
        row.mask_rules_json = {"enabled": bool(mask_rules), "rules": mask_rules}
        row.verify_status = "verified"
        row.verify_detail_json = {"compiled": True, "projection": projection}
        self.db.commit()
        self.db.refresh(row)
        return self._serialize(row)

    def _compile(self, row: MetaOntologyQuery):
        """编译正文：不写库、不提交，失败一律抛 :class:`ApiError`。

        :return: ``(sql, source_id, params_json, mask_rules, projection)``
        """
        # ① 版本解析：只认已发布版本快照，草稿一律拒绝
        version = int(row.version or 0)
        if version == 0:
            raise ApiError(QUERY_DRAFT_FORBIDDEN, "草稿版本查询不可编译，请先发布本体", 400)
        snap = self._snapshot(row.ontology_id, version)

        # ② 元素解析：对象按 code、属性按标准项 code
        acc = self._accepted(snap)
        spec = row.spec_json or {}
        objects = [str(c) for c in (spec.get("objects") or [])]
        attrs = [str(c) for c in (spec.get("attributes") or [])]
        if not objects or not attrs:
            raise ApiError(QUERY_COMPILE_FAILED, "spec 至少需引用 1 个对象与 1 个属性", 400,
                           {"objects": objects, "attributes": attrs})
        if len(objects) > MAX_OBJECTS:
            raise ApiError(QUERY_TOO_MANY_OBJECTS, f"P0 最多 {MAX_OBJECTS} 个对象", 400,
                           {"objects": objects})
        elements = [c for c in attrs if c not in acc["attr_codes"]]
        elements += [c for c in objects if c not in acc["obj_codes"]]
        if elements:
            raise ApiError(QUERY_ELEMENTS_UNREVIEWED, "引用了未采纳元素", 400,
                           {"elements": elements})

        # ③ 对象→物理表
        untabled = [c for c in objects if c not in acc["table"]]
        if untabled:
            raise ApiError(QUERY_MAPPING_MISSING, "对象未完成物理映射", 400,
                           {"objects": untabled})

        # ③′ JOIN 消歧：先于属性归属判定，路径不唯一时把候选交还用户（不猜）
        joins: List[dict] = []
        if len(objects) == 2:
            joins = self._resolve_join(acc, objects[0], objects[1], spec.get("join"))

        # ③″ 属性→物理列（含归属消歧）
        bound = self._bind_columns(acc, objects, attrs)

        # ④ 敏感闸（与发布门禁 5 同源）
        blocked = self._check_sensitive(bound)
        if blocked:
            raise ApiError(QUERY_SENSITIVE_UNCOVERED, f"{len(blocked)} 个敏感列缺脱敏覆盖", 400,
                           {"blocked_columns": blocked})

        # ⑤ 执行目标定死：全部对象同属一个数据源（P0 不做跨源 JOIN）
        source_ids = sorted({int(acc["table"][c]["source_id"]) for c in objects})
        if len(source_ids) > 1:
            raise ApiError(QUERY_COMPILE_FAILED, "P0 不支持跨数据源 JOIN", 400,
                           {"source_ids": source_ids})
        source_id = source_ids[0]
        ds = self.db.get(DataSource, source_id)
        if ds is None or int(ds.tenant_id) != int(self.tenant_id):
            raise ApiError(QUERY_MAPPING_MISSING, "数据源缺失或跨租户", 400,
                           {"source_id": source_id})
        dialect = _require_supported_dialect(ds.source_type)

        # ⑥ SQL 生成 + 参数化（值一律落 :p_n 占位符）
        sql, params_json, mask_rules = self._render(
            acc, objects, attrs, bound, joins, spec, list(row.params_json or []), dialect)
        sql = normalize_placeholders(sql)
        if not self._guard.is_readonly(sql, dialect):
            raise ApiError(QUERY_COMPILE_FAILED, "编译产物未通过只读校验", 400, {"sql": sql})
        return sql, source_id, params_json, mask_rules, [a for a in attrs if a in bound]

    # ------------------------------------------------------------------ 预览

    def preview(self, qid: int, params: Optional[dict] = None, limit: int = 200) -> dict:
        row = self._row_or_404(qid)
        if not row.compiled_sql:
            self.compile_query(qid)
            row = self._row_or_404(qid)
        source_id = int(row.source_id or 0)   # 编译期已定死，运行期不再解析快照
        if not source_id:
            raise ApiError(QUERY_MAPPING_MISSING, "编译产物缺少 source_id，请重新编译", 400)
        svc = ReadonlyQueryService(self.db, self.tenant_id)
        try:
            out = svc.run(source_id, row.compiled_sql, limit=min(int(limit), 200),
                          params=params or {}, params_declared=row.params_json or [])
        except Exception as exc:  # noqa: BLE001 — 预览失败一律回写 failed，供绑定抽屉展示原因
            row.verify_status = "failed"
            row.verify_detail_json = {"error": str(exc)[:400]}
            self.db.commit()
            raise
        records = [dict(zip(out["columns"], r)) for r in out["rows"]]
        shape = shape_result(row.result_shape, records, out["columns"])
        row.verify_status = "verified"
        row.verify_detail_json = {"columns": out["columns"], "row_count": out["row_count"],
                                 "truncated": out["truncated"]}
        self.db.commit()
        return {"query_id": qid, "result_shape": row.result_shape, **shape,
                "row_count": out["row_count"], "columns": out["columns"]}

    # ------------------------------------------------------------------ 内部

    def _serialize(self, r: MetaOntologyQuery) -> dict:
        return {
            "id": int(r.id), "ontology_id": int(r.ontology_id), "version": int(r.version),
            "code": r.code, "name": r.name, "description": r.description,
            "result_shape": r.result_shape, "spec_json": r.spec_json,
            "params_json": r.params_json or [], "compiled_sql": r.compiled_sql,
            "sql_sha256": r.sql_sha256, "source_id": r.source_id,
            "mask_rules_json": r.mask_rules_json,
            "verify_status": r.verify_status,
            "verify_detail_json": r.verify_detail_json, "status": r.status,
        }
```

> 模块级辅助函数 `_quote()`、`_param_type()`、`time_window_expr()`、`_require_supported_dialect()`
> 与 `shape_result()` 在同一文件实现（`shape_result` **刻意不进类**：Task 7 的批量取数要用同一套
> 形状归一，私有方法跳模块调用是坏味道；抽为模块函数后两处 import 同一份），代码见 Step 6。

- [ ] **Step 6: 实现编译内部方法与模块级辅助函数**

在同文件追加方法（类内）：

```python
    def _ontology_or_404(self, ontology_id: int) -> MetaOntology:
        row = self.db.get(MetaOntology, ontology_id)
        if row is None or int(row.tenant_id) != int(self.tenant_id):
            raise ApiError(ONTOLOGY_NOT_FOUND, "本体不存在", 404)
        return row

    def _row_or_404(self, qid: int) -> MetaOntologyQuery:
        row = self.db.get(MetaOntologyQuery, qid)
        if row is None or int(row.tenant_id) != int(self.tenant_id):
            raise ApiError(QUERY_NOT_FOUND, "查询不存在", 404)
        return row

    def _snapshot(self, ontology_id: int, version: int) -> dict:
        """版本快照是唯一真源：缺失即拒绝，绝不回落到 current_version。"""
        row = self.db.execute(
            select(MetaOntologyVersion).where(
                MetaOntologyVersion.tenant_id == self.tenant_id,
                MetaOntologyVersion.ontology_id == ontology_id,
                MetaOntologyVersion.version == version,
            )
        ).scalar()
        if row is None or not row.snapshot_json:
            raise ApiError(QUERY_COMPILE_FAILED, f"版本快照缺失：v{version}", 400,
                           {"ontology_id": ontology_id, "version": version})
        return row.snapshot_json

    def _accepted(self, snap: dict) -> dict:
        """把「只冻结 id」的快照补成可按 code 索引的编译输入。

        :return: {
          "obj_codes": set, "obj_ids": {obj_code: id},
          "attr_codes": set, "std_ids_by_code": {attr_code: standard_id},
          "prop_pairs": {(standard_id, object_id)},
          "table": {obj_code: {"table_id", "qname", "source_id"}},
          "col_by_std_table": {(standard_id, table_id): {"column_name", "pii_level",
                          "security_level_override", "mask_rule", "column_id"}},
          "relations": [{"id", "code", "from_code", "to_code", "via_std_ids"}],
        }
        """
        objs = [o for o in (snap.get("objects") or []) if o.get("review_status") == "accepted"]
        obj_ids = {str(o["code"]): int(o["id"]) for o in objs if o.get("code")}
        if not obj_ids:
            raise ApiError(QUERY_ELEMENTS_UNREVIEWED, "快照内无 accepted 对象", 400)
        code_by_obj = {v: k for k, v in obj_ids.items()}

        # 属性身份 = 标准项 code（快照只有 standard_id，名称回查 meta_standard）
        props = [p for p in (snap.get("properties") or []) if p.get("review_status") == "accepted"]
        std_ids = sorted({int(p["standard_id"]) for p in props if p.get("standard_id")})
        code_by_std: Dict[int, str] = {}
        mask_by_std: Dict[int, Optional[str]] = {}
        if std_ids:
            for sid, scode, srule in self.db.execute(
                select(MetaStandard.id, MetaStandard.code, MetaStandard.mask_rule).where(
                    MetaStandard.tenant_id == self.tenant_id, MetaStandard.id.in_(std_ids))
            ).all():
                code_by_std[int(sid)] = str(scode)
                mask_by_std[int(sid)] = srule
        prop_pairs = {(int(p["standard_id"]), int(p["object_id"])) for p in props
                      if p.get("standard_id") and p.get("object_id")}

        # 表绑定：快照已由 build_snapshot 按 status='accepted' 过滤，不再重查绑定表
        table_ids_by_obj: Dict[str, List[int]] = {}
        for tm in (snap.get("mappings") or {}).get("table") or []:
            oc = code_by_obj.get(int(tm.get("object_standard_id") or 0))
            if oc:
                table_ids_by_obj.setdefault(oc, []).append(int(tm["table_id"]))
        multi = [c for c, v in table_ids_by_obj.items() if len(v) > 1]
        if multi:
            raise ApiError(QUERY_COMPILE_FAILED, "对象有多个 accepted 表绑定，P0 不消歧", 400,
                           {"objects": sorted(multi)})
        tids = sorted({v[0] for v in table_ids_by_obj.values() if v})
        tables = {int(t.id): t for t in self.db.execute(
            select(MetaTable).where(MetaTable.tenant_id == self.tenant_id,
                                    MetaTable.id.in_(tids))).scalars().all()} if tids else {}
        table_map: Dict[str, dict] = {}
        for code, ids in table_ids_by_obj.items():
            t = tables.get(ids[0])
            if t is None or not t.source_id:
                continue
            # schema 存在 database 列（PG 族）；无 schema_name 列
            table_map[code] = {"table_id": int(t.id),
                               "qname": f"{_quote(t.database)}.{_quote(t.table_name)}",
                               "source_id": int(t.source_id)}

        # 列绑定：一个标准可绑多表多列，故键为 (standard_id, table_id) 而非 standard_id
        col_maps = list((snap.get("mappings") or {}).get("column") or [])
        cids = sorted({int(cm["column_id"]) for cm in col_maps})
        cols = {int(c.id): c for c in self.db.execute(
            select(MetaColumn).where(MetaColumn.tenant_id == self.tenant_id,
                                     MetaColumn.id.in_(cids))).scalars().all()} if cids else {}
        ovr_by_col = {int(cm["column_id"]): cm.get("security_level_override") for cm in col_maps}
        col_by_std_table: Dict[Tuple[int, int], dict] = {}
        for cm in col_maps:
            c = cols.get(int(cm["column_id"]))
            if c is None:
                continue
            col_by_std_table[(int(cm["standard_id"]), int(c.table_id))] = {
                "column_id": int(c.id), "column_name": c.column_name,
                "pii_level": c.pii_level, "mask_rule": mask_by_std.get(int(cm["standard_id"])),
                "security_level_override": ovr_by_col.get(int(c.id)),
            }

        # 关系：快照无连接键，via_attribute_ids 回查实表（一次批量查，不逐行查）
        rel_snap = [r for r in (snap.get("relations") or []) if r.get("review_status") == "accepted"]
        via_by_id: Dict[int, List[int]] = {}
        rids = [int(r["id"]) for r in rel_snap if r.get("id")]
        if rids:
            for rid, via in self.db.execute(
                select(MetaObjectRelation.id, MetaObjectRelation.via_attribute_ids).where(
                    MetaObjectRelation.tenant_id == self.tenant_id,
                    MetaObjectRelation.id.in_(rids))
            ).all():
                via_by_id[int(rid)] = [int(x) for x in (via or [])]
        relations = []
        for r in rel_snap:
            f = code_by_obj.get(int(r.get("from_object_id") or 0))
            t = code_by_obj.get(int(r.get("to_object_id") or 0))
            if not f or not t:
                continue
            relations.append({"id": int(r["id"]), "code": r.get("code"), "from_code": f,
                              "to_code": t, "via_std_ids": via_by_id.get(int(r["id"]), [])})
        return {"obj_codes": set(obj_ids), "obj_ids": obj_ids,
                "attr_codes": set(code_by_std.values()), "std_ids_by_code":
                {v: k for k, v in code_by_std.items()},
                "prop_pairs": prop_pairs, "table": table_map,
                "col_by_std_table": col_by_std_table, "relations": relations}

    def _bind_columns(self, acc: dict, objects: List[str], attrs: List[str]) -> Dict[str, dict]:
        """③″ 属性→物理列，并消歧归属对象；缺失或多归属一律 fail-closed。

        属性可用需同时命中两条链：``properties``（属性挂在该对象上）与列绑定落在
        该对象的物理表上。命中 0 个→未映射，命中≥2 个对象→P0 不猜归属。
        """
        bound: Dict[str, dict] = {}
        missing: List[str] = []
        ambiguous: List[str] = []
        for code in attrs:
            std_id = acc["std_ids_by_code"].get(code)
            hits: Dict[str, dict] = {}
            if std_id:
                for oc in objects:
                    if (std_id, acc["obj_ids"][oc]) not in acc["prop_pairs"]:
                        continue
                    info = acc["col_by_std_table"].get((std_id, acc["table"][oc]["table_id"]))
                    if info:
                        hits[oc] = dict(info, obj_code=oc)
            if not hits:
                missing.append(code)
            elif len(hits) > 1:
                ambiguous.append(code)
            else:
                bound[code] = next(iter(hits.values()))
        if missing:
            raise ApiError(QUERY_MAPPING_MISSING, "属性未完成物理映射", 400,
                           {"attributes": missing})
        if ambiguous:
            raise ApiError(QUERY_COMPILE_FAILED, "属性同时归属查询涉及的多个对象", 400,
                           {"attributes": ambiguous})
        return bound

    def _resolve_join(self, acc: dict, a: str, b: str, hint: Optional[str]) -> List[dict]:
        """③′ 路径唯一才返回；不唯一则把候选交给用户消歧（不猜）。

        方向无关：``{from_code, to_code} == {a, b}``——同一对对象的双向关系算两条。
        ON 子句不在本方法生成（需别名，交给 `_join_on`）。
        """
        cands = [r for r in acc["relations"] if {r["from_code"], r["to_code"]} == {a, b}]
        if hint:
            cands = [r for r in cands if r.get("code") == hint]
        if not cands:
            raise ApiError(QUERY_MAPPING_MISSING, f"{a} 与 {b} 之间无已采纳关系", 400,
                           {"objects": [a, b]})
        if len(cands) > 1:
            raise ApiError(QUERY_JOIN_AMBIGUOUS, "关系路径不唯一，请在 spec.join 指定关系编码", 400,
                           {"candidates": sorted(str(c.get("code")) for c in cands)})
        return [cands[0]]

    def _check_sensitive(self, bound: Dict[str, dict]) -> List[str]:
        """④ 敏感闸：只调 `sensitive_covered()`，与发布门禁 5 同一真源。

        ``exempt`` 恒为 False：编译期不知道运行者身份，豁免只能在出口脱敏时按角色
        判定（Task 7）；本步只做「有没有登记过脱敏规则」这一结构性检查。
        ``security_level_override`` 也从快照 mapping 行读，与门禁 5 完全同宽：上游
        ``build_snapshot:201-205`` 未写入该键（恒为 None），孪生刻意不提前修正，
        以免出现「发布拦下、孪生放行」的单向放宽。
        """
        return [code for code, v in bound.items()
                if not sensitive_covered(v.get("pii_level"), v.get("mask_rule"),
                                         v.get("security_level_override"), exempt=False)]

    def _join_on(self, acc: dict, rel: dict, alias: Dict[str, str]) -> str:
        """关系的 ``via`` 标准 id → 两侧物理列名（快照无连接键，全靠实表）。"""
        parts: List[str] = []
        for std_id in rel["via_std_ids"]:
            lhs = acc["col_by_std_table"].get((std_id, acc["table"][rel["from_code"]]["table_id"]))
            rhs = acc["col_by_std_table"].get((std_id, acc["table"][rel["to_code"]]["table_id"]))
            if not lhs or not rhs:
                raise ApiError(QUERY_MAPPING_MISSING, "关系连接键在对象表上无 accepted 列绑定",
                               400, {"relation": rel["code"], "standard_id": std_id})
            parts.append(f'{_quote(alias[rel["from_code"]])}.{_quote(lhs["column_name"])} = '
                         f'{_quote(alias[rel["to_code"]])}.{_quote(rhs["column_name"])}')
        if not parts:
            raise ApiError(QUERY_COMPILE_FAILED, "关系缺少连接键（via_attribute_ids 为空）", 400,
                           {"relation": rel["code"]})
        return " AND ".join(parts)

    def _render(self, acc: dict, objects: List[str], attrs: List[str],
                bound: Dict[str, dict], joins: List[dict], spec: dict,
                declared: List[dict], dialect: str) -> Tuple[str, List[dict], List[dict]]:
        """⑤⑥ 生成单语句、参数声明与出口脱敏规则。

        组装策略：先收集 WHERE 片段，一次拼出 SQL 文本，再交 ``sqlglot.parse_one``
        规范化渲染（顺带语法复检），最后由调用方 ``normalize_placeholders`` 收尾；
        **禁止字符串切片回写 SQL**。两个注入面各自封口：标识符走 :func:`_quote`
        双写转义，值一律落 ``:p_n`` 占位符（执行期由 ``validate_params`` 校验类型）。

        投影统一 ``AS`` 成标准项 code，因此结果集键、脱敏 ``field`` 与
        ``spec_json.attributes`` 三者同源；也避开同名列（两侧都有 ``dev_code``）互相覆盖。

        :return: ``(sql, params_json, mask_rules)``
        """
        alias = {c: f"t{i}" for i, c in enumerate(objects)}

        def col_of(code: str) -> str:
            v = bound[code]
            return f'{_quote(alias[v["obj_code"]])}.{_quote(v["column_name"])}'

        # 聚合与分组：算子白名单 + group_by 必为 attributes 子集
        agg = spec.get("agg")
        group = [str(g) for g in (spec.get("group_by") or [])]
        outside = [g for g in group if g not in attrs]
        if outside:
            raise ApiError(QUERY_COMPILE_FAILED, "group_by 必须是 attributes 的子集", 400,
                           {"group_by": outside})
        op = ""
        agg_col: Optional[str] = None
        if agg is not None:
            op = str(agg.get("op") or "").lower()
            agg_col = str(agg.get("attribute") or "")
            if op not in AGG_OPS:
                raise ApiError(QUERY_COMPILE_FAILED, f"非法聚合算子: {op}", 400, {"agg_op": op})
            if agg_col not in bound:
                raise ApiError(QUERY_MAPPING_MISSING, "聚合属性未完成物理映射", 400,
                               {"attributes": [agg_col]})
            if agg_col in group:
                raise ApiError(QUERY_COMPILE_FAILED, "聚合属性不可同时出现在 group_by", 400,
                               {"attribute": agg_col})
            for code in attrs:
                if code != agg_col and code not in group:
                    raise ApiError(QUERY_COMPILE_FAILED, "聚合查询下非聚合属性必须 group_by",
                                   400, {"attributes": [code]})

        sel = [f'{op}({col_of(code)}) AS {_quote(code)}' if code == agg_col
               else f'{col_of(code)} AS {_quote(code)}' for code in attrs]
        base = objects[0]
        sql = f'SELECT {", ".join(sel)} FROM {acc["table"][base]["qname"]} AS {_quote(alias[base])}'
        for j in joins:
            to = j["to_code"]
            sql += (f' JOIN {acc["table"][to]["qname"]} AS {_quote(alias[to])}'
                    f' ON {self._join_on(acc, j, alias)}')
        if group:
            sql += " GROUP BY " + ", ".join(col_of(g) for g in group)

        # 过滤与时间窗 → 一律占位符；占位符名不得与已声明参数冲突
        params_json = [dict(p) for p in declared]
        taken = {str(p.get("name")) for p in params_json}
        state = {"n": 0}

        def next_ph() -> str:
            while True:
                state["n"] += 1
                cand = f"p_{state['n']}"
                if cand not in taken:
                    taken.add(cand)
                    return cand

        where_bits: List[str] = []
        for f in (spec.get("filters") or []):
            code = str(f.get("attribute") or "")
            fop = str(f.get("op") or "").lower()
            if code not in bound:
                raise ApiError(QUERY_MAPPING_MISSING, "过滤属性未完成物理映射", 400,
                               {"attributes": [code]})
            if fop not in FILTER_OPS:
                raise ApiError(QUERY_COMPILE_FAILED, f"非法过滤算子: {fop}", 400, {"filter_op": fop})
            val = f.get("value")
            if fop == "in":
                if not isinstance(val, list) or not val:
                    raise ApiError(QUERY_COMPILE_FAILED, "in 过滤需非空数组", 400,
                                   {"attribute": code})
                subs = [next_ph() for _ in val]
                where_bits.append(f'{col_of(code)} IN ({", ".join(":" + s for s in subs)})')
                params_json += [{"name": s, "type": _param_type(v), "source": "compiled"}
                                for s, v in zip(subs, val)]
            else:
                ph = next_ph()
                where_bits.append(f'{col_of(code)} {FILTER_OPS[fop]} :{ph}')
                params_json.append({"name": ph, "type": _param_type(val), "source": "compiled"})

        tw = spec.get("time_window")
        if tw:
            code = str(tw.get("attribute") or "")
            days = tw.get("days")
            if code not in bound:
                raise ApiError(QUERY_MAPPING_MISSING, "时间窗属性未完成物理映射", 400,
                               {"attributes": [code]})
            if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 3650:
                raise ApiError(QUERY_COMPILE_FAILED, "时间窗天数须为 1~3650 的整数", 400,
                               {"days": days})
            ph = next_ph()
            where_bits.append(time_window_expr(col_of(code), ph))
            params_json.append({"name": ph, "type": "int", "source": "compiled"})
        if where_bits:
            sql += " WHERE " + " AND ".join(where_bits)

        limit = min(max(int(spec.get("limit") or 100), 1), MAX_LIMIT)
        sql += f" LIMIT {limit}"

        # 出口脱敏规则：编译期只知道「哪些列是敏感的」，保留位数给 0 即全掩码（fail-safe）
        mask_rules = [{"field": code, "strategy": "mask", "keep_prefix": 0, "keep_suffix": 0,
                       "exempt_roles": []}
                      for code, v in bound.items() if is_sensitive(v.get("pii_level"))]
        try:
            tree = sqlglot.parse_one(sql, dialect=dialect)
        except Exception as exc:  # noqa: BLE001 — 复检不过一律归为编译失败
            raise ApiError(QUERY_COMPILE_FAILED, "编译产物语法复检失败", 400,
                           {"error": str(exc)[:300], "sql": sql}) from exc
        return tree.sql(dialect=dialect), params_json, mask_rules
```

> 旧版本在此处的 `@staticmethod _shape_result()` 已上提为**模块级** `shape_result()`（见下方辅助函数块）：
> 它不依赖任何实例状态，而 Task 7 必须复用同一套形状归一，不得出现第二份实现。
```

再把五个**模块级**辅助函数插在 Step 5 的常量之后、`class OntologyQueryService` 之前：

```python
def _quote(ident: str) -> str:
    """双引号包裹并转义标识符。

    物理表/列名来自元数据而非用户输入，但扫描器/人工都无法保证上游干净，
    因此仍按注入面处理：内部 ``"`` 双写，外层一律带引号（大小写保留）。
    """
    return '"' + str(ident).replace('"', '""') + '"'


_PARAM_TYPES = {int: "int", float: "float", str: "str", bool: "bool"}


def _param_type(value: Any) -> str:
    """编译期根据字面量推断参数声明类型（不支持的类型直接拒）。"""
    t = _PARAM_TYPES.get(type(value))
    if t is None:
        raise ApiError(QUERY_COMPILE_FAILED,
                       f"不支持的过滤值类型: {type(value).__name__}", 400)
    return t


def time_window_expr(col: str, ph: str) -> str:
    """相对时间窗 → PG 语法（§10 U6 取默认 A：P0 仅支持 PG 族）。

    天数走绑定参数，因此不能写成 ``INTERVAL ':n day'``（驱动不绑定引号内）；
    改为乘法形式，已实测 sqlglot 可解析且渲染为 ``INTERVAL '1 DAY'``。
    """
    return f"{col} >= CURRENT_DATE - (:{ph} * INTERVAL '1 day')"


def _require_supported_dialect(source_type: str) -> str:
    """数据源类型 → sqlglot 方言；非 PG 族一律拒编译（而不是编出只能跑错的 SQL）。"""
    dialect = _dialect_of(source_type)
    if dialect not in SUPPORTED_DIALECTS:
        raise ApiError(QUERY_COMPILE_FAILED,
                       f"P0 仅支持 PostgreSQL 族数据源，当前为 {source_type}", 400,
                       {"source_type": source_type, "dialect": dialect})
    return dialect


def shape_result(shape: str, records: List[dict], columns: List[str]) -> dict:
    """按 result_shape 在后端归一，前端 renderer 不再二次整形（spec §6.2）。

    ``columns`` 即投影别名（标准项 code），``records`` 的键与之一致。
    **模块级、无实例状态**：`preview`（本文件）与批量取数（Task 7 的
    :mod:`app.services.twin.twin_data_service`）共用本函数，设计期预览与运行期取数
    因此不可能出现两套形状。
    """
    if shape == "kpi":
        first = records[0] if records else {}
        return {"value": first.get(columns[0]) if columns else None, "records": records}
    if shape in ("trend", "bar"):
        return {"records": records, "t": columns[0], "values": columns[1:]}
    if shape == "donut":
        return {"records": records, "parts": columns[:2]}
    return {"records": records}
```

> 删去旧版本里的 `_dialect_name()` 与 `_source_type()`：方言与数据源已在 `compile_query` 里从
> `row.source_id` → `DataSource.source_type` 一次定死，两个方法已无存在理由。

- [ ] **Step 7: 跑到通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ontology/test_query_compile.py -v`
Expected: PASS（12 passed）。失败排查条目（按此序查，不要改测试迁就实现）：

1. “快照内无 accepted 对象” → `seeded_ontology` 写的快照键与 `build_snapshot` 不一致；
2. `QUERY_MAPPING_MISSING` 意外出现在成功用例 → 查是否误用 `meta_table_standard`（快照已含 accepted 绑定，
   不需要再查）或 `MetaTable.database` 当成 `schema_name`；
3. `:p_1` 断言失败 → `normalize_placeholders()` 未在 `SqlGuard` 校验前执行；
4. 报 `password authentication failed` → DataSource 未用 `encrypt_secret` 写 `password_enc`。

- [ ] **Step 8: 追加 Q1–Q5 端点**

在 `backend/app/routers/ontology/ontology.py` 末尾追加（沿用该文件既有 `router`、`get_db`、`get_current_user`、`_require_tenant_id` 与 `Response` 风格）：

```python
# ─────────────────── 本体查询定义（孪生方案 Q1~Q5）───────────────────

from app.services.ontology.ontology_query_service import OntologyQueryService  # noqa: E402


class QueryCreateBody(BaseModel):
    version: int = Field(..., ge=0, description="钉住的发布版本；0=草稿")
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    result_shape: str = Field(..., description="kpi|trend|bar|donut|table|entity_set|graph")
    spec_json: Dict[str, Any]
    params_json: List[Dict[str, Any]] = Field(default_factory=list)


class QueryPatchBody(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    spec_json: Optional[Dict[str, Any]] = None
    params_json: Optional[List[Dict[str, Any]]] = None
    result_shape: Optional[str] = None


class PreviewBody(BaseModel):
    params: Dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=200, ge=1, le=200)


def _query_service(db: Session, current_user: SysUser) -> OntologyQueryService:
    return OntologyQueryService(db, _require_tenant_id(current_user))


@router.post("/ontologies/{ontology_id}/queries", status_code=201)
def create_query(ontology_id: int, body: QueryCreateBody,
                 db: Session = Depends(get_db),
                 current_user: SysUser = Depends(get_current_user)):
    return _query_service(db, current_user).create(
        ontology_id=ontology_id, version=body.version, code=body.code, name=body.name,
        description=body.description, result_shape=body.result_shape,
        spec_json=body.spec_json, params_json=body.params_json)


@router.get("/ontologies/{ontology_id}/queries")
def list_queries(ontology_id: int, shape: Optional[str] = None, kw: Optional[str] = None,
                 verified_only: bool = False, db: Session = Depends(get_db),
                 current_user: SysUser = Depends(get_current_user)):
    return _query_service(db, current_user).list_for_ontology(
        ontology_id, shape=shape, kw=kw, verified_only=verified_only)


@router.post("/queries/{query_id}/preview")
def preview_query(query_id: int, body: PreviewBody,
                  db: Session = Depends(get_db),
                  current_user: SysUser = Depends(get_current_user)):
    """预览上限 200 行（与真实取数同一口径，防止预览能拉全量而发布页不能）。"""
    return _query_service(db, current_user).preview(
        query_id, params=body.params, limit=body.limit)


@router.patch("/queries/{query_id}")
def update_query(query_id: int, body: QueryPatchBody, db: Session = Depends(get_db),
                 current_user: SysUser = Depends(get_current_user)):
    return _query_service(db, current_user).update(query_id, body.model_dump(exclude_unset=True))


@router.delete("/queries/{query_id}", status_code=204)
def delete_query(query_id: int, db: Session = Depends(get_db),
                 current_user: SysUser = Depends(get_current_user)):
    _query_service(db, current_user).delete(query_id)
    return Response(status_code=204)


@router.get("/queries/{query_id}/bindings")
def query_bindings(query_id: int, db: Session = Depends(get_db),
                   current_user: SysUser = Depends(get_current_user)):
    return _query_service(db, current_user).bindings(query_id)
```

> 路径前缀（计划缺陷修正（执行时实测，2026-11-01）：原说法有误）：本体子 router **并不带自己的
> prefix**，而是在 `dataops.py:1353-1355` 以 `router.include_router(ontology_router)`（无 prefix）
> 挂进 dataops 父 router，故完整 URL = 父 router 的 `/api/v1/dataops` + 本文件里写的相对路径：
> Q1/Q2 为 `/api/v1/dataops/ontologies/{id}/queries`，Q3–Q5 为 `/api/v1/dataops/queries/{qid}/...`。
> `router_registry.py` 里根本没有 `app.routers.dataops.ontology` 这条 RouterSpec，也没有
> `prefix="/ontologies"`（若有，`/queries/...` 会被误拼成 `/ontologies/queries/...` 而使 Q3–Q5 全 404）。
> 旁证：同一文件里已有的 `/sources/{source_id}/tables/...` 路由也只能是相对路径。
>
> `PreviewBody` 而不用裸 dict 形参：FastAPI 会把单个 dict 形参嵌成 `{"params": {...}}` 请求体，
> 测试里 `json=None` 会空返 422；显式模型同时把 `limit` 的范围校验交给 Pydantic。

- [ ] **Step 9: 端点级测试**

追加到 `backend/tests/ontology/test_query_compile.py`：

```python
def test_q1_returns_400_with_code_on_sensitive_missing(client_a, seeded_ontology):
    r = client_a.post(f"/api/v1/dataops/ontologies/{seeded_ontology['id']}/queries", json={
        "version": 1, "code": "q_pii", "name": "身份证", "result_shape": "table",
        "spec_json": {"objects": ["o_dev"], "attributes": ["a_idcard"], "limit": 10},
    })
    assert r.status_code == 400
    assert r.json()["code"] == "QUERY_SENSITIVE_UNCOVERED"
    assert "a_idcard" in r.json()["detail"]["blocked_columns"]


def test_q1_happy_then_q3_preview(client_a, seeded_ontology):
    r = client_a.post(f"/api/v1/dataops/ontologies/{seeded_ontology['id']}/queries", json={
        "version": 1, "code": "q_ok", "name": "OEE", "result_shape": "kpi",
        "spec_json": {"objects": ["o_dev"], "attributes": ["a_oee"], "limit": 5},
    })
    assert r.status_code == 201, r.text
    qid = r.json()["id"]
    p = client_a.post(f"/api/v1/dataops/queries/{qid}/preview", json={"params": {}, "limit": 5})
    assert p.status_code == 200, p.text
    body = p.json()
    assert body["result_shape"] == "kpi" and "records" in body
    # 预览回写 verified，且编译产物命中缓存键所需的 sql_sha256 已在 Q1 响应里
    assert len(r.json()["sql_sha256"]) == 64


def test_q5_delete_blocked_when_widget_bound(client_a, seeded_ontology, bound_widget):
    r = client_a.delete(f"/api/v1/dataops/queries/{bound_widget['query_id']}")
    assert r.status_code == 409
    assert r.json()["code"] == "WIDGET_IN_USE"
```

Run: `.\.venv\Scripts\python.exe -m pytest tests/ontology/test_query_compile.py -v`
Expected: PASS（15 passed）。`bound_widget` 夹具在本步追加到 `backend/tests/ontology/conftest.py`（任务 6 的 `twin_*` 表已由任务 1 迁移建好，此处用裸 SQL 插三行即可）：

```python
@pytest.fixture
def bound_widget(db: Session, seeded_ontology) -> dict:
    """一条真实引用 query_id 的孪生组件，用于验证 Q5 的 WIDGET_IN_USE 拦截。

    列名逐字对齐 Task 1 模型：卡片用 ``ontology_version``/``runtime_state``/``owner_id``
    （没有 ``version``/``status`` 列），页面只有 ``sort_order``/``refresh_json``（无布局列）。
    ``owner_id`` 无外键，取 101——即 ``_fake_user(TENANT_A)`` 的 user_id，与 client_a 同一人。
    """
    from sqlalchemy import text

    from tests.ontology.conftest import TENANT_A
    ex = lambda s, p=None: db.execute(text(s), p or {})  # noqa: E731
    qid = ex(
        "INSERT INTO onto_ontology_query (tenant_id, ontology_id, version, code, name, "
        "result_shape, spec_json, status) VALUES (:t,:o,1,'q_bound','绑定中','kpi',"
        "CAST(:s AS jsonb),'enabled') RETURNING id",
        {"t": TENANT_A, "o": seeded_ontology["id"], "s": '{"objects":["o_dev"],"attributes":["a_oee"]}'},
    ).scalar_one()
    cid = ex("INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, "
             "runtime_state, owner_id) VALUES (:t,'卡',:o,1,'draft',101) RETURNING id",
             {"t": TENANT_A, "o": seeded_ontology["id"]}).scalar_one()
    pid = ex("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
             "VALUES (:t,:c,'页',0) RETURNING id", {"t": TENANT_A, "c": cid}).scalar_one()
    wid = ex("INSERT INTO twin_widget (tenant_id, page_id, widget_key, title, query_id, sort_order) "
             "VALUES (:t,:p,'kpi','组件',:q,0) RETURNING id",
             {"t": TENANT_A, "p": pid, "q": qid}).scalar_one()
    db.commit()
    return {"query_id": int(qid), "widget_id": int(wid)}
```

> 若报 NOT NULL，按报错补写该列（以 Task 1 模型定义为准），**不得放宽模型约束来迁就夹具**。

- [ ] **Step 10: 提交**

```bash
git add backend/app/services/ontology/ontology_query_service.py backend/app/routers/ontology/ontology.py backend/app/core/api_error.py backend/tests/ontology
git commit -m "feat(ontology): named query entity with 7-step fail-closed compiler"
```

> **执行记录（2026-11-01）**：`test_query_compile.py` 15 passed；回归
> `tests/ontology tests/twin tests/dataops` 214 passed / 10 skipped。
> 本 Task 共修正计划缺陷 4 处（均已就地回写）：
> ⑴ **缺陷 #7｜夹具建不出**：`uq_meta_table_standard_table` 是 `UNIQUE(table_id)`，
>   而原 `seeded_ontology` 让 `o_line` 与 `o_site` 共用 `demo_line_stat`，插入即 UniqueViolation，
>   11/12 用例卡在 setup。修法：为 `o_site` 建 `demo_site_stat`。副作用：一个对象一张表。
> ⑵ **缺陷 #8｜夹具建不出**：`uq_meta_column_standard_column` 是 `UNIQUE(column_id)`，
>   而原夹具把 `a_devcode` 与 `a_pending` 同绑到 `c_dev_code`。修法：给 `a_pending` 自己的 `note` 列，
>   保留“列侧已绑、语义侧未采纳”的测试意图（该意图不依赖列绑定，`attr_codes` 只从 accepted
>   `properties` 里收集，因此即使不绑任何列也会拦住）。
> ⑶ **缺陷 #9｜Step 5 与 Step 2 自相矛盾**：`create()` 无条件自动编译，使 `version=0` 的草稿
>   在创建时就抛 `QUERY_DRAFT_FORBIDDEN`，而 `test_draft_version_cannot_compile` 要求“先建成功、
>   再显式编译才拒”。修在实现侧（草稿不自动编译），因为 spec §3.1 要求草稿态可保存；
>   `update()` 同步加同一护栏。未改测试迁就实现。
> ⑷ **文档缺陷｜路由前缀误述**：见 Step 8 注（子 router 无 prefix，靠父 router 单点挂载）。

---

### Task 5: TTL 缓存上提到 `app/core/cache.py`（含角色签名不变量）

**Files:**
- Create: `backend/app/core/cache.py`
- Modify: `backend/app/middleware/audit_logger.py:105-135`
- Test: `backend/tests/unit/test_ttl_cache.py`

**Interfaces:**
- Consumes: `_TTLCache`（现私有于 `audit_logger.py:107-132`，实例 `_perm_cache` 在 `:135`）
- Produces: `TTLCache(maxsize=256, ttl=60.0)`（方法 `get(key) -> Optional[Any]`、`set(key, value) -> None`，与旧 `_TTLCache` 逐字同义）与 `make_key(*parts: Any) -> str`（顺序敏感，调用方自行排序）；`data_cache_key(...)` 本任务**不产出**，它属于 Task 7（本任务只定“角色签名必须进键”这条不变量）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_ttl_cache.py`：

```python
"""TTL 缓存的键必须把角色签名算进去——漏掉即等于脱敏失效（spec §4.3 安全不变量）。"""
import time

from app.core.cache import TTLCache, make_key


def test_get_after_ttl_returns_none():
    c = TTLCache(maxsize=8, ttl=0.05)
    c.set("k", "v")
    assert c.get("k") == "v"
    time.sleep(0.06)
    assert c.get("k") is None


def test_lru_eviction_keeps_recent():
    c = TTLCache(maxsize=2, ttl=60)
    c.set("a", 1)
    c.set("b", 2)
    c.get("a")        # a 变为最近使用
    c.set("c", 3)     # 应淘汰 b
    assert c.get("a") == 1 and c.get("c") == 3 and c.get("b") is None


def test_role_signature_changes_key():
    base = ("100", 7, "abcdef", "sha256ofsql")
    k_exempt = make_key(*base, "SEC_ADMIN")
    k_normal = make_key(*base, "VIEWER")
    assert k_exempt != k_normal


def test_same_roles_different_order_same_key():
    assert make_key("100", 7, "h", "s", *sorted(["A", "B"])) == make_key("100", 7, "h", "s", *sorted(["B", "A"]))
```

- [ ] **Step 2: 跑到失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_ttl_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.cache'`

- [ ] **Step 3: 创建 `backend/app/core/cache.py`**

```python
"""进程内 TTL 缓存（线程安全 LRU）。

自 ``middleware/audit_logger.py`` 的私有 ``_TTLCache`` 上提，避免仓库出现第二份
内存缓存实现（``kb_cache._MemoryCache`` 含 Redis 回退，语义更重，本期不复用）。

⚠️ 安全用法：缓存脱敏后的结果时，键**必须**包含访问者角色签名
（见 :func:`make_key` 的 ``role_sig`` 部分）。否则拥有豁免角色的用户所对应的
**未脱敏**结果会命中到普通用户，等同于脱敏策略失效。
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Optional


class TTLCache:
    """简单的线程安全 TTL 缓存（LRU 淘汰）。"""

    def __init__(self, maxsize: int = 256, ttl: float = 60.0) -> None:
        self._cache: OrderedDict = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl
        self._lock = threading.Lock()

    def get(self, key: Any) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                value, ts = self._cache[key]
                if time.time() - ts < self._ttl:
                    self._cache.move_to_end(key)
                    return value
                del self._cache[key]
            return None

    def set(self, key: Any, value: Any) -> None:
        with self._lock:
            self._cache[key] = (value, time.time())
            self._cache.move_to_end(key)
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)


def make_key(*parts: Any) -> str:
    """把分散的键成分拼成稳定字符串（顺序敏感：调用方自行排序）。"""
    return "|".join(str(p) for p in parts)
```

- [ ] **Step 4: 跑到通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_ttl_cache.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 让 `audit_logger` 复用（删除私有实现，不改行为）**

`backend/app/middleware/audit_logger.py`：删掉 `:105-133` 的 `# ── 权限缓存 ──` 区块与 `class _TTLCache`，改为顶部 import 区追加：

```python
from app.core.cache import TTLCache
```

并把 `:135` 替换为：

```python
_perm_cache = TTLCache(maxsize=256, ttl=60.0)
```

文件内其余对 `_perm_cache.get(...)` / `.set(...)` 的调用点保持不变（方法名一致）。

- [ ] **Step 6: 回归权限缓存既有行为**

Run: `.\.venv\Scripts\python.exe -m pytest tests -v -k "audit or perm or middleware"`
Expected: 全绿，且无测试文件被修改（`git diff --name-only` 中不得出现 tests 下的 audit 相关文件）

> ⚠️ **计划缺陷修正（执行时实测，2026-11-01）：本 Step 的 `pytest tests` 全树单进程跑法不可用，与本 Task 无关。**
>
> 现象：`tests -k "audit or perm or middleware"` = 13 passed / 1 skipped / **3 errors**，3 个 error 全部落在
> `tests/sandbox`，且发生在 **fixture setup 阶段**，报错原文：
> `psycopg2.errors.UndefinedTable: relation "t_xxxx.kms_segment" does not exist`（`create_all` 的 DDL）。
>
> 根因（先行缺陷，非 Task 5 引入）：`tests/kb` 的 conftest 在 import 期把 `kms_*` / `kg_*` 等模型注册进
> **进程级全局 `Base.metadata`**；而 `tests/{ontology,twin,sandbox}/conftest.py::_tables()` 的建表清单是
> `Base.metadata.sorted_tables` **减去硬编码 3 个名字**（`kms_collection`/`kms_segment`/`kms_ref`）。两族用例
> 同进程收集时，被排除的 `kms_segment` 仍被别的表外键引用 → 悬空 FK → DDL 失败。单目录跑永不复现。
>
> 归因实验（全部实测）：
> - `tests/sandbox -k "..."` 单独跑 → **3 passed**
> - `tests/sandbox tests/kb -k "..."` 合并跑 → 9 passed / **3 errors**
> - 加 `--ignore=tests/unit` 仍 3 errors ⇒ 与 Task 5 新增文件无关
> - 曾尝试把排除清单改为「整族前缀排除 `kms_`」：失败点转移到 `kg_entity` → `kms_knowledge`（非 `kms_` 前缀的表
>   引用了被排除的表），越改越坏 ⇒ **已回退，三个 conftest 保持原样**
>
> **本 Step 的可信替代取证方式（按目录分别跑，禁止合并 `tests/`）**：
>
> ```powershell
> foreach ($d in @('tests/unit','tests/sandbox','tests/kb')) {
>   .\.venv\Scripts\python.exe -m pytest $d -q -k "audit or perm or middleware"
> }
> ```
> 实测结果：`tests/unit` 3 passed / 1 skipped；`tests/sandbox` 3 passed；`tests/kb` 9 passed；
> `tests/unit/test_ttl_cache.py` 单独跑 4 passed。合计 **0 failed / 0 error**，且 `git status` 中无任何
> 既有测试文件被修改。
>
> 后续修法（**不在本计划范围内，另立任务**）：各 conftest 的建表清单应改为**显式 allow-list**（本用例族真正需要的表），
> 而不是 `Base.metadata.sorted_tables` 减集；或为每族用例使用独立的 `MetaData` 注册域。
>
- [ ] **Step 7: 提交**

```bash
git add backend/app/core/cache.py backend/app/middleware/audit_logger.py backend/tests/unit/test_ttl_cache.py
git commit -m "refactor(core): lift TTLCache out of audit middleware into app.core.cache"
```

> 注（执行时实测，2026-11-01）：若 cwd 已在 `backend/`，上述 `backend/...` 前缀会使 `git add` 报
> `fatal: pathspec ... did not match`、commit 静默不发生。此时改用 `app/core/cache.py`、
> `app/middleware/audit_logger.py`、`tests/unit/test_ttl_cache.py` 与 `../docs/...`。**提交前必读 `git status --short`，**
> 绝不对未跟踪的临时文件与 frontend 改动做 `git add .`。

---

### Task 6: 编排层 `TwinService`（卡片/页面/组件）与 `/api/v1/twins` 端点 T1–T7

**Files:**
- Modify: `backend/app/core/api_error.py`（在 Task 4 追加的 `TWIN_*` 块内补三个码）
- Create: `backend/app/services/twin/__init__.py`
- Create: `backend/app/services/twin/twin_service.py`
- Create: `backend/app/routers/twin/__init__.py`
- Create: `backend/app/routers/twin/twin.py`
- Modify: `backend/app/core/router_registry.py:216`（列表末尾追加两条 `RouterSpec`）
- Test: `backend/tests/twin/test_twin_crud.py`

**Interfaces:**
- Consumes: Task 1 的 `TwinCard/TwinPage/TwinWidget/TwinCardShare`、`MetaOntologyQuery`（绑定校验直读表行）、`MetaOntology`/`MetaOntologyVersion`（钉版校验与 `stale`）、`build_user_context()`（取 `role_codes`）
- Produces: `TwinService(db, tenant_id, user_id, role_codes=())`；方法 `list_cards() -> dict[str, list[dict]]`、`get_card(int) -> dict`、`create_card(dict) -> dict`、`update_card(int, dict) -> dict`、`delete_card(int) -> None`、`create_from_template(str, str) -> dict`、`list_pages(int) -> list[dict]`、`create_page(int, str, dict) -> dict`、`update_page(int, dict) -> dict`、`delete_page(int) -> None`、`reorder_pages(int, list[int]) -> list[dict]`、`list_widgets(int) -> list[dict]`、`add_widget(int, dict) -> dict`、`update_widget(int, dict) -> dict`、`delete_widget(int) -> None`、`save_layout(int, list[dict]) -> list[dict]`、`card_or_404(int) -> TwinCard`、`page_with_card(int) -> tuple[TwinPage, TwinCard]`；模块常量 `WIDGET_KEY_TO_SHAPES`、`TEMPLATES`、`GRID_W_ALLOWED`；`app.routers.twin.twin.router`（自带 `prefix="/api/v1/twins"`）

- [ ] **Step 1: 补五个错误码**（标题修正：Step 1 原文写“三个”，但代码块实际列了 5 个）

在 `backend/app/core/api_error.py` 中 Task 4 追加的 `TWIN_WIDGET_NOT_FOUND` 之后插入：

```python
TWIN_LAYOUT_INVALID = "TWIN_LAYOUT_INVALID"          # 栅格位越界（w∉{3,6,12} 等）
TWIN_TEMPLATE_UNKNOWN = "TWIN_TEMPLATE_UNKNOWN"      # from-template 的模板 key 不存在
TWIN_BINDING_MISMATCH = "TWIN_BINDING_MISMATCH"      # 查询与卡片钉住的本体/版本不一致
TWIN_NAME_DUPLICATE = "TWIN_NAME_DUPLICATE"          # 同一 (租户,owner) 卡片重名 / 同卡页面重名
TWIN_TENANT_REQUIRED = "TWIN_TENANT_REQUIRED"        # 登录用户无租户上下文
```

> `TWIN_TENANT_REQUIRED` 只为**新建**的 twin 端点服务；既有 dataops/kg 的
> `HTTPException(400, detail="tenant_required")`（`dataops.py:32`、`kg.py:32`）**不改**，
> 那是 Global Constraints 里「不动既有契约」的一部分。

- [ ] **Step 2: 写失败测试**

创建 `backend/tests/twin/test_twin_crud.py`：

```python
"""编排层：结构、可见性分组与形状配对（spec §4.5 卡片三态、§5.2 第 3 闸、W5/W9）。"""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session  # 计划缺陷修正（执行时实测）：夹具注解 db: Session 需显式 import，
                                    # 否则模块定义期就 NameError（注解在无 PEP 563 时是立即求值的）

from tests.twin.conftest import TENANT_A, TENANT_B


@pytest.fixture
def published_version(db: Session, ontology_factory) -> dict:
    """本体 + 一个已发布版本行（卡片只能钉已发布版本）。"""
    oid = ontology_factory()
    db.execute(
        text("INSERT INTO onto_ontology_version (tenant_id, ontology_id, version, snapshot_json) "
             "VALUES (:t, :o, 1, CAST(:s AS jsonb))"),
        {"t": TENANT_A, "o": oid, "s": '{"objects": [], "relations": [], "properties": [],'
                                       '"mappings": {"table": [], "column": []}, "cq": []}'},
    )
    db.commit()
    return {"ontology_id": int(oid), "version": 1}


@pytest.fixture
def card_a(twin_client_a, published_version) -> int:
    r = twin_client_a.post("/api/v1/twins/cards", json={
        "name": "智慧工厂产线", "ontology_id": published_version["ontology_id"],
        "ontology_version": 1, "scene_key": "factory"})
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


def test_list_cards_groups_mine_shared_and_restricted(twin_client_a, db, card_a, published_version):
    """三组分派：自己的 draft 卡进 mine；他人 live 卡无授予进 restricted（🔒）。"""
    other = db.execute(text(
        "INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, runtime_state, owner_id) "
        "VALUES (:t,'园区安防',:o,1,'live',999) RETURNING id"),
        {"t": TENANT_A, "o": published_version["ontology_id"]}).scalar_one()
    db.commit()
    g = twin_client_a.get("/api/v1/twins/cards").json()
    assert {c["id"] for c in g["mine"]} == {card_a}
    assert g["shared"] == []
    assert {c["id"] for c in g["restricted"]} == {int(other)}
    assert g["restricted"][0]["restricted"] is True


def test_shared_card_moves_to_shared_group(twin_client_a, db, published_version):
    """user 型 share → shared；draft 卡不共享给任何人都不可见（草稿是私人作业区）。"""
    cid = db.execute(text(
        "INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, runtime_state, owner_id) "
        "VALUES (:t,'他人草稿',:o,1,'draft',999) RETURNING id"),
        {"t": TENANT_A, "o": published_version["ontology_id"]}).scalar_one()
    db.execute(text(
        "INSERT INTO twin_card_share (tenant_id, card_id, grantee_type, grantee_id, perm, source, granted_by) "
        "VALUES (:t,:c,'user',101,'read','manual',999)"), {"t": TENANT_A, "c": int(cid)})
    db.commit()
    g = twin_client_a.get("/api/v1/twins/cards").json()
    assert {c["id"] for c in g["shared"]} == {int(cid)} and g["restricted"] == []
    assert g["shared"][0]["access"] == "read"


def test_cross_tenant_card_is_404_not_403(twin_client_b, card_a):
    """租户不命中一律 404，不得用 403 泄露存在性。"""
    r = twin_client_b.get(f"/api/v1/twins/cards/{card_a}")
    assert r.status_code == 404
    assert r.json()["code"] == "TWIN_CARD_NOT_FOUND"


def test_card_can_only_pin_published_version(twin_client_a, ontology_factory):
    r = twin_client_a.post("/api/v1/twins/cards", json={
        "name": "钉未发布", "ontology_id": ontology_factory(), "ontology_version": 7})
    assert r.status_code == 400
    assert r.json()["code"] == "ONTOLOGY_NOT_FOUND"


def test_readonly_share_cannot_write(twin_client_a, twin_client_b, db, published_version):
    """read 授予可看不可写：回 403 + TWIN_ACCESS_REQUIRED（而非静默成功）。"""
    cid = db.execute(text(
        "INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, runtime_state, owner_id) "
        "VALUES (:t,'可分享',:o,1,'live',999) RETURNING id"),
        {"t": TENANT_B, "o": published_version["ontology_id"]}).scalar_one()
    db.execute(text("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) VALUES (:t,:c,'页',0)"),
               {"t": TENANT_B, "c": int(cid)})
    db.execute(text(
        "INSERT INTO twin_card_share (tenant_id, card_id, grantee_type, grantee_id, perm, source, granted_by) "
        "VALUES (:t,:c,'user',:u,'read','manual',999)"),
        {"t": TENANT_B, "c": int(cid), "u": abs(TENANT_B) + 1})
    db.commit()
    pages = twin_client_b.get(f"/api/v1/twins/cards/{int(cid)}/pages").json()
    r = twin_client_b.post(f"/api/v1/twins/pages/{pages[0]['id']}/widgets",
                           json={"widget_key": "kpi", "title": "越权"})
    assert r.status_code == 403 and r.json()["code"] == "TWIN_ACCESS_REQUIRED"


def test_widget_shape_mismatch_rejected_with_readable_reason(twin_client_a, db, card_a, published_version):
    """W9：kpi 组件绑 entity_set 查询 → 服务端拒，原因必须可读。"""
    pid = db.execute(text("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
                          "VALUES (:t,:c,'页',0) RETURNING id"),
                     {"t": TENANT_A, "c": card_a}).scalar_one()
    qid = db.execute(text(
        "INSERT INTO onto_ontology_query (tenant_id, ontology_id, version, code, name, result_shape, "
        "spec_json, compiled_sql, verify_status, status) VALUES (:t,:o,1,'q_e','实体集','entity_set',"
        "CAST('{\"objects\":[]}' AS jsonb),'SELECT 1','verified','enabled') RETURNING id"),
        {"t": TENANT_A, "o": published_version["ontology_id"]}).scalar_one()
    db.commit()
    r = twin_client_a.post(f"/api/v1/twins/pages/{int(pid)}/widgets",
                           json={"widget_key": "kpi", "title": "OEE", "query_id": int(qid)})
    assert r.status_code == 400
    body = r.json()
    assert body["code"] == "QUERY_SHAPE_MISMATCH"
    assert body["detail"]["result_shape"] == "entity_set"
    assert "alert_table" in body["detail"]["compatible_widgets"]


def test_widget_binding_must_match_card_ontology_and_version(twin_client_a, db, card_a, ontology_factory):
    pid = db.execute(text("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
                          "VALUES (:t,:c,'页',0) RETURNING id"), {"t": TENANT_A, "c": card_a}).scalar_one()
    other = ontology_factory()
    qid = db.execute(text(
        "INSERT INTO onto_ontology_query (tenant_id, ontology_id, version, code, name, result_shape, "
        "spec_json, compiled_sql, verify_status, status) VALUES (:t,:o,1,'q_x','跳本体','kpi',"
        "CAST('{\"objects\":[]}' AS jsonb),'SELECT 1','verified','enabled') RETURNING id"),
        {"t": TENANT_A, "o": other}).scalar_one()
    db.commit()
    r = twin_client_a.post(f"/api/v1/twins/pages/{int(pid)}/widgets",
                           json={"widget_key": "kpi", "title": "X", "query_id": int(qid)})
    assert r.status_code == 400 and r.json()["code"] == "TWIN_BINDING_MISMATCH"


def test_scene_widget_cannot_bind_query(twin_client_a, db, card_a, published_version):
    """scene2d 吃卡片自身的 scene_key，绑查询即拒——不给它开“看起来能用”的后门。"""
    pid = db.execute(text("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
                          "VALUES (:t,:c,'页',0) RETURNING id"), {"t": TENANT_A, "c": card_a}).scalar_one()
    qid = db.execute(text(
        "INSERT INTO onto_ontology_query (tenant_id, ontology_id, version, code, name, result_shape, "
        "spec_json, compiled_sql, verify_status, status) VALUES (:t,:o,1,'q_s','实体','entity_set',"
        "CAST('{\"objects\":[]}' AS jsonb),'SELECT 1','verified','enabled') RETURNING id"),
        {"t": TENANT_A, "o": published_version["ontology_id"]}).scalar_one()
    db.commit()
    r = twin_client_a.post(f"/api/v1/twins/pages/{int(pid)}/widgets",
                           json={"widget_key": "scene2d", "title": "园区", "query_id": int(qid)})
    assert r.status_code == 400 and r.json()["code"] == "QUERY_SHAPE_MISMATCH"


def test_layout_batch_write_is_atomic(twin_client_a, db, card_a):
    pid = db.execute(text("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
                          "VALUES (:t,:c,'页',0) RETURNING id"), {"t": TENANT_A, "c": card_a}).scalar_one()
    ids = [int(db.execute(text("INSERT INTO twin_widget (tenant_id, page_id, widget_key, title, sort_order) "
                               "VALUES (:t,:p,'kpi',:n,:s) RETURNING id"),
                          {"t": TENANT_A, "p": int(pid), "n": f"w{i}", "s": i}).scalar_one())
           for i in range(2)]
    db.commit()
    ok = twin_client_a.post(f"/api/v1/twins/pages/{int(pid)}/widgets/layout", json={
        "items": [{"widget_id": ids[0], "grid_json": {"x": 0, "y": 0, "w": 12, "h": 4}}]})
    assert ok.status_code == 200 and ok.json()[0]["grid_json"]["w"] == 12
    bad = twin_client_a.post(f"/api/v1/twins/pages/{int(pid)}/widgets/layout", json={
        "items": [{"widget_id": ids[0], "grid_json": {"x": 0, "y": 0, "w": 5, "h": 4}},
                  {"widget_id": ids[1], "grid_json": {"x": 0, "y": 4, "w": 6, "h": 4}}]})
    assert bad.status_code == 400 and bad.json()["code"] == "TWIN_LAYOUT_INVALID"
    # 原子性：第二条合法也不得落库（整批回滚）
    after = twin_client_a.get(f"/api/v1/twins/pages/{int(pid)}/widgets").json()
    assert next(w for w in after if w["id"] == ids[1])["grid_json"]["y"] == 0


def test_page_reorder_rejects_foreign_page_id(twin_client_a, db, card_a):
    pids = [int(db.execute(text("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
                                "VALUES (:t,:c,:n,:s) RETURNING id"),
                           {"t": TENANT_A, "c": card_a, "n": f"p{s}", "s": s}).scalar_one())
            for s in (0, 1)]
    db.commit()
    ok = twin_client_a.post(f"/api/v1/twins/cards/{card_a}/pages/reorder", json={"page_ids": list(reversed(pids))})
    assert ok.status_code == 200 and [p["id"] for p in ok.json()] == list(reversed(pids))
    r = twin_client_a.post(f"/api/v1/twins/cards/{card_a}/pages/reorder",
                           json={"page_ids": pids + [999999]})
    assert r.status_code == 400 and r.json()["detail"]["unknown"] == [999999]


def test_from_template_creates_unbound_widgets(twin_client_a, published_version):
    """模板只搭骨架：全部组件 query_id=NULL，回到「待绑定」空态。"""
    r = twin_client_a.post("/api/v1/twins/cards/from-template",
                           json={"template_key": "ops-line", "name": "产线看板"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["source_template_key"] == "ops-line" and body["runtime_state"] == "draft"
    pages = twin_client_a.get(f"/api/v1/twins/cards/{body['id']}/pages").json()
    widgets = twin_client_a.get(f"/api/v1/twins/pages/{pages[0]['id']}/widgets").json()
    assert len(widgets) == 3 and all(w["query_id"] is None for w in widgets)
    assert twin_client_a.post("/api/v1/twins/cards/from-template",
                             json={"template_key": "nope", "name": "x"}).json()["code"] == "TWIN_TEMPLATE_UNKNOWN"


def test_stale_flag_when_ontology_publishes_newer_version(twin_client_a, db, card_a):
    db.execute(text("UPDATE onto_ontology SET current_version = 2 WHERE id = "
                    "(SELECT ontology_id FROM twin_card WHERE id = :c)"), {"c": card_a})
    db.commit()
    assert twin_client_a.get(f"/api/v1/twins/cards/{card_a}").json()["stale"] is True
```

- [ ] **Step 3: 跑到失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/twin/test_twin_crud.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.twin'`

- [ ] **Step 4: 创建 `backend/app/services/twin/__init__.py`**

```python
"""孪生域服务：编排（twin_service）/ 取数（twin_data_service）/ 发布（twin_publish_service）/ 授权（twin_access_service）。

包内**不做**任何自动 import：四个模块分属 Task 6~9，空 `__init__` 让“导入即依赖”保持显式，
也避免先创建的服务 import 尚未创建的后继模块。
"""
```

- [ ] **Step 5: 写 `backend/app/services/twin/twin_service.py`（上半：常量 · 可见性 · 卡片）**

```python
"""编排层（spec §2.1 第 2 层）：卡片 / 页面 / 组件的结构与绑定关系。

本层**不做**的事：生成 SQL、连数据源、判断脱敏、归一形状——它们分属语义层（Task 4）
与执行/出口层（Task 7）。本层唯一的业务判断是**形状配对**：某个 `widget_key`
能不能吃某个 `result_shape`。

只维护**一张**配对表（widget_key → 允许的 result_shape）：绑定校验、错误回执与后续的
AI 受限生成（T14）都从同一张表反推候选，反向表一旦并存就会 drift。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.api_error import (
    ApiError, ONTOLOGY_NOT_FOUND, QUERY_COMPILE_FAILED, QUERY_NOT_FOUND,
    QUERY_SHAPE_MISMATCH, TWIN_ACCESS_REQUIRED, TWIN_BINDING_MISMATCH,
    TWIN_CARD_NOT_FOUND, TWIN_LAYOUT_INVALID, TWIN_NAME_DUPLICATE,
    TWIN_PAGE_NOT_FOUND, TWIN_TEMPLATE_UNKNOWN, TWIN_WIDGET_NOT_FOUND,
)
from app.models.ontology.ontology import MetaOntology, MetaOntologyVersion
from app.models.ontology.query import MetaOntologyQuery
from app.models.twin import TwinCard, TwinCardShare, TwinPage, TwinWidget
from app.models.twin.widget import WIDGET_KEYS

# 卡片可见性四档。restricted = 原型 🔒「受限」（只能看徽标与申请入口，不可取数）
ACCESS_OWNER, ACCESS_EDIT, ACCESS_READ, ACCESS_RESTRICTED = "owner", "edit", "read", "restricted"
WRITABLE_ACCESS = (ACCESS_OWNER, ACCESS_EDIT)
# 他人可见范围：live 与 paused 都是“已对外”的卡（paused = 停轮询但页面仍可访问，§10 Q3-A）
PUBLIC_STATES = ("live", "paused")

# 唯一的配对表。空元组 = 该模块不吃任何查询：scene2d 读卡片自身的 scene_key，
# scene3d 属 P1（T3），绑了就是后门，因此一律拒。
WIDGET_KEY_TO_SHAPES: Dict[str, Tuple[str, ...]] = {
    "kpi": ("kpi",),
    "trend": ("trend",),
    "bar": ("bar",),
    "donut": ("donut",),
    "alert_table": ("table", "entity_set"),
    "graph": ("graph",),
    "scene2d": (),
    "scene3d": (),
}

# 离散栅格（P0 不做自由拖拽，spec §1.2）：w 只允许 3/6/12，且不得溢出 12 列——
# “拖不动到非法位”在服务端就成立，而不是靠前端按钮藏起来。
#
# 原计划另要求「x 必须是 w 的整数倍」，实测**自相矛盾已删**（计划缺陷修正，2026-11-01）：
# 内置模板 ops-line 自己的第二个组件就是 x=3/w=6（3+6=9，后再放 w=3 正好铺满 12 列），
# 按该规则会被自己的 `_clean_grid()` 判成 TWIN_LAYOUT_INVALID，`from-template` 必然建卡失败。
# 收益（限制对齐位）远小于它否决合法紧凑布局的代价，故闸门保留“离散宽度 + 不溢出 +
# h 在范围内 + x/y 非负”，不再约束 x 与 w 的整除关系。
GRID_W_ALLOWED = (3, 6, 12)
GRID_H_RANGE = (1, 24)
GRID_COLS = 12

REFRESH_MODES = ("interval", "manual", "off")
REFRESH_INTERVALS = (10, 30, 0)          # off ⇒ interval_seconds=0
DEFAULT_REFRESH: Dict[str, Any] = {"mode": "interval", "interval_seconds": 10}

# T3 内置模板：只搭骨架（全部组件 query_id=NULL，回到原型「待绑定」空态）。
# 模板**不预建查询**：查询属于语义层且必须逐一 preview，预绑会把 R1 风险藏到运行期。
TEMPLATES: Dict[str, Dict[str, Any]] = {
    "ops-line": {
        "name": "产线运行看板", "scene_key": "factory",
        "pages": [{"name": "总览", "widgets": [
            {"widget_key": "kpi", "title": "综合效率 OEE", "grid": {"x": 0, "y": 0, "w": 3, "h": 4}},
            {"widget_key": "trend", "title": "产量趋势", "grid": {"x": 3, "y": 0, "w": 6, "h": 4}},
            {"widget_key": "alert_table", "title": "告警列表", "grid": {"x": 9, "y": 0, "w": 3, "h": 4}},
        ]}],
    },
    "energy-park": {
        "name": "园区能耗看板", "scene_key": "park",
        "pages": [
            {"name": "能耗总览", "widgets": [
                {"widget_key": "kpi", "title": "今日电费", "grid": {"x": 0, "y": 0, "w": 3, "h": 4}},
                {"widget_key": "donut", "title": "分项占比", "grid": {"x": 3, "y": 0, "w": 3, "h": 4}},
                {"widget_key": "scene2d", "title": "园区平面", "grid": {"x": 6, "y": 0, "w": 6, "h": 4}},
            ]},
            {"name": "趋势对比", "widgets": [
                {"widget_key": "trend", "title": "24h 负荷曲线", "grid": {"x": 0, "y": 0, "w": 12, "h": 6}},
            ]},
        ],
    },
}


class TwinService:
    """卡片/页面/组件的租户隔离 CRUD。写操作要求 owner 或 edit 授予。"""

    def __init__(self, db: Session, tenant_id: Optional[int], user_id: int,
                 role_codes: Sequence[str] = ()) -> None:
        if tenant_id is None:
            raise ValueError("tenant_required")
        self.db = db
        self.tenant_id = int(tenant_id)
        self.user_id = int(user_id or 0)
        self.role_codes = tuple(sorted({r for r in role_codes if r}))

    # ------------------------------------------------------------- 可见性

    def _my_shares(self) -> Dict[int, TwinCardShare]:
        """我对本租户卡片的有效授予（card_id -> share）：已过期的不算，edit 覆盖 read。"""
        conds = [and_(TwinCardShare.grantee_type == "user",
                      TwinCardShare.grantee_id == self.user_id)]
        if self.role_codes:
            conds.append(and_(TwinCardShare.grantee_type == "role",
                              TwinCardShare.grantee_code.in_(list(self.role_codes))))
        rows = self.db.execute(
            select(TwinCardShare)
            .where(TwinCardShare.tenant_id == self.tenant_id, or_(*conds),
                   # 用 DB 侧 now() 比较，不把应用时区带进 naive TIMESTAMP 列
                   or_(TwinCardShare.expires_at.is_(None), TwinCardShare.expires_at > func.now()))
        ).scalars().all()
        best: Dict[int, TwinCardShare] = {}
        for s in rows:
            key = int(s.card_id)
            if key not in best or (best[key].perm != "edit" and s.perm == "edit"):
                best[key] = s
        return best

    @staticmethod
    def _access_of(card: TwinCard, shares: Dict[int, TwinCardShare],
                   user_id: int) -> Optional[str]:
        if int(card.owner_id) == user_id:
            return ACCESS_OWNER
        sh = shares.get(int(card.id))
        if sh is not None:
            return ACCESS_EDIT if sh.perm == "edit" else ACCESS_READ
        if (card.runtime_state or "") in PUBLIC_STATES:
            return ACCESS_RESTRICTED
        return None          # 他人的 draft：不入任何列表

    def _current_versions(self, ontology_ids: set) -> Dict[int, int]:
        if not ontology_ids:
            return {}
        rows = self.db.execute(
            select(MetaOntology.id, MetaOntology.current_version)
            .where(MetaOntology.id.in_(ontology_ids))
        ).all()
        return {int(r[0]): int(r[1] or 0) for r in rows}

    def _card_dict(self, c: TwinCard, access: Optional[str],
                   current_versions: Dict[int, int]) -> dict:
        # stale：卡片钉的版落后于本体最新版（R5：只提示不自动跟随）
        cur = current_versions.get(int(c.ontology_id), 0)
        return {
            "id": int(c.id), "name": c.name, "icon": c.icon, "description": c.description,
            "source_template_key": c.source_template_key,
            "ontology_id": int(c.ontology_id), "ontology_version": int(c.ontology_version or 0),
            "ontology_current_version": cur, "stale": cur > int(c.ontology_version or 0),
            "scene_key": c.scene_key, "runtime_state": c.runtime_state,
            "owner_id": int(c.owner_id), "access": access,
            "restricted": access == ACCESS_RESTRICTED,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }

    def card_or_404(self, card_id: int) -> TwinCard:
        row = self.db.get(TwinCard, card_id)
        if row is None or int(row.tenant_id) != self.tenant_id:
            raise ApiError(TWIN_CARD_NOT_FOUND, "卡片不存在", 404)
        return row

    def _writable_card(self, card_id: int) -> TwinCard:
        card = self.card_or_404(card_id)
        access = self._access_of(card, self._my_shares(), self.user_id)
        if access not in WRITABLE_ACCESS:
            raise ApiError(TWIN_ACCESS_REQUIRED, "无权编辑该卡片", 403,
                           {"card_id": int(card.id), "access": access})
        return card

    # ------------------------------------------------------------- 卡片

    def list_cards(self) -> Dict[str, List[dict]]:
        shares = self._my_shares()
        rows = self.db.execute(
            select(TwinCard).where(TwinCard.tenant_id == self.tenant_id)
            .order_by(TwinCard.updated_at.desc(), TwinCard.id.desc())
        ).scalars().all()
        current = self._current_versions({int(r.ontology_id) for r in rows})
        out: Dict[str, List[dict]] = {"mine": [], "shared": [], "restricted": []}
        for c in rows:
            acc = self._access_of(c, shares, self.user_id)
            if acc is None:
                continue
            d = self._card_dict(c, acc, current)
            if acc == ACCESS_OWNER:
                out["mine"].append(d)
            elif acc == ACCESS_RESTRICTED:
                out["restricted"].append(d)
            else:
                out["shared"].append(d)
        return out

    def get_card(self, card_id: int) -> dict:
        card = self.card_or_404(card_id)
        acc = self._access_of(card, self._my_shares(), self.user_id)
        if acc is None:
            # 非 owner / 非共享 / 非对外：与跨租户同一信号，不用 403 泄露存在性
            raise ApiError(TWIN_CARD_NOT_FOUND, "卡片不存在", 404)
        return self._card_dict(card, acc, self._current_versions({int(card.ontology_id)}))

    def _require_published_version(self, ontology_id: int, version: int) -> None:
        ont = self.db.get(MetaOntology, ontology_id)
        if ont is None or int(ont.tenant_id) != self.tenant_id:
            raise ApiError(ONTOLOGY_NOT_FOUND, "本体不存在", 404, {"ontology_id": ontology_id})
        hit = self.db.execute(
            select(MetaOntologyVersion.id).where(
                MetaOntologyVersion.tenant_id == self.tenant_id,
                MetaOntologyVersion.ontology_id == ontology_id,
                MetaOntologyVersion.version == version)
        ).scalar_one_or_none()
        if hit is None:
            # 卡片只能钉已发布版本：只有发布才会写 onto_ontology_version 快照，
            # 钉一个不存在的版本等于允诺一个永远编译不过的卡片。
            raise ApiError(ONTOLOGY_NOT_FOUND, "本体版本不存在（仅已发布版本有快照）", 400,
                           {"ontology_id": ontology_id, "version": version})

    def create_card(self, payload: Dict[str, Any]) -> dict:
        ontology_id = int(payload["ontology_id"])
        version = int(payload["ontology_version"])
        self._require_published_version(ontology_id, version)
        card = TwinCard(
            tenant_id=self.tenant_id, name=str(payload["name"]).strip(),
            icon=payload.get("icon"), description=payload.get("description"),
            source_template_key=None, ontology_id=ontology_id, ontology_version=version,
            scene_key=payload.get("scene_key"), runtime_state="draft", owner_id=self.user_id,
        )
        self.db.add(card)
        self._commit_unique_or_409()
        self.db.refresh(card)
        return self._card_dict(card, ACCESS_OWNER, self._current_versions({ontology_id}))

    def update_card(self, card_id: int, patch: Dict[str, Any]) -> dict:
        card = self._writable_card(card_id)
        if "ontology_id" in patch or "ontology_version" in patch:
            oid = int(patch.get("ontology_id") or card.ontology_id)
            ver = int(patch.get("ontology_version") or card.ontology_version)
            self._require_published_version(oid, ver)
        # 非法 runtime_state 必须在 setattr **之前**拒（计划缺陷修正：执行时实测）：
        # 原序先赋值再校验，脏值已挂在 session 对象上；本次虽未 commit，但 SessionLocal
        # 配了 expire_on_commit=False，同会话的后续 flush 会把它写进库并撞上 ck_twin_card_state。
        if "runtime_state" in patch and patch["runtime_state"] not in ("draft", "live", "paused"):
            raise ApiError(TWIN_LAYOUT_INVALID, "runtime_state 取值非法", 400,
                           {"runtime_state": patch["runtime_state"]})
        allowed = {"name", "icon", "description", "scene_key", "runtime_state",
                   "ontology_id", "ontology_version"}
        for k, v in patch.items():
            if k in allowed:
                setattr(card, k, v)
        self._commit_unique_or_409()
        acc = self._access_of(card, self._my_shares(), self.user_id)
        return self._card_dict(card, acc, self._current_versions({int(card.ontology_id)}))

    def delete_card(self, card_id: int) -> None:
        card = self._writable_card(card_id)
        # 页面/组件/发布/共享/申请单均由 FK CASCADE 带走，不在应用层逐表删
        self.db.delete(card)
        self.db.commit()

    def create_from_template(self, template_key: str, name: str,
                             ontology_id: Optional[int] = None) -> dict:
        """T3：模板只搭骨架，卡片钉住哪个本体是调用方的事。

        `ontology_id` 省略时默认取本租户“最新已发布本体”（按 ontology_id 倒序取第一个
        有发布版本者）——演示路径上零参数可用；生产接入时前端必须显式传。
        """
        tpl = TEMPLATES.get(template_key)
        if tpl is None:
            raise ApiError(TWIN_TEMPLATE_UNKNOWN, "模板不存在", 400,
                           {"template_key": template_key, "available": sorted(TEMPLATES)})
        if ontology_id is not None:
            ont = self.db.get(MetaOntology, int(ontology_id))
            if ont is None or int(ont.tenant_id) != self.tenant_id:
                raise ApiError(ONTOLOGY_NOT_FOUND, "本体不存在", 404, {"ontology_id": ontology_id})
            version = self.db.execute(
                select(func.max(MetaOntologyVersion.version))
                .where(MetaOntologyVersion.ontology_id == ont.id)
            ).scalar_one_or_none()
        else:
            row = self.db.execute(
                select(MetaOntology, func.max(MetaOntologyVersion.version).label("v"))
                .join(MetaOntologyVersion, MetaOntologyVersion.ontology_id == MetaOntology.id)
                .where(MetaOntology.tenant_id == self.tenant_id)
                .group_by(MetaOntology.id)
                .order_by(MetaOntology.id.desc()).limit(1)
            ).first()
            if row is None:
                raise ApiError(ONTOLOGY_NOT_FOUND, "本租户无已发布本体，无法套模板", 400)
            ont, version = row[0], row[1]
        if not version:
            raise ApiError(ONTOLOGY_NOT_FOUND, "该本体尚未发布任何版本", 400,
                           {"ontology_id": int(ont.id)})
        card = TwinCard(tenant_id=self.tenant_id, name=name.strip(), icon=None,
                        description=f"由模板 {template_key} 创建",
                        source_template_key=template_key, ontology_id=int(ont.id),
                        ontology_version=int(version), scene_key=tpl["scene_key"],
                        runtime_state="draft", owner_id=self.user_id)
        self.db.add(card)
        self.db.flush()
        for pi, page_spec in enumerate(tpl["pages"]):
            page = TwinPage(tenant_id=self.tenant_id, card_id=int(card.id),
                            name=page_spec["name"], sort_order=pi,
                            refresh_json=dict(DEFAULT_REFRESH))
            self.db.add(page)
            self.db.flush()
            for wi, wspec in enumerate(page_spec["widgets"]):
                self.db.add(TwinWidget(
                    tenant_id=self.tenant_id, page_id=int(page.id),
                    widget_key=wspec["widget_key"], title=wspec["title"],
                    query_id=None, param_values_json={}, display_json={},
                    grid_json=dict(wspec["grid"]), refresh_json=None, sort_order=wi,
                ))
        self._commit_unique_or_409()
        self.db.refresh(card)
        return self._card_dict(card, ACCESS_OWNER, self._current_versions({int(ont.id)}))

    def _commit_unique_or_409(self) -> None:
        """把两个唯一约束的数据库报错翻译成人话（不外抛 500）。"""
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ApiError(TWIN_NAME_DUPLICATE, "名称重复（同租户同人卡片名/同卡页面名必须唯一）",
                           409, {"error": str(exc.orig)[:200]}) from exc
```

> 卡片重名的并发路径：`uq_twin_card_name` 在库侧兜底，应用层不先查后插（查-插之间存在窗口），
> 因此 `_commit_unique_or_409()` 是**唯一**的重名错误出口；回 409 而不是 400，
> 跟仓库已有的“资源冲突”约定对齐（`WIDGET_IN_USE` 亦为 409）。

- [ ] **Step 6: 追写 `twin_service.py`（下半：页面 · 组件 · 布局）**

接在 `_commit_unique_or_409()` 之后（仍在 `TwinService` 类内，缩进四格）：

```python
    # ------------------------------------------------------------- 页面

    def page_with_card(self, page_id: int) -> Tuple[TwinPage, TwinCard]:
        page = self.db.get(TwinPage, page_id)
        if page is None or int(page.tenant_id) != self.tenant_id:
            raise ApiError(TWIN_PAGE_NOT_FOUND, "页面不存在", 404)
        return page, self.card_or_404(int(page.card_id))

    def _writable_page(self, page_id: int) -> Tuple[TwinPage, TwinCard]:
        page, card = self.page_with_card(page_id)
        self._writable_card(int(card.id))
        return page, card

    @staticmethod
    def _page_dict(p: TwinPage, widget_count: int = 0) -> dict:
        return {"id": int(p.id), "card_id": int(p.card_id), "name": p.name,
                "sort_order": int(p.sort_order or 0), "refresh_json": p.refresh_json,
                "widget_count": widget_count,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None}

    def list_pages(self, card_id: int) -> List[dict]:
        self.get_card(card_id)                      # 可读校验（不可读 → 404）
        rows = self.db.execute(
            select(TwinPage, func.count(TwinWidget.id))
            .outerjoin(TwinWidget, TwinWidget.page_id == TwinPage.id)
            .where(TwinPage.card_id == card_id)
            .group_by(TwinPage.id)
            .order_by(TwinPage.sort_order, TwinPage.id)
        ).all()
        return [self._page_dict(r[0], int(r[1])) for r in rows]

    def create_page(self, card_id: int, name: str,
                    refresh_json: Optional[dict] = None) -> dict:
        self._writable_card(card_id)
        page = TwinPage(tenant_id=self.tenant_id, card_id=card_id, name=name.strip(),
                        sort_order=int(self.db.query(func.count(TwinPage.id))
                                       .filter(TwinPage.card_id == card_id).scalar() or 0),
                        refresh_json=self._clean_refresh(refresh_json))
        self.db.add(page)
        self._commit_unique_or_409()
        self.db.refresh(page)
        return self._page_dict(page)

    def update_page(self, page_id: int, patch: Dict[str, Any]) -> dict:
        page, _ = self._writable_page(page_id)
        if "name" in patch:
            page.name = str(patch["name"]).strip()
        if "refresh_json" in patch:
            page.refresh_json = self._clean_refresh(patch["refresh_json"])
        self._commit_unique_or_409()
        self.db.refresh(page)
        return self._page_dict(page)

    def delete_page(self, page_id: int) -> None:
        page, _ = self._writable_page(page_id)
        self.db.delete(page)
        self.db.commit()

    def reorder_pages(self, card_id: int, page_ids: List[int]) -> List[dict]:
        self._writable_card(card_id)
        existing = {int(p.id) for p in self.db.execute(
            select(TwinPage).where(TwinPage.card_id == card_id)
        ).scalars().all()}
        wanted = [int(x) for x in page_ids]
        unknown = [x for x in wanted if x not in existing]
        if unknown:
            raise ApiError(TWIN_PAGE_NOT_FOUND, "页序包含非本卡页面", 400,
                           {"unknown": unknown, "expected": sorted(existing)})
        if len(set(wanted)) != len(existing):
            raise ApiError(TWIN_PAGE_NOT_FOUND, "页序必须覆盖该卡全部页面且不重复", 400,
                           {"given": wanted, "existing_count": len(existing)})
        for idx, pid in enumerate(wanted):
            self.db.execute(TwinPage.__table__.update().where(TwinPage.id == pid)
                            .values(sort_order=idx))
        self.db.commit()
        # Core 批量 UPDATE 不会同步 ORM identity map（上面 `select(TwinPage)` 已把行载入），
        # 而 SessionLocal 是 `expire_on_commit=False`——不显式 expire 就会把内存里的旧 sort_order
        # 当作重读结果返回（计划缺陷修正：执行时实测）。
        self.db.expire_all()
        return self.list_pages(card_id)

    @staticmethod
    def _clean_refresh(raw: Optional[dict]) -> dict:
        """刷新档位只能落在三档上（§4.3：“实时”= 最短 10s 轮询，不是推送）。"""
        if not raw:
            return dict(DEFAULT_REFRESH)
        mode = str(raw.get("mode", "interval"))
        if mode not in REFRESH_MODES:
            raise ApiError(TWIN_LAYOUT_INVALID, "refresh.mode 取值非法", 400,
                           {"mode": mode, "allowed": list(REFRESH_MODES)})
        secs = int(raw.get("interval_seconds", 10))
        if mode == "interval" and secs not in (10, 30):
            raise ApiError(TWIN_LAYOUT_INVALID, "interval 仅允许 10/30 秒", 400,
                           {"interval_seconds": secs, "allowed": [10, 30]})
        if mode in ("manual", "off"):
            secs = 0
        return {"mode": mode, "interval_seconds": secs}

    # ------------------------------------------------------------- 组件

    @staticmethod
    def _widget_dict(w: TwinWidget) -> dict:
        return {"id": int(w.id), "page_id": int(w.page_id), "widget_key": w.widget_key,
                "title": w.title, "query_id": int(w.query_id) if w.query_id else None,
                "param_values_json": w.param_values_json, "display_json": w.display_json,
                "grid_json": w.grid_json, "refresh_json": w.refresh_json,
                "sort_order": int(w.sort_order or 0),
                "updated_at": w.updated_at.isoformat() if w.updated_at else None}

    def list_widgets(self, page_id: int) -> List[dict]:
        page, card = self.page_with_card(page_id)
        self.get_card(int(card.id))                 # 可读校验
        rows = self.db.execute(
            select(TwinWidget).where(TwinWidget.page_id == int(page.id))
            .order_by(TwinWidget.sort_order, TwinWidget.id)
        ).scalars().all()
        return [self._widget_dict(w) for w in rows]

    @staticmethod
    def _clean_grid(grid: Optional[dict]) -> dict:
        g = grid or {}
        x, y, w, h = (int(g.get("x", 0)), int(g.get("y", 0)),
                      int(g.get("w", 6)), int(g.get("h", 4)))
        bad: Dict[str, Any] = {}
        if w not in GRID_W_ALLOWED:
            bad["w"] = f"{w} 不在 {GRID_W_ALLOWED}"
        if not (GRID_H_RANGE[0] <= h <= GRID_H_RANGE[1]):
            bad["h"] = f"{h} 不在 {GRID_H_RANGE}"
        if x < 0:
            bad["x"] = f"{x} 不得为负"
        elif x + w > GRID_COLS:
            bad["x"] = f"x={x} 与 w={w} 溢出 {GRID_COLS} 列"
        if y < 0:
            bad["y"] = f"{y} 不得为负"
        if bad:
            raise ApiError(TWIN_LAYOUT_INVALID, "栅格位非法", 400,
                           {"grid": {"x": x, "y": y, "w": w, "h": h}, "violations": bad})
        return {"x": x, "y": y, "w": w, "h": h}

    def _validate_binding(self, card: TwinCard, widget_key: str,
                          query_id: Optional[int]) -> Tuple[Optional[MetaOntologyQuery], Tuple[str, ...]]:
        """绑定三验：同一个本体+版本 → 已编译通过 → 形状配对（§5.2 第 2/3 闸）。"""
        allowed_shapes = WIDGET_KEY_TO_SHAPES[widget_key]
        if query_id is None:
            return None, allowed_shapes
        q = self.db.get(MetaOntologyQuery, int(query_id))
        if q is None or int(q.tenant_id) != self.tenant_id:
            raise ApiError(QUERY_NOT_FOUND, "查询定义不存在", 404, {"query_id": query_id})
        if int(q.ontology_id) != int(card.ontology_id) or int(q.version) != int(card.ontology_version):
            raise ApiError(TWIN_BINDING_MISMATCH, "查询不属于卡片钉住的本体+版本", 400,
                           {"query_id": int(q.id), "query_ontology": int(q.ontology_id),
                            "query_version": int(q.version),
                            "card_ontology": int(card.ontology_id),
                            "card_version": int(card.ontology_version)})
        if q.verify_status != "verified" or not q.compiled_sql:
            raise ApiError(QUERY_COMPILE_FAILED, "查询未通过编译，请先 preview", 400,
                           {"query_id": int(q.id), "verify_status": q.verify_status,
                            "verify_detail": q.verify_detail_json})
        return q, allowed_shapes

    def add_widget(self, page_id: int, payload: Dict[str, Any]) -> dict:
        page, card = self._writable_page(page_id)
        widget_key = str(payload["widget_key"])
        if widget_key not in WIDGET_KEYS:
            raise ApiError(QUERY_SHAPE_MISMATCH, "模块类型不存在", 400,
                           {"widget_key": widget_key, "allowed": list(WIDGET_KEYS)})
        q, allowed_shapes = self._validate_binding(card, widget_key, payload.get("query_id"))
        if q is not None and q.result_shape not in allowed_shapes:
            # W9：错误原因必须可读——给出不匹配的两个值 + 本查询可用的组件清单
            raise ApiError(QUERY_SHAPE_MISMATCH,
                           f"查询结果形状 {q.result_shape} 与组件 {widget_key} 不配对", 400,
                           {"widget_key": widget_key, "result_shape": q.result_shape,
                            "expected_shapes": list(allowed_shapes),
                            "compatible_widgets": self._widgets_for_shape(q.result_shape),
                            "query_code": q.code, "query_name": q.name})
        w = TwinWidget(
            tenant_id=self.tenant_id, page_id=int(page.id), widget_key=widget_key,
            title=str(payload.get("title") or (q.name if q else widget_key)).strip(),
            query_id=int(q.id) if q else None,
            param_values_json=payload.get("param_values_json") or {},
            display_json=payload.get("display_json") or {},
            grid_json=self._clean_grid(payload.get("grid_json")),
            refresh_json=(self._clean_refresh(payload["refresh_json"])
                          if payload.get("refresh_json") else None),
            sort_order=int(self.db.query(func.count(TwinWidget.id))
                           .filter(TwinWidget.page_id == int(page.id)).scalar() or 0),
        )
        self.db.add(w)
        self.db.commit()
        self.db.refresh(w)
        return self._widget_dict(w)

    @staticmethod
    def _widgets_for_shape(shape: str) -> List[str]:
        return sorted(k for k, v in WIDGET_KEY_TO_SHAPES.items() if shape in v)

    def widget_or_404(self, widget_id: int) -> TwinWidget:
        w = self.db.get(TwinWidget, widget_id)
        if w is None or int(w.tenant_id) != self.tenant_id:
            raise ApiError(TWIN_WIDGET_NOT_FOUND, "组件不存在", 404)
        return w

    def update_widget(self, widget_id: int, patch: Dict[str, Any]) -> dict:
        w = self.widget_or_404(widget_id)
        _, card = self._writable_page(int(w.page_id))
        # PATCH 语义：exclude_unset 而非 exclude_none——前端清空绑定会显式发 query_id=null
        if "query_id" in patch:
            q, allowed_shapes = self._validate_binding(card, w.widget_key, patch["query_id"])
            if q is not None and q.result_shape not in allowed_shapes:
                raise ApiError(QUERY_SHAPE_MISMATCH, "改绑后形状不配对", 400,
                               {"widget_key": w.widget_key, "result_shape": q.result_shape,
                                "compatible_widgets": self._widgets_for_shape(q.result_shape)})
            w.query_id = int(q.id) if q else None
            if q is None:
                w.param_values_json = {}            # 解绑同时丢实值，避免旧参数默默长在新绑定上
        for src, dst in (("title", "title"), ("widget_key", "widget_key"),
                         ("param_values_json", "param_values_json"),
                         ("display_json", "display_json")):
            if src in patch:
                setattr(w, dst, patch[src])
        if "grid_json" in patch:
            w.grid_json = self._clean_grid(patch["grid_json"])
        if "refresh_json" in patch:
            w.refresh_json = self._clean_refresh(patch["refresh_json"]) if patch["refresh_json"] else None
        self.db.commit()
        self.db.refresh(w)
        return self._widget_dict(w)

    def delete_widget(self, widget_id: int) -> None:
        w = self.widget_or_404(widget_id)
        self._writable_page(int(w.page_id))
        self.db.delete(w)
        self.db.commit()

    def save_layout(self, page_id: int, items: List[Dict[str, Any]]) -> List[dict]:
        """T7：拖拽/自动布局/AI 应用共用同一个写入口（确定性的批量写）。"""
        self._writable_page(page_id)
        # 两阶段：先全量校验后落库，自然得到原子性（无需中途 rollback）
        cleaned = []
        for it in items:
            wid = int(it["widget_id"])
            w = self.widget_or_404(wid)
            if int(w.page_id) != int(page_id):
                raise ApiError(TWIN_WIDGET_NOT_FOUND, "组件不属于该页面", 400,
                               {"widget_id": wid, "page_id": int(w.page_id)})
            cleaned.append((wid, self._clean_grid(it["grid_json"])))
        for wid, grid in cleaned:
            self.db.execute(TwinWidget.__table__.update().where(TwinWidget.id == wid)
                            .values(grid_json=grid))
        self.db.commit()
        # 同 reorder_pages：校验期的 `widget_or_404()` 已把这些组件载入 identity map，
        # 而 session 配了 `expire_on_commit=False`，不 expire 就会返回旧的栅格位。
        # （本行由 `test_layout_batch_write_is_atomic` 实测拓出：缺它则 `w == 6` 而非 12。）
        self.db.expire_all()
        return self.list_widgets(page_id)
```

- [ ] **Step 7: 创建 `backend/app/routers/twin/__init__.py` 与 `twin.py`**

`__init__.py`：

```python
"""孪生应用路由（Task 6 编排端点，Task 8 只读发布端点）。"""
```

`twin.py`：

```python
"""孪生应用编排端点 T1～T7（spec §6.1）。

完整前缀写在 router 自身（与 `app.routers.kb.kg:26` 同律），因此 `router_registry`
的 `RouterSpec` 不再叠加 prefix。路径参数一律标 `int`，因此 `/cards/{card_id}`
与 `/cards/from-template` 不会互相遮蔽（字面路径优先由 Starlette 的注册顺序决定，
因此把字面最具体的端点放在参数量端点之前）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.tool_manager.tool_context import build_user_context
from app.core.api_error import ApiError, TWIN_TENANT_REQUIRED
from app.deps import get_current_user, get_db
from app.models.sys.sys_user import SysUser
from app.services.twin.twin_service import TEMPLATES, TwinService

router = APIRouter(prefix="/api/v1/twins", tags=["孪生应用"])


def _require_tenant_id(current_user: SysUser) -> int:
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise ApiError(TWIN_TENANT_REQUIRED, "登录用户缺少租户上下文", 400)
    return int(tenant_id)


def _svc(db: Session, current_user: SysUser) -> TwinService:
    """角色码走 `build_user_context()`（失败降级为最小权限），不自己拼 SQL 查 sys_role。"""
    ctx = build_user_context(db, current_user)
    return TwinService(db, _require_tenant_id(current_user),
                       int(getattr(current_user, "user_id", 0) or 0),
                       tuple(ctx.role_codes) if ctx else ())


class CardCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    icon: Optional[str] = Field(None, max_length=32)
    description: Optional[str] = None
    ontology_id: int
    ontology_version: int = Field(..., ge=1, description="只能钉已发布版本")
    scene_key: Optional[str] = Field(None, max_length=64)


class CardPatchBody(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    icon: Optional[str] = Field(None, max_length=32)
    description: Optional[str] = None
    scene_key: Optional[str] = Field(None, max_length=64)
    runtime_state: Optional[str] = Field(None, description="draft|live|paused")
    ontology_id: Optional[int] = None
    ontology_version: Optional[int] = Field(None, ge=1)


class TemplateBody(BaseModel):
    template_key: str = Field(..., description=f"内置模板：{sorted(TEMPLATES)}")
    name: str = Field(..., min_length=1, max_length=200)
    ontology_id: Optional[int] = None


class PageCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    refresh_json: Optional[Dict[str, Any]] = None


class PagePatchBody(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    refresh_json: Optional[Dict[str, Any]] = None


class ReorderBody(BaseModel):
    page_ids: List[int] = Field(..., min_length=1)


class WidgetCreateBody(BaseModel):
    widget_key: str = Field(..., min_length=1, max_length=32)
    title: Optional[str] = Field(None, max_length=200)
    query_id: Optional[int] = None
    param_values_json: Dict[str, Any] = Field(default_factory=dict)
    display_json: Dict[str, Any] = Field(default_factory=dict)
    grid_json: Dict[str, Any] = Field(default_factory=dict)
    refresh_json: Optional[Dict[str, Any]] = None


class WidgetPatchBody(BaseModel):
    widget_key: Optional[str] = Field(None, max_length=32)
    title: Optional[str] = Field(None, max_length=200)
    query_id: Optional[int] = None          # 显式 null = 解绑（因此端点用 exclude_unset）
    param_values_json: Optional[Dict[str, Any]] = None
    display_json: Optional[Dict[str, Any]] = None
    grid_json: Optional[Dict[str, Any]] = None
    refresh_json: Optional[Dict[str, Any]] = None


class LayoutItem(BaseModel):
    widget_id: int
    grid_json: Dict[str, Any]


class LayoutBody(BaseModel):
    items: List[LayoutItem] = Field(..., min_length=1, max_length=64)


# ---------------------------------------------------------------- T1–T3 卡片


@router.get("/cards")
def list_cards(db: Session = Depends(get_db),
               current_user: SysUser = Depends(get_current_user)) -> dict:
    """三组分派：我的 / 共享给我的 / 受限（原型左标 `_myCards` 与 🔒 徽标）。"""
    return _svc(db, current_user).list_cards()


@router.post("/cards/from-template", status_code=201)
def create_from_template(body: TemplateBody, db: Session = Depends(get_db),
                         current_user: SysUser = Depends(get_current_user)) -> dict:
    return _svc(db, current_user).create_from_template(
        body.template_key, body.name, body.ontology_id)


@router.post("/cards", status_code=201)
def create_card(body: CardCreateBody, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)) -> dict:
    return _svc(db, current_user).create_card(body.model_dump())


@router.get("/cards/{card_id}")
def get_card(card_id: int, db: Session = Depends(get_db),
             current_user: SysUser = Depends(get_current_user)) -> dict:
    return _svc(db, current_user).get_card(card_id)


@router.patch("/cards/{card_id}")
def update_card(card_id: int, body: CardPatchBody, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)) -> dict:
    return _svc(db, current_user).update_card(card_id, body.model_dump(exclude_unset=True))


@router.delete("/cards/{card_id}", status_code=204)
def delete_card(card_id: int, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)) -> Response:
    _svc(db, current_user).delete_card(card_id)
    return Response(status_code=204)


# ------------------------------------------------------------------- T4 页面


@router.get("/cards/{card_id}/pages")
def list_pages(card_id: int, db: Session = Depends(get_db),
               current_user: SysUser = Depends(get_current_user)) -> list:
    return _svc(db, current_user).list_pages(card_id)


@router.post("/cards/{card_id}/pages", status_code=201)
def create_page(card_id: int, body: PageCreateBody, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)) -> dict:
    return _svc(db, current_user).create_page(card_id, body.name, body.refresh_json)


@router.post("/cards/{card_id}/pages/reorder")
def reorder_pages(card_id: int, body: ReorderBody, db: Session = Depends(get_db),
                  current_user: SysUser = Depends(get_current_user)) -> list:
    return _svc(db, current_user).reorder_pages(card_id, body.page_ids)


@router.patch("/pages/{page_id}")
def update_page(page_id: int, body: PagePatchBody, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)) -> dict:
    return _svc(db, current_user).update_page(page_id, body.model_dump(exclude_unset=True))


@router.delete("/pages/{page_id}", status_code=204)
def delete_page(page_id: int, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)) -> Response:
    _svc(db, current_user).delete_page(page_id)
    return Response(status_code=204)


# -------------------------------------------------------------- T5–T7 组件


@router.get("/pages/{page_id}/widgets")
def list_widgets(page_id: int, db: Session = Depends(get_db),
                 current_user: SysUser = Depends(get_current_user)) -> list:
    return _svc(db, current_user).list_widgets(page_id)


@router.post("/pages/{page_id}/widgets", status_code=201)
def add_widget(page_id: int, body: WidgetCreateBody, db: Session = Depends(get_db),
               current_user: SysUser = Depends(get_current_user)) -> dict:
    return _svc(db, current_user).add_widget(page_id, body.model_dump(exclude_unset=True))


@router.post("/pages/{page_id}/widgets/layout")
def save_layout(page_id: int, body: LayoutBody, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)) -> list:
    """拖拽、自动布局与 AI 应用共用本口（确定性批量写，可整体回滚）。"""
    return _svc(db, current_user).save_layout(
        page_id, [it.model_dump() for it in body.items])


@router.patch("/widgets/{widget_id}")
def update_widget(widget_id: int, body: WidgetPatchBody, db: Session = Depends(get_db),
                  current_user: SysUser = Depends(get_current_user)) -> dict:
    return _svc(db, current_user).update_widget(widget_id, body.model_dump(exclude_unset=True))


@router.delete("/widgets/{widget_id}", status_code=204)
def delete_widget(widget_id: int, db: Session = Depends(get_db),
                  current_user: SysUser = Depends(get_current_user)) -> Response:
    _svc(db, current_user).delete_widget(widget_id)
    return Response(status_code=204)
```

- [ ] **Step 8: 挂载 router**

`backend/app/core/router_registry.py` 的 `ROUTER_SPECS` 列表末尾（`:216` 的 `admin_voice_config` 之后、`]` 之前）追加：

```python
    # --- 33. 孪生应用（自带完整 prefix /api/v1/twins，故此处不叠加）---
    # Task 8 会在同一模块再加一条 attr="publish_router"（先例：app.routers.kb.kg 的
    # router + build_router 两条目，:202/:204），本期先不声明尚未存在的 publish_router。
    RouterSpec("app.routers.twin.twin", attr="router", tags=["孪生应用"]),
```

- [ ] **Step 9: 跑到通过 + 启动不报错**

Run: `.\.venv\Scripts\python.exe -m pytest tests/twin/test_twin_crud.py -v`
Expected: PASS（12 passed）。失败时的排查序：

1. `TWIN_ACCESS_REQUIRED` 未定义 → Task 4 Step 1 的常量块没插对位置（必须在 `CONFIRM_EXPIRED` 之后）；
2. `test_stale_flag_...` 拿到 `stale: false` → `_current_versions()` 漏了 `current_version` 或 UPDATE 后未 `db.commit()`；
3. `test_layout_batch_write_is_atomic` 第二条写入了 → 把校验和写库混在同一次循环里了（必须两阶段）；
4. 405/404 路由找不到 → `router_registry` 条目没加，或 `router` 自身 prefix 被叠加了两次。

> 执行时补记（2026-11-01）：Step 3 的实际红灯信号是 `ModuleNotFoundError: No module named 'app.routers.twin'`
> 而非计划预期的 `'app.services.twin'`，因为 `tests/twin/conftest.py::build_client(with_twin=True)` 比服务更早 import；
> 两者同一事实（目标模块不存在），红灯成立。

Run: `.\.venv\Scripts\python.exe -c "import app.main; print('router load ok')"`
Expected: 输出 `router load ok`，且日志无 `路由模块加载失败: app.routers.twin.twin`

- [ ] **Step 10: 提交**

```bash
git add backend/app/core/api_error.py backend/app/services/twin backend/app/routers/twin backend/app/core/router_registry.py backend/tests/twin/test_twin_crud.py
git commit -m "feat(twin): card/page/widget orchestration with shape pairing gate"
```

#### Task 6 执行记录（2026-11-01）

实测结果：`tests/twin/test_twin_crud.py` **12 passed**；`import app.main` 输出 `router load ok`
（路由注册 45 个成功 / 0 跳过，无 `路由模块加载失败`）；回归 `tests/twin` 20 passed、
`tests/ontology` 79 passed、`tests/dataops` 127 passed / 10 skipped（均按目录分跑，原因见 Task 5 Step 6 注）。

发现并修正的 5 处计划缺陷（代码已就地改定，本节只存目）：

1. **测试文件缺 `from sqlalchemy.orm import Session`**——夹具签名 `db: Session` 在模块定义期即 NameError（无
   `from __future__ import annotations` 时注解立即求值），整文件无法收集。
2. **夹具的 `onto_ontology_query` INSERT 缺 `compiled_sql`**——绑定三验的顺序是「同本体+版本 → 已编译 → 形状」，
   无产物会被 `QUERY_COMPILE_FAILED` 先拦，导致 `test_widget_shape_mismatch_...` 与
   `test_scene_widget_cannot_bind_query` 拿不到预期的 `QUERY_SHAPE_MISMATCH`。修在**夹具侧**（补
   `compiled_sql,'SELECT 1'`）而非放宽闸门：`verify_status='verified'` 而无产物在生产上不可能存在。
3. **栅格规则「x 必须是 w 的整数倍」与内置模板自相矛盾**——ops-line 的 trend 就是 x=3/w=6，`from-template`
   会被自家 `_clean_grid()` 拒掉。已删该约束，保留「离散宽度 + 不溢出 12 列 + h 范围 + x/y 非负」。
4. **`save_layout` / `reorder_pages` 返回脏数据（真实生产缺陷，非仅测试）**——Core 批量 UPDATE 不同步
   ORM identity map，而 `app/db/database.py:42` 的 `SessionLocal` 配了 `expire_on_commit=False`，
   重读拿到旧值（由 `test_layout_batch_write_is_atomic` 抓出：`w == 6` 而非 12）。修法：commit 后
   `self.db.expire_all()` 再重读。`reorder_pages` 同病（它先 `select(TwinPage)` 载入了行）但既有断言只看 id
   序列以故未被发现。
5. **`update_card` 先 `setattr` 后校验 `runtime_state`**——脏值会留在 session 上（同一
   `expire_on_commit=False` 配位），同会话后续 flush 将撞上 `ck_twin_card_state`。已把校验提到赋值之前。

另有两处文档修正：Step 1 标题写「三个错误码」但代码块列了 5 个（已改「五个」）；Step 3 的预期红灯
`'app.services.twin'` 实际为 `'app.routers.twin'`（conftest 更早 import，同一事实）。

未采纳的候选改造（留给后续）：`add_widget` 内两次 `self.db.commit()` 与 `_commit_unique_or_409()` 混用
（组件表无唯一约束，所以不致错），不构成功能缺陷。

---

### Task 7: 批量取数服务（扇出闸门 · 角色签名缓存 · 出口脱敏 · 四态）T8–T9

对应 **P0-4**（验收 W8 / W11）。本任务不新增一张表、不新增一行 SQL 生成代码：
它的全部价值在于把【编排→语义→执行→出口】四层串成一条**不会把未脱敏值泄露给缓存**的链路。

**Files:**
- Modify: `backend/app/core/api_error.py`（在 Task 6 追加的 `TWIN_TENANT_REQUIRED` 之后补三个码）
- Create: `backend/app/services/twin/twin_data_service.py`
- Modify: `backend/app/routers/twin/twin.py`（末尾追加 `DataBody`、`_data_svc()` 与 T8/T9 两个端点；**不新建 router 文件**，T8/T9 同一前缀同一鉴权链）
- Test: `backend/tests/twin/test_twin_data.py`

**Interfaces:**
- Consumes: Task 3 `ReadonlyQueryService(db, tenant_id).run(source_id, sql, limit=100, params=None, params_declared=None) -> {columns, rows, row_count, truncated}`；Task 4 模块级 `shape_result(shape, records, columns) -> dict`；Task 5 `TTLCache` 与 `make_key(*parts)`；Task 6 `TwinService.page_with_card/get_card/widget_or_404` 与常量 `ACCESS_RESTRICTED`；库内纯函数 `apply_masking(rows, masking, user) -> (rows, applied_fields)`、`MaskingConfig.model_validate`；`build_user_context(db, user) -> Optional[ToolUserContext]`
- Produces: 模块常量 `FANOUT_MAX=4`、`QUERY_TIMEOUT_S=5.0`、`PAGE_DEADLINE_S=8.0`、`CACHE_TTL_S=10.0`、`DATA_ROW_LIMIT=200`、`STATE_{OK,EMPTY,ERROR,MASKED}`、`REASON_{UNBOUND,ZERO_ROWS}`；函数 `param_sha(values) -> str`、`role_signature(ctx) -> str`、`data_cache_key(tenant_id, query_id, param_digest, sql_sha256, role_sig) -> str`、`reset_data_cache() -> None`；`WidgetSpec(widget_id, widget_key, title, query_id, param_values, grid, refresh, base_params)` + `WidgetSpec.from_row(TwinWidget)` + `WidgetSpec.from_snapshot(dict)`；`TwinDataService(db, tenant_id, user_id, ctx=None, session_factory=None)` 方法 `load_page(page_id, page_params=None) -> dict`、`load_widget(widget_id, params=None) -> dict`、`execute_specs(specs: list[WidgetSpec]) -> list[dict]`（Task 8 发布快照通道直接复用后两者）；错误码常量 `TWIN_DATA_TIMEOUT`、`TWIN_DATA_FAILED`、`TWIN_QUERY_DISABLED`

**组件结果项的统一键**（前端 `WidgetShell` 四态的唯一契约，**所有分支必须凑齐这 15 个键**）：

```
widget_id, widget_key, title, query_id, state, reason, result_shape,
columns, data, row_count, truncated, masked_fields, error, cached, updated_at
```

- [ ] **Step 1: 补三个错误码**

在 `backend/app/core/api_error.py` 中 Task 6 追加的 `TWIN_TENANT_REQUIRED` 之后插入：

```python
TWIN_DATA_TIMEOUT = "TWIN_DATA_TIMEOUT"          # 单组件超闸门（> QUERY_TIMEOUT_S 或整页 deadline）
TWIN_DATA_FAILED = "TWIN_DATA_FAILED"            # 执行层异常 / 脱敏配置非法（fail-closed）
TWIN_QUERY_DISABLED = "TWIN_QUERY_DISABLED"      # 绑定的查询定义已被 owner 停用
```

> 三个码**只出现在组件结果项的 `error.code` 里**（整页请求本身仍回 200），
> 除非卡片不可读（403）或页面不存在（404）。这是 spec §4.3「超时组件各自回 error 态，
> **绝不让整页失败**」的直接体现。

- [ ] **Step 2: 写失败测试**

创建 `backend/tests/twin/test_twin_data.py`：

```python
"""批量取数：四态、扇出超时、出口脱敏与**缓存键含角色签名**（spec §4.3 / W8 / W11）。

测试分两层：
- **服务层**（直接 `TwinDataService(...)`）：凡是与**角色**有关的断言全部在此层——
  `tests/twin/conftest.py` 的 `_fake_user()` 不落 `sys_role` 行，走 HTTP 拿到的
  `role_codes` 恒为空，无法构造“豁免 / 不豁免”两个用户（为了不往测试库里灌权限表，
  也不把 `build_user_context()` monkeypatch 成说谎的样子）。
- **HTTP 层**（`twin_client_a`）：只验端点形状、逐组件隔离与权限门。

执行层 `ReadonlyQueryService` 整体打桩（本任务测的是**编排**，不是 SQL 执行；
真实直连已由 Task 4 的 `demo_env` 夹具覆盖）。
"""
import time

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.tool_manager.tool_context import ToolUserContext
from app.models.twin import TwinWidget
from app.services.twin import twin_data_service as td
from app.services.twin.twin_data_service import (
    TwinDataService, data_cache_key, param_sha, reset_data_cache, role_signature,
)
from tests.twin.conftest import TENANT_A, TENANT_B


class FakeQueryService:
    """执行层桩：按类属性返回固定结果，并把每次调用记进 `calls`。"""

    calls = []
    payload = {"columns": ["oee"], "rows": [[0.85]], "row_count": 1, "truncated": False}
    raise_for = None      # sql 含此子串 → 抛异常（单组件失败不拖垮整页）
    sleep_for = None      # sql 含此子串 → 睡 0.3s（命中超时闸门）

    def __init__(self, db, tenant_id):
        self.db, self.tenant_id = db, tenant_id

    def run(self, source_id, sql, limit=100, params=None, params_declared=None):
        cls = FakeQueryService
        cls.calls.append({"source_id": source_id, "sql": sql, "params": params or {}, "limit": limit})
        if cls.raise_for and cls.raise_for in sql:
            raise RuntimeError("源库连接失败")
        if cls.sleep_for and cls.sleep_for in sql:
            time.sleep(0.3)
        return dict(cls.payload)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """每个用例一份干净缓存 + 零调用记录 + 桩上执行层。"""
    reset_data_cache()
    FakeQueryService.calls, FakeQueryService.payload = [], {"columns": ["oee"], "rows": [[0.85]],
                                                            "row_count": 1, "truncated": False}
    FakeQueryService.raise_for = FakeQueryService.sleep_for = None
    monkeypatch.setattr(td, "ReadonlyQueryService", FakeQueryService)
    yield
    reset_data_cache()


@pytest.fixture
def env(db):
    """卡（owner=101）+ 页 + 3 组件：kpi 绑 q_kpi、trend 绑 q_trend、scene2d 未绑定。"""
    ex = lambda s, p=None: db.execute(text(s), p or {})  # noqa: E731
    oid = int(ex("INSERT INTO onto_ontology (tenant_id, code, name, status, current_version) "
                 "VALUES (:t, gen_random_uuid()::text, '本体', 'published', 1) RETURNING id",
                 {"t": TENANT_A}).scalar_one())
    cid = int(ex("INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, "
                 "runtime_state, owner_id) VALUES (:t, '设别卡', :o, 1, 'live', 101) RETURNING id",
                 {"t": TENANT_A, "o": oid}).scalar_one())
    pid = int(ex("INSERT INTO twin_page (tenant_id, card_id, name, sort_order, refresh_json) "
                 "VALUES (:t, :c, '总览', 0, CAST(:r AS jsonb)) RETURNING id",
                 {"t": TENANT_A, "c": cid,
                  "r": '{"mode":"interval","interval_seconds":10}'}).scalar_one())

    def add_query(code, shape, sql, **kw):
        return int(ex(
            "INSERT INTO onto_ontology_query (tenant_id, ontology_id, version, code, name, "
            "result_shape, spec_json, params_json, compiled_sql, sql_sha256, source_id, "
            "mask_rules_json, verify_status, status) VALUES "
            "(:t, :o, 1, :code, :name, :shape, CAST('{}' AS jsonb), CAST(:pj AS jsonb), :sql, "
            ":sha, 999, CAST(:mr AS jsonb), :verify, :status) RETURNING id",
            {"t": TENANT_A, "o": oid, "code": code, "name": code, "shape": shape,
             "pj": kw.get("params_json", '[{"name":"line","type":"string"}]'),
             "sql": sql, "sha": f"sha-{code}",
             "mr": kw.get("mask_rules", "null"),
             "verify": kw.get("verify", "verified"), "status": kw.get("status", "enabled")},
        ).scalar_one())

    def add_widget(page_id, key, qid, order, params=None):
        return int(ex(
            "INSERT INTO twin_widget (tenant_id, page_id, widget_key, title, query_id, "
            "param_values_json, grid_json, sort_order) VALUES "
            "(:t, :p, :k, :n, :q, CAST(:pv AS jsonb), CAST(:g AS jsonb), :s) RETURNING id",
            {"t": TENANT_A, "p": page_id, "k": key, "n": f"{key}-{order}", "q": qid,
             "pv": params or "null", "g": '{"x":0,"y":0,"w":6,"h":4}', "s": order}).scalar_one())

    q_kpi = add_query("q_kpi", "kpi", "SELECT oee FROM demo_device_stat")
    q_trend = add_query("q_trend", "trend", "SELECT ts FROM demo_line_trend",
                        params_json='[{"name":"line","type":"string"},'
                                    '{"name":"site","type":"string"}]')
    w_kpi = add_widget(pid, "kpi", q_kpi, 0, '{"line":"L1"}')
    w_trend = add_widget(pid, "trend", q_trend, 1)
    w_scene = add_widget(pid, "scene2d", None, 2)
    db.commit()
    return {"ontology_id": oid, "card_id": cid, "page_id": pid, "q_kpi": q_kpi,
            "q_trend": q_trend, "w_kpi": w_kpi, "w_trend": w_trend, "w_scene": w_scene}


def svc(db, ctx=None, tenant_id=TENANT_A, user_id=101):
    """绑定到**测试引擎**的会话工厂：工作线程不得复用 `db`（Session 非线程安全）。"""
    bind = db.get_bind()
    return TwinDataService(db, tenant_id, user_id, ctx,
                           session_factory=lambda: Session(bind, expire_on_commit=False))


def ctx_of(*roles, is_admin=False):
    return ToolUserContext(user_id=101, username="u-101", is_admin=is_admin, role_codes=roles)


def by_widget(items):
    return {i["widget_id"]: i for i in items}


# ------------------------------------------------------------------ 四态

def specs_of(db, env, *wids):
    """把库里的组件行转成取数请求（Task 8 的快照通道走同一类型）。"""
    return [td.WidgetSpec.from_row(db.get(TwinWidget, w)) for w in wids]


def set_query(db, qid, col, value, as_json=False):
    """改一行查询定义。JSONB 列必须显式 CAST，否则 PG 报“表达式类型是 varchar”。"""
    cast = "CAST(:v AS jsonb)" if as_json else ":v"
    db.execute(text(f"UPDATE onto_ontology_query SET {col} = {cast} WHERE id = :i"),
               {"v": value, "i": qid})
    db.commit()


def test_unbound_widget_is_empty_with_reason(db, env):
    """query_id=NULL → empty/unbound（原型「待绑定」），不得抛异常也不得进 error。"""
    it = by_widget(svc(db, ctx_of()).execute_specs(specs_of(db, env, env["w_scene"])))
    assert it[env["w_scene"]]["state"] == "empty"
    assert it[env["w_scene"]]["reason"] == "unbound"
    assert FakeQueryService.calls == []


def test_zero_rows_is_empty_not_error(db, env):
    """empty/zero_rows 与 error 必须可区分：W6 要求文案不同。"""
    FakeQueryService.payload = {"columns": ["oee"], "rows": [], "row_count": 0, "truncated": False}
    it = by_widget(svc(db, ctx_of()).execute_specs(specs_of(db, env, env["w_kpi"])))
    assert it[env["w_kpi"]]["state"] == "empty"
    assert it[env["w_kpi"]]["reason"] == "zero_rows"
    assert it[env["w_kpi"]]["error"] is None


def test_disabled_or_unverified_query_is_error(db, env):
    """停用与无编译产物都是 error，且错误码不同（owner 得知道自己该做什么）。"""
    set_query(db, env["q_kpi"], "status", "disabled")
    set_query(db, env["q_trend"], "verify_status", "pending")
    it = by_widget(svc(db, ctx_of()).execute_specs(specs_of(db, env, env["w_kpi"], env["w_trend"])))
    assert it[env["w_kpi"]]["error"]["code"] == "TWIN_QUERY_DISABLED"
    assert it[env["w_trend"]]["error"]["code"] == "QUERY_COMPILE_FAILED"
    assert FakeQueryService.calls == []            # 不合法的定义根本不进执行层


def test_query_defined_in_another_tenant_is_not_runnable(db, env):
    """组件绑了 B 租户的查询（FK 允许）：租户过滤后当作不存在，不泄内容也不执行。"""
    other = db.execute(text(
        "INSERT INTO onto_ontology_query (tenant_id, ontology_id, version, code, name, result_shape, "
        "spec_json, compiled_sql, sql_sha256, source_id, verify_status, status) VALUES "
        "(:t, :o, 1, 'q_b', '它租', 'kpi', CAST('{}' AS jsonb), 'SELECT 1', 'sha-b', 999, 'verified', 'enabled') "
        "RETURNING id"), {"t": TENANT_B, "o": env["ontology_id"]}).scalar_one()
    wid = int(db.execute(text(
        "INSERT INTO twin_widget (tenant_id, page_id, widget_key, title, query_id, sort_order) "
        "VALUES (:t, :p, 'kpi', '跳租', :q, 9) RETURNING id"),
        {"t": TENANT_A, "p": env["page_id"], "q": int(other)}).scalar_one())
    db.commit()
    it = by_widget(svc(db, ctx_of()).execute_specs(specs_of(db, env, wid)))
    assert it[wid]["state"] == "error" and it[wid]["error"]["code"] == "QUERY_NOT_FOUND"
    assert FakeQueryService.calls == []


# ---------------------------------------------------- 整页扇出（HTTP 层 W8）

def test_page_data_returns_all_widgets_in_one_request(twin_client_a, db, env):
    """W8：整页刷新只发 1 个端点请求，回体按 sort_order 覆盖全部组件。"""
    r = twin_client_a.post(f"/api/v1/twins/pages/{env['page_id']}/data", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["page_id"] == env["page_id"] and body["card_id"] == env["card_id"]
    assert [i["widget_id"] for i in body["items"]] == [env["w_kpi"], env["w_trend"], env["w_scene"]]
    assert body["count"] == 3
    assert all(len(i) == 15 for i in body["items"])     # 15 个统一键，无缺列


def test_one_failing_widget_does_not_fail_the_page(twin_client_a, db, env):
    FakeQueryService.raise_for = "demo_line_trend"
    body = twin_client_a.post(f"/api/v1/twins/pages/{env['page_id']}/data", json={}).json()
    it = by_widget(body["items"])
    assert it[env["w_trend"]]["state"] == "error"
    assert it[env["w_trend"]]["error"]["code"] == "TWIN_DATA_FAILED"
    assert "源库连接失败" in it[env["w_trend"]]["error"]["message"]
    assert it[env["w_kpi"]]["state"] == "ok"


def test_slow_widget_times_out_others_survive(twin_client_a, db, env, monkeypatch):
    monkeypatch.setattr(td, "QUERY_TIMEOUT_S", 0.05)
    FakeQueryService.sleep_for = "demo_line_trend"
    body = twin_client_a.post(f"/api/v1/twins/pages/{env['page_id']}/data", json={}).json()
    it = by_widget(body["items"])
    assert it[env["w_trend"]]["error"]["code"] == "TWIN_DATA_TIMEOUT"
    assert it[env["w_kpi"]]["state"] == "ok"


def test_page_params_apply_only_where_declared(twin_client_a, db, env):
    """页面级参数是**可选覆盖**，不是广播：

    1. 只灌进在本查询 `params_json` 里声明过的同名参数（否则一个页面级 `site`
       会把未声明它的组件全部打成“未知参数”error）；
    2. 组件已存实值优先（设计期 preview 确认过的值不得被运行期刷新静默改写）。
    """
    twin_client_a.post(f"/api/v1/twins/pages/{env['page_id']}/data",
                       json={"params": {"line": "L9", "site": "S1"}})
    got = {c["sql"]: c["params"] for c in FakeQueryService.calls}
    assert got["SELECT oee FROM demo_device_stat"] == {"line": "L1"}            # site 未声明→丢，L1 覆盖 L9
    assert got["SELECT ts FROM demo_line_trend"] == {"line": "L9", "site": "S1"}  # 两个都声明了→均落地


def test_single_widget_endpoint_reuses_stored_params(twin_client_a, db, env):
    """T9 无请求体：只用已存 param_values_json（不偏离 spec）。"""
    r = twin_client_a.get(f"/api/v1/twins/widgets/{env['w_kpi']}/data")
    assert r.status_code == 200 and r.json()["widget_id"] == env["w_kpi"]
    assert FakeQueryService.calls[0]["params"] == {"line": "L1"}


# ---------------------------------------------------- 出口脱敏与缓存安全（W11）

ID_CARD = "310101199001011234"
MASK_RULES = ('{"enabled": true, "rules": [{"field": "id_card", "strategy": "mask", '
              '"keep_prefix": 3, "keep_suffix": 2, "exempt_roles": ["SEC_ADMIN"]}]}')


def prepare_masked_kpi(db, env):
    """把 q_kpi 换成“全掩规则 + 工号列”（keep 3/2 避开 `guess_strategy_for_field` 的预设干扰）。

    计划缺陷修正（执行时实测，2026-11-01）：`id_card` **必须排在第一列**。
    `shape_result("kpi")` 的 `value` 只读 `columns[0]`（ontology_query_service.py:109），
    计划原稿的 `["dev_code", "id_card"]` 使 `value` 永远是未脱敏的工号，
    两条脱敏断言以假失败；保留第二列是为了继续测“原值不得出现在 `records` 里”。
    """
    set_query(db, env["q_kpi"], "mask_rules_json", MASK_RULES, as_json=True)
    FakeQueryService.payload = {"columns": ["id_card", "dev_code"], "rows": [[ID_CARD, "D1"]],
                                "row_count": 1, "truncated": False}


def test_masked_column_switches_state_to_masked(db, env):
    prepare_masked_kpi(db, env)
    it = by_widget(svc(db, ctx_of("VIEWER")).execute_specs(specs_of(db, env, env["w_kpi"])))
    item = it[env["w_kpi"]]
    assert item["state"] == "masked" and item["masked_fields"] == ["id_card"]
    assert ID_CARD not in str(item["data"])        # 原值不得出现在任何返回位置
    assert item["data"]["value"] == "310" + "*" * 13 + "34"


def test_exempt_role_gets_raw_value_and_ok(db, env):
    prepare_masked_kpi(db, env)
    it = by_widget(svc(db, ctx_of("SEC_ADMIN")).execute_specs(specs_of(db, env, env["w_kpi"])))
    assert it[env["w_kpi"]]["state"] == "ok"
    assert it[env["w_kpi"]]["data"]["value"] == ID_CARD


def test_cache_key_includes_role_signature(db, env):
    """W11 安全回归（R3）：豁免与不豁免交替请求同一查询，后者不得命中前者的缓存。"""
    prepare_masked_kpi(db, env)
    sql_of = lambda cs: [c for c in FakeQueryService.calls if "demo_device_stat" in c["sql"]]  # noqa: E731
    a = by_widget(svc(db, ctx_of("SEC_ADMIN")).load_page(env["page_id"])["items"])
    b = by_widget(svc(db, ctx_of("VIEWER")).load_page(env["page_id"])["items"])
    assert a[env["w_kpi"]]["state"] == "ok" and b[env["w_kpi"]]["state"] == "masked"
    assert len(sql_of(FakeQueryService.calls)) == 2          # 两个角色各跑一次，零串味
    # 键本身：角色不同→不同；同角色不同排列→相同（否则无豁免用户会拿到无豁免用户的键 miss 不是安全问题，而是拖平缓存）
    base = (TENANT_A, env["q_kpi"], param_sha({"line": "L1"}), "sha-q_kpi")
    assert data_cache_key(*base, role_signature(ctx_of("SEC_ADMIN"))) != \
        data_cache_key(*base, role_signature(ctx_of("VIEWER")))
    assert role_signature(ctx_of("A", "B")) == role_signature(ctx_of("B", "A"))


def test_cache_hit_skips_second_execution(db, env):
    kpi_calls = lambda: len([c for c in FakeQueryService.calls if "demo_device_stat" in c["sql"]])  # noqa: E731
    first = by_widget(svc(db, ctx_of("VIEWER")).load_page(env["page_id"])["items"])
    second = by_widget(svc(db, ctx_of("VIEWER")).load_page(env["page_id"])["items"])
    assert kpi_calls() == 1 and first[env["w_kpi"]]["cached"] is False
    assert second[env["w_kpi"]]["cached"] is True


def test_error_result_is_not_cached(db, env):
    """失败不入缓存：否则一次抽风会把 error 态钉住 10s，↻ 重试永远重试不了。"""
    FakeQueryService.raise_for = "demo_device_stat"
    for _ in range(2):
        svc(db, ctx_of("VIEWER")).load_page(env["page_id"])
    assert len([c for c in FakeQueryService.calls if "demo_device_stat" in c["sql"]]) == 2


def test_invalid_mask_rules_fail_closed_before_execution(db, env):
    """脱敏配置坏 → **宁可 error 也不返回真值**（降级不脱敏等于没闸）。"""
    set_query(db, env["q_kpi"], "mask_rules_json", '{"enabled": true, "rules": [{"field": ""}]}',
              as_json=True)
    it = by_widget(svc(db, ctx_of("VIEWER")).execute_specs(specs_of(db, env, env["w_kpi"])))
    assert it[env["w_kpi"]]["state"] == "error"
    assert it[env["w_kpi"]]["error"]["code"] == "TWIN_DATA_FAILED"
    assert FakeQueryService.calls == []


# ---------------------------------------------------------------- 权限门

def test_restricted_card_cannot_fetch_data(twin_client_a, db, env):
    """🔒 受限卡只能看徽标与申请入口，取数直接 403（§4.5）。"""
    cid = int(db.execute(text(
        "INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, runtime_state, owner_id) "
        "VALUES (:t, '园区安防', :o, 1, 'live', 999) RETURNING id"),
        {"t": TENANT_A, "o": env["ontology_id"]}).scalar_one())
    pid = int(db.execute(text(
        "INSERT INTO twin_page (tenant_id, card_id, name, sort_order) VALUES (:t, :c, '页', 0) RETURNING id"),
        {"t": TENANT_A, "c": cid}).scalar_one())
    db.execute(text("INSERT INTO twin_widget (tenant_id, page_id, widget_key, title, query_id, sort_order) "
                    "VALUES (:t, :p, 'kpi', 'OEE', :q, 0)"),
               {"t": TENANT_A, "p": pid, "q": env["q_kpi"]})
    db.commit()
    r = twin_client_a.post(f"/api/v1/twins/pages/{pid}/data", json={})
    assert r.status_code == 403 and r.json()["code"] == "TWIN_ACCESS_REQUIRED"


def test_cross_tenant_page_is_404(twin_client_b, db, env):
    r = twin_client_b.post(f"/api/v1/twins/pages/{env['page_id']}/data", json={})
    assert r.status_code == 404 and r.json()["code"] == "TWIN_PAGE_NOT_FOUND"
```

- [ ] **Step 3: 跑到失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/twin/test_twin_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.twin.twin_data_service'`

- [ ] **Step 4: 写 `backend/app/services/twin/twin_data_service.py`（上半：常量 · 缓存键 · WidgetSpec）**

```python
"""批量取数编排（spec §2.2 一次页面刷新 / §4.3 扇出闸门 / §4.6 错误处理）。

四层职责在本文件的落点（任何一条被破坏即视为架构违规）：

- **不生成 SQL、不改 SQL**：编译产物 `compiled_sql` 属于语义层（Task 4）；
- **不开第二条取数通道**：一律经 `ReadonlyQueryService.run`（执行层，Task 3 已扩 `params`）；
- **不自己掩码**：值位替换交给 `apply_masking`（出口层纯函数），本层只决定 `state`；
- **不重做形状**：归一复用 Task 4 的模块级 `shape_result()`，设计期预览与运行期取数共用一份。

⚠️ **安全不变量（R3 / W11）**：缓存键**必须**包含访问者角色签名。
漏掉即等于把豁免角色的**未脱敏**结果命中给普通用户，脱敏形同虚设。
构造入口唯一：:func:`data_cache_key`；回归：`test_cache_key_includes_role_signature`。
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.tool_manager.masking import apply_masking
from app.ai.tool_manager.sqlbot_tool_config import MaskingConfig
from app.ai.tool_manager.tool_context import ToolUserContext
from app.core.api_error import (
    ApiError, QUERY_COMPILE_FAILED, QUERY_NOT_FOUND, TWIN_ACCESS_REQUIRED,
    TWIN_DATA_FAILED, TWIN_DATA_TIMEOUT, TWIN_QUERY_DISABLED,
)
from app.core.cache import TTLCache, make_key
from app.db.database import SessionLocal
from app.models.ontology.query import MetaOntologyQuery
from app.models.twin import TwinWidget
from app.services.dataops.query_service import ReadonlyQueryService
from app.services.ontology.ontology_query_service import shape_result
from app.services.twin.twin_service import ACCESS_RESTRICTED, TwinService

logger = logging.getLogger(__name__)

# 扇出闸门（spec §4.3）。本仓库路由一律是同步 `def`，因此每请求
# `asyncio.Semaphore(4)` 的等价物是**进程级**线程池：`max_workers=4` 比“每请求 4”更保守
# （多页并发刷新时后来者排队，而不是把源库并发推高），符合 R2 的缓解方向。
# 先例：`services/ontology/ontology_build_service.py:97`（同为模块级 ThreadPoolExecutor）。
FANOUT_MAX = 4
QUERY_TIMEOUT_S = 5.0          # 对齐原型 `getSensorStream` 超时文案（prototype:460）
PAGE_DEADLINE_S = 8.0          # 整页 deadline：到点即把未完成组件回 error，**绝不整页 500**
CACHE_TTL_S = 10.0
CACHE_MAXSIZE = 256
DATA_ROW_LIMIT = 200           # 与语义层 preview 同一上限，不给运行期“看到更多行”的后门

STATE_OK, STATE_EMPTY, STATE_ERROR, STATE_MASKED = "ok", "empty", "error", "masked"
REASON_UNBOUND, REASON_ZERO_ROWS = "unbound", "zero_rows"

_EXECUTOR = ThreadPoolExecutor(max_workers=FANOUT_MAX, thread_name_prefix="twin_data")


def _new_cache() -> TTLCache:
    return TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_S)


_data_cache: TTLCache = _new_cache()


def reset_data_cache() -> None:
    """清缓存。**只给测试用**（用例之间必须隔离，否则上一个用例的未脱敏命中会假装本用例通过）。"""
    global _data_cache
    _data_cache = _new_cache()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def param_sha(values: Optional[Dict[str, Any]]) -> str:
    """参数实值摘要。`sort_keys` 保证同值不同录入顺序得到同一摘要；`default=str`
    兜住 `Decimal`/`datetime`（驱动返回的类型不稳定，不兜就会偶尔 `TypeError` 直接掉整个缓存）。"""
    payload = json.dumps(values or {}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def role_signature(ctx: Optional[ToolUserContext]) -> str:
    """角色签名：`apply_masking` 的豁免判定只看 `role_codes` 与 `is_admin`（`masking.py:112-117`），
    因此签名只取这两项；多取（如 region）只会无谓碎化缓存命中率。"""
    if ctx is None:
        return "anon"
    roles = ",".join(sorted({r for r in ctx.role_codes if r})) or "-"
    digest = hashlib.sha1(roles.encode("utf-8")).hexdigest()[:12]
    return f"{'a' if ctx.is_admin else 'u'}:{digest}"


def data_cache_key(tenant_id: int, query_id: int, param_digest: str,
                   sql_sha256: Optional[str], role_sig: str) -> str:
    """缓存键的**唯一**构造入口（spec §4.3 四元组 + `sql_sha256`）。

    为何还拼 `sql_sha256`：重编译后同一 `query_id` 的定义已变，不拼摘要就会把
    旧结果当新结果端出去最多 TTL 时长；拼上则“改一句话立即失效”，无需写主动刷缓存。
    """
    return make_key(tenant_id, query_id, param_digest, sql_sha256 or "-", role_sig)


@dataclass
class WidgetSpec:
    """一个组件的取数请求（**与 ORM 无关**：T8/T9 走行记录，T11 发布快照走 `from_snapshot`）。"""

    widget_id: int
    widget_key: str
    title: str
    query_id: Optional[int] = None
    param_values: Dict[str, Any] = field(default_factory=dict)
    grid: Dict[str, Any] = field(default_factory=dict)
    refresh: Dict[str, Any] = field(default_factory=dict)
    # 页面级参数底（仅 T8 填入）：到 `_precheck` 才按各查询的声明裁剪，因为那时才拿到定义行。
    base_params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, w: TwinWidget) -> "WidgetSpec":
        return cls(widget_id=int(w.id), widget_key=w.widget_key, title=w.title,
                   query_id=int(w.query_id) if w.query_id else None,
                   param_values=dict(w.param_values_json or {}),
                   grid=dict(w.grid_json or {}), refresh=dict(w.refresh_json or {}))

    @classmethod
    def from_snapshot(cls, d: Dict[str, Any]) -> "WidgetSpec":
        """发布快照条目（Task 8 写 `snapshot_json.widgets` 的结构与此对称）。"""
        return cls(widget_id=int(d.get("widget_id") or 0), widget_key=str(d.get("widget_key") or ""),
                   title=str(d.get("title") or ""),
                   query_id=int(d["query_id"]) if d.get("query_id") else None,
                   param_values=dict(d.get("param_values_json") or {}),
                   grid=dict(d.get("grid_json") or {}), refresh=dict(d.get("refresh_json") or {}))


def _blank_item(spec: WidgetSpec) -> Dict[str, Any]:
    """结果项模板：**每个分支都从此出发**，因而 15 个键不可能漏。"""
    return {
        "widget_id": spec.widget_id, "widget_key": spec.widget_key, "title": spec.title,
        "query_id": spec.query_id, "state": STATE_OK, "reason": None, "result_shape": None,
        "columns": [], "data": {"records": []}, "row_count": 0, "truncated": False,
        "masked_fields": [], "error": None, "cached": False, "updated_at": _now_iso(),
    }
```

> `from __future__ import annotations` 之后才能写 `Optional[dict]` 不带 `typing`；此处仍显式
> import `Any/Dict/...` 是因为 `dataclass` 的字段注解会在运行期求值（`field(default_factory=...)`）。
> 常量全部**模块级、不封装为配置项**：Global Constraints 禁止新增环境变量，调闸门需改代码重新部署，
> P0 接受这个代价（YAGNI；真需要按租户不同时再抽配置）。

- [ ] **Step 5: 追写 `twin_data_service.py`（下半：TwinDataService）**

接在 `_blank_item()` 之后（模块级，不是类内）：

```python
class TwinDataService:
    """页面/组件级批量取数（T8 / T9）。Task 8 的只读发布通道复用 `execute_specs`。"""

    def __init__(self, db: Session, tenant_id: Optional[int], user_id: int,
                 ctx: Optional[ToolUserContext] = None,
                 session_factory: Optional[Callable[[], Session]] = None) -> None:
        if tenant_id is None:
            raise ValueError("tenant_required")
        self.db = db
        self.tenant_id = int(tenant_id)
        self.user_id = int(user_id or 0)
        self.ctx = ctx
        self.role_codes = tuple(sorted({r for r in (ctx.role_codes if ctx else ()) if r}))
        self._role_sig = role_signature(ctx)
        # 工作线程**绝不复用** self.db：SQLAlchemy Session 不是线程安全的。
        # 缺省用应用引擎（与 SessionLocal 同一个连接池）；测试注入绑定到测试引擎的工厂。
        self._session_factory: Callable[[], Session] = session_factory or SessionLocal
        self._orch = TwinService(db, self.tenant_id, self.user_id, self.role_codes)

    # ------------------------------------------------------------ 端点入口

    def _assert_readable(self, card) -> None:
        """取数前的可读门：不可读 404（由 `get_card` 给），🔒 受限 403。

        受限卡只能看徽标与申请入口（§4.5），**不能把取数当旁路读别人的业务数据**。
        """
        access = self._orch.get_card(int(card.id))["access"]
        if access == ACCESS_RESTRICTED:
            raise ApiError(TWIN_ACCESS_REQUIRED, "受限卡片：需先取得访问权限", 403,
                           {"card_id": int(card.id), "access": access})

    def load_page(self, page_id: int,
                  page_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """T8：整页刷新只发 1 个请求（W8）。"""
        page, card = self._orch.page_with_card(page_id)
        self._assert_readable(card)
        rows = self.db.execute(
            select(TwinWidget).where(TwinWidget.page_id == int(page.id))
            .order_by(TwinWidget.sort_order, TwinWidget.id)
        ).scalars().all()
        specs = [WidgetSpec.from_row(w) for w in rows]
        base = dict(page_params or {})
        for s in specs:
            s.base_params = base            # 具体哪些键能落地，由 `_precheck` 按声明裁剪
        items = self.execute_specs(specs)
        return {"page_id": int(page.id), "card_id": int(card.id),
                "runtime_state": card.runtime_state, "refresh": page.refresh_json,
                "collected_at": _now_iso(), "count": len(items), "items": items}

    def load_widget(self, widget_id: int,
                    params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """T9：单组件刷新 / error 态 ↻ 重试。不传 `params` 时**只用已存实值**（不偏离 spec）。"""
        w = self._orch.widget_or_404(widget_id)
        _page, card = self._orch.page_with_card(int(w.page_id))
        self._assert_readable(card)
        spec = WidgetSpec.from_row(w)
        if params:
            spec.param_values = {**spec.param_values, **params}
        return self.execute_specs([spec])[0]

    # ------------------------------------------------------------ 扇出执行

    def execute_specs(self, specs: List[WidgetSpec]) -> List[Dict[str, Any]]:
        """未绑定 / 不可运行 / 缓存命中全部在主线程解决，**只把真需要跑 SQL 的送进线程池**。"""
        if not specs:
            return []
        wanted = sorted({s.query_id for s in specs if s.query_id})
        defs: Dict[int, MetaOntologyQuery] = {}
        if wanted:
            defs = {int(r.id): r for r in self.db.execute(
                select(MetaOntologyQuery).where(
                    MetaOntologyQuery.tenant_id == self.tenant_id,
                    MetaOntologyQuery.id.in_(wanted))
            ).scalars().all()}

        results: Dict[int, Dict[str, Any]] = {}
        pending: List[Tuple[WidgetSpec, str, MetaOntologyQuery]] = []
        for spec in specs:
            item, cache_key = self._precheck(spec, defs)
            if item is not None:
                results[spec.widget_id] = item
            else:
                pending.append((spec, cache_key, defs[int(spec.query_id)]))

        # 一次性提交全部待执行项：线程池排队本身即是 Semaphore(4) 的同步等价物。
        futures = [(spec, _EXECUTOR.submit(self._run_one, spec, q, key))
                   for spec, key, q in pending]
        deadline = time.monotonic() + PAGE_DEADLINE_S
        for spec, fut in futures:
            wait = max(min(QUERY_TIMEOUT_S, deadline - time.monotonic()), 0.0)
            try:
                results[spec.widget_id] = fut.result(timeout=wait)
            except FutureTimeout:
                fut.cancel()
                logger.warning("孪生取数超时 widget_id=%s wait=%.3fs", spec.widget_id, wait)
                results[spec.widget_id] = self._error_item(
                    spec, TWIN_DATA_TIMEOUT, f"取数超时（>{QUERY_TIMEOUT_S:.0f}s）")
            except ApiError as exc:
                results[spec.widget_id] = self._error_item(spec, exc.code, exc.message)
            except Exception as exc:  # noqa: BLE001 — 单组件失败不得波及整页（spec §4.3）
                logger.warning("孪生取数失败 widget_id=%s: %s", spec.widget_id, exc)
                results[spec.widget_id] = self._error_item(spec, TWIN_DATA_FAILED, str(exc)[:200])
        return [results[s.widget_id] for s in specs]

    def _precheck(self, spec: WidgetSpec,
                  defs: Dict[int, MetaOntologyQuery]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """返回 `(item, None)`（可直接回前端）或 `(None, cache_key)`（需要真跑 SQL）。"""
        if spec.query_id is None:
            item = _blank_item(spec)
            item.update(state=STATE_EMPTY, reason=REASON_UNBOUND)
            return item, None
        q = defs.get(int(spec.query_id))
        if q is None:
            return self._error_item(spec, QUERY_NOT_FOUND,
                                    "绑定的查询定义不存在或不属于本租户"), None
        # 页面级参数只在该查询声明了同名参数时才生效（spec §2.2 的 `{params}` 是**可选覆盖**，
        # 不是广播）；组件已存实值永远覆盖页面级。未声明的键交给 Task 3 的 `validate_params` 拒。
        declared = {str(d.get("name")) for d in (q.params_json or [])
                    if isinstance(d, dict) and d.get("name")}
        spec.param_values = {**{k: v for k, v in spec.base_params.items() if k in declared},
                             **spec.param_values}
        if q.status != "enabled":
            return self._error_item(spec, TWIN_QUERY_DISABLED, f"查询 {q.code} 已被 owner 停用"), None
        if q.verify_status != "verified" or not q.compiled_sql or not q.source_id:
            return self._error_item(
                spec, QUERY_COMPILE_FAILED,
                f"查询 {q.code} 无可用编译产物（verify_status={q.verify_status}）"), None
        key = data_cache_key(self.tenant_id, int(q.id), param_sha(spec.param_values),
                             q.sql_sha256, self._role_sig)
        hit = _data_cache.get(key)
        if hit is None:
            return None, key
        # 缓存项是**查询结果**，不带组件身份：同一查询被两个组件绑定时共用一条记录，
        # 因此身份四字段必须按当前请求重写——忘了这一步就会把 A 组件的 widget_id 回给 B。
        item = dict(hit)
        item.update(widget_id=spec.widget_id, widget_key=spec.widget_key,
                    title=spec.title, query_id=spec.query_id, cached=True)
        return item, None

    def _run_one(self, spec: WidgetSpec, q: MetaOntologyQuery,
                 cache_key: str) -> Dict[str, Any]:
        """在工作线程里跑一个组件：独立 Session → 出口脱敏 → 形状归一 → 回填缓存。"""
        cfg = self._masking_of(q)          # 先解析脱敏配置：**坏配置直接拒，不先跑 SQL**
        session = self._session_factory()
        try:
            out = ReadonlyQueryService(session, self.tenant_id).run(
                int(q.source_id), q.compiled_sql, limit=DATA_ROW_LIMIT,
                params=spec.param_values, params_declared=q.params_json or [])
        finally:
            session.close()
        columns = list(out["columns"])
        records = [dict(zip(columns, r)) for r in out["rows"]]
        records, masked_fields = apply_masking(records, cfg, self.ctx)   # §4.5 出口层
        item = _blank_item(spec)
        item.update(result_shape=q.result_shape, columns=columns,
                    data=shape_result(q.result_shape, records, columns),
                    row_count=int(out.get("row_count", len(records))),
                    truncated=bool(out.get("truncated")), masked_fields=list(masked_fields))
        if masked_fields:
            item["state"] = STATE_MASKED          # §6.4：任一列被脱敏即 masked（值位 🔒）
        elif not records:
            item["state"], item["reason"] = STATE_EMPTY, REASON_ZERO_ROWS
        else:
            item["state"] = STATE_OK
        # 失败永远到不了这一行（异常已抛出）：**error 态不入缓存**，否则一次抽风会把 error
        # 钉住整个 TTL，前端的 ↻ 重试永远重试不掉。
        _data_cache.set(cache_key, item)
        return item

    @staticmethod
    def _masking_of(q: MetaOntologyQuery) -> MaskingConfig:
        """`mask_rules_json` 必须是可直接 `MaskingConfig.model_validate` 的形状（Task 1 §3.1 已定）。"""
        if not q.mask_rules_json:
            return MaskingConfig(enabled=False, rules=[])
        try:
            return MaskingConfig.model_validate(q.mask_rules_json)
        except ValidationError as exc:
            # fail-closed：宁可回 error，也不把“脱敏配置坏了”降级成“返回真值”。
            # http_status 此处不参与渲染（异常被 execute_specs 收敛为组件 error 态），取 400。
            raise ApiError(TWIN_DATA_FAILED, "查询的脱敏配置非法，已拒绝返回数据", 400,
                           {"query_id": int(q.id), "errors": str(exc)[:300]}) from exc

    @staticmethod
    def _error_item(spec: WidgetSpec, code: str, message: str) -> Dict[str, Any]:
        item = _blank_item(spec)
        # W6：错误态必须回显“错误码 + 人话原因”，不得只给“接口异常”。
        item.update(state=STATE_ERROR, error={"code": code, "message": message})
        return item
```

> **诚实说明 deadline 的边界**：`fut.result(timeout=…)` 只约束“我们什么时候放弃等待”，
> **不取消**已在执行的线程，也不向源库发取消报文。SQL 能不能在库侧被掐断取决于驱动
> 的 statement timeout（spec §8.3 待核实 **U3**，本期不承诺）；最坏情况下一个慢查询仍会
> 占住一个 worker 直到自然结束。这一权衡必须在 review 时告知，不得把本实现当成“硬超时”。

- [ ] **Step 6: 给 `backend/app/routers/twin/twin.py` 加 T8 / T9**

顶部 import 区追加两行（按字母序插入现有行内，不整块另起）：

```python
from app.services.twin.twin_data_service import TwinDataService
```

在 `LayoutBody` 之后追加 Body：

```python
class DataBody(BaseModel):
    """整页取数的**可选**页面级参数（spec §2.2 `{params}`）：只对本查询声明过的同名参数生效。"""

    params: Dict[str, Any] = Field(default_factory=dict)
```

在 `_svc()` 之后追加数据服务构造器：

```python
def _data_svc(db: Session, current_user: SysUser) -> TwinDataService:
    """取数上下文走 `build_user_context()`：**同一个 ctx 同时驱动脱敏豁免与缓存键**，
    两处各取一次角色就会不一致（R3 的事故面）。

    `session_factory` 从当前请求 session 的 bind 派生：生产上就是应用引擎（等价
    `SessionLocal`），测试里自然落到带 `search_path` 监听器的测试引擎——无需为测试另开配置。
    """
    ctx = build_user_context(db, current_user)
    bind = db.get_bind()
    return TwinDataService(db, _require_tenant_id(current_user),
                           int(getattr(current_user, "user_id", 0) or 0), ctx,
                           session_factory=lambda: Session(bind, expire_on_commit=False))
```

在文件末尾（T5–T7 区块之后）追加两个端点：

```python
# ------------------------------------------------------------ T8–T9 取数


@router.post("/pages/{page_id}/data")
def load_page_data(page_id: int, body: Optional[DataBody] = None,
                   db: Session = Depends(get_db),
                   current_user: SysUser = Depends(get_current_user)) -> dict:
    """T8：整页刷新只发 1 个请求（W8）。空体合法（组件用已存实值）；
    单组件失败只影响该组件的 state，**端点本身永远回 200**。"""
    return _data_svc(db, current_user).load_page(page_id, body.params if body else None)


@router.get("/widgets/{widget_id}/data")
def load_widget_data(widget_id: int, db: Session = Depends(get_db),
                     current_user: SysUser = Depends(get_current_user)) -> dict:
    """T9：单组件刷新与错误重试（原型 error 态的 ↻），只用已存 `param_values_json`。"""
    return _data_svc(db, current_user).load_widget(widget_id)
```

> 无需改 `router_registry`：Task 6 已挂 `attr="router"`，本步只往同一个 `APIRouter` 加路由。

- [ ] **Step 7: 跑到通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/twin/test_twin_data.py -v`
Expected: PASS（17 passed）。失败时的排查序（按此序查，不得改测试迁就实现）：

1. `test_cache_key_includes_role_signature` 只看到 1 次执行→缓存键漏了 `role_sig`，或
   `reset_data_cache()` 没跑（用例间串了缓存）；
2. `state == "ok"` 但期望 `"masked"`→`apply_masking` 的返回值当单值用了（它是
   `(rows, applied_fields)` **二元组**）；或 `mask_rules_json` 不是 `{enabled, rules:[…]}` 形状；
3. `test_page_params_apply_only_where_declared` 拿到 `site` 进了 kpi→`_precheck` 里的声明裁剪
   没生效（检查 `declared` 取的是 `q.params_json` 而不是页面级键集）；
4. `test_invalid_mask_rules_fail_closed_before_execution` 看到 `Fake.calls` 非空→`_masking_of()`
   被排在 `run()` 之后了（必须先解析配置，坏配置不耗库）；
5. `Worker threads` 报 `Session` 相关异常（如“同一 Session 并发使用”）→`_run_one` 里用了
   `self.db` 而非 `self._session_factory()`；
6. `test_slow_widget_times_out_others_survive` 反而变慢/不超→`QUERY_TIMEOUT_S` 被写成了
   默认参数值而不是运行时读模块全局（`monkeypatch.setattr(td, …)` 要求代码里每次读 `QUERY_TIMEOUT_S`）。

Run: `.\.venv\Scripts\python.exe -m pytest tests/twin tests/ontology tests/unit -v`
Expected: 全绿（Task 1/4/5/6 的用例不得因本任务回归；尤其 Task 5 的 4 个与 Task 6 的 12 个）

> ⚠️ **计划缺陷修正（执行时实测，2026-11-01）：本条合并跑不可用，必须按目录分跑。**
> 同进程跑三个目录会得到 `335 passed, 1 skipped, 90 errors`，错文全部是
> `psycopg2.errors.UndefinedTable: relation "t_xxxx.kms_segment" does not exist`（fixture setup 阶段的 `create_all`），
> 即 Task 5 Step 6 已记录的**跨目录收集污染 `Base.metadata` 先行缺陷**（此处由 `app.main` 导入链带入 kms_*，
> 而 `tests/{ontology,twin}/conftest.py::_tables()` 只靠硬编码 3 个名字做黑名单减法），
> **与本任务代码无关**。取证实际命令（逐目录跑，全部 EXIT=0）：
>
> ```powershell
> foreach ($d in 'tests/twin','tests/ontology','tests/unit') {
>   .\.venv\Scripts\python.exe -m pytest $d -q -p no:logging 1>"_t7_$d.txt" 2> $null
>   echo "$d EXIT=$LASTEXITCODE"
> }
> ```
>
> 实测结果：`tests/twin` **37 passed**（Task 6 的 20 + 本任务的 17）、`tests/ontology` **79 passed**、
> `tests/unit` **309 passed / 1 skipped**（含 Task 5 的 4 个）。

- [ ] **Step 8: 提交**

```bash
git add backend/app/core/api_error.py backend/app/services/twin/twin_data_service.py backend/app/routers/twin/twin.py backend/tests/twin/test_twin_data.py
git commit -m "feat(twin): batched page fan-out with role-salted cache and egress masking"
```

> 路径需按实际 cwd 写（cwd=`backend` 时去掉 `backend/` 前缀），提交前用
> `git diff --cached --name-only` 核对无 frontend 混入。

#### Task 7 执行记录（2026-11-01）

交付：`twin_data_service.py`（335 行）+ T8/T9 两端点 + `tests/twin/test_twin_data.py`（17 用例）
+ 3 个错误码。**本 Task 未发现实现层生产缺陷**，但共有 3 处需修正：

| # | 类别 | 现象 | 修法 |
|---|---|---|---|
| 16 | 计划缺陷（测试夹具） | `prepare_masked_kpi` 的 kpi 结果集把 `dev_code` 排在第一列，而 `shape_result("kpi")` 的 `value` 只读 `columns[0]` ⇒ 两条脱敏断言拿到未脱敏的 `'D1'`，`15 passed / 2 failed` | 改夹具为列序 `["id_card", "dev_code"]`（保留第二列继续验 `records` 不回原值），不改实现 |
| 17 | 先行缺陷（同 Task 5） | Step 7 的 `pytest tests/twin tests/ontology tests/unit` 合并跑 = 90 errors | 按目录分跑（见 Step 7 注），根因同 Task 5 Step 6 |
| 18 | 计划笔误 | `HTTP戒 W8` / `绞不复用` | 已在代码块内改正 |

另两点执行期收敛：

- **“`MaskingRule.field` 无 `min_length`，空串不会 `ValidationError`”的怀疑不成立**：
  `sqlbot_tool_config.py:155-160` 已有 `@field_validator("field")` 拒绝空白 field，
  所以 `test_invalid_mask_rules_fail_closed_before_execution` 按计划原样即可通过，**无需额外守卫**。
- `Add-Content` 追写的分隔注释用的是 ASCII `-`，已用编辑工具回改为与文件内其余区块一致的 `T8–T9`（全角短横）。

缓存安全不变量已双向验证：`test_cache_key_includes_role_signature` 要求两个角色各执行一次 SQL（未串味），
`role_signature(ctx_of("A","B")) == role_signature(ctx_of("B","A"))` 要求同角色不同排列不碎化命中率。

---

### Task 8: 发布与只读运行（快照语义 · 反枚举 403 · 访问审计）T10–T11

对应 **P0-7**（验收 W12）。发布不是「复制一份页面」，而是**把配置冻成一行快照**并按随机
`slug` 对外放行；数据**永远实时**（查询期直连，遵守上游 D2）。

**⚠️ 对 spec 的一处必要修订（已实测，执行者不得自行改回）**

spec §6.1 T11 与 §4.4 把只读页写作 `/twin-p/{slug}`（无 `/api/v1`）。但部署事实是：
`frontend/nginx.default.conf:34` 只代理 `location /api/`，其余路径全部落
`location / { try_files $uri $uri/ /index.html; }`（`:28-32`）。因此后端若真用
`/twin-p/*`，**在生产环境永远拿不到响应**——浏览器只会得到 `index.html`。
本计划把后端路径定为 **`/api/v1/twin-p/{slug}`**，`/twin-p/:slug` 保留为**前端路由**
（spec §2.3 的顶层路由本来就是这个意思）。T10 的返回值同时给 `url`（前端路由）与
`api_path`（后端调用路径）两个字段，避免 Plan 2 拿错。

**Files:**
- Modify: `backend/app/core/api_error.py`（在 Task 7 追加的 `TWIN_QUERY_DISABLED` 之后补一个码）
- Create: `backend/app/services/twin/twin_publish_service.py`
- Modify: `backend/app/routers/twin/twin.py`（新建同文件的 `publish_router` + T10/T11 四个端点）
- Modify: `backend/app/core/router_registry.py`（追加第三条 `RouterSpec`）
- Modify: `backend/tests/twin/conftest.py`（`build_client` 增加 `with_publish` 开关与两个夹具）
- Test: `backend/tests/twin/test_twin_publish.py`

**Interfaces:**
- Consumes: Task 6 `TwinService.get_card/page_with_card` 与常量 `ACCESS_OWNER/ACCESS_EDIT/WRITABLE_ACCESS`；Task 7 `WidgetSpec.from_snapshot(dict)`、`TwinDataService(db, tenant_id, user_id, ctx, session_factory).execute_specs(list[WidgetSpec])`、`reset_data_cache()`；Task 1 模型 `TwinPublish`（`slug` 为 `String(32)`，`uq_twin_publish_slug(tenant_id, slug)`）；`ToolUserContext.has_any_role(roles)`（`tool_context.py:59`，**空集合返回 False**）；库内既有 `SysAuditLog` 手写法先例（`sqlbot_template_tool.py:312-344`）
- Produces: 常量 `ACCESS_ORG="org"`、`ACCESS_ROLE="role"`、`PUBLISH_ACCESS`、`SLUG_BYTES=18`、`SNAPSHOT_SCHEMA=1`、`DENY_MESSAGE`；函数 `new_slug() -> str`、`_record_access(db, *, tenant_id, user_id, username, slug, action, allowed, reason, version) -> None`；`TwinPublishService(db, tenant_id, user_id, ctx=None, session_factory=None)` 方法 `publish(page_id, *, access="org", role_codes=None) -> dict`、`unpublish(publish_id) -> None`、`get_by_slug(slug) -> dict`、`run_by_slug(slug, page_params=None) -> dict`；错误码常量 `TWIN_PUBLISH_FORBIDDEN`（复用 Task 4 已声明的 `TWIN_NOT_PUBLISHED`）；router 对象 `publish_router`（prefix `/api/v1/twin-p`）

**三条边界（review 时逐条对照，破坏任一条即打回）**

| # | 边界 | 为什么 | 锚点 |
|---|---|---|---|
| 1 | slug 一律 `secrets` 随机，**禁止自增 id 派生** | id 派生 = 未发布页面可枚举 | `test_new_slug_is_random_and_unpredictable` |
| 2 | 未知 slug / 跨租户 / 已停用 / 角色不命中 → **同一 403 同一 message**，差异只写进审计不上响应体 | spec §4.4「失败即 403，不降级返回空数据」；差异化反馈就是枚举预言机 | `test_every_denial_shares_one_code_and_message` |
| 3 | 只读页放行由 `twin_publish.access` 决定，**与 `twin_card_share` 无关**；卡片 `runtime_state` 亦不参与 | 见下方说明 | `test_paused_card_still_serves_readonly_page` |

> **边界 3 的取舍（必须让 reviewer 看见）**：发布是 owner 把这一页**显式授予**一个更大人群的
> 动作。若同时要求「访客在 `twin_card_share` 里可读」，那么 `access=org` 的发布对同租户绝大多数
> 用户永远 403——他们本来就在原型 🔒「受限」列表里（`prototype:299`），发布功能形同虚设。
> 补偿控制两条：**出口脱敏照常按访客角色执行**（发布从不放大未脱敏值，Task 7 的缓存键含
> 角色签名因此也天然生效），以及**取消发布即回收**（`status='disabled'` 后同一 slug 立即 403）。

- [ ] **Step 1: 补一个错误码**

在 `backend/app/core/api_error.py` 中 Task 7 追加的 `TWIN_QUERY_DISABLED` 之后插入：

```python
TWIN_PUBLISH_FORBIDDEN = "TWIN_PUBLISH_FORBIDDEN"  # 发布前置不满足（空页 / 绑定不可运行 / 参数非法）
```

> 分工写死，避免三个码互相串味：
> `TWIN_PUBLISH_FORBIDDEN`=**发布时**拒（400，发布动作本身不合法）；
> `TWIN_NOT_PUBLISHED`=取消发布时找不到记录（404，Task 4 已声明）；
> `TWIN_ACCESS_REQUIRED`=**访问时**拒（403，只读页统一拒绝信号）。

- [ ] **Step 2: 改 `backend/tests/twin/conftest.py`（加只读页客户端）**

把 Task 1 Step 2 定义的 `build_client` 整体替换为（改动只在签名与挂载块两处）：

```python
def build_client(db: Session, tenant_id: Optional[int], *, with_twin: bool = False,
                 with_publish: bool = False) -> TestClient:
    from app.routers.dataops.dataops import router as dataops_router

    app = FastAPI()
    app.include_router(dataops_router)
    if with_twin or with_publish:
        from app.routers.twin.twin import router as twin_router
        app.include_router(twin_router)
    if with_publish:
        # 只读页要取数，而取数在**主 router** 上（T8/T9）；发布端点 T10 也在主 router。
        # 所以 with_publish 必须把两个 router 都挂上，而不是只挂 publish_router。
        from app.routers.twin.twin import publish_router
        app.include_router(publish_router)

    from app.core.api_error import register_api_error_handler
    register_api_error_handler(app)

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: _fake_user(tenant_id)
    return TestClient(app)
```

在 `twin_client_b` 之后追加两个夹具：

```python
@pytest.fixture
def publish_client_a(db: Session) -> TestClient:
    """同时挂 `/api/v1/twins/*`（T10 发布 + T8 取数）与 `/api/v1/twin-p/*`（T11 只读页）。"""
    return build_client(db, TENANT_A, with_publish=True)


@pytest.fixture
def publish_client_b(db: Session) -> TestClient:
    return build_client(db, TENANT_B, with_publish=True)
```

> `with_twin` 分支不删：Task 6/7 的既有夹具仍在用它，且 `with_twin or with_publish` 的写法
> 保证同一请求 Session 上不会出现主 router 的重复挂载（重复 include 会得到两份同路径路由，
> Starlette 只匹配第一条，看似无害，实则让 OpenAPI 文档出现重复项）。
>
> 执行时保留（2026-11-01）：上面的代码块省略了 `build_client` 的 docstring，但本步自己的
> 说明写的是「改动只在签名与挂载块两处」，因此**执行时保留并更新了 docstring**（把
> `/twin-p` 从 `with_twin` 的描述里移给 `with_publish`），与计划意图一致。

- [ ] **Step 3: 写失败测试（上：夹具 + slug / 快照 / 空页 / 未验证）**

创建 `backend/tests/twin/test_twin_publish.py`：

```python
"""发布与只读运行（spec §4.4 / P0-7 / W12）：slug 随机、反枚举 403、快照语义、访问审计。

两层测试，分工与 `test_twin_data.py` 一致：
- **HTTP 层**（`publish_client_a`）：端点形状、访问校验链、快照与实时的边界；
- **服务层**（直接构造 `TwinPublishService`）：凡是与**角色**有关的判定——
  `conftest._fake_user()` 不落 `sys_role`，HTTP 拿到的 `role_codes` 恒为空，
  造不出「命中角色的访客」。

执行层沿用 Task 7 的打桩点（`twin_data_service.ReadonlyQueryService`）：本任务测的是
**发布与放行**，取数链路本身已由 `test_twin_data.py` 覆盖，不在这里重测一遍。
"""
import re

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.tool_manager.tool_context import ToolUserContext
from app.core.api_error import ApiError
from app.services.twin import twin_data_service as td
from app.services.twin import twin_publish_service as tp
from app.services.twin.twin_publish_service import TwinPublishService
from tests.twin.conftest import TENANT_A


class FakeRun:
    """执行层桩：只关心「跑了什么 SQL、带了什么参数」。"""

    calls = []
    payload = {"columns": ["oee"], "rows": [[0.85]], "row_count": 1, "truncated": False}

    def __init__(self, db, tenant_id):
        self.db, self.tenant_id = db, tenant_id

    def run(self, source_id, sql, limit=100, params=None, params_declared=None):
        FakeRun.calls.append({"sql": sql, "params": params or {}})
        return dict(FakeRun.payload)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """每用例一份干净缓存：Task 7 的缓存是进程级全局，不清就会跨用例串结果。"""
    td.reset_data_cache()
    FakeRun.calls = []
    FakeRun.payload = {"columns": ["oee"], "rows": [[0.85]], "row_count": 1, "truncated": False}
    monkeypatch.setattr(td, "ReadonlyQueryService", FakeRun)
    yield
    td.reset_data_cache()


@pytest.fixture
def env(db):
    """卡（owner=101, live）+ 页 + 两条已 preview 的查询 + 两个组件。"""
    ex = lambda s, p=None: db.execute(text(s), p or {})  # noqa: E731
    oid = int(ex("INSERT INTO onto_ontology (tenant_id, code, name, status, current_version) "
                 "VALUES (:t, gen_random_uuid()::text, '本体', 'published', 1) RETURNING id",
                 {"t": TENANT_A}).scalar_one())
    cid = int(ex("INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, "
                 "runtime_state, owner_id) VALUES (:t, '设备卡', :o, 1, 'live', 101) RETURNING id",
                 {"t": TENANT_A, "o": oid}).scalar_one())
    pid = int(ex("INSERT INTO twin_page (tenant_id, card_id, name, sort_order, refresh_json) "
                 "VALUES (:t, :c, '总览', 0, CAST(:r AS jsonb)) RETURNING id",
                 {"t": TENANT_A, "c": cid,
                  "r": '{"mode":"interval","interval_seconds":10}'}).scalar_one())

    def add_query(code, shape, sql):
        return int(ex(
            "INSERT INTO onto_ontology_query (tenant_id, ontology_id, version, code, name, "
            "result_shape, spec_json, params_json, compiled_sql, sql_sha256, source_id, "
            "verify_status, status) VALUES "
            "(:t, :o, 1, :code, :name, :shape, CAST('{}' AS jsonb), "
            "CAST(:pj AS jsonb), :sql, :sha, 999, 'verified', 'enabled') RETURNING id",
            {"t": TENANT_A, "o": oid, "code": code, "name": code, "shape": shape,
             "pj": '[{"name":"line","type":"string"}]', "sql": sql, "sha": f"sha-{code}"},
        ).scalar_one())

    def add_widget(page_id, key, qid, order, params=None):
        return int(ex(
            "INSERT INTO twin_widget (tenant_id, page_id, widget_key, title, query_id, "
            "param_values_json, grid_json, sort_order) VALUES "
            "(:t, :p, :k, :n, :q, CAST(:pv AS jsonb), CAST(:g AS jsonb), :s) RETURNING id",
            {"t": TENANT_A, "p": page_id, "k": key, "n": f"{key}-{order}", "q": qid,
             "pv": params or '{"line":"L1"}', "g": '{"x":0,"y":0,"w":6,"h":4}',
             "s": order}).scalar_one())

    q_kpi = add_query("q_kpi", "kpi", "SELECT oee FROM demo_device_stat")
    q_trend = add_query("q_trend", "trend", "SELECT ts FROM demo_line_trend")
    w_kpi = add_widget(pid, "kpi", q_kpi, 0)
    w_trend = add_widget(pid, "trend", q_trend, 1)
    db.commit()
    return {"ontology_id": oid, "card_id": cid, "page_id": pid, "q_kpi": q_kpi,
            "q_trend": q_trend, "w_kpi": w_kpi, "w_trend": w_trend,
            "add_page": lambda name: int(ex(
                "INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
                "VALUES (:t, :c, :n, 1) RETURNING id",
                {"t": TENANT_A, "c": cid, "n": name}).scalar_one()),
            "add_widget": add_widget, "add_query": add_query}


def pub(db, ctx=None, tenant_id=TENANT_A, user_id=101):
    bind = db.get_bind()
    return TwinPublishService(db, tenant_id, user_id, ctx,
                              session_factory=lambda: Session(bind, expire_on_commit=False))


def ctx_of(*roles, is_admin=False, user_id=101):
    return ToolUserContext(user_id=user_id, username=f"u-{user_id}",
                           is_admin=is_admin, role_codes=roles)


def publish_a(publish_client_a, env, **kw):
    """走 T10 发布并断言 200，返回响应体（多数用例只需要 slug）。"""
    r = publish_client_a.post(f"/api/v1/twins/pages/{env['page_id']}/publish", json=kw)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- slug 与发布

def test_new_slug_is_random_and_unpredictable():
    """边界 1：单调有序是自增派生的指纹，随机串 8 个全排序的概率是 1/40320。"""
    slugs = [tp.new_slug() for _ in range(8)]
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{24}", s) for s in slugs)
    assert len(set(slugs)) == 8
    assert slugs != sorted(slugs) and slugs != sorted(slugs, reverse=True)


def test_publish_returns_both_frontend_url_and_api_path(publish_client_a, db, env):
    """T10 回体：`url` 给前端路由用，`api_path` 给 HTTP 调用用——两者不同前缀，必须都回。"""
    b = publish_a(publish_client_a, env)
    assert b["version"] == 1 and b["status"] == "enabled" and b["widget_count"] == 2
    assert b["url"] == f"/twin-p/{b['slug']}"
    assert b["api_path"] == f"/api/v1/twin-p/{b['slug']}"
    assert b["page_id"] == env["page_id"] and b["card_id"] == env["card_id"]


def test_republish_reuses_slug_and_bumps_version(publish_client_a, db, env):
    """同一页面重复发布 = 同一资源的版本推进：slug 不变（外链不失效）、version+1、快照刷新。"""
    first = publish_a(publish_client_a, env)
    db.execute(text("UPDATE twin_widget SET title = '新标题' WHERE id = :i"), {"i": env["w_kpi"]})
    db.commit()
    second = publish_a(publish_client_a, env)
    assert second["slug"] == first["slug"] and second["version"] == 2
    meta = publish_client_a.get(f"/api/v1/twin-p/{second['slug']}").json()
    assert meta["version"] == 2
    assert [w["title"] for w in meta["widgets"]] == ["新标题", "trend-1"]


def test_empty_page_cannot_be_published(publish_client_a, db, env):
    """空页发布出去只是一张白页——直接在 T10 拒掉（400，不是 403）。"""
    pid = env["add_page"]("空白页")
    db.commit()
    r = publish_client_a.post(f"/api/v1/twins/pages/{pid}/publish", json={})
    assert r.status_code == 400 and r.json()["code"] == "TWIN_PUBLISH_FORBIDDEN"
    assert r.json()["detail"]["widget_count"] == 0


def test_unverified_binding_blocks_publish(publish_client_a, db, env):
    """发布是对外承诺：绑了但没 preview 过的查询不得进入只读页（spec §7.2 闭环顺序）。

    未绑定（`query_id IS NULL`）**合法**——`scene2d` 天生不吃查询（Task 6 配对表里形状集为空），
    拒未绑定会把整个场景模块打成不可发布；运行期由四态里的 empty/unbound 表达。
    """
    db.execute(text("UPDATE onto_ontology_query SET verify_status = 'pending' WHERE id = :i"),
               {"i": env["q_kpi"]})
    db.commit()
    r = publish_client_a.post(f"/api/v1/twins/pages/{env['page_id']}/publish", json={})
    assert r.status_code == 400 and r.json()["code"] == "TWIN_PUBLISH_FORBIDDEN"
    bad = r.json()["detail"]["widgets"]
    assert [x["widget_id"] for x in bad] == [env["w_kpi"]]
    assert "preview" in bad[0]["reason"]


def test_unbound_widget_does_not_block_publish(publish_client_a, db, env):
    env["add_widget"](env["page_id"], "scene2d", None, 2, "null")
    db.commit()
    assert publish_a(publish_client_a, env)["widget_count"] == 3


def test_role_access_requires_non_empty_roles(publish_client_a, db, env):
    """access=role 却不给角色码 = 谁都不能看，属于发布参数非法，当场拒（而不是留到访问时 403）。"""
    r = publish_client_a.post(f"/api/v1/twins/pages/{env['page_id']}/publish",
                              json={"access": "role", "role_codes": []})
    assert r.status_code == 400 and r.json()["code"] == "TWIN_PUBLISH_FORBIDDEN"


def test_org_publish_stores_no_role_codes(publish_client_a, db, env):
    """access=org 时 `role_codes_json` 必须为 NULL：留着值会被误读成「还有角色限制」。"""
    b = publish_a(publish_client_a, env, role_codes=["SEC_ADMIN"])
    assert b["access"] == "org" and b["role_codes"] is None
```

- [ ] **Step 4: 写失败测试（下：访问链 · 快照边界 · 审计 · 权限门）**

接在同一文件之后：

```python
# ------------------------------------------------------------ 访问校验链

def test_every_denial_shares_one_code_and_message(publish_client_a, publish_client_b, db, env):
    """边界 2（反枚举）：未知 slug / 跨租户 / 已停用 / 角色不命中，四种失败**逐字相同**。

    差异只写进审计记录（`reason`），绝不上响应体——否则调用方可以用返回码差把
    「存在但无权」与「不存在」区分出来，等于给了枚举预言机。
    """
    b = publish_a(publish_client_a, env, access="role", role_codes=["SEC_ADMIN"])
    role_miss = publish_client_a.get(f"/api/v1/twin-p/{b['slug']}")   # 存在，但访客无角色
    cross = publish_client_b.get(f"/api/v1/twin-p/{b['slug']}")       # 存在于 A 租，B 租看不到
    unknown = publish_client_a.get("/api/v1/twin-p/definitely-not-a-slug")
    data_denied = publish_client_a.post(f"/api/v1/twin-p/{b['slug']}/data", json={})
    for r in (role_miss, cross, unknown, data_denied):
        assert r.status_code == 403, r.text
        assert r.json()["code"] == "TWIN_ACCESS_REQUIRED"
        assert r.json()["message"] == tp.DENY_MESSAGE      # 同一句话，无差异信号


def test_role_gate_is_fail_closed_at_service_layer(db, env):
    """角色命中→放行；不命中→403；`ctx is None`→403（`tool_context.py:13-15` 的安全红线）。"""
    row = pub(db, ctx_of()).publish(env["page_id"], access="role", role_codes=["SEC_ADMIN"])
    assert pub(db, ctx_of("SEC_ADMIN")).get_by_slug(row["slug"])["slug"] == row["slug"]
    with pytest.raises(ApiError) as miss:
        pub(db, ctx_of("VIEWER")).get_by_slug(row["slug"])
    assert miss.value.code == "TWIN_ACCESS_REQUIRED" and miss.value.http_status == 403
    with pytest.raises(ApiError) as anon:
        pub(db, None).get_by_slug(row["slug"])
    assert anon.value.code == "TWIN_ACCESS_REQUIRED"


def test_admin_bypasses_role_gate(db, env):
    row = pub(db, ctx_of()).publish(env["page_id"], access="role", role_codes=["SEC_ADMIN"])
    assert pub(db, ctx_of(is_admin=True)).get_by_slug(row["slug"])["version"] == 1


def test_unpublish_revokes_and_keeps_row(publish_client_a, db, env):
    """停用=改 status，**留行**（审计链与版本史不断档），slug 不回收；重复停用 404。"""
    b = publish_a(publish_client_a, env)
    r = publish_client_a.delete(f"/api/v1/twins/publish/{b['publish_id']}")
    assert r.status_code == 204
    assert publish_client_a.get(f"/api/v1/twin-p/{b['slug']}").status_code == 403
    kept = db.execute(text("SELECT status, version FROM twin_publish WHERE slug = :s"),
                      {"s": b["slug"]}).first()
    assert kept[0] == "disabled" and int(kept[1]) == 1
    assert publish_client_a.delete(f"/api/v1/twins/publish/{b['publish_id']}").status_code == 404


def test_republish_after_unpublish_revokes_back(publish_client_a, db, env):
    """停用后重发布：**沿用同 slug**（对外已分发出去的链接不该因一次误停而永久作废）、
    version 继续 +1、status 回到 enabled。"""
    b = publish_a(publish_client_a, env)
    publish_client_a.delete(f"/api/v1/twins/publish/{b['publish_id']}")
    second = publish_a(publish_client_a, env)
    assert second["slug"] == b["slug"] and second["version"] == 2
    assert publish_client_a.get(f"/api/v1/twin-p/{second['slug']}").status_code == 200


def test_delete_page_cascades_publish_row(publish_client_a, db, env):
    """删页面 → FK CASCADE 带走发布行 → slug 立即失效（无需「先取消发布」的口头约定）。"""
    b = publish_a(publish_client_a, env)
    assert publish_client_a.delete(f"/api/v1/twins/pages/{env['page_id']}").status_code == 204
    assert publish_client_a.get(f"/api/v1/twin-p/{b['slug']}").status_code == 403


def test_paused_card_still_serves_readonly_page(publish_client_a, db, env):
    """边界 3：`runtime_state` 管轮询与工作台可见性，`twin_publish.status` 管只读页可用性，
    两者正交。暂停卡片不得静默打断已经分发的只读链接。"""
    b = publish_a(publish_client_a, env)
    db.execute(text("UPDATE twin_card SET runtime_state = 'paused' WHERE id = :c"),
               {"c": env["card_id"]})
    db.commit()
    assert publish_client_a.get(f"/api/v1/twin-p/{b['slug']}").status_code == 200


# ---------------------------------------------------- 快照语义 vs 实时数据

def test_metadata_and_params_come_from_snapshot(publish_client_a, db, env):
    """发布冻的是**结构**：发布后改组件标题与参数实值，只读页仍按快照回。"""
    b = publish_a(publish_client_a, env)
    db.execute(text("UPDATE twin_widget SET title = '改过名', "
                    "param_values_json = CAST(:p AS jsonb) WHERE id = :i"),
               {"p": '{"line":"ZZ"}', "i": env["w_kpi"]})
    db.commit()
    meta = publish_client_a.get(f"/api/v1/twin-p/{b['slug']}").json()
    assert [w["title"] for w in meta["widgets"]] == ["kpi-0", "trend-1"]
    publish_client_a.post(f"/api/v1/twin-p/{b['slug']}/data", json={"params": {"line": "L9"}})
    got = {c["sql"]: c["params"] for c in FakeRun.calls}
    # 快照值：既不是发布后改的 ZZ，也不是请求里传来的 L9（快照已存的实值优先）
    assert got["SELECT oee FROM demo_device_stat"] == {"line": "L1"}


def test_run_returns_current_query_output(publish_client_a, db, env):
    """数据**恒实时**：快照只冻结构、不冻行业务数据（发布时不物化，遵守上游 D2）。

    换一次执行层返回值并清缓存，只读页立刻看到新值——10s TTL 是性能措施，不是数据快照。
    """
    b = publish_a(publish_client_a, env)
    first = publish_client_a.post(f"/api/v1/twin-p/{b['slug']}/data", json={}).json()
    FakeRun.payload = {"columns": ["oee"], "rows": [[0.42]], "row_count": 1, "truncated": False}
    td.reset_data_cache()
    second = publish_client_a.post(f"/api/v1/twin-p/{b['slug']}/data", json={}).json()
    assert first["items"][0]["data"]["value"] == 0.85
    assert second["items"][0]["data"]["value"] == 0.42


def test_run_items_share_the_15_key_contract(publish_client_a, db, env):
    """T11 与 T8 共用同一个结果契约：前端因此只有一套 `WidgetShell`（§6.3 承重原则）。"""
    b = publish_a(publish_client_a, env)
    body = publish_client_a.post(f"/api/v1/twin-p/{b['slug']}/data", json={}).json()
    assert body["slug"] == b["slug"] and body["version"] == 1 and body["count"] == 2
    assert all(len(i) == 15 for i in body["items"])
    assert [i["state"] for i in body["items"]] == ["ok", "ok"]


# ---------------------------------------------------------- 审计埋点（§4.4）

def test_access_audit_fires_on_both_allow_and_deny(publish_client_a, db, env, monkeypatch):
    """只读页的访问审计由服务层自己埋，**成功与失败都记**，差异只进 `reason`。"""
    seen: list = []
    monkeypatch.setattr(tp, "_record_access", lambda _db, **kw: seen.append(kw))
    b = publish_a(publish_client_a, env)
    assert publish_client_a.get(f"/api/v1/twin-p/{b['slug']}").status_code == 200
    assert publish_client_a.get("/api/v1/twin-p/nope-nope-nope-nope").status_code == 403
    assert [s["reason"] for s in seen] == ["granted", "not-found"]
    assert [s["allowed"] for s in seen] == [True, False]
    assert [s["action"] for s in seen] == ["metadata", "metadata"]
    assert seen[0]["version"] == 1 and seen[1]["version"] is None


def test_record_access_never_raises(db, env):
    """审计写是**尽力而为**：失败必须吞掉，不能把只读页打成 500，也不能弄坏请求 Session。"""
    tp._record_access(db, tenant_id=TENANT_A, user_id=101, username="u-101",
                      slug="x" * 24, action="metadata", allowed=False,
                      reason="not-found", version=None)          # 不得抛
    assert db.execute(text("SELECT 1")).scalar_one() == 1        # 请求 Session 仍可用


# ---------------------------------------------------------- 发布权限门

def _other_card(db, env, perm):
    """builder：owner=999 的卡 + 1 个已绑查询的组件 + 给 101 的 `perm` 授予，返回 page_id。"""
    ex = lambda s, p=None: db.execute(text(s), p or {})  # noqa: E731
    cid = int(ex("INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, "
                 "runtime_state, owner_id) VALUES (:t, '他人卡', :o, 1, 'live', 999) RETURNING id",
                 {"t": TENANT_A, "o": env["ontology_id"]}).scalar_one())
    pid = int(ex("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
                 "VALUES (:t, :c, '页', 0) RETURNING id", {"t": TENANT_A, "c": cid}).scalar_one())
    ex("INSERT INTO twin_widget (tenant_id, page_id, widget_key, title, query_id, sort_order) "
       "VALUES (:t, :p, 'kpi', 'OEE', :q, 0)", {"t": TENANT_A, "p": pid, "q": env["q_kpi"]})
    ex("INSERT INTO twin_card_share (tenant_id, card_id, grantee_type, grantee_id, perm, granted_by) "
       "VALUES (:t, :c, 'user', 101, :perm, 999)", {"t": TENANT_A, "c": cid, "perm": perm})
    db.commit()
    return pid


def test_read_share_is_not_enough_to_publish(publish_client_a, db, env):
    """T10 是**写操作**：只有 read 授予的人能看这一张卡，不能把它发布出去。"""
    pid = _other_card(db, env, "read")
    r = publish_client_a.post(f"/api/v1/twins/pages/{pid}/publish", json={})
    assert r.status_code == 403 and r.json()["code"] == "TWIN_ACCESS_REQUIRED"


def test_edit_share_may_publish(publish_client_a, db, env):
    r = publish_client_a.post(f"/api/v1/twins/pages/{_other_card(db, env, 'edit')}/publish", json={})
    assert r.status_code == 200, r.text


def test_cross_tenant_publish_is_404(publish_client_b, db, env):
    """跨租户发布：页面不存在于 B 租 → 404（与「无权发布」的 403 不同，因为资源本身不可见）。"""
    r = publish_client_b.post(f"/api/v1/twins/pages/{env['page_id']}/publish", json={})
    assert r.status_code == 404 and r.json()["code"] == "TWIN_PAGE_NOT_FOUND"
```

- [ ] **Step 5: 跑到失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/twin/test_twin_publish.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.twin.twin_publish_service'`
（若先报 `ImportError: cannot import name 'publish_router'`，那是 Step 2 的 conftest 已改而
 Step 8 的 router 未建——属正常失败序，继续写实现即可）

- [ ] **Step 6: 写 `backend/app/services/twin/twin_publish_service.py`（上半：slug · 审计埋点 · 写权限门 · T10）**

```python
"""发布登记与只读运行（spec §4.4 / §3.5 / P0-7 / W12）。

一句话职责：**把页面配置冻成一行快照**，并按随机 `slug` 对访客放行或拒止。
本层不取数（全部交 Task 7）、不做列脱敏（交出口层）、不生成 SQL（交语义层）。

三条不可妥协的边界（与测试一一对应）：

1. **slug 一律随机**（`secrets.token_urlsafe(18)` = 24 字符）：自增 id 派生等于把
   未发布的孪生页变成可枚举资源。→ `test_new_slug_is_random_and_unpredictable`
2. **访问失败一律同一信号**（403 + 同一 message）：未知 slug / 跨租户 / 已停用 /
   角色不命中共用 `TWIN_ACCESS_REQUIRED`，差异只写进审计的 `reason`，**绝不上响应体**。
   → `test_every_denial_shares_one_code_and_message`
3. **快照只冻结构、不冻数据**：元数据与参数实值回快照，行数据每次直连现查（上游 D2）。
   → `test_metadata_and_params_come_from_snapshot` / `test_run_returns_current_query_output`
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.tool_manager.tool_context import ToolUserContext
from app.core.api_error import (
    ApiError, TWIN_ACCESS_REQUIRED, TWIN_NOT_PUBLISHED, TWIN_PUBLISH_FORBIDDEN,
)
from app.models.ontology.query import MetaOntologyQuery
from app.models.sys.sys_user import SysAuditLog
from app.models.twin import TwinCard, TwinPage, TwinPublish, TwinWidget
from app.services.twin.twin_data_service import TwinDataService, WidgetSpec
from app.services.twin.twin_service import WRITABLE_ACCESS, TwinService

logger = logging.getLogger(__name__)

ACCESS_ORG, ACCESS_ROLE = "org", "role"
PUBLISH_ACCESS = (ACCESS_ORG, ACCESS_ROLE)
SLUG_BYTES = 18                  # token_urlsafe(18) → 24 字符：落在 String(32) 内且无 '=' 填充
SNAPSHOT_SCHEMA = 1              # 快照结构版本：Plan 2 的渲染器按它兼容历史发布行
DENY_MESSAGE = "只读页不存在或无权访问"     # 所有拒因共用的一句话（边界 2）
AUDIT_MODULE = "twin:publish"    # 命名律照 `ai:sqlbot_tool`（sqlbot_template_tool.py:50）


def new_slug() -> str:
    """只读页标识：**随机、不可猜、非 id 派生**（边界 1）。"""
    return secrets.token_urlsafe(SLUG_BYTES)


def _now_iso() -> str:
    """与 Task 7 同格式的时间戳。**故意不 import 它的私有 `_now_iso`**：跨模块吃下划线
    函数会把两个服务的改动面焊在一起，两行复制更便宜。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _record_access(db: Session, *, tenant_id: int, user_id: int, username: str,
                   slug: str, action: str, allowed: bool, reason: str,
                   version: Optional[int]) -> None:
    """把一次只读页访问写进 `sys_audit_log`（spec §4.4「审计日志覆盖每次访问」）。

    三条设计取舍，都是实测结论：

    1. **不走中间件**：`AUDIT_LOG_SKIP_METHODS` 默认 `"GET"`（`app/config/_audit.py:10`），
       而元数据端点是 GET，中间件根本不会记它；改全局默认值会波及所有既有 GET 接口，P0 不动。
    2. **成功也记**：安全事件的价值是「谁在什么时候看过哪一页」，只记 403 等于只记失败。
       `reason` 只落审计，**不上响应体**（否则就是枚举预言机）。
    3. **尽力而为**：用 `db.get_bind()` 开**独立 Session**（不搭请求事务的车：请求失败也要
       留下审计），并吞掉一切异常——审计表缺失不得把只读页打成 500
       （先例同律：`sqlbot_template_tool.py:343-344`）。
    """
    try:
        # 计划缺陷修正（执行时实测，2026-11-01）：`sys_audit_log` **没有 `tenant_id` 列**
        # （`models/sys/sys_user.py` 的 `SysAuditLog` 以 `log_id` 为主键，不带 TenantMixin），
        # 原稿的 `tenant_id=tenant_id` 会在构造实体时 `TypeError`；租户维度改落
        # `request_params.tenantId`（与先例 `sqlbot_template_tool.py:328-336` 同律）。
        with Session(db.get_bind()) as s:
            s.add(SysAuditLog(
                user_id=user_id or None,
                username=username or None,
                operation_type="query",              # 沿用中间件的取值域，不发明新枚举
                operation_module=AUDIT_MODULE,
                operation_desc=f"访问孪生只读页 {slug}（{action}）"
                               + ("" if allowed else "：拒绝"),
                request_params={"tenantId": tenant_id, "slug": slug, "action": action,
                                "allowed": allowed, "reason": reason, "publishVersion": version},
                response_status=200 if allowed else 403,
            ))
            s.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("孪生只读页审计写入失败（已忽略）slug=%s allowed=%s: %s", slug, allowed, exc)


class TwinPublishService:
    """T10 发布/停用 + T11 只读页元数据与取数。"""

    def __init__(self, db: Session, tenant_id: Optional[int], user_id: int,
                 ctx: Optional[ToolUserContext] = None,
                 session_factory: Optional[Callable[[], Session]] = None) -> None:
        if tenant_id is None:
            raise ValueError("tenant_required")      # Global Constraints：服务构造必带租户
        self.db = db
        self.tenant_id = int(tenant_id)
        self.user_id = int(user_id or 0)
        self.ctx = ctx
        self._session_factory = session_factory
        self._orch = TwinService(db, self.tenant_id, self.user_id,
                                 tuple(ctx.role_codes) if ctx else ())

    # ------------------------------------------------------------ 写权限门

    def _assert_writable_card(self, card_id: int) -> None:
        """发布是**写操作**：owner 或 edit 授予才能发。

        刻意不伸进 `TwinService._writable_card()`（私有实现），而是复用公开的 `get_card()`：
        它已经把「不可读→404 / 非写→无权」两步口径收在一处，两个服务各写一遍内部判断迟早 drift。
        """
        access = self._orch.get_card(int(card_id))["access"]
        if access not in WRITABLE_ACCESS:
            raise ApiError(TWIN_ACCESS_REQUIRED, "无权发布该卡片的页面", 403,
                           {"card_id": int(card_id), "access": access})

    def _assert_writable_page(self, page_id: int) -> Tuple[TwinPage, TwinCard]:
        page, card = self._orch.page_with_card(page_id)      # 不存在或跨租户 → 404
        self._assert_writable_card(int(card.id))
        return page, card

    def _widgets_of(self, page_id: int) -> List[TwinWidget]:
        return list(self.db.execute(
            select(TwinWidget).where(TwinWidget.page_id == int(page_id))
            .order_by(TwinWidget.sort_order, TwinWidget.id)
        ).scalars().all())

    # ------------------------------------------------------------ T10 发布

    @staticmethod
    def _clean_role_codes(access: str,
                          role_codes: Optional[Sequence[str]]) -> Optional[List[str]]:
        """`access=org` 时**不存角色码**：留着值会被误读成「还有角色限制」。"""
        codes = sorted({str(c).strip() for c in (role_codes or []) if str(c).strip()})
        if access == ACCESS_ROLE:
            if not codes:
                raise ApiError(TWIN_PUBLISH_FORBIDDEN, "access=role 必须至少给出一个角色码", 400,
                               {"access": access, "role_codes": list(role_codes or [])})
            return codes
        return None

    def _assert_bindings_runnable(self, widgets: List[TwinWidget]) -> None:
        """发布前置闸：**绑了就必须能跑**。

        未绑定（`query_id IS NULL`）合法——`scene2d` 天生不吃查询（Task 6 配对表里它的形状集
        为空），拒未绑定会把整个场景模块打成不可发布；运行期由四态里的 empty/unbound 表达。
        """
        qids = sorted({int(w.query_id) for w in widgets if w.query_id})
        defs: Dict[int, MetaOntologyQuery] = {}
        if qids:
            defs = {int(r.id): r for r in self.db.execute(
                select(MetaOntologyQuery).where(
                    MetaOntologyQuery.tenant_id == self.tenant_id,
                    MetaOntologyQuery.id.in_(qids))
            ).scalars().all()}
        bad: List[Dict[str, Any]] = []
        for w in widgets:
            if not w.query_id:
                continue
            q = defs.get(int(w.query_id))
            if q is None:
                bad.append({"widget_id": int(w.id), "reason": "查询定义不存在或不属于本租户"})
            elif q.status != "enabled":
                bad.append({"widget_id": int(w.id), "reason": f"查询 {q.code} 已被 owner 停用"})
            elif q.verify_status != "verified" or not q.compiled_sql or not q.source_id:
                bad.append({"widget_id": int(w.id),
                            "reason": f"查询 {q.code} 尚未 preview 通过"
                                      f"（verify_status={q.verify_status}）"})
        if bad:
            raise ApiError(TWIN_PUBLISH_FORBIDDEN, "存在不可运行的绑定：逐条 preview 通过后再发布",
                           400, {"widgets": bad})

    def _build_snapshot(self, page: TwinPage, card: TwinCard,
                        widgets: List[TwinWidget]) -> Dict[str, Any]:
        """发布时冻结的配置。**键名与 `WidgetSpec.from_snapshot`（Task 7）逐字对称**：
        两侧字段名不一致就会出现「只读页把编辑期实值当快照值用」这类难查 bug。
        """
        return {
            "schema": SNAPSHOT_SCHEMA,
            "card": {"id": int(card.id), "name": card.name, "icon": card.icon,
                     "description": card.description, "scene_key": card.scene_key,
                     "ontology_id": int(card.ontology_id),
                     "ontology_version": int(card.ontology_version or 0)},
            "page": {"id": int(page.id), "name": page.name,
                     "sort_order": int(page.sort_order or 0), "refresh_json": page.refresh_json},
            "widgets": [{
                "widget_id": int(w.id), "widget_key": w.widget_key, "title": w.title,
                "query_id": int(w.query_id) if w.query_id else None,
                "param_values_json": dict(w.param_values_json or {}),
                "grid_json": dict(w.grid_json or {}),
                "refresh_json": dict(w.refresh_json or {}),
                "display_json": dict(w.display_json or {}),
                "sort_order": int(w.sort_order or 0),
            } for w in widgets],
        }

    def _latest_row(self, page_id: int) -> Optional[TwinPublish]:
        """该页**最近一版**发布记录（**不限 status**：disabled 的行重发布时沿用同 slug）。"""
        return self.db.execute(
            select(TwinPublish)
            .where(TwinPublish.tenant_id == self.tenant_id, TwinPublish.page_id == int(page_id))
            .order_by(TwinPublish.version.desc(), TwinPublish.id.desc()).limit(1)
        ).scalar_one_or_none()

    def _unique_slug(self) -> str:
        """生成本租户未占用的 slug。24 字符随机串的碰撞概率可忽略，但唯一约束在库侧，
        重试只是把一个难看的 500 变成一次静默重来。"""
        for _ in range(5):
            slug = new_slug()
            taken = self.db.execute(
                select(TwinPublish.id).where(TwinPublish.tenant_id == self.tenant_id,
                                             TwinPublish.slug == slug)
            ).scalar_one_or_none()
            if taken is None:
                return slug
        raise ApiError(TWIN_PUBLISH_FORBIDDEN, "slug 生成失败（极小概率碰撞），请重试发布", 409)

    @staticmethod
    def _publish_dict(row: TwinPublish, widget_count: int) -> Dict[str, Any]:
        snap = row.snapshot_json or {}
        return {
            "publish_id": int(row.id), "page_id": int(row.page_id), "card_id": int(row.card_id),
            "slug": row.slug,
            # 两个路径字段缺一不可：`url` 是前端路由，`api_path` 是后端调用路径（nginx 只代理 /api/）
            "url": f"/twin-p/{row.slug}",
            "api_path": f"/api/v1/twin-p/{row.slug}",
            "version": int(row.version or 1), "access": row.access,
            "role_codes": row.role_codes_json, "status": row.status,
            "widget_count": widget_count,
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "snapshot_schema": int(snap.get("schema") or 0),
        }

    def publish(self, page_id: int, *, access: str = ACCESS_ORG,
                role_codes: Optional[Sequence[str]] = None) -> Dict[str, Any]:
        """发布/重发布：写权限门 → 前置闸 → 冻快照 → 插新行或版本+1。

        同页重复发布**沿用 slug**（已分发出去的外链不能因一次重发布而作废），
        `version` 继续 +1，`snapshot_json` 整体重写。已停用的行被重新发布时回到 enabled。
        """
        page, card = self._assert_writable_page(page_id)
        if access not in PUBLISH_ACCESS:
            raise ApiError(TWIN_PUBLISH_FORBIDDEN, f"access 只支持 {ACCESS_ORG} 或 {ACCESS_ROLE}",
                           400, {"access": access})
        codes = self._clean_role_codes(access, role_codes)
        widgets = self._widgets_of(int(page.id))
        if not widgets:
            raise ApiError(TWIN_PUBLISH_FORBIDDEN, "页面还没有任何模块，发布出去只是一张空页",
                           400, {"page_id": int(page.id), "widget_count": 0})
        self._assert_bindings_runnable(widgets)
        snapshot = self._build_snapshot(page, card, widgets)
        row = self._latest_row(int(page.id))
        if row is None:
            row = TwinPublish(tenant_id=self.tenant_id, card_id=int(card.id),
                              page_id=int(page.id), slug=self._unique_slug(), access=access,
                              role_codes_json=codes, snapshot_json=snapshot, version=1,
                              status="enabled", published_by=self.user_id)
            self.db.add(row)
        else:
            # 不改 row.slug：这就是“外链不失效”的全部实现（故意不写 `row.slug = row.slug`）
            row.version = int(row.version or 1) + 1
            row.status = "enabled"
            row.access = access
            row.role_codes_json = codes
            row.snapshot_json = snapshot          # JSONB 列直接赋新 dict：整体重写，不做 merge
            row.published_by = self.user_id
            row.published_at = func.now()         # DB 侧 now()：不把应用时区带进 naive TIMESTAMP 列
        self.db.commit()
        self.db.refresh(row)
        logger.info("孪生页面发布 card=%s page=%s slug=%s version=%s access=%s",
                    int(card.id), int(page.id), row.slug, row.version, access)
        return self._publish_dict(row, len(widgets))

    def unpublish(self, publish_id: int) -> None:
        """停用：**改 status，不删行**。

        删行会让 slug 可被他人复用（历史链接指向新内容），且审计日志里的
        `publishVersion` 失去可追溯的记载。行由卡片/页面删除时的 FK CASCADE 自然带走。

        重复停用回 **404**：已停用的行不再是「可被撤下的发布」。
        （计划缺陷修正：执行时实测，2026-11-01——本步原稿缺这一道闸门，会得到
        幂等式 204，与 Step 4 的 `test_unpublish_revokes_and_keeps_row` 相矛盾。）
        """
        row = self.db.get(TwinPublish, publish_id)
        if row is None or int(row.tenant_id or 0) != self.tenant_id:
            raise ApiError(TWIN_NOT_PUBLISHED, "发布记录不存在", 404, {"publish_id": int(publish_id)})
        if str(row.status) != "enabled":
            raise ApiError(TWIN_NOT_PUBLISHED, "发布记录已停用", 404,
                           {"publish_id": int(publish_id), "status": str(row.status)})
        self._assert_writable_card(int(row.card_id))
        row.status = "disabled"
        self.db.commit()
        logger.info("孪生只读页停用 publish_id=%s slug=%s", int(row.id), row.slug)
```

- [ ] **Step 7: 追写 `twin_publish_service.py`（下半：T11 访问校验链 + 只读取数）**

接在 `unpublish()` 之后（仍在 `TwinPublishService` 类内，缩进四格）：

```python
    # ------------------------------------------------------------ T11 只读页

    def _role_hit(self, codes: Optional[Sequence[str]]) -> bool:
        if self.ctx is None:
            return False            # 上下文构造失败 = 最小权限（tool_context.py:13-15 的红线）
        if self.ctx.is_admin:
            return True
        # `has_any_role([])` 本身返回 False（tool_context.py:61-62），所以空角色集天然 fail-closed
        return self.ctx.has_any_role(list(codes or []))

    def _verdict(self, row: Optional[TwinPublish]) -> Tuple[bool, str]:
        """返回 `(allowed, reason)`。**reason 只进审计，永远不上响应体**（边界 2）。"""
        if row is None:
            # 未知 slug / 跨租户 / 已停用——三者在查行阶段就合并成同一个信号，不区分
            return False, "not-found"
        if str(row.access) == ACCESS_ROLE and not self._role_hit(row.role_codes_json):
            return False, "role-miss"
        return True, "granted"

    def _grant_or_deny(self, slug: str, *, action: str) -> TwinPublish:
        """访问校验链（spec §4.4）：`slug → status=enabled → access(org/role) → 放行`。

        租户过滤与 `status='enabled'` 全部写进**同一条查询**：把「不存在」与「已停用」
        在代码里分成两个分支，就是给枚举留差异化信号。
        """
        row = self.db.execute(
            select(TwinPublish).where(TwinPublish.tenant_id == self.tenant_id,
                                      TwinPublish.slug == slug,
                                      TwinPublish.status == "enabled")
        ).scalar_one_or_none()
        allowed, reason = self._verdict(row)
        _record_access(self.db, tenant_id=self.tenant_id, user_id=self.user_id,
                       username=(self.ctx.username if self.ctx else ""),
                       slug=slug, action=action, allowed=allowed, reason=reason,
                       version=int(row.version) if row is not None else None)
        if not allowed:
            raise ApiError(TWIN_ACCESS_REQUIRED, DENY_MESSAGE, 403,
                           {"slug": slug, "action": action})
        return row

    def get_by_slug(self, slug: str) -> Dict[str, Any]:
        """T11 元数据：**一律回快照**，绝不回表读 `twin_widget`。

        否则「发布后继续编辑」会静默改掉已发布页面的结构，而编辑者并不认为自
        己发布了新版本——这正是只读页最难排查的一类问题。
        """
        row = self._grant_or_deny(slug, action="metadata")
        snap = dict(row.snapshot_json or {})
        page = dict(snap.get("page") or {})
        return {
            "slug": row.slug, "version": int(row.version or 1), "access": row.access,
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "card": dict(snap.get("card") or {}),
            "page": page,
            "widgets": list(snap.get("widgets") or []),
            "refresh": page.get("refresh_json"),       # 前端轮询档位（快照值，非实时）
            "snapshot_schema": int(snap.get("schema") or 0),
        }

    def _data_service(self) -> TwinDataService:
        """取数直接交给 Task 7：四态、15 键契约、扇出闸门、角色签名缓存与出口脱敏
        在编辑态与运行态**逐字相同**，前端因此只需一套 `WidgetShell`（§6.3 承重原则）。"""
        return TwinDataService(self.db, self.tenant_id, self.user_id, self.ctx,
                               session_factory=self._session_factory)

    def run_by_slug(self, slug: str,
                    page_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """T11 取数：**结构来自快照，数据来自直连**（每次访问现查，不落任何物化行）。

        访客身份驱动出口脱敏：发布**从不放大未脱敏值**——无豁免角色的访客得到的仍是
        `state=masked` 的结果，与他在工作台里看到的完全一致。
        """
        row = self._grant_or_deny(slug, action="data")
        specs = [WidgetSpec.from_snapshot(w)
                 for w in ((row.snapshot_json or {}).get("widgets") or [])]
        base = dict(page_params or {})
        for s in specs:
            s.base_params = base        # 与 T8 同律：只在查询声明过的键上落地，不是广播
        items = self._data_service().execute_specs(specs)
        return {"slug": row.slug, "version": int(row.version or 1),
                "page_id": int(row.page_id), "card_id": int(row.card_id),
                "collected_at": _now_iso(), "count": len(items), "items": items}
```

> **为何只读页不再查 `twin_card_share`**（设计决策，不是遗漏）：发布就是 owner 把这一页
> **显式授予**一个更大人群的动作。若同时要求「访客在 `twin_card_share` 里可读」，那么
> `access=org` 的发布对同租户绝大多数用户永远 403——他们本来就在原型 🔒「受限」列表里
> （`prototype:299`），发布功能形同虚设。两条补偿控制：出口脱敏照常按访客角色执行，
> 以及取消发布即回收（`status='disabled'` 后同一 slug 立即 403）。同理 `runtime_state` 也不参与
> 判定（它管工作台可见性与轮询，与 `twin_publish.status` 正交）——`test_paused_card_still_serves_readonly_page` 钉住这一条。

- [ ] **Step 8: 给 `backend/app/routers/twin/twin.py` 加 T10 / T11**

顶部 import 区追加一行（按字母序插在 `twin_data_service` 那行之后）：

```python
from app.services.twin.twin_publish_service import TwinPublishService
```

在 `router = APIRouter(prefix="/api/v1/twins", tags=["孪生应用"])` 那一行之后紧接着声明第二个 router：

```python
# 只读页与工作台共用同一个模块，但**不同前缀**：工作台走 /api/v1/twins/*（要写权限），
# 只读页走 /api/v1/twin-p/*（只要发布授权）。分成两个 APIRouter 才可能在
# router_registry 里各自挂载，也才挡住「把只读端点误挂到写权限链上」的错。
publish_router = APIRouter(prefix="/api/v1/twin-p", tags=["孪生应用·只读页"])
```

在 `LayoutBody` 之后追加 Body：

```python
class PublishBody(BaseModel):
    """发布参数（spec §3.5）：`access=org` 同租户可见，`role` 仅指定角色可见（public 留 P1）。"""

    access: str = Field("org", description="org|role")
    role_codes: Optional[List[str]] = Field(None, max_length=32)
```

在 `_data_svc()` 之后追加发布服务构造器：

```python
def _pub_svc(db: Session, current_user: SysUser) -> TwinPublishService:
    """`session_factory` 与 `_data_svc()` 同一做法：只读页取数也要在工作线程里开新 Session，
    不能复用当前请求 Session（SQLAlchemy Session 不是线程安全的）。"""
    ctx = build_user_context(db, current_user)
    bind = db.get_bind()
    return TwinPublishService(db, _require_tenant_id(current_user),
                              int(getattr(current_user, "user_id", 0) or 0), ctx,
                              session_factory=lambda: Session(bind, expire_on_commit=False))
```

在文件末尾（T8–T9 区块之后）追加四个端点：

```python
# ------------------------------------------------------------ T10 发布 / 停用


@router.post("/pages/{page_id}/publish")
def publish_page(page_id: int, body: Optional[PublishBody] = None,
                 db: Session = Depends(get_db),
                 current_user: SysUser = Depends(get_current_user)) -> dict:
    """T10 发布。**恒回 200 而不是 201**：同一页面的重复发布是同一资源的版本推进
    （slug 不变、version+1），回 201 会诱导前端把它当新资源再插一条。"""
    b = body or PublishBody()
    return _pub_svc(db, current_user).publish(page_id, access=b.access, role_codes=b.role_codes)


@router.delete("/publish/{publish_id}", status_code=204)
def unpublish_page(publish_id: int, db: Session = Depends(get_db),
                   current_user: SysUser = Depends(get_current_user)) -> Response:
    """T10 停用：改 `status='disabled'`，留行保审计与版本史，slug 不回收。"""
    _pub_svc(db, current_user).unpublish(publish_id)
    return Response(status_code=204)


# ---------------------------------------------------------- T11 只读页（发布前缀）


@publish_router.get("/{slug}")
def read_published_page(slug: str, db: Session = Depends(get_db),
                        current_user: SysUser = Depends(get_current_user)) -> dict:
    """T11 元数据：结构来自发布快照，发布后的编辑动作不影响已发布页面。

    仍然要 `get_current_user`：P0 只发**登录态**只读页（§7.1 7a），分享票据与公开链接属 P1
    （T17，新攻击面必须与水印/限流同批）。"""
    return _pub_svc(db, current_user).get_by_slug(slug)


@publish_router.post("/{slug}/data")
def read_published_data(slug: str, body: Optional[DataBody] = None,
                        db: Session = Depends(get_db),
                        current_user: SysUser = Depends(get_current_user)) -> dict:
    """T11 取数：数据恒实时。复用 Task 7 的 `DataBody`，**不另建同名 Body**。"""
    return _pub_svc(db, current_user).run_by_slug(slug, body.params if body else None)
```

再把 `backend/app/core/router_registry.py` 里 Task 6 加的那一段**整体替换**（原文含 Task 6 留下的
「本期先不声明」注释，本步必须一并清掉，否则注释与代码矛盾）：

原文：

```python
    # --- 33. 孪生应用（自带完整 prefix /api/v1/twins，故此处不叠加）---
    # Task 8 会在同一模块再加一条 attr="publish_router"（先例：app.routers.kb.kg 的
    # router + build_router 两条目，:202/:204），本期先不声明尚未存在的 publish_router。
    RouterSpec("app.routers.twin.twin", attr="router", tags=["孪生应用"]),
```

改为：

```python
    # --- 33. 孪生应用（同一模块两个 router，均自带完整 prefix，故此处不叠加）---
    # 先例：app.routers.kb.kg 的 router + build_router 两条目（:202/:204）。
    # 顺序不可颠倒也不可插到其它清单之间：本仓库的注册顺序即 Starlette 的匹配顺序。
    RouterSpec("app.routers.twin.twin", attr="router", tags=["孪生应用"]),
    RouterSpec("app.routers.twin.twin", attr="publish_router", tags=["孪生应用·只读页"]),
```

> 计划缺陷修正（执行时实测，2026-11-01）：原稿把注释写成 `--- 33~34.`，但 Task 6 之后清单
> 尾部已多了一条外部加进来的 **`--- 34. 视频会议 ---`**（LiveKit，不属于本计划），
> 写 `33~34` 会与之重号；因此注释保持单号 `33.`，只在正文说明「同一模块两个 router」。

- [ ] **Step 9: 跑到通过 + 启动不报错**

Run: `.\.venv\Scripts\python.exe -m pytest tests/twin/test_twin_publish.py -v`
Expected: PASS（23 passed）。失败时的排查序（按此序查，**不得改测试迁就实现**）：

1. `import publish_router` 报 `ImportError` → Step 8 里 `publish_router` 的声明被写到了
   `router` 之前或塞进了某个函数体（必须在模块顶层、`router = APIRouter(...)` 行之后）；
2. `TWIN_PUBLISH_FORBIDDEN` 未定义 → Step 1 的码没插到 `TWIN_QUERY_DISABLED` 之后，或拼写不同；
3. 四个拒绝路径的 `message` 不一致 → `_grant_or_deny` 里按 `reason` 拼了不同文案。**正确做法**：
   文案只取 `DENY_MESSAGE` 常量，`reason` 只能出现在审计 `request_params` 里；
4. `test_run_returns_current_query_output` 拿到旧值 → `run_by_slug` 里复用了元数据那次调用的
   缓存（应仅靠 Task 7 的 `_data_cache`，测试开头已 `reset_data_cache()`；若仍旧值，检查是否把
   `items` 也写进了 `snapshot_json`）；
5. `test_metadata_and_params_come_from_snapshot` 拿到新 title → `get_by_slug` 直连了 `twin_page`
   而不是 `row.snapshot_json["page"]`；快照字段名必须与 Step 6 `_build_snapshot()` 逐字一致；
6. 审计 spy 断言失败（`seen` 为空或只有一条）→ `_record_access` 被放在 `if not allowed:` 分支里了，
   或者异常被 `try/except` 吞在调用点而不是内部；正确形态是**先记后拒**；
7. `Session` 相关异常（并发使用 / 已关闭）→ `_record_access` 用了 `with Session(db.get_bind())` 而
   不是复用请求 Session；注意它**不开事务也不 commit 外层**，自身 `s.add` + `s.commit`；
8. `test_delete_page_cascades_publish_row` 拿到 403 以外的码 → 确认测试库真的执行了 0013 迁移
   （外键 `ondelete="CASCADE"` 缺失时会是 500 `IntegrityError`，而不是 403）。

Run: `.\.venv\Scripts\python.exe -m pytest tests/twin tests/ontology tests/unit -v`
Expected: 全绿。本任务不得回归 Task 1/4/5/6/7 的任何用例（尤其 `test_twin_data.py` 的 17 个：
若它们变红，优先怀疑 `_pub_svc` 里改了 `_data_svc` 的构造顺序，或误动了 `TwinDataService` 的签名）。

> ⚠️ **同 Task 7：本条合并跑不可用，必须逐目录跑**（跨目录收集污染 `Base.metadata` 先行缺陷，
> 会得到成片的 `UndefinedTable: … "kms_segment" does not exist`）。实测（全部 EXIT=0）：
> `tests/twin` **60 passed**（Task 6 的 20 + Task 7 的 17 + 本任务的 23）、
> `tests/ontology` **79 passed**、`tests/unit` **309 passed / 1 skipped**。

Run: `.\.venv\Scripts\python.exe -c "import app.main; print('router load ok')"`
Expected: 输出 `router load ok`，且日志无 `路由模块加载失败: app.routers.twin.twin`（新增的
第三条 `RouterSpec` 就是本步的验证对象；若 `attr="publish_router"` 写错，仓库的加载器会**打日志
而不抛异常**——所以必须目视确认日志里没有那一行失败，不能只看退出码）。

- [ ] **Step 10: 提交**

```bash
git add backend/app/core/api_error.py backend/app/services/twin/twin_publish_service.py backend/app/routers/twin/twin.py backend/app/core/router_registry.py backend/tests/twin/conftest.py backend/tests/twin/test_twin_publish.py
git commit -m "feat(twin): publish snapshot with anti-enumeration 403 and access audit"
```

> 路径需按实际 cwd 写（cwd=`backend` 时去掉 `backend/` 前缀），提交前用
> `git diff --cached --name-only` 核对无 frontend 混入。

#### Task 8 执行记录（2026-11-01）

交付：`twin_publish_service.py`（380 行）+ `publish_router` 与 T10/T11 四端点 +
`router_registry` 第二条 `RouterSpec` + `conftest` 的 `with_publish` 与两个夹具 +
`test_twin_publish.py`（**23 passed**）。未发现实现层生产缺陷，但计划有 3 处需修正：

| # | 类别 | 现象 | 修法 |
|---|---|---|---|
| 19 | 计划缺陷（Step 6 代码） | `_record_access` 给 `SysAuditLog(tenant_id=…)`：该表**无 `tenant_id` 列**（不带 TenantMixin，主键 `log_id`），计划 Step 4 的 `test_record_access_never_raises` 因异常被吞成 warning 而**不会报错**——真实的审计写入在线上会 100% 静默失败 | 去掉 `tenant_id=` 入参，租户维度改落 `request_params.tenantId`（照 `sqlbot_template_tool.py` 先例） |
| 20 | 计划缺陷（Step 6 vs Step 4） | `unpublish()` 无 `status` 闸门 ⇒ 重复停用回 204，`test_unpublish_revokes_and_keeps_row` 的 `assert 204 == 404` 失败（`22 passed / 1 failed`） | 按测试为真：补 `status != 'enabled'` → `TWIN_NOT_PUBLISHED` 404，不改测试 |
| 21 | 环境漂移（Step 8） | 计划把注释写为 `--- 33~34.`，但尾部已存在外部加入的 `--- 34. 视频会议 ---`，会重号 | 注释保持 `33.`，只拆条目不拆编号 |
| 22 | 环境漂移（Step 10 提交） | `app/core/router_registry.py` 的工作区 diff 是**单 hunk 混合**：我的 `publish_router` 条目与外部 LiveKit 的 `--- 34. 视频会议 ---` 三行落在同一个 `@@` 块里，`git add <file>` 会把他人接线并入本次提交 | 先临时删掉外部三行 → `git add` 该文件 → 原样写回；用 `git diff --cached … \| Select-String meeting` 为空证实索引干净，外部改动仍留在工作区未提交 |

提交：`56caf2e feat(twin): publish snapshot with anti-enumeration 403 and access audit`（7 文件）。

反枚举不变量已按期望钉住：四条拒因不同的失败（角色不命中 / 跨租户 / 未知 slug / data 端点）
得到**逐字相同**的 403 `DENY_MESSAGE`，差异只进审计 `request_params.reason`。
快照/实时边界同样双向：结构（标题与参数实值）回快照、行数据每次直连现查。

---

### Task 9: 权限申请闭环（申请 · 审批 · 授予 · 懒式过期）T12

对应 **P0-8**（验收 **W13**：申请 → owner 审批 → 转入「共享给我的（只读）」并含过期时间）。
本任务是 spec §4.5 表格里的第二行，也是 W5（进受限卡片自动弹 PermDrawer）能闭环的后端前提。

**六个自决项（执行者不需要再提问，但 review 时可逐条否定）**

| # | 议题 | 本计划的选定 | 为什么不是另一种 |
|---|---|---|---|
| 1 | 审批人范围 | **仅卡片 `owner`**（§10 Q1-A） | 方案 B（owner 或持 `kg:twin:publish` 者可批）把发布权变相成授权权。代价说白：owner 不在岗即卡死——P0 接受，不回避这个后果 |
| 2 | `required_role_code` 从哪来 | **申请时从该卡已启用发布行的 `role_codes_json` 取首码快照**（无则 NULL） | 给 `twin_card` 加一列要同时改 Task 1 模型/迁移/测试与 Task 6 的建卡体，性价比低；而发布闸已经是同一语义（「哪些角色能看」） |
| 3 | 批准的产物 | `twin_card_share`（`grantee_type='user'`、`perm='read'`、`source='request'`、`expires_at`）**upsert** | 不发一次性令牌（§3.7）；采 upsert（有则续期、无才插）而不就是为了避免同一 (card, user) 堆多行 share——`uq_twin_share` 在 Task 1 落库时是**普通索引**（见下方已知限制） |
| 4 | 过期怎么推 | **懒式**：读列表/审批前 `_lazy_expire()` 把过期 approved 单翻 `expired`；share 行不动 | 不引定时任务（零新依赖）。share 可见性已由 `_my_shares()` 的 `expires_at > now()` 天然闸住，故翻状态只是记账 |
| 5 | 申请人姓名 | **不 join `sys_user`**，只回 `applicant_id` | 测试库的建表清单 `_tables()` 未 import `app.models.sys.sys_user`（`backend/tests/ontology/conftest.py:59-69`），join 会在测试里直接 `relation "sys_user" does not exist`；Plan 2 可用现成的 `GET /api/v1/admin/users`（`backend/app/routers/sys/__init__.py:114`）在前端补姓名 |
| 6 | 已可读的人能不能申请 | **不能**：`access ∈ {owner, edit, read}` 一律 400 | 允许只会堆出一堆永远该被自动批准的单子，把抽屉变成噪声 |

**Files:**
- Modify: `backend/app/core/api_error.py`（在 Task 8 的 `TWIN_PUBLISH_FORBIDDEN` 之后补两个码）
- Create: `backend/app/services/twin/twin_access_service.py`
- Modify: `backend/app/services/twin/twin_service.py`（`_card_dict` 多一个 `share_expires_at`，W13 需要）
- Modify: `backend/app/routers/twin/twin.py`（文件末尾追加 T12 四个端点，全在**主 router** 上）
- Modify: `backend/tests/twin/conftest.py`（`build_client` 加 `as_user_id` 与一个夹具）
- Test: `backend/tests/twin/test_twin_access.py`

**Interfaces:**
- Consumes: Task 1 的 `TwinAccessRequest`（含部分唯一索引 `uq_twin_access_pending`）、`TwinCardShare`、`TwinPublish`；Task 4 已声明的 `TWIN_REQUEST_NOT_FOUND` / `TWIN_REQUEST_NOT_PENDING`；Task 6 `TwinService(db, tenant_id, user_id, role_codes=())` 的公开 `get_card()` 与常量 `ACCESS_OWNER/ACCESS_EDIT/ACCESS_READ`；Task 8 的 `ACCESS_ROLE`常量（`twin_publish_service.py`）；Task 1 的 `TWIN_ACCESS_REQUIRED`
- Produces: `TwinAccessService(db, tenant_id, user_id, role_codes=())`；方法 `request_access(int, Optional[str]) -> dict`、`approve(int, Optional[int]) -> dict`、`reject(int) -> dict`、`list_requests() -> dict`、`_lazy_expire() -> int`；模块常量 `STATUS_PENDING/STATUS_APPROVED/STATUS_REJECTED/STATUS_EXPIRED/DEFAULT_GRANT_DAYS`；`TwinService._card_dict` 的回包新增键 `share_expires_at`；四个新端点（路径见 Step 8）；夹具 `twin_client_a_as_other` 与常量 `OTHER_USER_ID`

- [ ] **Step 1: 补两个错误码**

在 `backend/app/core/api_error.py` 中 Task 8 追加的 `TWIN_PUBLISH_FORBIDDEN` 之后插入：

```python
TWIN_REQUEST_DUPLICATE = "TWIN_REQUEST_DUPLICATE"            # 已有在途申请（409）
TWIN_ACCESS_ALREADY_GRANTED = "TWIN_ACCESS_ALREADY_GRANTED"  # 已可读，无需申请（400）
```

> 五个码的分工写死（与 Task 8 Step 1 同一张表精神）：
> `TWIN_REQUEST_NOT_FOUND`=单据不存在 / 跨租户（404）；
> `TWIN_REQUEST_NOT_PENDING`=单据已处理过，不能重复审（400）；
> `TWIN_REQUEST_DUPLICATE`=同一人同一卡已有在途单（409，带 `pending_id`）；
> `TWIN_ACCESS_ALREADY_GRANTED`=权限已经有了（400）；
> `TWIN_ACCESS_REQUIRED`=**只有卡片 owner 能处理**（403，与 Task 6/8 的「无权做 X」同一信号）。

- [ ] **Step 2: 改 `backend/tests/twin/conftest.py`（加第二个同租户身份）**

Task 1 抄来的 `_fake_user` 把 `user_id` 写死成 `abs(tenant_id) + 1`（`tests/ontology/conftest.py:158-160`），
而 T12 天然需要**同一租户内的两个不同用户**（owner 与 applicant）。所以先整体替换 `_fake_user` 与 `build_client`：

原文：

```python
def _fake_user(tenant_id: Optional[int]) -> SysUser:
    user = SysUser()
    user.user_id = abs(tenant_id) + 1 if tenant_id is not None else 1
```

改为（其余行不动）：

```python
OTHER_USER_ID = 9001     # 同租户内的第二个身份：T12 的申请人（与 TENANT_A 推导出的 101 不撞）


def _fake_user(tenant_id: Optional[int], user_id: Optional[int] = None) -> SysUser:
    user = SysUser()
    # 不传 user_id 时保持 Task 1/6/7/8 的行为逐字不变（TENANT_A → 101、TENANT_B → 201），
    # 否则那两个任务的夹具与断言（写死 owner_id=101）会整批错。
    user.user_id = int(user_id) if user_id is not None else (
        abs(tenant_id) + 1 if tenant_id is not None else 1)
```

`build_client` 的签名与用户覆写行同步改为（其余保持 Task 8 Step 2 的样子）：

```python
def build_client(db: Session, tenant_id: Optional[int], *, with_twin: bool = False,
                 with_publish: bool = False,
                 as_user_id: Optional[int] = None) -> TestClient:
```

```python
    app.dependency_overrides[get_current_user] = lambda: _fake_user(tenant_id, as_user_id)
```

在 `publish_client_b` 之后追加一个夹具（**只挂主 router**：T12 全部在 `/api/v1/twins/*` 下）：

```python
@pytest.fixture
def twin_client_a_as_other(db: Session) -> TestClient:
    """B 身份看 A 租户：T12 的申请人与审批人必须是两个不同 `user_id`。"""
    return build_client(db, TENANT_A, with_twin=True, as_user_id=OTHER_USER_ID)
```

> 夹具只动 `tests/twin/conftest.py`，**不动** `tests/ontology/conftest.py`：后者的
> `_fake_user` 被本体域十几个用例依赖，改它属于无收益的爆炸半径。

- [ ] **Step 3: 写失败测试**

创建 `backend/tests/twin/test_twin_access.py`：

```python
"""T12 权限申请闭环（spec §4.5 / §6.1 / 验收 W5+W13）。

两个身份：owner = TENANT_A 推导出的 101（`_fake_user`），applicant = `OTHER_USER_ID`。
夹具自带：`published_version` / `card_a` 是 `test_twin_crud.py` 的**模块局部**夹具，
跨文件不共享，所以这里只重写所需的最小一份（本体 + 已发布版本 + live 卡）。

一个必须知道的测试库事实：`db` 夹具的 Session 是 `autoflush=False`
（`tests/ontology/conftest.py:150`），所以本服务**不得依赖「写完还没 commit 就能查回来」**；
每个用例的 schema 由 `schema_name` 随机生成并 `create_all`（`:104-141`），跨用例不串数据。
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select, text

from app.core.api_error import ApiError
from app.models.twin import TwinAccessRequest, TwinCardShare
from app.services.twin.twin_access_service import (
    DEFAULT_GRANT_DAYS, STATUS_APPROVED, STATUS_EXPIRED, STATUS_PENDING, STATUS_REJECTED,
    TwinAccessService,
)
from tests.twin.conftest import OTHER_USER_ID, TENANT_A, TENANT_B

OWNER = 101          # = abs(TENANT_A) + 1，即 twin_client_a 背后的用户


@pytest.fixture
def card_factory(db, ontology_factory):
    """建一张默认属于 OWNER 的卡（默认 **live**：他人的 draft 对 applicant 不可见，走不到申请）。"""
    oid = ontology_factory()

    def _make(name: str = '园区安防孪生', state: str = "live", owner_id: int = OWNER) -> int:
        cid = db.execute(
            text("INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, "
                 "runtime_state, owner_id) VALUES (:t, :n, :o, 1, :s, :u) RETURNING id"),
            {"t": TENANT_A, "n": name, "o": oid, "s": state, "u": owner_id}).scalar_one()
        db.commit()
        return int(cid)

    return _make


@pytest.fixture
def live_card(card_factory) -> int:
    return card_factory()


def svc(db, user_id: int, tenant_id=TENANT_A) -> TwinAccessService:
    return TwinAccessService(db, tenant_id, user_id)


def apply_as_other(client, card_id: int, reason: str = "需要查看安防态势"):
    return client.post(f"/api/v1/twins/cards/{card_id}/access-request", json={"reason": reason})


def shares_of(db, card_id: int):
    return db.execute(select(TwinCardShare).where(TwinCardShare.card_id == card_id)).scalars().all()


def request_ids_of_card(db, card_id: int):
    return db.execute(select(func.count()).select_from(TwinAccessRequest).where(
        TwinAccessRequest.card_id == card_id)).scalar_one()


# ---------------------------------------------------------------- 申请（T12 入口）


def test_apply_returns_201_and_stores_pending_row(twin_client_a_as_other, db, live_card):
    r = apply_as_other(twin_client_a_as_other, live_card)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == STATUS_PENDING
    assert body["card_id"] == live_card and body["applicant_id"] == OTHER_USER_ID
    assert body["reason"] and body["approver_id"] is None and body["reviewed_at"] is None
    row = db.get(TwinAccessRequest, int(body["id"]))
    db.refresh(row)                       # 测试 Session 是 autoflush=False，refresh 才能拿到库里的值
    assert int(row.tenant_id) == TENANT_A and int(row.applicant_id) == OTHER_USER_ID


def test_owner_cannot_apply_for_its_own_card(twin_client_a, db, live_card):
    """已可读就不得申请（自决项 6）：否则抽屉会堆满注定自动批准的单子。"""
    r = twin_client_a.post(f"/api/v1/twins/cards/{live_card}/access-request", json={})
    assert r.status_code == 400
    assert r.json()["code"] == "TWIN_ACCESS_ALREADY_GRANTED"
    assert r.json()["detail"]["access"] == "owner"
    assert request_ids_of_card(db, live_card) == 0


def test_read_share_holder_cannot_apply(twin_client_a_as_other, db, live_card):
    """已持有效 read 授予的人再申请→ 400（access=read 也算已授权）。"""
    db.execute(text(
        "INSERT INTO twin_card_share (tenant_id, card_id, grantee_type, grantee_id, perm, source, granted_by) "
        "VALUES (:t, :c, 'user', :u, 'read', 'manual', :o)"),
        {"t": TENANT_A, "c": live_card, "u": OTHER_USER_ID, "o": OWNER})
    db.commit()
    r = apply_as_other(twin_client_a_as_other, live_card)
    assert r.status_code == 400 and r.json()["code"] == "TWIN_ACCESS_ALREADY_GRANTED"
    assert r.json()["detail"]["access"] == "read"


def test_duplicate_pending_apply_is_409_with_pending_id(twin_client_a_as_other, live_card):
    first = apply_as_other(twin_client_a_as_other, live_card).json()
    r = apply_as_other(twin_client_a_as_other, live_card)
    assert r.status_code == 409 and r.json()["code"] == "TWIN_REQUEST_DUPLICATE"
    assert r.json()["detail"]["pending_id"] == int(first["id"])


def test_apply_for_others_draft_is_404_not_403(twin_client_a_as_other, card_factory):
    """draft 卡对他人根本不入列（§4.5），申请它得与不存在的卡同一信号。"""
    draft = card_factory(name="私人草稿", state="draft")
    r = apply_as_other(twin_client_a_as_other, draft)
    assert r.status_code == 404 and r.json()["code"] == "TWIN_CARD_NOT_FOUND"


def test_apply_for_cross_tenant_card_is_404(twin_client_b, live_card):
    """B 租户用户申请 A 租户的卡：租户闸在可见性里，不得用 403 泄露存在性。"""
    r = twin_client_b.post(f"/api/v1/twins/cards/{live_card}/access-request", json={})
    assert r.status_code == 404 and r.json()["code"] == "TWIN_CARD_NOT_FOUND"


def test_required_role_code_snapshots_first_role_publish(twin_client_a_as_other, db, live_card):
    """所需角色从**已启用发布行**取首码（自决项 2）：申请单留的是当时的快照。"""
    pid = db.execute(text("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
                          "VALUES (:t, :c, '总览', 0) RETURNING id"),
                     {"t": TENANT_A, "c": live_card}).scalar_one()
    db.execute(
        text("INSERT INTO twin_publish (tenant_id, card_id, page_id, slug, access, role_codes_json, "
             "version, status, published_by) VALUES (:t, :c, :p, 'sl-role', 'role', "
             "CAST('[\"SEC_ADMIN\", \"NIGHT_WATCH\"]' AS jsonb), 1, 'enabled', :o)"),
        {"t": TENANT_A, "c": live_card, "p": int(pid), "o": OWNER})
    db.commit()
    body = apply_as_other(twin_client_a_as_other, live_card).json()
    assert body["required_role_code"] == "SEC_ADMIN"


def test_required_role_code_is_null_without_role_publish(twin_client_a_as_other, live_card):
    """未发布或 `access=org` 的卡没有「所需角色」可声明，就是 NULL，**不得编造**。"""
    assert apply_as_other(twin_client_a_as_other, live_card).json()["required_role_code"] is None


# ---------------------------------------------------------------- 审批与驳回


def test_only_card_owner_can_approve(db, live_card):
    """§10 Q1-A：同租户非 owner 是 403（无权），跨租户是 404（不存在）。"""
    rid = int(svc(db, OTHER_USER_ID).request_access(live_card, "审批门")["id"])
    with pytest.raises(ApiError) as miss:
        svc(db, 8080).approve(rid)
    assert miss.value.code == "TWIN_ACCESS_REQUIRED" and miss.value.http_status == 403
    with pytest.raises(ApiError) as cross:
        svc(db, OWNER, tenant_id=TENANT_B).approve(rid)
    assert cross.value.code == "TWIN_REQUEST_NOT_FOUND" and cross.value.http_status == 404
    db.rollback()


def test_approve_moves_card_to_shared_with_expiry(twin_client_a, twin_client_a_as_other,
                                                  db, live_card):
    """**W13 主判据**：申请 → owner 批 → 转入「共享给我的（只读）」并含过期时间。"""
    rid = int(apply_as_other(twin_client_a_as_other, live_card).json()["id"])
    r = twin_client_a.post(f"/api/v1/twins/access-requests/{rid}/approve", json={})
    assert r.status_code == 200, r.text
    approved = r.json()
    assert approved["status"] == STATUS_APPROVED and approved["approver_id"] == OWNER
    assert approved["reviewed_at"] and approved["expires_at"]

    g = twin_client_a_as_other.get("/api/v1/twins/cards").json()
    assert {c["id"] for c in g["shared"]} == {live_card}
    assert g["shared"][0]["access"] == "read" and g["shared"][0]["restricted"] is False
    # Step 7 新增的键：前端要渲染「剩余 N 天」，没它就只好看得到卡、看不到期限
    assert g["shared"][0]["share_expires_at"] == approved["expires_at"]

    rows = shares_of(db, live_card)
    assert len(rows) == 1 and rows[0].source == "request" and rows[0].perm == "read"
    assert int(rows[0].granted_by) == OWNER and int(rows[0].grantee_id) == OTHER_USER_ID


def test_approve_expiry_window_is_configurable(db, card_factory):
    """缺省 30 天（W13 的「含过期时间」不能是永久），也可 1–365 天自定。"""
    def _days_ahead(iso: str) -> timedelta:
        return datetime.fromisoformat(iso) - datetime.now()

    c1 = card_factory(name="默认期")
    d1 = svc(db, OWNER).approve(int(svc(db, OTHER_USER_ID).request_access(c1, "默认")["id"]))
    assert abs(_days_ahead(d1["expires_at"]) - timedelta(days=DEFAULT_GRANT_DAYS)) < timedelta(minutes=5)

    c2 = card_factory(name="短期")
    d2 = svc(db, OWNER).approve(int(svc(db, OTHER_USER_ID).request_access(c2, "一周")["id"]),
                               expires_in_days=7)
    assert abs(_days_ahead(d2["expires_at"]) - timedelta(days=7)) < timedelta(minutes=5)


def test_approve_after_decision_is_400_not_pending(twin_client_a, twin_client_a_as_other, live_card):
    rid = int(apply_as_other(twin_client_a_as_other, live_card).json()["id"])
    assert twin_client_a.post(f"/api/v1/twins/access-requests/{rid}/approve", json={}).status_code == 200
    r = twin_client_a.post(f"/api/v1/twins/access-requests/{rid}/approve", json={})
    assert r.status_code == 400 and r.json()["code"] == "TWIN_REQUEST_NOT_PENDING"
    assert r.json()["detail"]["status"] == STATUS_APPROVED
    # 批过的单子也不能再驳（两个动作共用同一个前置闸）
    assert twin_client_a.post(f"/api/v1/twins/access-requests/{rid}/reject", json={}).status_code == 400


def test_reject_grants_nothing(twin_client_a, twin_client_a_as_other, db, live_card):
    """驳回不落授予：卡片仍属 🔒 受限（W5 三态可回退）。"""
    rid = int(apply_as_other(twin_client_a_as_other, live_card).json()["id"])
    r = twin_client_a.post(f"/api/v1/twins/access-requests/{rid}/reject", json={})
    assert r.status_code == 200 and r.json()["status"] == STATUS_REJECTED
    assert r.json()["expires_at"] is None and r.json()["approver_id"] == OWNER
    assert shares_of(db, live_card) == []
    g = twin_client_a_as_other.get("/api/v1/twins/cards").json()
    assert g["shared"] == [] and {c["id"] for c in g["restricted"]} == {live_card}


def test_reapply_after_reject_and_upsert_single_share_row(twin_client_a, twin_client_a_as_other,
                                                          db, live_card):
    """rejected 不挡重申（部分唯一索引只管 pending），且续期复用同一行 share。

    这一条就是在钉住 `uq_twin_share` 未落库带来的风险：上一轮的**过期**授予行已存在，
    再批一次必须是 UPDATE 而不是插出第二行。"""
    rid = int(apply_as_other(twin_client_a_as_other, live_card).json()["id"])
    twin_client_a.post(f"/api/v1/twins/access-requests/{rid}/reject", json={})
    rid2 = int(apply_as_other(twin_client_a_as_other, live_card).json()["id"])
    assert rid2 != rid

    db.execute(text(
        "INSERT INTO twin_card_share (tenant_id, card_id, grantee_type, grantee_id, perm, source, "
        "expires_at, granted_by) VALUES (:t, :c, 'user', :u, 'edit', 'manual', :e, :o)"),
        {"t": TENANT_A, "c": live_card, "u": OTHER_USER_ID,
         "e": datetime.now() - timedelta(days=1), "o": OWNER})
    db.commit()

    twin_client_a.post(f"/api/v1/twins/access-requests/{rid2}/approve", json={"expires_in_days": 7})
    rows = shares_of(db, live_card)
    assert len(rows) == 1, f"同一 (card, user) 只应留一行授予，实得 {len(rows)} 行"
    assert rows[0].perm == "read" and rows[0].source == "request"
    assert rows[0].expires_at > datetime.now()


def test_approve_writes_share_and_request_in_one_transaction(db, live_card, monkeypatch):
    """半批准（单子 approved 但 share 没写）等于用户看到成功却仍看不了——必须同事务。"""
    rid = int(svc(db, OTHER_USER_ID).request_access(live_card, "原子性")["id"])

    def boom(*args, **kwargs):
        raise RuntimeError("share 写入失败")

    monkeypatch.setattr(TwinAccessService, "_upsert_share", boom)
    with pytest.raises(RuntimeError):
        svc(db, OWNER).approve(rid)
    db.rollback()                          # 只 commit 一次，回滚就能整体作废

    row = db.get(TwinAccessRequest, rid)
    db.refresh(row)
    assert row.status == STATUS_PENDING and row.approver_id is None
    assert shares_of(db, live_card) == []


# ---------------------------------------------------------------- 列表与过期


def test_lazy_expire_flips_stale_approved_rows(db, live_card):
    """approved 单过期后翻 expired（仅记账，不删 share 行）。"""
    rid = int(svc(db, OTHER_USER_ID).request_access(live_card, "过期")["id"])
    svc(db, OWNER).approve(rid)
    past = datetime.now() - timedelta(minutes=1)
    db.execute(text("UPDATE twin_access_request SET expires_at = :e WHERE id = :i"),
               {"e": past, "i": rid})
    db.commit()

    out = svc(db, OWNER).list_requests()   # 读列表时顺带清
    assert {d["status"] for d in out["incoming"] if d["id"] == rid} == {STATUS_EXPIRED}
    row = db.get(TwinAccessRequest, rid)
    db.refresh(row)
    assert row.status == STATUS_EXPIRED and int(row.card_id) == live_card


def test_expired_grant_returns_card_to_restricted(twin_client_a, twin_client_a_as_other,
                                                  db, live_card):
    """授予到期→ 卡片从 shared 回到 restricted：可见性闸在 `_my_shares()` 里，不依赖申请单。"""
    rid = int(apply_as_other(twin_client_a_as_other, live_card).json()["id"])
    twin_client_a.post(f"/api/v1/twins/access-requests/{rid}/approve", json={})
    g = twin_client_a_as_other.get("/api/v1/twins/cards").json()
    assert {c["id"] for c in g["shared"]} == {live_card}

    db.execute(text("UPDATE twin_card_share SET expires_at = :e WHERE card_id = :c"),
               {"e": datetime.now() - timedelta(seconds=1), "c": live_card})
    db.commit()
    after = twin_client_a_as_other.get("/api/v1/twins/cards").json()
    assert after["shared"] == [] and {c["id"] for c in after["restricted"]} == {live_card}


def test_list_requests_splits_incoming_and_outgoing(twin_client_a, twin_client_a_as_other,
                                                    card_factory):
    """一次请求同时给两组（卡片管理页的待办计数与「我的申请」列表共用它）。"""
    c1 = card_factory(name="安防孪生")
    c2 = card_factory(name="能耗孪生")
    r1 = int(apply_as_other(twin_client_a_as_other, c1).json()["id"])
    r2 = int(apply_as_other(twin_client_a_as_other, c2).json()["id"])

    inc = twin_client_a.get("/api/v1/twins/access-requests").json()
    assert {d["id"] for d in inc["incoming"]} == {r1, r2}
    assert inc["outgoing"] == [] and inc["incoming_pending"] == 2
    assert {d["card_name"] for d in inc["incoming"]} == {"安防孪生", "能耗孪生"}

    out = twin_client_a_as_other.get("/api/v1/twins/access-requests").json()
    assert {d["id"] for d in out["outgoing"]} == {r1, r2} and out["incoming"] == []
    assert out["incoming_pending"] == 0      # 计数只算 incoming，申请方看不到别人的单
```

> `test_list_requests_...` 里故意发了**两张卡**：`incoming` 必须只按 owner 分派，
> 否则第二张卡的单子会把分派断言淡化成“只返了一条”。

- [ ] **Step 4: 跑到失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/twin/test_twin_access.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.twin.twin_access_service'`
（先确认 `test_only_card_owner_can_approve` 之前的用例会因 import 失败而整体收集错误，
而不是“全部 pass”——后者意味着 Step 2 的夹具没生效。）

- [ ] **Step 5: 写 `backend/app/services/twin/twin_access_service.py`（上半：申请）**

```python
"""权限申请闭环（spec §4.5 / §6.1 T12 / §10 Q1-A）。对应 P0-8，验收 W13。

三件事，不多做：
1. 申请单的生死（pending → approved / rejected / expired）；
2. 批准的产物 = 写 `twin_card_share`，**不发一次性令牌**（§3.7）；
3. 可见性与租户闸**一律交给 Task 6 的 `TwinService`**，本层绝不复制第二套 access 算法
   ——两处判据并存必然漂移，而漂移的方向通常是「新写的那份更松」。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.api_error import (
    ApiError, TWIN_ACCESS_ALREADY_GRANTED, TWIN_ACCESS_REQUIRED,
    TWIN_REQUEST_DUPLICATE, TWIN_REQUEST_NOT_FOUND, TWIN_REQUEST_NOT_PENDING,
)
from app.models.twin import TwinAccessRequest, TwinCard, TwinCardShare, TwinPublish
from app.services.twin.twin_publish_service import ACCESS_ROLE
from app.services.twin.twin_service import (
    ACCESS_EDIT, ACCESS_OWNER, ACCESS_READ, TwinService,
)

# 与 Task 1 的 CHECK 约束 `ck_twin_access_status` 逐字一致（四态，§3.8 状态机）
STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, STATUS_EXPIRED = (
    "pending", "approved", "rejected", "expired")

# W13 要求「含过期时间」，所以缺省**不能是永久**。`twin_*` 的 TIMESTAMP 列不带时区，
# 因此本层全程用应用时钟（仓库同律：`services/sys/sys_notification_service.py:36`），
# 不去混 DB 的 now()：两套时钟写同一列，比较大小会变成运气。**不照抄**
# `services/dataops/write_request_service.py:156` 的 `obj.expires_at < func.now()`，
# 那是把 Python datetime 属性与 SQL 构造子比较，是个隐形错。
DEFAULT_GRANT_DAYS = 30
MAX_GRANT_DAYS = 365
GRANTED_PERM = "read"          # 批准申请单的产物永远是只读：edit 只能 owner 手工授


class TwinAccessService:
    """申请/审批。审批权只认卡片 `owner`（§10 Q1-A）。"""

    def __init__(self, db: Session, tenant_id: Optional[int], user_id: int,
                 role_codes: Sequence[str] = ()) -> None:
        if tenant_id is None:
            raise ValueError("tenant_required")     # 与 query_service.py:34 同一惯例
        self.db = db
        self.tenant_id = int(tenant_id)
        self.user_id = int(user_id or 0)
        # 传 role_codes 是为了让「靠角色授予已能读」的人也拿到 400，而不是发一张注定自动批准的单子
        self.role_codes = tuple(sorted({r for r in role_codes if r}))

    def _orchestrator(self) -> TwinService:
        return TwinService(self.db, self.tenant_id, self.user_id, self.role_codes)

    # ---------------------------------------------------------------- 内部查询

    def _pending_of(self, card_id: int) -> Optional[TwinAccessRequest]:
        return self.db.execute(
            select(TwinAccessRequest).where(
                TwinAccessRequest.tenant_id == self.tenant_id,
                TwinAccessRequest.card_id == card_id,
                TwinAccessRequest.applicant_id == self.user_id,
                TwinAccessRequest.status == STATUS_PENDING)
        ).scalars().first()

    def _required_role_code_of(self, card_id: int) -> Optional[str]:
        """所需角色 = 该卡已启用、`access=role` 的发布行里的**首个**角色码（无则 NULL）。

        为什么不用另建一列：发布闸已经回答了「哪些角色能看」（spec §3.5），
        工作台与只读页的口径必须同源，否则会出现「能申请的角色」与「能看页的角色」两套答案。
        写入的是**申请时刻的快照**，事后改发布配置不回写历史单据（审计语义）。
        """
        rows = self.db.execute(
            select(TwinPublish.role_codes_json).where(
                TwinPublish.tenant_id == self.tenant_id,
                TwinPublish.card_id == card_id,
                TwinPublish.status == "enabled",
                TwinPublish.access == ACCESS_ROLE)
        ).all()
        for (codes,) in rows:
            for code in (codes or []):
                text_code = str(code).strip()
                if text_code:
                    return text_code[:64]        # 列宽 String(64)，截而不炸
        return None

    def _request_or_404(self, request_id: int) -> TwinAccessRequest:
        row = self.db.get(TwinAccessRequest, request_id)
        if row is None or int(row.tenant_id) != self.tenant_id:
            # 跨租户与不存在同一信号：不得用 403 泄露“这张单子存在”
            raise ApiError(TWIN_REQUEST_NOT_FOUND, "申请单不存在", 404)
        return row

    # ---------------------------------------------------------------- 申请

    def request_access(self, card_id: int, reason: Optional[str] = None) -> dict:
        """提交申请。**已可读就不得申请**，否则抽屉会被注定自动批准的单子淹没。"""
        card = self._orchestrator().get_card(card_id)   # 不可见/跨租 → 已在里层抛 404
        if card["access"] in (ACCESS_OWNER, ACCESS_EDIT, ACCESS_READ):
            raise ApiError(TWIN_ACCESS_ALREADY_GRANTED, "你已具备该卡片的访问权限，无需申请",
                           400, {"card_id": card_id, "access": card["access"]})
        pending = self._pending_of(card_id)
        if pending is not None:
            # 把已在途单号回给前端，它才能直接“查看进度”，而不是只会提示“你提过了”
            raise ApiError(TWIN_REQUEST_DUPLICATE, "已有在途申请，请等待卡片创建者处理", 409,
                           {"pending_id": int(pending.id),
                            "created_at": pending.created_at.isoformat() if pending.created_at else None})
        row = TwinAccessRequest(
            tenant_id=self.tenant_id, card_id=int(card_id), applicant_id=self.user_id,
            reason=(reason or "").strip()[:500] or None,
            required_role_code=self._required_role_code_of(int(card_id)),
            status=STATUS_PENDING)
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError:
            # 并发双提：部分唯一索引 `uq_twin_access_pending` 兜住（Task 1 已建），
            # 这里把它降级成与预查同样的 409，而不是把数据库错抬给用户。
            self.db.rollback()
            pending = self._pending_of(card_id)
            raise ApiError(TWIN_REQUEST_DUPLICATE, "已有在途申请，请等待卡片创建者处理", 409,
                           {"pending_id": int(pending.id) if pending is not None else None}) from None
        self.db.refresh(row)
        return self._row_dict(row, card["name"])
```

> `_row_dict` 与审批部分在 Step 6 补齐：本步单独跑仍会 `AttributeError: _row_dict`，
> 这是正常的——TDD 的绿灯属于 Step 6 之后。

- [ ] **Step 6: 给同一个类补齐下半（审批 / 驳回 / 列表 / 懒过期）**

接 Step 5 的类体末尾继续写（不是新建文件）：

```python
    # ---------------------------------------------------------------- 审批

    def _owner_card_of(self, row: TwinAccessRequest) -> TwinCard:
        """§10 Q1-A：只有卡片 owner 能处理。非 owner 403，卡已不在则与不存在同信号。"""
        card = self.db.get(TwinCard, int(row.card_id))
        if card is None or int(card.tenant_id) != self.tenant_id:
            # CASCADE 会连单子一起删，走到这里只可能是脏数据；不另开一个码
            raise ApiError(TWIN_REQUEST_NOT_FOUND, "申请单不存在", 404)
        if int(card.owner_id) != self.user_id:
            raise ApiError(TWIN_ACCESS_REQUIRED, "仅卡片创建者可处理权限申请", 403,
                           {"request_id": int(row.id), "card_id": int(card.id)})
        return card

    def _pending_row(self, request_id: int) -> "tuple[TwinAccessRequest, TwinCard]":
        """approve / reject 共用的前置闸：存在 → 是我卡 → 还在途。三闸一序不得重排。"""
        self._lazy_expire()
        row = self._request_or_404(request_id)
        card = self._owner_card_of(row)
        if row.status != STATUS_PENDING:
            raise ApiError(TWIN_REQUEST_NOT_PENDING, "申请单已处理，不能重复审批", 400,
                           {"request_id": int(row.id), "status": row.status})
        return row, card

    def _upsert_share(self, card_id: int, applicant_id: int, expires_at: datetime,
                      *, granted_by: int) -> TwinCardShare:
        """同一 (card, user) 只留一行授予：有就续期，没有才插。

        为什么是 upsert 而不是靠唯一键：spec §3.6 写的 `uq_twin_share` 在 Task 1 落库时是
        **普通索引** `idx_twin_share_card`（`grantee_id` / `grantee_code` 二选一，要硬约束
        得拆两条部分唯一索引），所以重复授予由这里兜住。
        **已知限制**：并发双批仍可能插出两行（两个事务都读到“无行”）。影响面说白：
        `_my_shares()` 取 edit 覆盖 read，行为无害，只是脏史。要硬保证时补两条部分唯一索引
        （`WHERE grantee_type='user'` / `='role'`），并把这里的插行改成 ON CONFLICT DO UPDATE。
        Plan 2 一旦开放「手工共享」就必须同时改两处，否则第二插入点会各写各的。
        """
        row = self.db.execute(
            select(TwinCardShare).where(
                TwinCardShare.tenant_id == self.tenant_id,
                TwinCardShare.card_id == card_id,
                TwinCardShare.grantee_type == "user",
                TwinCardShare.grantee_id == applicant_id)
        ).scalars().first()
        if row is None:
            row = TwinCardShare(tenant_id=self.tenant_id, card_id=card_id,
                                grantee_type="user", grantee_id=applicant_id,
                                perm=GRANTED_PERM, source="request",
                                expires_at=expires_at, granted_by=granted_by)
            self.db.add(row)
        else:
            # 回落成 read 是刻意的：让过期 edit 因为一张「申请只读」的单子被静默复活，
            # 等于权限上探。要恢复 edit 只能是 owner 在共享管理里显式动作（Plan 2）。
            row.perm = GRANTED_PERM
            row.source = "request"
            row.expires_at = expires_at
            row.granted_by = granted_by
        return row

    def approve(self, request_id: int, expires_in_days: Optional[int] = None) -> dict:
        days = max(1, min(int(expires_in_days or DEFAULT_GRANT_DAYS), MAX_GRANT_DAYS))
        row, card = self._pending_row(request_id)
        expires_at = datetime.now() + timedelta(days=days)
        # 顺序是故意如此：先改单子、再写授予、**只在最后 commit 一次**。
        # 「单子已 approved 但 share 没写」等于用户看到成功却仍看不了，两者必须同事务
        # （`test_approve_writes_share_and_request_in_one_transaction` 钉住这一条）。
        row.status = STATUS_APPROVED
        row.approver_id = self.user_id
        # 与 Task 8 的 `published_at = func.now()` **不同律**，也不是写错了：
        # reviewed_at 与 expires_at 要互相比较（过期判定、前端算天数），必须共用一个时钟；
        # 一半交给 DB、一半交给应用就会变成比较运气。
        row.reviewed_at = datetime.now()
        row.expires_at = expires_at
        self._upsert_share(int(card.id), int(row.applicant_id), expires_at,
                           granted_by=self.user_id)
        self.db.commit()
        self.db.refresh(row)
        return self._row_dict(row, card.name)

    def reject(self, request_id: int) -> dict:
        row, card = self._pending_row(request_id)
        row.status = STATUS_REJECTED
        row.approver_id = self.user_id
        row.reviewed_at = datetime.now()
        row.expires_at = None          # 驳回不带任何有效期
        self.db.commit()
        self.db.refresh(row)
        return self._row_dict(row, card.name)

    # ------------------------------------------------------------ 列表 / 懒过期

    def _lazy_expire(self) -> int:
        """把已过期却还挂着 approved 的单子翻成 expired（P0 不引定时任务，读时顺带清）。

        只动申请单，**不动 `twin_card_share`**：可见性已由 `_my_shares()` 的
        `expires_at > now()` 闸住（Task 6），share 行留着就是授权史。
        """
        now = datetime.now()
        rows = self.db.execute(
            select(TwinAccessRequest).where(
                TwinAccessRequest.tenant_id == self.tenant_id,
                TwinAccessRequest.status == STATUS_APPROVED,
                TwinAccessRequest.expires_at.is_not(None),
                TwinAccessRequest.expires_at <= now)
        ).scalars().all()
        for r in rows:
            r.status = STATUS_EXPIRED
        if rows:
            self.db.commit()
        return len(rows)

    def list_requests(self) -> Dict[str, Any]:
        """一次给两组：owner 视角的待办 + 我发出的申请。

        **不 join `sys_user`**（自决项 5）：测试库的建表清单 `_tables()` 未 import `sys_user`
        （`tests/ontology/conftest.py:59-69`），姓名由 Plan 2 用现成的
        `GET /api/v1/admin/users`（`routers/sys/__init__.py:114`）在前端补。
        """
        self._lazy_expire()
        rows = self.db.execute(
            select(TwinAccessRequest, TwinCard.name)
            .join(TwinCard, TwinCard.id == TwinAccessRequest.card_id)
            .where(TwinAccessRequest.tenant_id == self.tenant_id,
                   or_(TwinCard.owner_id == self.user_id,
                       TwinAccessRequest.applicant_id == self.user_id))
            .order_by(TwinAccessRequest.created_at.desc(), TwinAccessRequest.id.desc())
        ).all()
        incoming: List[dict] = []
        outgoing: List[dict] = []
        for r, card_name in rows:
            d = self._row_dict(r, card_name)
            # 分派口径写死：先看“是不是我发的”。owner == applicant 在 P0 不可达
            # （owner 申请自己的卡在 request_access 就被 400 挡了），所以两组不会重叠。
            (outgoing if int(r.applicant_id) == self.user_id else incoming).append(d)
        return {"incoming": incoming, "outgoing": outgoing,
                "incoming_pending": sum(1 for d in incoming if d["status"] == STATUS_PENDING)}

    @staticmethod
    def _row_dict(r: TwinAccessRequest, card_name: Optional[str] = None) -> dict:
        return {
            "id": int(r.id), "card_id": int(r.card_id), "card_name": card_name,
            "applicant_id": int(r.applicant_id),
            "approver_id": int(r.approver_id) if r.approver_id is not None else None,
            "status": r.status, "reason": r.reason,
            "required_role_code": r.required_role_code,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        }
```

- [ ] **Step 7: 给 `TwinService._card_dict` 暴露 `share_expires_at`（W13 需要）**

W13 的判据是「转入共享给我的（只读）**并含过期时间**」：卡片列表不给期限，前端就只能看到
“它能看”而看不到“还能看几天”。`_my_shares()` 已经把 `TwinCardShare` 行拿到手了，
只是 `_card_dict` 没往下传。三处改动，都在 `backend/app/services/twin/twin_service.py`。

一、`_card_dict` 本身（新增一个带默认值的参数，因此**现有调用方不改签名也能跑**，但本步会把它们全部改上）：

原文：

```python
    def _card_dict(self, c: TwinCard, access: Optional[str],
                   current_versions: Dict[int, int]) -> dict:
```

改为：

```python
    def _card_dict(self, c: TwinCard, access: Optional[str],
                   current_versions: Dict[int, int],
                   share: Optional[TwinCardShare] = None) -> dict:
```

并在返回字典的 `"restricted"` 行之后、`"updated_at"` 行之前插一行（其余逐字不动）：

```python
            # 只读期限（仅 share 进来的卡有值；owner 自己的卡恒 NULL）。前端据此渲染
            # 「共享给我的（只读）· 剩余 N 天」（W13），没这个字段抽屉就只能含糊地说「已共享」。
            "share_expires_at": share.expires_at.isoformat() if share is not None and share.expires_at else None,
```

二、`list_cards()` 里的调用点：

原文：`            d = self._card_dict(c, acc, current)`
改为：`            d = self._card_dict(c, acc, current, shares.get(int(c.id)))`

三、`get_card()` 整体替换（局部变量提出来，不重复算 `_my_shares()`）：

原文：

```python
    def get_card(self, card_id: int) -> dict:
        card = self.card_or_404(card_id)
        acc = self._access_of(card, self._my_shares(), self.user_id)
        if acc is None:
            # 非 owner / 非共享 / 非对外：与跨租户同一信号，不用 403 泄露存在性
            raise ApiError(TWIN_CARD_NOT_FOUND, "卡片不存在", 404)
        return self._card_dict(card, acc, self._current_versions({int(card.ontology_id)}))
```

改为：

```python
    def get_card(self, card_id: int) -> dict:
        card = self.card_or_404(card_id)
        shares = self._my_shares()          # 同一个字典同时供可见性判定与期限回显
        acc = self._access_of(card, shares, self.user_id)
        if acc is None:
            # 非 owner / 非共享 / 非对外：与跨租户同一信号，不用 403 泄露存在性
            raise ApiError(TWIN_CARD_NOT_FOUND, "卡片不存在", 404)
        return self._card_dict(card, acc, self._current_versions({int(card.ontology_id)}),
                               shares.get(int(card.id)))
```

> 只动这三处，**不动** `_access_of` / `_my_shares` 的任何判定：否则 Task 6/7/8 的 52 个用例
>（12 + 17 + 23，其中 Task 6 的 `test_shared_card_moves_to_shared_group` 直接断言 access）就进入回归风险区。

- [ ] **Step 8: 给 `backend/app/routers/twin/twin.py` 加 T12**

顶部 import 区追加一行（按字母序它是 twin 服务里最早的一条，插在 `twin_data_service` 那行**之前**）：

```python
from app.services.twin.twin_access_service import TwinAccessService
```

在 `PublishBody` 之后追加两个 Body：

```python
class AccessRequestBody(BaseModel):
    """申请理由（原型 PermDrawer 的「申请访问权限」按钮背后就是这一段文本）。"""

    reason: Optional[str] = Field(None, max_length=500)


class ApproveBody(BaseModel):
    """审批可选参数：授予有效期（天）。缺省走服务层的 `DEFAULT_GRANT_DAYS`。"""

    expires_in_days: Optional[int] = Field(None, ge=1, le=365)
```

> 范围写两份不是冗余：`ge/le` 挡住 HTTP 调用（422），服务层的 `max/min` 守住直接调服务的
> 内部代码（Task 9 自己的用例与 Plan 2 可能复用）。只留一份时，另一侧总能绕过它。

在 `_pub_svc()` 之后追加申请服务构造器：

```python
def _access_svc(db: Session, current_user: SysUser) -> TwinAccessService:
    """`role_codes` 与 `_svc()` 同源（`build_user_context`，失败降级最小权限）：
    靠角色已能读的人不应该再发一张注定自动批准的单子。"""
    ctx = build_user_context(db, current_user)
    return TwinAccessService(db, _require_tenant_id(current_user),
                             int(getattr(current_user, "user_id", 0) or 0),
                             tuple(ctx.role_codes) if ctx else ())
```

在文件末尾（Task 8 的 T11 区块之后）追加四个端点：

```python
# ------------------------------------------------------------ T12 权限申请闭环


@router.post("/cards/{card_id}/access-request", status_code=201)
def request_card_access(card_id: int, body: Optional[AccessRequestBody] = None,
                        db: Session = Depends(get_db),
                        current_user: SysUser = Depends(get_current_user)) -> dict:
    """T12 申请。**回 201**：每次合法申请都新建一行单（历史 rejected 不占坑）。"""
    return _access_svc(db, current_user).request_access(
        card_id, body.reason if body else None)


@router.get("/access-requests")
def list_access_requests(db: Session = Depends(get_db),
                         current_user: SysUser = Depends(get_current_user)) -> dict:
    """一次回两组：`incoming`（我卡上别人提的）/ `outgoing`（我提给别人的）+ 待办计数。"""
    return _access_svc(db, current_user).list_requests()


@router.post("/access-requests/{request_id}/approve")
def approve_access_request(request_id: int, body: Optional[ApproveBody] = None,
                          db: Session = Depends(get_db),
                          current_user: SysUser = Depends(get_current_user)) -> dict:
    """T12 批准：同事务写 `twin_card_share` 并把单子置 approved（§10 Q1-A：仅 owner）。"""
    return _access_svc(db, current_user).approve(
        request_id, body.expires_in_days if body else None)


@router.post("/access-requests/{request_id}/reject")
def reject_access_request(request_id: int, db: Session = Depends(get_db),
                         current_user: SysUser = Depends(get_current_user)) -> dict:
    """T12 驳回：不带 Body（无需理由字段也能驳），不产生任何授予。"""
    return _access_svc(db, current_user).reject(request_id)
```

> **无需再改 `router_registry.py`**：T12 四个端点全在 Task 6 已注册的 `router`（前缀
> `/api/v1/twins`）上，不新建 router。
> 路径也不与本文件里的现有端点遮蔽：`/cards/{card_id}/access-request` 与 `/cards/{card_id}/pages`
> 是不同字面段，`/access-requests` 与 `/cards/*` 不同首段——`router_registry.py:87` 那条
> 「`/users/{id}` 注册在 `/users/me` 之前会遮蔽后者」的注释只适用于**同层同形**的路径。

- [ ] **Step 9: 跑到通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/twin/test_twin_access.py -v`
Expected: PASS（**18 passed**）。计划缺陷修正（执行时实测，2026-11-01）：原稿写
「17 passed」是少计了一个用例——本步代码块里的 `def test_` 正好 18 个（申请 8 + 审批 7 + 列表与过期 3）。
失败时的排查序（按此序查，**不得改测试迁就实现**）：

1. `AttributeError: 'TwinAccessService' object has no attribute '_row_dict'` → Step 6 下半没贴完；
2. `TWIN_ACCESS_ALREADY_GRANTED` 未定义 → Step 1 的码没插到 `TWIN_PUBLISH_FORBIDDEN` 之后；
3. `twin_client_a_as_other` 拿到 401/403 而不是预期结果 → `build_client` 的
   `as_user_id` 没传到 `_fake_user`（或者两个代码路径只改了一个）；
4. `test_apply_for_others_draft_is_404_not_403` 拿到 403 → `request_access` 自己写了“无权”分支，
   而不是把存不存在这件事全权交给 `TwinService.get_card()`；
5. `test_approve_moves_card_to_shared_with_expiry` 的 `share_expires_at` 为 `None` → Step 7 的
   三个调用点只改了一处（最容易漏 `get_card`）；两处不等则 Step 6 里 `expires_at` 被算了两次；
6. `test_reapply_after_reject_and_upsert_single_share_row` 拿到 2 行 share → `_upsert_share`
   的查旧行条件漏了 `grantee_type == "user"`，或走了新分支而不是更新分支；
7. `test_approve_writes_share_and_request_in_one_transaction` 回滚后仍是 `approved` → 中途多了一个
   `self.db.commit()`（整个 `approve` 只允许**末尾那一次**）；
8. `test_lazy_expire_...` 拿到 `approved` 而不是 `expired` → 比较写成了 `func.now()`（应用时钟与
   DB 时钟在这条上必须一致），或者 `_lazy_expire` 只在 `list_requests` 里调、没在 `_pending_row` 里调。

Run: `.\.venv\Scripts\python.exe -m pytest tests/twin tests/ontology tests/unit -v`
Expected: 全绿（Task 1/4/5/6/7/8 的全部用例不得因本任务回归：Step 7 动了 `twin_service.py`，
它是 Task 6/7/8 三个任务的共同地基，改错了会成批飘红）。

> **必须改成按目录分跑**（同 Task 7 Step 7 的先行缺陷：三个目录一起收集会污染全局
> `Base.metadata`，报 `UndefinedTable: relation "t_xxxx.kms_segment" does not exist`）：
>
> ```powershell
> foreach ($d in 'tests/twin','tests/ontology','tests/unit') {
>   .\.venv\Scripts\python.exe -m pytest $d -q 1> "_t9r.txt" 2> $null
>   echo "$d EXIT=$LASTEXITCODE"
> }
> ```
>
> 实测（2026-11-01）：`tests/twin` 78 passed、`tests/ontology` 79 passed、
> `tests/unit` 309 passed + 1 skipped，三个 EXIT 均为 0。

Run: `.\.venv\Scripts\python.exe -c "import app.main; print('router load ok')"`
Expected: 输出 `router load ok`，日志无 `路由模块加载失败`。（本任务不新增 `RouterSpec`，
这一步只验证新增 import 没把模块循环拉起来：`twin_access_service` 同时 import 了
`twin_service` 与 `twin_publish_service`，而后者又 import 前者写过的 `TwinDataService`。）

- [ ] **Step 10: 提交**

```bash
git add backend/app/core/api_error.py backend/app/services/twin/twin_access_service.py backend/app/services/twin/twin_service.py backend/app/routers/twin/twin.py backend/tests/twin/conftest.py backend/tests/twin/test_twin_access.py
git commit -m "feat(twin): access request workflow with owner approval and expiring grants"
```

> 路径需按实际 cwd 写（cwd=`backend` 时去掉 `backend/` 前缀），提交前用
> `git diff --cached --name-only` 核对零外部文件混入；本任务同时改动计划文档，需一并 `git add`。

---

#### Task 9 执行记录（2026-11-01）

交付：`twin_access_service.py`（275 行）+ `twin.py` 的 `_access_svc`/两个 Body/T12 四端点 +
`twin_service._card_dict` 的 `share_expires_at`（三处）+ `conftest` 的 `as_user_id` 与
`twin_client_a_as_other` + `test_twin_access.py`（**18 passed**）。

| # | 类别 | 现象 | 修法 |
|---|---|---|---|
| 23 | 计划缺陷（Step 9 期望值） | 写「Expected: PASS（17 passed）」，但 Step 3 的用例块实际含 18 个 `def test_`；执行者若按 17 验收会怀疑多写了一个用例 | 改为 18 passed（Step 9 已就地修正） |
| 24 | 环境漂移（Step 10） | 任务未列计划文档为提交件，但本文档的回写属于同一 Task 的事实记录 | `git add` 额外带上 `../docs/superpowers/plans/…md` |

执行差异说明（不影响最终态）：Step 5 与 Step 6 是同一文件的上下两半，本次**一次写成**
（避开 `Add-Content` 的 LF 污染），因此跳过了 Step 5 单独运行必然出现的
`AttributeError: _row_dict`；红灯证据由 Step 4 的 `ModuleNotFoundError: No module named
'app.services.twin.twin_access_service'`（EXIT=2）提供，与计划预期一致。

关键不变量已钉住：批准的单次 `commit`（`test_approve_writes_share_and_request_in_one_transaction`
用 `_upsert_share` 抛错验证回滚后单子仍 `pending` 且无 share 行）、同一 (card, user)
只留一行授予（过期 `edit` 被重申后回落成 `read`，权限不上探）、全链路用应用时钟
（`reviewed_at`/`expires_at` 可比较），以及审批三闸一序（存在 → 是我卡 → 还在途）
依次给出的 404 / 403 / 400 三种信号各归其位。

提交：`8dd9b62 feat(twin): access request workflow with owner approval and expiring grants`（7 文件）。

---

### Task 10: `sys_menu` 2407 菜单行（两处 SQL 同步；原定 2406 已被占用）

对应 **P0-1** 的后半（「迁移可 upgrade/downgrade + 菜单/权限 SQL」）与 spec §2.3 「菜单」行、§3.9。
本任务不碰一行 Python 业务代码，但它是唯一**两个文件必须逐字一致**的任务，也是最容易被
“改了 `menu_knowledge_governance.sql` 忘了 `init.sql`” 拖到上线才发现的那种。

**三个自决项**

| # | 议题 | 选定 | 依据 |
|---|---|---|---|
| 1 | `visible` 给 1 还是 0 | **0**（隐藏） | Plan 1 只交后端，`/admin/kg-twin` 对应的 `TwinWorkspace` 路由属 Plan 2（P0-5/P0-6）。先亮菜单会点出空白页；仓库已有同一手法：收口后的旧「wiki 知识库」靠 `UPDATE … SET visible = 0` 留路由遮入口（`menu_knowledge_governance.sql:72`、`init.sql:4678`）。**Plan 2 落地页面时把 2406 的 visible 改回 1**，同一文件里再追加一行幂等 UPDATE 即可 |
| 2 | 后端会不会消费 `kg:twin:read` | **不消费** | 本计划的鉴权全部在 owner / share / publish 三层（Task 6/8/9）；Global Constraints 已写明不走 `AuditLogRoute` 的 `openapi_extra={"permissions": ...}` 分支（全仓零处使用、未运行验证）。这一行是**入口位 + 授权位**，不是后端闸门 |
| 3 | 行尾逗号 | 前一行（2405）**必须加逗号** | `VALUES (…) , (…)` 语法；不改它就是一条 `syntax error at or near "("`，而且只在部署跑 SQL 时才暴露 |

> #### 计划缺陷修正（执行时实测，2026-11-01）：菜单号 2406 已被占用
>
> 执行本 Task 时工作区已存在**并行在飞的「数据资产目录」特性**（AF-01~AF-08），它已把 2406 分给自己：
>
> ```sql
> -- menu_knowledge_governance.sql:44（当时未提交的工作区内容）
> (2406, '数据资产', 'knowledge.menu.dataAsset', '/admin/data-asset', 2401, 4, 0, 'kg:asset:read', …)
> ```
>
> 同一 `VALUES` 块里出现两行 2406 = 一条重复主键 SQL（`WHERE NOT EXISTS` 只按 id 去重，
> 第二行会被当成“已存在”而默默吃掉孪生菜单）。因此本次交付按下列三点偏移执行，
> **下面各 Step 的代码块保留原稿的 2406 文本作为来源，不再逐处刷写**：
>
> 1. **`id` 2406 → 2407**（全仓 `docs/sql/*.sql` 搜索确认 2407 未被任何模块使用）；
> 2. **`sort` 4 → 5**（数据资产已拿走 `parent_id=2401` 下的 sort=4，平号会让两页排序退化成不确定）；
> 3. **角色授权范围 `BETWEEN 2401 AND 2406` → `AND 2407`**（两文件），同时它**越级盖住了**他人
>    已改到一半的 `AND 2406`——这是超集关系（范围同时包含数据资产与孪生），不丢他人成果；
> 4. 尾逗号测试不再钉死「2405 行」而改成「除块内末行外全部以 `),` 结尾」：真实末行现在随
>    并行特性漂移（governance 块是 2407，init.sql 块也是 2407 但中间没有 2406），钉行号会在
>    任何人追加菜单时假失败。

**Files:**
- Modify: `docs/sql/menu_knowledge_governance.sql`（VALUES 块 `:33-43`、角色授权范围 `:78`）
- Modify: `docs/sql/init.sql`（同源镜像块 `:4647-4656`、`:4683`）
- Test: `backend/tests/twin/test_menu_sql_twin.py`

**Interfaces:**
- Consumes: 无（不依赖 Task 1–9 的代码）
- Produces: 两个 SQL 文件里逐字一致的 `(2406, …)` 行；角色授权范围 `BETWEEN 2401 AND 2406`；测试侧三个纯文本工具 `twin_row(path)` / `values_columns(path)` / `row_parts(row)` 只服务本文件，Task 11 不依赖它们

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/twin/test_menu_sql_twin.py`。这里有两类断言：**文本断言**防两个文件漂开，
**执行断言**防字段个数与列名对不上（新增一行最容易错的就是数错列）：

```python
"""菜单 SQL 的两处一致性与可执行性（spec §2.3 菜单行 / §3.9）。

不用 `db` 夹具里的表列表建 `sys_menu`：`tests/twin/conftest.py::_tables()` 沿用本体版，
没 import `app.models.sys.sys_user`，所以这里自己 `create(checkfirst=True)`。
"""
import re
from pathlib import Path

import pytest
from sqlalchemy import text

from app.models.sys.sys_user import SysMenu

REPO = Path(__file__).resolve().parents[3]      # backend/tests/twin/本文件 → 仓库根
GOV = REPO / "docs" / "sql" / "menu_knowledge_governance.sql"
INIT = REPO / "docs" / "sql" / "init.sql"

# spec §2.3 定死的 15 个字段（顺序即 VALUES 列顺序）
FIELDS = ["id", "name", "i18n_key", "path", "parent_id", "sort", "status", "permission",
          "type", "icon", "component", "is_deleted", "visible", "keep_alive", "always_show"]
EXPECTED = {
    "id": "2406", "name": "'孪生应用'", "i18n_key": "'knowledge.menu.twin'",
    "path": "'/admin/kg-twin'", "parent_id": "2401", "sort": "4", "status": "0",
    "permission": "'kg:twin:read'", "type": "2", "icon": "'DeploymentUnitOutlined'",
    "component": "NULL", "is_deleted": "false", "visible": "0",
    "keep_alive": "0", "always_show": "0",
}


def twin_row(path: Path) -> str:
    """取出 2406 那一行（去首尾空白与行尾逗号），多于/少于一条都是失败。"""
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    hits = [ln for ln in lines if ln.startswith("(2406,")]
    assert len(hits) == 1, f"{path.name} 应恰好有一行 2406，实得 {len(hits)} 行"
    return hits[0].rstrip(",")


def values_columns(path: Path) -> list:
    """从文件里抽 `INSERT INTO "public"."sys_menu"` 后的列名清单（不自己另写一列）。

    只取**包含 2406 那一行**的那个 INSERT 块：`init.sql` 里有十几个菜单 INSERT，
    拿错块会让测试假绿。
    """
    raw = path.read_text(encoding="utf-8")
    blocks = re.findall(r'INSERT INTO "public"\."sys_menu"\s*\n\s*\(([^)]*)\)(.*?);',
                        raw, flags=re.S)
    hit = [b for b in blocks if "(2406," in b[1]]
    assert len(hit) == 1, f"{path.name} 里包含 2406 的 INSERT 块应唯一，实得 {len(hit)}"
    return [c.strip() for c in hit[0][0].split(",")]


def row_parts(row: str) -> list:
    """拆 VALUES 元组。本行的 15 个值**均不含逗号**（名字/路径/角色码都无逗号），
    所以直接 split 就够；若将来加了带逗号的值，这里必须换真解析器而不是改测试。"""
    return [p.strip() for p in row.strip()[1:-1].split(",")]


def test_both_files_have_identical_2406_row():
    # 两文件逐字一致：`init.sql` 是各菜单 SQL 的同源镜像（文件里就写着“来源：menu_knowledge_governance.sql”）
    assert twin_row(GOV) == twin_row(INIT)


def test_row_has_exactly_15_fields_in_declared_order():
    for path in (GOV, INIT):
        assert values_columns(path) == FIELDS, f"{path.name} 的列清单与 spec §2.3 不一致"
        assert len(row_parts(twin_row(path))) == 15, f"{path.name} 的 2406 行字段个数不是 15"


def test_row_field_values_match_spec():
    for path in (GOV, INIT):
        got = dict(zip(FIELDS, row_parts(twin_row(path))))
        assert got == EXPECTED, f"{path.name} 的 2406 行与 spec §2.3 不符：{got}"


def test_previous_row_gained_trailing_comma():
    """经典坑：在 VALUES 块末尾追加一行时，原来的最后一行必须接上逗号。"""
    for path in (GOV, INIT):
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
        prev = [ln for ln in lines if ln.startswith("(2405,")]
        assert len(prev) == 1 and prev[0].endswith("),"), \
            f"{path.name} 的 2405 行没补上尾逗号，整段 SQL 会语法错"
        assert not twin_row(path).endswith(","), f"{path.name} 的 2406 行现在才是最后一行，不应带尾逗号"


def test_role_grant_range_covers_2406():
    """角色授权范围不同步 → 菜单真打开那天所有角色都看不到它（比后端 403 更难查的幽灵 bug）。"""
    needle = "BETWEEN 2401 AND 2406 AND id <> 2404"
    for path in (GOV, INIT):
        raw = path.read_text(encoding="utf-8")
        assert needle in raw, f"{path.name} 的角色授权范围仍停在 2405"
        assert "BETWEEN 2401 AND 2405 AND id <> 2404" not in raw, f"{path.name} 还残留旧范围"


def test_2406_row_inserts_and_is_idempotent(db):
    """拿**文件里**的行元组与列清单拼成 INSERT 真跑两遍：第二遍必须 0 行。

    列清单与元组都来自文件，所以这一条同时钉住了字段个数、字面量合法性与幂等写法。
    裸 NULL（`parent_id`/`component`）不需 CAST：2401 行已在生产上用同一形状跑过。"""
    SysMenu.__table__.create(bind=db.get_bind(), checkfirst=True)
    cols = ", ".join(values_columns(GOV))
    row = twin_row(GOV)
    sql = (f'INSERT INTO sys_menu ({cols}) SELECT v.* FROM (VALUES {row}) AS v({cols}) '
           f'WHERE NOT EXISTS (SELECT 1 FROM sys_menu s WHERE s.id = v.id)')

    first = db.execute(text(sql))
    db.commit()
    assert first.rowcount == 1
    second = db.execute(text(sql))
    db.commit()
    assert second.rowcount == 0, "WHERE NOT EXISTS 没生效 → 重跑会插重复菜单"

    got = db.execute(text("SELECT id, name, path, permission, type, parent_id, sort, visible "
                          "FROM sys_menu WHERE id = 2406")).mappings().all()
    assert len(got) == 1
    assert dict(got[0]) == {"id": 2406, "name": "孪生应用", "path": "/admin/kg-twin",
                            "permission": "kg:twin:read", "type": 2, "parent_id": 2401,
                            "sort": 4, "visible": 0}
```

- [ ] **Step 2: 跑到失败**

Run：`.\.venv\Scripts\python.exe -m pytest tests/twin/test_menu_sql_twin.py -v`

Expected：**6 条全部 FAIL，一条都不许 PASS。** 已核实的当前文件状态决定了每条的失败点：

| 用例 | 失败点 | 真实原因（当前文件状态） |
|---|---|---|
| `test_both_files_have_identical_2406_row` | `twin_row(GOV)` → `应恰好有一行 2406，实得 0 行` | 两文件都还没有 2406 行 |
| `test_row_has_exactly_15_fields_in_declared_order` | `values_columns(GOV)` → `包含 2406 的 INSERT 块应唯一，实得 0` | 同上——先卡在挑块，还没走到列清单比对 |
| `test_row_field_values_match_spec` | `twin_row(GOV)` 同上 | 同上 |
| `test_previous_row_gained_trailing_comma` | `2405 行没补上尾逗号` | **已核实**：`menu_knowledge_governance.sql:42` 与 `init.sql:4654` 的 2405 行均以 `)` 结尾、**无逗号**（它们是当时的末行） |
| `test_role_grant_range_covers_2406` | `角色授权范围仍停在 2405` | 两处均写 `BETWEEN 2401 AND 2405 AND id <> 2404`（`:78` / `:4683`） |
| `test_2406_row_inserts_and_is_idempotent` | `values_columns(GOV)` 同上 | 同上 |

若某条意外 PASS，先查 `REPO = parents[3]` 是否真的指到仓库根（写成 `parents[2]` 会指到 `backend/`，
那时 `read_text` 抛 `FileNotFoundError` 而不是断言失败——报错形态不同，别把它当成本任务的红灯）。
若 `test_2406_row_inserts_and_is_idempotent` 报 `FileNotFoundError` 而非上面的断言失败，即为路径算错。

---

- [ ] **Step 3: 改 `docs/sql/menu_knowledge_governance.sql`（两处）**

**改动 3a** VALUES 块末行（`:41-43`）。给 2405 行接上逗号，并追一行 2406：

改前：

```sql
-- 本体（ontology 建模）
(2405, '本体',               'knowledge.menu.ontology',  '/admin/kg-ontology',         2401, 3, 0, 'kg:ontology:read', 2, 'ApartmentOutlined', NULL, false, 1, 0, 0)
) AS v(id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
```

改后（**这三行的前缀必须与上面逐字一致**，只在 2405 行末尾多一个逗号、中间插一个注释行）：

```sql
-- 本体（ontology 建模）
(2405, '本体',               'knowledge.menu.ontology',  '/admin/kg-ontology',         2401, 3, 0, 'kg:ontology:read', 2, 'ApartmentOutlined', NULL, false, 1, 0, 0),
-- 孪生应用（菜单入口；Plan 1 只落后端，页面/路由属 Plan 2，故 visible=0 先压住侧栏）
(2406, '孪生应用',         'knowledge.menu.twin',      '/admin/kg-twin',         2401, 4, 0, 'kg:twin:read',    2, 'DeploymentUnitOutlined', NULL, false, 0, 0, 0)
) AS v(id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
```

**改动 3b** 角色授权范围（`:78`）：

改前：

```sql
CROSS JOIN (SELECT id FROM "public"."sys_menu" WHERE id BETWEEN 2401 AND 2405 AND id <> 2404) m
```

改后：

```sql
CROSS JOIN (SELECT id FROM "public"."sys_menu" WHERE id BETWEEN 2401 AND 2406 AND id <> 2404) m
```

> 3b 不是凑数。范围停在 2405 的话，今天看不出任何异常（菜单本来就是隐藏的），等到 Plan 2
> 把 `visible` 改回 1 那天，所有角色都看不到入口——而 SQL 已经跑过、重跑又被
> `WHERE NOT EXISTS` 闸住，这是比后端 403 更难查的幽灵 bug。现在改，授权随菜单行一起落库。

- [ ] **Step 4: 改 `docs/sql/init.sql`（同样两处，逐字复制）**

`init.sql:4644` 写着 `-- 来源：menu_knowledge_governance.sql`，它是同源镜像。注意两个文件的
**块体形状不同**：`init.sql` 的 VALUES 块里没有 governance 版那些 `-- ====` 注释行（`:4651-4654`
直接是四行元组），所以**只能逐行对打，不能整块复制**，否则会把 governance 版的注释刷进 init。

**改动 4a** VALUES 块末行（`:4654-4655`）。改前：

```sql
(2405, '本体',               'knowledge.menu.ontology',  '/admin/kg-ontology',         2401, 3, 0, 'kg:ontology:read', 2, 'ApartmentOutlined', NULL, false, 1, 0, 0)
) AS v(id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
```

改后（2406 行与 Step 3 的那一行**必须字节相同，含对齐空格**）：

```sql
(2405, '本体',               'knowledge.menu.ontology',  '/admin/kg-ontology',         2401, 3, 0, 'kg:ontology:read', 2, 'ApartmentOutlined', NULL, false, 1, 0, 0),
-- 孪生应用（菜单入口；Plan 1 只落后端，页面/路由属 Plan 2，故 visible=0 先压住侧栏）
(2406, '孪生应用',         'knowledge.menu.twin',      '/admin/kg-twin',         2401, 4, 0, 'kg:twin:read',    2, 'DeploymentUnitOutlined', NULL, false, 0, 0, 0)
) AS v(id, name, i18n_key, path, parent_id, sort, status, permission, type, icon, component, is_deleted, visible, keep_alive, always_show)
```

**改动 4b** 角色授权范围（`:4683`），与 3b 同一句话：`BETWEEN 2401 AND 2405` → `BETWEEN 2401 AND 2406`。
该句式全仓共 2 处（本行与 governance 版 `:78`），**不要顺手改全文件**：`init.sql` 里还有其他
`BETWEEN 2501 AND 2502`（`:4638`）、`BETWEEN 2601 AND …`（duplex 块）这类属另外的模块。
改完跑一次全仓搜索确认：

```powershell
Select-String -Path docs\sql\*.sql -Pattern 'BETWEEN 2401 AND 240'
```

Expected：恰好 2 行命中，且**均为 `AND 2406`**；出现任何 `AND 2405` 即未改净。

- [ ] **Step 5: 跑到通过 + 双行目视比对**

Run：`.\.venv\Scripts\python.exe -m pytest tests/twin/test_menu_sql_twin.py -v`
Expected: PASS（6 passed）。失败时的排查序（按此序查，**不得改测试迁就实现**）：

1. `应恰好有一行 2406，实得 2 行` → 把一个文件里的 2405 行改成了两行，或往块里粘了两次；
2. `twin_row(GOV) == twin_row(INIT)` 不等但肉眼看字一样 → 对齐空格数目不同（Tab vs 空格、
   全角空格尤其常见）。拿 Step 5 下面的 `Select-String` 输出直接比，不要靠眼睛；
3. `的 2405 行没补上尾逗号` → 只改了 3a 没改 4a（两文件各有一条 2405 行，测试逐文件断言）；
4. `列清单与 spec §2.3 不一致` → 误改了 `INSERT INTO` 后的列名行。**列行一个字都不需改**：
   15 列已含 2406 需要的全部字段；
5. `row_parts` 报 `个数不是 15` → 2406 行少写或多写了值（最常见的是 `NULL, false, 0, 0, 0` 只给了 4 个）；
6. `test_2406_row_inserts_and_is_idempotent` 报 `syntax error at or near ")"` → 2405 行的逗号多加了一个
   （`(…),(,)` 形式），或 2406 行末尾被顺手带上了逗号（它现在是末行，**不应带逗号**）；
7. 同上但报 `column "updated_at" …` 或 `NULL not allowed` → 把值写到了错误的列位，
   拿 `row_parts()` 与 `FIELDS` 的 zip 结果比对（测试失败消息里的 `got` 字典就是它）。

Run（目视比对两行，独立于 pytest 的第二双确认；`2406` 按缺陷 #25 已改为 `2407`）：

```powershell
Select-String -Path docs\sql\menu_knowledge_governance.sql,docs\sql\init.sql -Pattern '^\(2407,'
```

Expected：恰好 2 行输出，除文件名/行号前缀外**后半段完全相同**。

Run：`.\.venv\Scripts\python.exe -m pytest tests/twin tests/ontology tests/unit -v`
Expected: 全绿。本任务不改 Python 代码，这条只是确认新增的
`tests/twin/test_menu_sql_twin.py` 自己没弄坏共享夹具（它 `import app.models.sys.sys_user`，
而 `tests/twin/conftest.py::_tables()` 默认不导该模型——这就是测试里要自己
`SysMenu.__table__.create(checkfirst=True)` 的原因）。

单文件确认（Step 5 首条命令）：实测 **6 passed**。

目录回归（上面那条合并命令）**必须按目录分跑**（同 Task 7/8/9 的先行缺陷：跨目录收集会污染
全局 `Base.metadata`，`tests/kb` 的导入链把 `kms_*` 注册进来而 `_tables()` 不建这些表）：

```powershell
foreach ($d in 'twin','ontology','unit') { .\.venv\Scripts\python.exe -m pytest "tests/$d" -v 1>"_t10r_$d.txt" 2> $null; "$d EXIT=$LASTEXITCODE" }
```

实测 `tests/twin` **84 passed**（含本任务新增 6 条）、`tests/ontology` 79 passed、
`tests/unit` 309 passed + 1 skipped，三个 EXIT 均为 0。

> **不要拿真库或测试库直接跑整个 SQL 文件。** 两个文件写的是 `"public"."sys_menu"`，
> 而 `tests/twin` 夹具跑在每个用例独立的随机 schema 里：整文件执行会去动 `public`，
> 还会顺带 `DELETE FROM sys_menu WHERE id = 2404`。需要真跑整文件时，另用一次性
> `docker run` 的空库，不在本计划的 CI 里。
> 同理，本任务**不新加 Alembic 菜单数据迁移**：菜单 SQL 属仓库现有约定（`docs/sql/` 双文件），
> 而 Task 1 的 `2026_11_01_0013_add_twin_tables` 只负责建 7 张表。

- [ ] **Step 6: 提交**

```bash
git add docs/sql/menu_knowledge_governance.sql docs/sql/init.sql backend/tests/twin/test_menu_sql_twin.py
git commit -m "feat(twin): add sys_menu row for twin workspace (visible=0)"
```

> 本任务的三个文件全在仓库根下，故 **cwd 要切回仓库根**（在 `backend/` 里写 `docs/sql/…` 会
> `pathspec … did not match any files`），且需一并 `git add` 本文档。
> `menu_knowledge_governance.sql` 的工作区 diff 含**他人未提交的 2406 数据资产两行**，
> 因而是 Task 8 同一手法的延伸：先临时删那两行 → `git add` → 原样写回，
> 并用 `git diff --cached -- docs/sql/menu_knowledge_governance.sql | Select-String dataAsset` 为空坐实。

---

#### Task 10 执行记录（2026-11-01）

交付：`menu_knowledge_governance.sql` + `init.sql` 各新增 `2407` 孪生菜单行（两行**字节相同**，
由 `test_both_files_have_identical_twin_row` 钉住）+ 两处角色授权范围 → `BETWEEN 2401 AND 2407` +
`test_menu_sql_twin.py`（**6 passed**，红灯阶段 6 条全失败、0 条假绿）。

| # | 类别 | 现象 | 修法 |
|---|---|---|---|
| 25 | 计划缺陷（整个 Task 的前提） | 原定 `id=2406` 已被并行的「数据资产」特性占用（同块两行 2406 = 重复主键，且 `WHERE NOT EXISTS` 会默默吃掉后一行） | 改取 `2407`，`sort` 顺延为 5（已在 Task 10 开头就地修正） |
| 26 | 计划缺陷（Step 1 尾逗号测试） | `test_previous_row_gained_trailing_comma` 钉死「2405 行末必须接逗号」，而真实前驱行已不定（governance 是 2406）；同时 `assert not twin_row(path).endswith(",")` 假设本行是末行，也不定 | 改为「除块内末行外全部以 `),` 结尾 + 末行不带逗号」，不钉行号 |
| 27 | 环境漂移（Step 6 提交） | 两个 SQL 文件里都有他人未提交内容；直接 `git add menu_knowledge_governance.sql` 会把「数据资产」菜单行并入本次提交 | 沿用 Task 8 手法：临时删他人两行 → `git add` → 原样写回；索引内 `dataAsset` 命中数为 0 |
| 28 | 观察（不属本任务） | `init.sql` 作为同源镜像**尚未**包含 2406 数据资产行（只有 `menu_knowledge_governance.sql` 有），两文件已因并行开发短暂失同步 | 不由本次代偿（那会把别人的特性写进我的 commit）；已在 SQL 注释里标注 2406 归属，留给数据资产一方自己镜像 |

两个未消的后续（都属 Plan 2，不阻断 P0）：

1. `knowledge.menu.twin` 这个 i18n key **四个 locale 文件都还没有**（`frontend/src/i18n/locales/*.ts` 的
   `knowledge.menu` 块里目前只到 `dataAsset`）。今天看不出问题（`visible=0` 不进侧栏），
   Plan 2 把 2407 改回 `visible=1` 时必须同批补 key，否则侧栏直接渲染裸 key。
2. 本次**未动前端**：按自决项 2，`kg:twin:read` 只是入口位 + 授权位，后端不消费。

提交：`TODO`。

---

### Task 11: 规格关账（P0-11 / W16，验收阻断项）

对应 spec §0.1 「与上游/姊妹规格的冲突关账」与 §7.5 R7。**不碰一行代码**，但不做完它
W16 不通过：上游规格现把孪生应用写成「不做 / 维持 P3 观察项」，而 Task 1–10 已把它落地。
本项目已有过同类教训（规格现文本逐字摘自当前文件，非记忆转述）。

**三个自决项**

| # | 议题 | 选定 | 依据 |
|---|---|---|---|
| 1 | 改哪份上游 | 只改 `2026-10-31-ontology-capability-design.md` | 实测：§0.1 给出的行号 `:64/:77/:148/:1066` 全部**逐字命中**该文件（四个针句各 1 处）；同名前缀的 `2026-10-31-minworkbuddy-ontology-capability-design.md` 行号对不上。孪生规格 §8.1 事实清单点名的也是前者 |
| 2 | 早期并行草案（minworkbuddy- 版）里还有 4 处「孪生应用…列远期」怎么办 | **不逐行回写，只加一行“以主规格为准”的横幅**（Step 7） | `git log` 实测：该文件 2026-10-31 一次提交后未再动过，而主规格在 2026-11-01 接过沙盘回写——它是未同步的早期草案。改它的内容会适得其反（后人会拿草案当主规格读）；标记成本一行，且消除同一个矛盾向量 |
| 3 | 验证手法 | **grep 门闸，不写 pytest** | 本任务改的是 Markdown 表格/mermaid，断言“旧针句仍存在”比断言新文案更稳定（新文案会措词微调）。四个针句已实测**在上游各命中恰好 1 行**，删零即可判定完成 |

**Files:**
- Modify: `docs/superpowers/specs/2026-10-31-ontology-capability-design.md`（`:64` `:77` `:148` `:1066`）
- Modify: `docs/superpowers/specs/2026-11-01-simulation-sandbox-design.md`（`:364`）
- Modify: `docs/superpowers/specs/2026-10-31-minworkbuddy-ontology-capability-design.md`（`:4` 后插一行）
- Test: 无新文件（Step 1 与 Step 8 的命令即门闸）

**Interfaces:**
- Consumes: Task 0 的探测结论（决定 Step 4 里 AF-22 的“演示口径”措词）、Task 1–10 的实际落地范围
- Produces: 无（文档终端，后续任务不依赖）

- [ ] **Step 1: 跑门闸，确认红灯（当前仍是旧口径）**

```powershell
Select-String -Path docs\superpowers\specs\2026-10-31-ontology-capability-design.md -SimpleMatch `
  -Pattern '维持 P3 观察项','依赖推演与实时物化','推演/孪生维持非目标','推演孪生（观察项）'
Select-String -Path docs\superpowers\specs\2026-11-01-simulation-sandbox-design.md -SimpleMatch `
  -Pattern '孪生应用维持非目标'
```

Expected：第一段命中 **4 行，行号恰好是 64 / 77 / 148 / 1066**（已实测每个针句各 1 处）；
第二段命中 **1 行，行号 364**。若行号不对，先确认可作分支的基准提交与本计划的假设一致，
**不要改后面的目标文案来迁就行号**。

- [ ] **Step 2: 改上游 §1.2 能力边界行（`:64`）**

改前（整行）：

```markdown
| — | **孪生应用** | 依赖推演物化与实时回显；维持 P3 观察项。**推演沙盘已从本行拆出并单独立项**（沙箱域例外物化裁决，见 `2026-11-01-simulation-sandbox-design.md` 与 §1.3 行「六、推演沙盘」） |
```

改后（表头是「做（本期）| 不做（明确排除）| 原因」，所以孪生要从第 2 列移到第 1 列，
并把“不做”列填上 T3/T4 真正放弃的部分；**同行的推演沙盘拆分说明逐字保留**）：

```markdown
| **孪生应用（P0/P1 已立项，2026-11-01）** | 公开分享链接 / 3D 真渲染 / 因果传导 | 依 T1 **查询期直连**，**不依赖推演物化**，原「依赖物化 → 维持 P3 观察项」判据失效；设计见 `2026-11-01-digital-twin-app-design.md`。**推演沙盘已从本行拆出并单独立项**（沙箱域例外物化裁决，见 `2026-11-01-simulation-sandbox-design.md` 与 §1.3 行「六、推演沙盘」） |
```

- [ ] **Step 3: 改上游 §1.3 对标表行（`:77`）**

改前（整行，4 列）：

```markdown
| 七、孪生应用 | 拖拽指标/告警/图表、绑定本体查询 | **不做** | 依赖推演与实时物化 |
```

改后（保持 4 列；写法照抄相邻「六、推演沙盘」行 `:76` 的「**已立项（2026-11-01）**」句式）：

```markdown
| 七、孪生应用 | 拖拽指标/告警/图表、绑定本体查询 | **已立项（2026-11-01）**：P0 组件栅格 + 绑定本体查询（`onto_ontology_query`）+ 发布只读页 | 依 T1 查询期直连，不依赖物化；3D 场景编辑与因果传导 P1；设计见 `2026-11-01-digital-twin-app-design.md` |
```

- [ ] **Step 4: 改上游 §1.5 对照矩阵 AF-22 行（`:148`）**

这一行有 5 列，旧口径**同时出现在第 2 列与第 5 列**，只改一列就是假关账。

改前（整行）：

```markdown
| AF-22 一次查询多端消费 | **部分具备**：`query_service` + `sql_guard` + Agent 工具注册可复用；推演/孪生端不存在 | §4.6 覆盖 图/问数/Agent/导出 四端 | 已覆盖但深度不足 | §4.6 增「应用端」一行（经 `meta_ontology_publish`）；推演/孪生维持非目标 |
```

改后：

```markdown
| AF-22 一次查询多端消费 | **部分具备**：`query_service` + `sql_guard` + Agent 工具注册可复用；**孪生端经 `onto_ontology_query` 一等公民消费（已立项 2026-11-01）**；推演端按沙箱域另行立项 | §4.6 覆盖 图/问数/Agent/导出 四端 | 已覆盖但深度不足 | §4.6 消费端由「图/问数/Agent/导出」扩为含**应用端**（经 `onto_ontology_query`，非 `meta_ontology_publish`）；推演端单独表述见姊妹规格 V1 裁决 |
```

> 第 5 列里的「经 `meta_ontology_publish`」是原行的笔误延续：本体应用发布登记与孪生页发布
> 是两个不同的表（后者 `twin_publish`，Task 8）。本任务顺手把消费入口写对；
> **第 150 行的「汇总」不改**（AF-22 仍属「已覆盖但深度不足 5」，判定列未变）。

- [ ] **Step 5: 改上游 §7.1 分期图 mermaid 行（`:1066`）**

改前（一行，注意前置 4 个空格）：

```text
    P1C --> P2B["P2-2 多本体合并 / 推演孪生（观察项）"]
```

改后（三行；新节点源用 `P0E`——本体发布与版本快照，这是孪生/沙盘的共同前置）：

```text
    P1C --> P2B["P2-2 多本体合并"]
    P0E --> SBX["推演沙盘 P1：沙箱域例外物化（已立项 2026-11-01）"]
    P0E --> TWN["孪生应用 P0/P1：查询期直连（已立项 2026-11-01）"]
```

改完必看：`P2B` 节点名里的「观察项」三字必须消失，否则本任务的门闸（Step 8）不会变绿。
mermaid 的 `flowchart LR` 不要求额外声明，`SBX` / `TWN` 作为新节点自动入图；如果本地有
mermaid 渲染预览，眼过一眼即可， CI 不渲染它。

- [ ] **Step 6: 改姊妹沙盘规格 §11 回写表行（`2026-11-01-simulation-sandbox-design.md:364`）**

改前（整行）：

```markdown
| §1.2 非目标表 | 「推演沙盘、孪生应用」行拆分：推演沙盘已单独立项（沙箱域物化裁决）；孪生应用维持非目标 |
```

改后（前 4 处只改上游不够：这一行会让两份规格互相打脸，它就是孪生规格 §0.1 备注里
所说的“第 5 处=self-review 新发现”那一类）：

```markdown
| §1.2 非目标表 | 「推演沙盘、孪生应用」行拆分：**两者均已单独立项**——推演沙盘见本文档（沙箱域物化裁决），孪生应用见 `2026-11-01-digital-twin-app-design.md`（T1 查询期直连，不依赖物化，与本文 V1 裁决不冲突） |
```

- [ ] **Step 7: 给早期并行草案加标记行（minworkbuddy- 版）**

该文件 `:4` 现文本：

```markdown
> 状态：设计已确认（3 项遗留决策已裁决，见 §14.3），待实施计划
```

在它**之后**插一行（不改原文任何字，避免把草案伪装成已同步）：

```markdown
> ⚠️ 本文件为 2026-10-31 的**并行早期草案**，未同步后续立项。主规格为
> `2026-10-31-ontology-capability-design.md`；推演沙盘与孪生应用的现状以
> `2026-11-01-simulation-sandbox-design.md` 与 `2026-11-01-digital-twin-app-design.md` 为准。
> 本文件内的 N3（`:43`）、D−2（`:610`）、P4 远期表（`:1099`）、D2 范围行（`:1140`）、
> §15 远期展望（`:1176`）**不再回写**，仅作历史快照。实测：该文件自 2026-10-31 提交后未再修改。
```

- [ ] **Step 8: 跑到通过（门闸变绿）+ 全仓反查**

```powershell
Select-String -Path docs\superpowers\specs\2026-10-31-ontology-capability-design.md -SimpleMatch `
  -Pattern '维持 P3 观察项','依赖推演与实时物化','推演/孪生维持非目标','推演孪生（观察项）'
Select-String -Path docs\superpowers\specs\2026-11-01-simulation-sandbox-design.md -SimpleMatch `
  -Pattern '孪生应用维持非目标'
```

Expected：**两段都是 0 行命中。** 非 0 就是没改净（注意不是删除文本而是改写了含针句的句子）。

反查一次（确认没伤及无辜：沙盘规格里「维持 P3 观察项仅做预研」在 `:17` 的 V1 行，属推演沙盘
的被否备选，**不在关账范围、不得删除**，所以第二段命令只查 `孪生应用维持非目标` 而不查该针句）：

```powershell
Select-String -Path docs\superpowers\specs\2026-11-01-simulation-sandbox-design.md -SimpleMatch -Pattern '维持 P3 观察项'
```

Expected：仍为 **1 行命中（`:17`）**——它是合法文本，本任务不应改变它的存在。

Run：`.\.venv\Scripts\python.exe -m pytest tests/twin -q`
Expected：全绿（本任务不改代码，这一条确认改文档时没顺手碰到 `backend/`）。

- [ ] **Step 9: 提交**

```bash
git add docs/superpowers/specs/2026-10-31-ontology-capability-design.md docs/superpowers/specs/2026-11-01-simulation-sandbox-design.md docs/superpowers/specs/2026-10-31-minworkbuddy-ontology-capability-design.md
git commit -m "docs(specs): close twin-app non-goal statements in upstream specs (W16)"
```

> 本任务单独一个 commit，**不要与 Task 1–10 的代码提交合并**：关账改动需要单独回滚能力，
> 而 R7 的触发信号正是“代码已合、文档还是旧口径”。

---

## Self-Review（计划自检结果，已逐条核过）

### 1. Spec 覆盖表（§7.3 P0 项 → 本计划任务）

| spec P0 项 | 内容 | 落在哪个任务 | 备注 |
|---|---|---|---|
| P0-1 | Alembic 迁移 7 表 + 菜单/权限 SQL | Task 1（表+迁移）+ Task 10（菜单） | 两半分开交，各自可入仓 |
| P0-2 | 编译 7 步 + preview + 反向引用 + 抽 `_sensitive_covered()` | Task 4（服务+Q1–Q5）+ Task 2（抽取） | 6 类失败路径在 Task 4 逐条钉住 |
| P0-3 | `ReadonlyQueryService.run` 扩 `params` + 等价回归 | Task 3 | 含占位符归一纯函数 |
| P0-4 | 批量取数：扇出闸门 + TTL 缓存（键含角色签名）+ 出口脱敏 | Task 7（主体）+ Task 5（`core/cache.py` 上提） | W8 / W11 在 Task 7 测试里 |
| P0-7 | 发布 + 只读路由 + 访问校验与审计 | Task 8 | W12 |
| P0-8 | 受限三态 + 权限申请审批闭环 | Task 9（后端） | 三态的 UI 属 Plan 2 |
| P0-11 | 规格关账（上游 4 处 + 姊妹 1 处） | Task 11 | 纯文档，验收阻断项 |
| P0-5 / P0-6 / P0-9 / P0-10 | 前端栅格 / CRUD UI / AI 双通道 / tokens | **不属本计划** | Plan 2；Task 6 已交 P0-6 的后端半边 |

### 2. Placeholder 扫描结果

全文已逐项 grep：`TBD` / `TODO` / `实现时改写` / `Similar to Task` / “略” / 空代码块——均无。
每个“写代码”的 Step 都带可直接粘贴的完整体，每个“跑”的 Step 都带命令 + 预期输出 + 失败排查序。

### 3. 类型与命名一致性（关关键跨任务接缝逐条比对过）

- `TwinService(db, tenant_id, user_id, role_codes=())`（Task 6）——Task 8/9 的构造调用参同形；
- `masking.apply_masking(rows, masking, user)` 吃 records（Task 7 已 `zip(columns, row)`），
  与前置发现 3 一致；
- 错误码全集在 `api_error.py` 一处声明：Task 3/4 的 `QUERY_*`、Task 6–9 的 `TWIN_*`，
  下游任务只引用不重复定义；
- `data_cache_key(...)` 参数个数与 Task 5 定义一致（R3/W11 不变量的唯一入口）；
- Task 9 的 `_card_dict(..., current_versions)` 与 Task 6 定义同形，仅多了 `share_expires_at` 一个输出键（Step 7）。

### 4. 计划未覆盖的已知事项（显式记录，不当作完成）

1. **W1–W7 / W9 / W14** 属前端，本计划不发一枚前端组件；依赖本计划的 Plan 2 接手时，
   卡片/页面/组件的字段形状以 Task 6 的 `_card_dict` / `_page_dict` / `_widget_dict` 为准；
2. **nginx**：`/twin-p/:slug` 的最终访问路径已在 Task 8 修订为 `/api/v1/twin-p/{slug}`
   （因为 nginx 只代理 `/api/`）；若上线时要改成根路径，需同步改 nginx 配置，不在本计划内；
3. **分享票据 / 公开链接（T4 的 P1 部分）**、**3D 场景编辑（T3 的 P1 部分）**：本计划只留状态位与
   字段，不实现；
4. **性能压测**（§7.4 “不做” + 待核实 U3）：不属任何任务。

---

## Execution Handoff

计划已落盘：`docs/superpowers/plans/2026-11-01-digital-twin-p0-backend-core.md`。
两种执行方式，二选一：

1. **Subagent-Driven（推荐）**——每个 Task 派一个全新 subagent，任务之间做 review。
   本计划的任务颗粒已按“一个任务一套测试一个提交”切好，Task 0（探测决策闸）与
   Task 2（行为不变重构）特别适合单独过一道人眼。
   REQUIRED SUB-SKILL：`superpowers:subagent-driven-development`。
2. **Inline Execution**——当前会话逐批执行，批次之间停下检查。
   REQUIRED SUB-SKILL：`superpowers:executing-plans`。

执行前置（两种方式都需要）：

- 本地 PostgreSQL 可用（夹具自建库 `minworkbuddy_test`），命令均在 `backend/` 目录用
  `.\.venv\Scripts\python.exe` 执行；
- 从 **Task 0 开始**，不得跳到 Task 1：Task 0 的输出决定 P0 演示口径（哪几条 demo 本体
  已完成物理映射），影响 Task 4 的错误文案与 Task 11 的关账措词；
- 每个任务的 Step “提交”都是单独一个 commit，**不要把几个任务摊成一个提交**——回滚粒度依赖它。

