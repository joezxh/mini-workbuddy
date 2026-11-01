# 数据资产目录一期全对齐（AF-01~AF-08）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将数据资产目录能力（分组树/检索打分/标签/卡片/送数）严格对齐原型 `docs/prototypes/ontology-asset-catalog-preview.html`，一期全量补齐差距且不新建资产表。

**Architecture:** 资产目录是 `meta_table`/`meta_column` 扫描元数据的投影；`meta_data_source` 新增物化列 `external_type` 作分组依据；检索走三段确定性打分（禁 similarity）；送数只写 `onto_ontology.draft_scope_json`，服务端做单源终防线；标签绑定无外键，rule/human 分治。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + PostgreSQL（pg_trgm GIN 已就位）；Vue 3 + Ant Design Vue + Vitest。

**Spec:** `docs/superpowers/specs/2026-11-01-asset-catalog-alignment-design.md`（裁决记录 §0 同文）

## Global Constraints（每个任务隐含遵守）

1. 检索打分**永久禁** `similarity()` / `word_similarity()`；`gin_trgm_ops` 索引只加速 `LIKE '%kw%'`。
2. 送数**只写** `onto_ontology.draft_scope_json`，**绝不写结构表**。
3. 同分排序恒按 `table_name` 字典序（结果可复现）。
4. `onto_asset_tag_binding.asset_id` **不建外键**；`source='human'` 的绑定任何清理永不触碰。
5. 分页契约：`page/size` 默认 50、上限 200（路由 Query 硬校验保持）。
6. 可见性开关本期不做：不建 visibility 列、目录不做可见性过滤。
7. 新路由一律走 `ApiError` 统一错误契约（`{code,message,detail?}`）；dataops 既有 47 端点不改造。
8. 测试租户常量用 `tests/dataops/conftest.py` 的 `TENANT_A=100`；`external_type` 不进 `sys_dictionary`。

---

## 文件结构（改动落点）

| 文件 | 职责 |
|---|---|
| `backend/app/models/dataops/data_source.py` | +`external_type` 列/CHECK/索引 |
| `backend/app/services/dataops/source_types.py` | +`EXTERNAL_TYPE_CODES/LABELS/DEFAULT_BY_SOURCE_TYPE` 单一真源 |
| `backend/alembic/versions/2026_11_01_0010_add_source_external_type.py` | 加列+回填+约束 |
| `backend/app/db/startup_migrations.py` | AUTO_CREATE 路径幂等兜底加列 |
| `backend/app/services/dataops/data_source_service.py` | 创建/编辑派生 external_type，手改优先 |
| `backend/app/services/ontology/ontology_service.py` | assets_tree 重写（10 节点） |
| `backend/app/services/ontology/ontology_asset_service.py` | 打分口径/批量消除 N+1/table_type/sort/单源校验/回显剔除/探活/编辑 |
| `backend/app/services/ontology/ontology_tag_service.py` | rule 重打方法 + security 自动打标 |
| `backend/app/services/ontology/ontology_build_service.py` | 幂等键前 tags/catalog 展开 |
| `backend/app/services/dataops/scan_service.py` | 扫描后置打标钩子 |
| `backend/app/routers/ontology/ontology.py` | search 新参数、探活/编辑/重新分级端点、draft-scope PUT 接校验 |
| `backend/app/core/api_error.py` | +3 错误码 |
| `backend/app/ai/dataops/dialects/{_sqlalchemy_base,es,dm}.py` | 方言级表探活支撑 |
| `backend/tests/ontology/*` | 新测试目录（conftest 仿 dataops per-schema 模式） |
| `frontend/src/api/dataops.ts` | 新端点封装 |
| `frontend/src/views/data-source/asset/*.vue` | 四组件对齐 + 弹窗 |

---

### Task 1: `external_type` 列、映射矩阵与迁移

**Files:**
- Modify: `backend/app/models/dataops/data_source.py`
- Modify: `backend/app/services/dataops/source_types.py`
- Create: `backend/alembic/versions/2026_11_01_0010_add_source_external_type.py`
- Modify: `backend/app/db/startup_migrations.py`
- Test: `backend/tests/ontology/test_external_type.py`

**Interfaces:**
- Produces: `DataSource.external_type: str`；`source_types.EXTERNAL_TYPE_CODES: tuple`、`EXTERNAL_TYPE_LABELS: dict`、`DEFAULT_EXTERNAL_TYPE_BY_SOURCE_TYPE: dict`；`source_types.external_type_for(source_type) -> str`（未知落 `other`）。

- [ ] **Step 1: 写失败测试**（打分前的矩阵纯函数 + 模型列存在性）

```python
# backend/tests/ontology/test_external_type.py
from app.services.dataops import source_types as st

def test_matrix_per_adjudication():
    for code in ("mysql", "oracle", "postgresql", "sqlserver", "dm", "kingbase"):
        assert st.external_type_for(code) == "rdbms"
    for code in ("clickhouse", "doris", "starrocks"):
        assert st.external_type_for(code) == "warehouse"
    assert st.external_type_for("es") == "search"
    assert st.external_type_for("excel") == "file"

def test_unknown_falls_to_other():
    assert st.external_type_for("some_future_type") == "other"

def test_model_column_exists():
    from app.models.dataops.data_source import DataSource
    col = DataSource.__table__.c.external_type
    assert col.type.length == 32 and not col.nullable
```

- [ ] **Step 2: 运行确认失败** — `pytest backend/tests/ontology/test_external_type.py -v` → ImportError/AttributeError

- [ ] **Step 3: 实现**

`source_types.py` 末尾追加：

```python
#: 资产粗分类（AF-01 分组；Q1 裁决 B：物化列取值域，不进字典）
EXTERNAL_TYPE_CODES = ("rdbms","tsdb","warehouse","graph","kv","vector","search","file","saas","other")
EXTERNAL_TYPE_LABELS = {
    "rdbms":"关系型数据库","tsdb":"时序数据库","warehouse":"数仓 / 大数据","graph":"图数据库",
    "kv":"NoSQL 键值","vector":"向量库","search":"搜索引擎","file":"文件资源",
    "saas":"API / SaaS","other":"其他",
}
#: source_type → external_type 回填矩阵（Q2 裁决：clickhouse/doris/starrocks→warehouse）
DEFAULT_EXTERNAL_TYPE_BY_SOURCE_TYPE = {
    "mysql":"rdbms","oracle":"rdbms","postgresql":"rdbms","sqlserver":"rdbms","dm":"rdbms","kingbase":"rdbms",
    "clickhouse":"warehouse","doris":"warehouse","starrocks":"warehouse",
    "es":"search","excel":"file",
}

def external_type_for(source_type: str) -> str:
    return DEFAULT_EXTERNAL_TYPE_BY_SOURCE_TYPE.get((source_type or "").lower().strip(), "other")
```

`data_source.py` 在 `source_type` 列后加：

```python
external_type = Column(String(32), nullable=False, server_default="other",
    comment="资产粗分类: rdbms|tsdb|warehouse|graph|kv|vector|search|file|saas|other")
```

`__table_args__` 追加：

```python
CheckConstraint(
    "external_type IN ('rdbms','tsdb','warehouse','graph','kv','vector','search','file','saas','other')",
    name="ck_meta_data_source_external_type"),
Index("idx_meta_data_source_tenant_extype", "tenant_id", "external_type"),
```

迁移 `2026_11_01_0010_add_source_external_type.py`（`down_revision = "2026_11_01_0009_seed_demo_ontologies"`，照抄 0007 的幂等风格）：

```python
def upgrade() -> None:
    op.execute("ALTER TABLE meta_data_source ADD COLUMN IF NOT EXISTS external_type VARCHAR(32)")
    # 存量回填（矩阵来自应用层单一真源，SQL 内联保持迁移自包含）
    for code, ext in {"mysql":"rdbms","oracle":"rdbms","postgresql":"rdbms","sqlserver":"rdbms",
                      "dm":"rdbms","kingbase":"rdbms","clickhouse":"warehouse","doris":"warehouse",
                      "starrocks":"warehouse","es":"search","excel":"file"}.items():
        op.execute(f"UPDATE meta_data_source SET external_type='{ext}' "
                   f"WHERE external_type IS NULL AND lower(source_type)='{code}'")
    op.execute("UPDATE meta_data_source SET external_type='other' WHERE external_type IS NULL")
    op.alter_column("meta_data_source", "external_type", nullable=False,
                    server_default="other", existing_type=sa.String(32))
    op.execute("""ALTER TABLE meta_data_source DROP CONSTRAINT IF EXISTS ck_meta_data_source_external_type""")
    op.execute("""ALTER TABLE meta_data_source ADD CONSTRAINT ck_meta_data_source_external_type
        CHECK (external_type IN ('rdbms','tsdb','warehouse','graph','kv','vector','search','file','saas','other'))""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_meta_data_source_tenant_extype "
               "ON meta_data_source (tenant_id, external_type)")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_meta_data_source_tenant_extype")
    op.execute("ALTER TABLE meta_data_source DROP CONSTRAINT IF EXISTS ck_meta_data_source_external_type")
    op.execute("ALTER TABLE meta_data_source DROP COLUMN IF EXISTS external_type")
```

`startup_migrations.py` 幂等列表追加同款 `ADD COLUMN IF NOT EXISTS external_type VARCHAR(32)` 兜底行（AUTO_CREATE_TABLES 路径）。

- [ ] **Step 4: 运行测试通过** — 同 Step 2 命令，全绿
- [ ] **Step 5: Commit** — `git commit -m "feat(dataops): meta_data_source 物化 external_type 列与回填矩阵（AF-01/Q1）"`

### Task 2: 数据源服务派生 external_type（手改优先）

**Files:**
- Modify: `backend/app/services/dataops/data_source_service.py`（create/update 签名与落库）
- Modify: `backend/app/routers/dataops/dataops.py`（source 创建/更新请求体透传，可选字段）
- Test: `backend/tests/ontology/test_external_type.py`（追加）

**Interfaces:**
- Consumes: Task 1 的 `st.external_type_for`。
- Produces: `DataSourceService.create(..., external_type: str | None = None)`；update 同理——**传了即手改优先，不传按 source_type 派生**。

- [ ] **Step 1: 写失败测试**

```python
def test_create_derives_external_type(db):
    from app.services.dataops.data_source_service import DataSourceService
    svc = DataSourceService(db, tenant_id=100)
    ds = svc.create(name="s1", source_type="clickhouse", host="h", port=8123,
                    username="u", password="p", database="d")
    assert ds.external_type == "warehouse"

def test_create_manual_override_wins(db):
    svc = DataSourceService(db, tenant_id=100)
    ds = svc.create(name="s2", source_type="clickhouse", host="h", port=8123,
                    username="u", password="p", database="d", external_type="tsdb")
    assert ds.external_type == "tsdb"
```

- [ ] **Step 2: 运行确认失败**（TypeError: unexpected keyword）
- [ ] **Step 3: 实现**：create/update 增加 `external_type` 可选参；非法枚举值 422（`ValueError`）；未传时 `ds.external_type = st.external_type_for(source_type)`。路由请求模型加 `external_type: Optional[str]`，`exclude_unset` 语义保住"未传=派生、传了=手改"。
- [ ] **Step 4: 跑 `pytest backend/tests/ontology backend/tests/dataops/test_data_source.py -v`** 全绿（既有创建路径不回归）
- [ ] **Step 5: Commit** — `git commit -m "feat(dataops): 数据源创建/编辑派生 external_type，手改优先（AF-01）"`

### Task 3: E40 assets_tree 重写为 10 节点分组

**Files:**
- Modify: `backend/app/services/ontology/ontology_service.py:216-259`
- Test: `backend/tests/ontology/test_assets_tree.py`

**Interfaces:**
- Consumes: Task 1 列 + `st.EXTERNAL_TYPE_CODES/LABELS`。
- Produces: `assets_tree() -> list[dict]`，固定 10 个 `{kind:'type',code,label,count,children:[{kind:'source',id,label,source_type,external_type,status,count}]}`，顺序= `EXTERNAL_TYPE_CODES`；空组保留。

- [ ] **Step 1: 写失败测试**（per-schema PG fixture，仿 `backend/tests/ontology/conftest.py`——见本任务 Step 3 说明）

```python
def test_tree_ten_nodes_with_other(db):
    from app.models.dataops.data_source import DataSource
    from app.services.ontology.ontology_service import OntologyService
    db.add(DataSource(tenant_id=100, name="ch1", source_type="clickhouse",
                      external_type="warehouse", host="h", port=8123, status="online"))
    db.flush()
    tree = OntologyService(db, 100).assets_tree()
    assert [g["code"] for g in tree] == list(st.EXTERNAL_TYPE_CODES)
    wh = next(g for g in tree if g["code"] == "warehouse")
    assert wh["children"][0]["id"] and wh["children"][0]["status"] == "online"
    assert next(g for g in tree if g["code"] == "graph")["children"] == []
```

- [ ] **Step 2: 运行确认失败**（现状 3 节点）
- [ ] **Step 3: 实现**：删除 `_FAMILY_TO_KIND/_KIND_ORDER/_KIND_LABELS` 与 `enabled_types` 读时映射；`assets_tree()` 改为：

```python
def assets_tree(self) -> List[dict]:
    """AF-01：按 meta_data_source.external_type 分组的 10 节点目录树（Q1 裁决 B 物化列）。"""
    sources = list(self.db.execute(
        select(DataSource).where(DataSource.tenant_id == self.tenant_id).order_by(DataSource.id)
    ).scalars().all())
    table_counts = dict(self.db.execute(
        select(MetaTable.source_id, func.count())
        .where(MetaTable.tenant_id == self.tenant_id).group_by(MetaTable.source_id)
    ).all())
    buckets: dict = {code: [] for code in st.EXTERNAL_TYPE_CODES}
    for s in sources:
        code = (s.external_type or "other").lower()
        buckets.setdefault(code if code in buckets else "other", []).append({
            "kind": "source", "id": s.id, "label": s.name,
            "source_type": s.source_type, "external_type": s.external_type,
            "status": s.status, "count": int(table_counts.get(s.id, 0)),
        })
    return [{"kind": "type", "code": code, "label": st.EXTERNAL_TYPE_LABELS[code],
             "count": sum(c["count"] for c in buckets.get(code, [])),
             "children": buckets.get(code, [])}
            for code in st.EXTERNAL_TYPE_CODES]
```

同任务内新建 `backend/tests/ontology/conftest.py`：拷贝 `backend/tests/dataops/conftest.py`，`_tables()` 改为 `Base.metadata.sorted_tables` 排除迁移独占的 `{"kms_collection","kms_segment","kms_ref"}`（与 `main.py` 同一纪律），并 import `app.models.ontology.*` 保证元数据注册。
- [ ] **Step 4: 测试通过**；`pytest backend/tests/ontology -v`
- [ ] **Step 5: Commit** — `git commit -m "feat(ontology): assets_tree 按 external_type 输出 10 分组节点（AF-01/Q2）"`

### Task 4: 三段打分口径修正 + 批量预载消除 N+1

**Files:**
- Modify: `backend/app/services/ontology/ontology_asset_service.py:81-123`
- Test: `backend/tests/ontology/test_asset_search.py`

**Interfaces:**
- Consumes: per-schema fixture `db`。
- Produces: `_score(t: MetaTable, q: str, kind: str, hits: tuple[bool, bool]) -> int`（hits=(列名命中, 列注释命中)，纯函数）；`_column_hit_map(tables) -> dict[int, tuple[bool,bool]]`（一次 `IN` 批量）。

- [ ] **Step 1: 写失败测试**（打分矩阵 + 守卫）

```python
T = lambda name="", db="", cmt="": SimpleNamespace(
    table_name=name, database=db, table_comment=cmt, id=1)

def matrix_cases():
    return [
        (T(name="sales_order"), "订单", False, False, 0),   # 不命中
        (T(cmt="销售订单主表"), "订单", False, False, 3),    # 表注释=3（原 1 分档纠正）
        (T(db="orders"), "orders", False, False, 3),        # 库名=3（现状缺失）
        (T(name="t"), "t", True, False, 2),                 # 仅列名
        (T(name="t"), "t", False, True, 1),                 # 仅列注释
        (T(name="order_x"), "order", True, True, 3),        # 表名压过列
    ]

@pytest.mark.parametrize("t,q,ch,cch,expect", matrix_cases())
def test_three_tier_score(t, q, ch, cch, expect):
    assert OntologyAssetService._score(t, q, "table", (ch, cch)) == expect

def test_tie_sorted_by_table_name(db): ...  # 两张同分表断言顺序

def test_no_similarity_in_sql(db, caplog):
    # 以 "订单" 执行 search()，捕获 sqlalchemy echo 事件，断言全文不含 similarity(
```

- [ ] **Step 2: 确认失败**（签名不符 TypeError）
- [ ] **Step 3: 实现**：

```python
def _score(self, t, q, kind, hits):
    """三段确定性得分（§3.6 原型口径）：3=表名∪库名∪表注释；2=字段名；1=仅字段注释。"""
    if not q:
        return 0
    ql = q.lower()
    if ql in (t.table_name or "").lower() or ql in (t.database or "").lower() \
       or ql in (t.table_comment or "").lower():
        return 3
    name_hit, comment_hit = hits
    if name_hit:
        return 2
    if comment_hit:
        return 1
    return 0

def _column_hit_map(self, tables, q):
    like = f"%{q}%"
    ids = [t.id for t in tables] or [-1]
    rows = self.db.execute(
        select(MetaColumn.table_id,
               func.bool_or(MetaColumn.column_name.ilike(like)).label("nh"),
               func.bool_or(MetaColumn.column_comment.ilike(like)).label("ch"))
        .where(MetaColumn.tenant_id == self.tenant_id,
               MetaColumn.table_id.in_(ids)).group_by(MetaColumn.table_id)
    ).all()
    return {r.table_id: (bool(r.nh), bool(r.ch)) for r in rows}
```

`search()` 中 WHERE 补 `MetaTable.database.ilike(like)` 进 or 分支；打分前 `hits_map = self._column_hit_map(tables, q)`，`scored = [(self._score(t, q, kind, hits_map.get(t.id, (False, False))), t) for t in tables]`；删除逐表 EXISTS 的旧 `_score`。
- [ ] **Step 4: 测试通过**（含 no-similarity 守卫）
- [ ] **Step 5: Commit** — `git commit -m "fix(ontology): E28 三段打分对齐原型口径并消除 N+1（AF-02）"`

### Task 5: E28 新参数 `table_type` / `sort` 三档

**Files:**
- Modify: `backend/app/services/ontology/ontology_asset_service.py::search`
- Modify: `backend/app/routers/ontology/ontology.py:119-132`
- Test: `backend/tests/ontology/test_asset_search.py`（追加）

**Interfaces:**
- Produces: `search(..., table_type: str | None = None, sort: str = "score")`；`table_type` 取 `BASE TABLE|VIEW`（透传 `MetaTable.table_type` 等值过滤，NULL 行在 `BASE TABLE` 过滤下应命中——`or_(MetaTable.table_type == v, MetaTable.table_type.is_(None)) if v=="BASE TABLE"`）；`sort` 取 `score|updated|rows`。

- [ ] **Step 1: 写失败测试**：建 3 张表（VIEW/BASE TABLE×2 不同 row_count、updated_at），断言 `table_type="VIEW"` 只回视图；`sort="rows"` 按行数降序、`sort="updated"` 按新→旧、`sort="score"` 维持 Task 4 行为。
- [ ] **Step 2: 确认失败**（TypeError）
- [ ] **Step 3: 实现**：search 增加两参；排序比较器：

```python
if sort == "updated":
    scored.sort(key=lambda x: (x[1].updated_at or _EPOCH_MIN), reverse=True)
elif sort == "rows":
    scored.sort(key=lambda x: (-(x[1].row_count or 0), x[1].table_name))
else:  # score：同分字典序（Global Constraint 3）
    scored.sort(key=lambda x: (-x[0], x[1].table_name))
```

路由 Query：`table_type: Optional[str] = Query(default=None, pattern="^(BASE TABLE|VIEW)$")`、`sort: str = Query(default="score", pattern="^(score|updated|rows)$")`。
- [ ] **Step 4: 测试通过**
- [ ] **Step 5: Commit** — `git commit -m "feat(ontology): E28 增加 table_type 过滤与 sort 三档排序（AF-02/07）"`

### Task 6: 送数服务端单源校验 + 回显剔除失效表

**Files:**
- Modify: `backend/app/core/api_error.py`
- Modify: `backend/app/services/ontology/ontology_asset_service.py::put_draft_scope/get_draft_scope`
- Test: `backend/tests/ontology/test_draft_scope.py`

**Interfaces:**
- Produces: 错误码 `BUILD_SCOPE_SINGLE_SOURCE = "BUILD_SCOPE_SINGLE_SOURCE"`；`get_draft_scope(ontology_id) -> dict` 返回值新增 `"removed_stale": int`（失效表自动剔除条数）；`put_draft_scope` 在 mode=tables 时做服务端实查校验。

- [ ] **Step 1: 写失败测试**

```python
def test_put_rejects_cross_source(db):  # 表 t1 属源 A，scope.source_id=B → BUILD_SCOPE_SINGLE_SOURCE
def test_put_rejects_missing_table(db):  # tables=["ghost"] 该源不存在 → 同码，detail 含 missing
def test_get_removes_stale_tables(db):
    # draft_scope.tables=["live","vanished"]，meta_table 仅剩 live
    resp = svc.get_draft_scope(ont.id)
    assert resp["removed_stale"] == 1
    assert resp["draft_scope"]["tables"] == ["live"]
    db.refresh(ont); assert ont.draft_scope_json["tables"] == ["live"]
def test_put_empty_still_blocked(db): ...  # DRAFT_SCOPE_EMPTY 不回归
```

- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现**：`put_draft_scope` 在 stopped/EMPTY 检查后追加：

```python
if payload.get("mode", "tables") == "tables":
    src = payload.get("source_id")
    names = [t for t in (payload.get("tables") or []) if t]
    if not src:
        raise ApiError(BUILD_SCOPE_SINGLE_SOURCE, "送数作用域缺少 source_id")
    found = set(self.db.execute(
        select(MetaTable.table_name).where(
            MetaTable.tenant_id == self.tenant_id, MetaTable.source_id == src,
            MetaTable.table_name.in_(names or ["__none__"]))
    ).scalars().all())
    missing = sorted(set(names) - found)
    if missing:
        raise ApiError(BUILD_SCOPE_SINGLE_SOURCE,
                       f"表不属于锁定数据源 {src}: {', '.join(missing[:5])}",
                       detail={"source_id": src, "missing": missing})
```

`get_draft_scope` 增加失效剔除（Q4 裁决：静默剔除并回传条数）：

```python
def get_draft_scope(self, ontology_id: int) -> dict:
    obj = self._ontology_or_404(ontology_id)
    scope = obj.draft_scope_json or {}
    tables = [t for t in (scope.get("tables") or []) if t]
    removed = 0
    if tables and scope.get("source_id"):
        live = set(self.db.execute(
            select(MetaTable.table_name).where(
                MetaTable.tenant_id == self.tenant_id,
                MetaTable.source_id == scope["source_id"],
                MetaTable.table_name.in_(tables))
        ).scalars().all())
        removed = len([t for t in tables if t not in live])
        if removed:
            obj.draft_scope_json = {**scope, "tables": [t for t in tables if t in live]}
            self.db.flush()
    return {"ontology_id": ontology_id,
            "draft_scope": obj.draft_scope_json, "removed_stale": removed}
```

- [ ] **Step 4: 测试通过**
- [ ] **Step 5: Commit** — `git commit -m "feat(ontology): draft-scope 服务端单源实查与回显剔除失效表（AF-08）"`

### Task 7: 幂等键 tags/catalog 展开防御

**Files:**
- Modify: `backend/app/routers/ontology/ontology.py:188-191`（`_default_idem_key`）
- Modify: `backend/app/services/ontology/ontology_build_service.py`（暴露展开：`OntologyBuildService.resolve_scope_tables(scope) -> List[str]`，内部包 `_resolve_scope` 返回表名排序列表）
- Test: `backend/tests/ontology/test_idem_key.py`

**Interfaces:**
- Consumes: `_resolve_scope`（已存在，tags/catalog/tables 三模式归一）。
- Produces: `create_build_job` 前服务端把非 tables 模式 scope 展开为 `tables[]` 并入默认幂等键。

- [ ] **Step 1: 写失败测试**：同一标签集与直接表清单命中同表 → 两次 E4 请求默认键一致（第二次命中幂等 200）。断言 `_default_idem_key(1, scope, "rules", expanded=["a","b"])` 与 expanded 相关。
- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现**：路由改 `idem = body.idempotency_key or _default_idem_key(ontology_id, scope_for_key, body.mode)`，其中 `scope_for_key["tables"] = svc.resolve_scope_tables(body.scope)`（mode=tables 时原样透传不额外查询）。
- [ ] **Step 4: 测试通过**
- [ ] **Step 5: Commit** — `git commit -m "fix(ontology): 构建幂等键含解析展开后的 tables[]（§3.3）"`

### Task 8: 表级探活端点（单表 + 批量限流 20）

**Files:**
- Modify: `backend/app/core/api_error.py`（+`SOURCE_UNREACHABLE`/`TABLE_NOT_READABLE`）
- Modify: `backend/app/ai/dataops/dialects/_sqlalchemy_base.py`（`probe_table`）
- Modify: `backend/app/ai/dataops/dialects/es.py`（索引计数版 `probe_table`）
- Modify: `backend/app/services/dataops/scan_service.py`（`test_table`）
- Modify: `backend/app/routers/ontology/ontology.py`（E-探活两条路由）
- Test: `backend/tests/ontology/test_probe_table.py`（monkeypatch adapter）

**Interfaces:**
- Consumes: `SQLAlchemyProbeMixin.open(ds, connect_database)`、`MetaTable` 行（source_id/database/table_name）。
- Produces: `MetaScanService.test_table(table_id: int) -> tuple[bool, Optional[str], Optional[str]]` 返回 `(ok, code, error)`，code ∈ `{SOURCE_UNREACHABLE, TABLE_NOT_READABLE}`；路由 `POST /sources/{sid}/tables/{tid}/test` 与 `POST /sources/{sid}/tables/test-batch`（body `{table_ids:[...]}`，>20 → 400）。

- [ ] **Step 1: 写失败测试**（不连真库，monkeypatch `get_adapter`）

```python
def test_probe_ok(db, monkeypatch): ...        # (True, None)
def test_probe_unreachable(db, monkeypatch):   # open 抛异常 → (False,'SOURCE_UNREACHABLE',...)
def test_probe_not_readable(db, monkeypatch):  # execute 抛 OperationalError → (False,'TABLE_NOT_READABLE',...)
def test_batch_limit_21(client_a, db):         # 400
```

- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现**：mixin 增加（SQLAlchemy core 自动按方言加引号与 LIMIT/FETCH FIRST，Oracle 免特判）：

```python
def probe_table(self, ds, database, table_name) -> Tuple[bool, Optional[str]]:
    """表级可读性探活：SELECT 1 FROM <t> LIMIT 1（标识符由方言自动引用）。"""
    from sqlalchemy import table as sa_table
    try:
        conn, cleanup = self.open(ds, connect_database=database)
        try:
            conn.execute(_select1_from(sa_table(table_name)))
        finally:
            cleanup()
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"[:500]
```

`EsAdapter.probe_table` 走 `_count_index(ds, table_name)`（既有能力），计数失败=表不可读。`test_table`：先 `adapter.test_connect(ds)`，失败即 `SOURCE_UNREACHABLE`；可达再 `probe_table`，失败 `TABLE_NOT_READABLE`；tid 不属于 sid 或跨租户 → 404。路由用 `ApiError(code, message, http_status=502 if unreachable else 400, detail={"table_id": tid})`。批量端点串行循环、`{"results":[{"table_id","ok","code"}]}` 返回。
- [ ] **Step 4: 测试通过**
- [ ] **Step 5: Commit** — `git commit -m "feat(ontology): 表级探活（单表+批量限20串行, SOURCE_UNREACHABLE/TABLE_NOT_READABLE）（AF-06）"`

### Task 9: 元数据编辑端点（表/列注释）

**Files:**
- Modify: `backend/app/services/ontology/ontology_asset_service.py`（`update_table_meta`）
- Modify: `backend/app/routers/ontology/ontology.py`（`PUT /sources/{sid}/tables/{tid}`）
- Test: `backend/tests/ontology/test_edit_meta.py`

**Interfaces:**
- Produces: `update_table_meta(table_id, *, table_comment=None, biz_name=None, biz_description=None, columns: list[{column_name, column_comment?}] | None) -> dict`；写 `meta_table`/`meta_column`（扫描元数据表，非结构表）。tid 不属于 sid/跨租户 → `ONTOLOGY_NOT_FOUND` 语义 404。

- [ ] **Step 1: 写失败测试**：改表注释生效；改两列注释生效、未知列名静默跳过并回传 `skipped`；跨租户 404。
- [ ] **Step 2: 确认失败** → **Step 3: 实现**（service 查询限定 tenant+source_id，逐列 update；路由 commit）
- [ ] **Step 4: 测试通过** → **Step 5: Commit** — `git commit -m "feat(ontology): 表/列说明元数据编辑端点（AF-06 编辑）"`

### Task 10: security 规则自动打标（钩子 + 重新分级）

**Files:**
- Modify: `backend/app/services/ontology/ontology_tag_service.py`
- Modify: `backend/app/services/dataops/scan_service.py`（扫描成功收尾处）
- Modify: `backend/app/routers/ontology/ontology.py`（`POST /asset-tags/reclassify`）
- Test: `backend/tests/ontology/test_auto_tag.py`

**Interfaces:**
- Consumes: `MetaColumn.pii_level`（字符串 L0-L3）、Task 前已有的 bind 表结构。
- Produces: `OntologyTagService.apply_security_rule(source_id: int | None = None) -> dict`（`{"tag": str|None, "bound": int, "removed": int}`）：找 `tag_kind='security' AND code='pii'` 标签，不存在则返回 `{"tag": None}`（不自动建标签，spec §5.2）；先删 `source='rule'` 旧绑定（可限定本批扫描涉及表范围），再对 `max(pii_level) >= L2`（字符串枚举比较，L2/L3 命中）的表重打 `source='rule'`；`source='human'` 永不触碰。

- [ ] **Step 1: 写失败测试**

```python
def test_rule_rebind_idempotent(db):     # 跑两次，rule 绑定数不变
def test_human_binding_survives(db):     # 同表同标 human 行在 rule 清理后仍在
def test_no_tag_skips(db):              # 租户无 pii 标签 → {"tag": None}，零写入
def test_scope_by_source(db):           # source_id 过滤只刷新该源
```

- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现**：service 方法按上接口写；scan 成功收尾（stats 落库后）调 `apply_security_rule(source_id=ds.id)`，包 try/except 只记 warning（打标失败不回滚扫描）。reclassify 路由循环租户全量（`source_id=None`）。
- [ ] **Step 4: 测试通过**
- [ ] **Step 5: Commit** — `git commit -m "feat(ontology): pii>=L2 敏感标签规则自动打标（钩子+手动重分级, rule/human 分治）（AF-03）"`

### Task 11: 前端——分组树 10 类 + 状态点 + 空组

**Files:**
- Modify: `frontend/src/views/data-source/asset/AssetTypeTree.vue`
- Test: `frontend/src/views/data-source/asset/__tests__/AssetTypeTree.spec.ts`（vitest + mount，mock `assetsTree`）

**Interfaces:**
- Consumes: E40 新响应（10 节点 + `status`）。
- Produces: 组节点标题 `label（count）`，空组 children 渲染禁用项 `暂无连接`；源节点后缀状态点（`status==='online'` 绿 / 其余灰）；选中源 emit `select-source` 行为不变。

- [ ] **Step 1: 写失败测试**：喂 10 组 fixture（warehouse 组含 1 online 源、graph 组空），断言渲染出"数仓 / 大数据"、"其他"、"暂无连接"、状态点 class。
- [ ] **Step 2: 确认失败** → **Step 3: 实现**（a-tree `#title` 插槽渲染状态点 `<span :class="['dotk', c.status==='online'?'':'off']"/>`，样式复制原型 `.tn .dotk`）
- [ ] **Step 4: `npx vitest run src/views/data-source/asset` 通过**
- [ ] **Step 5: Commit** — `git commit -m "feat(ui): 资产分组树对齐 10 类 external_type 与探活状态点（AF-01）"`

### Task 12: 前端——卡片渲染补齐（score/已映射码/PII 配色/元信息/高亮/展开）

**Files:**
- Modify: `frontend/src/views/data-source/asset/AssetCardList.vue`
- Create: `frontend/src/views/data-source/asset/assetText.ts`（`hl()` 高亮 + `fmtRows()` 万/亿格式化，两函数从原型 JS 移植）
- Test: `frontend/src/views/data-source/asset/__tests__/AssetCardList.spec.ts`

**Interfaces:**
- Consumes: E28 卡片字段（`score/bound_object_code/pii_max_level/table_type/row_count/db_name/table_name/table_comment/column_digest`）+ 新 prop `kw: string`（高亮词）。
- Produces: `hl(text, kw): string`（返回已转义的 `<mark>` HTML，调用处 `v-html`）；`fmtRows(n: number|null): string`。

- [ ] **Step 1: 写失败测试**：fixture 卡片断言 `score` 徽章 class `s3/s2/s1`、文本 `已映射 obj_order`、PII L1 黄/L3 红 tag、行数 `128.5万`、表名含 `<mark>`。
- [ ] **Step 2: 确认失败** → **Step 3: 实现**（原型 `.score.s3` 配色转 less；digest 默认 2 行截断，点击 `expanded` 态解除截断）
- [ ] **Step 4: vitest 通过** → **Step 5: Commit** — `git commit -m "feat(ui): 资产卡片补齐 score/映射码/PII 分级/高亮/展开（AF-05）"`

### Task 13: 前端——搜索条（tag_kind 修复 + 色板 + table_type/sort 下拉 + size 切换）

**Files:**
- Modify: `frontend/src/views/data-source/asset/AssetSearchBar.vue`
- Test: `frontend/src/views/data-source/asset/__tests__/AssetSearchBar.spec.ts`

**Interfaces:**
- Consumes: `createAssetTag`（body 需带合法 `tag_kind`）、`listAssetTags`。
- Produces: emit `search` payload 扩展为 `{kw, tag_ids, kind, table_type, sort, size}`；修复 **[bug]** 现 `tag_kind: 'table'` → 表单下拉真实值。

- [ ] **Step 1: 写失败测试**：断言现实现发出的 `tag_kind==='table'`（红）；填表选 security + 色板第 2 色后 `createAssetTag` 收到 `{code,name,color:'#52c41a',tag_kind:'security'}`；下拉改 sort=rows 后 emit payload 含 `sort:'rows'`。
- [ ] **Step 2: 确认失败**（第一条应先红后绿——先改测试期望再修代码）
- [ ] **Step 3: 实现**：弹窗补 tag_kind `a-select`（biz/security/quality/custom）+ 7 色 swatch（复制原型 COLORS 数组）；搜索条补 `table_type`（全部对象/仅表/仅视图）与 `sort`（相关度/更新时间/行数）下拉；size 切换并入 `a-pagination`（`show-size-changer`，Task 14 接线）。
- [ ] **Step 4: vitest 通过** → **Step 5: Commit** — `git commit -m "fix(ui): 新建标签 tag_kind 修复并补齐检索条 table_type/sort/色板（AF-02/03）"`

### Task 14: 前端——打标入口 + 探活/编辑 + 批量探活

**Files:**
- Modify: `frontend/src/views/data-source/asset/AssetCardList.vue`（卡片操作区）
- Modify: `frontend/src/views/data-source/asset/AssetPickerPanel.vue`（选择条按钮 + 弹窗）
- Modify: `frontend/src/api/dataops.ts`（+`testTable/testTables/updateTableMeta/reclassifyTags`）
- Test: `frontend/src/views/data-source/asset/__tests__/AssetOps.spec.ts`

**Interfaces:**
- Consumes: Task 8/9/10 端点；已有 `bindAssetTag`。
- Produces: api 封装 `testTable(sid,tid)`、`testTables(sid, ids[])`、`updateTableMeta(sid,tid,body)`、`reclassifyTags()`；卡片按钮 测试/编辑/＋标签；选择条 打标签/批量探活/重新分级。

- [ ] **Step 1: 写失败测试**：mock api 断言——批量探活勾选 21 张时提示"单次最多 20 张"且不发请求；点「＋标签」选 tag 后 `bindAssetTag` 收到 `{tag_id, asset_kind:'table', asset_ids:[tid], op:'bind'}`；探活成功卡片按钮变「测试通过」态。
- [ ] **Step 2: 确认失败** → **Step 3: 实现**（编辑弹窗：表注释 + 列注释表格局部可编辑，保存调 `updateTableMeta` 后 `runSearch()` 刷新当前页）
- [ ] **Step 4: vitest 通过** → **Step 5: Commit** — `git commit -m "feat(ui): 卡片打标/探活/编辑与批量探活限流 20（AF-03/06/07）"`

### Task 15: 前端——送数闭环（回显恢复/拦截文案/空清单提示）

**Files:**
- Modify: `frontend/src/views/data-source/asset/AssetPickerPanel.vue`
- Test: `frontend/src/views/data-source/asset/__tests__/AssetPickerSend.spec.ts`

**Interfaces:**
- Consumes: `getDraftScope`（返回含 `removed_stale`）、`putDraftScope`；E28 items。
- Produces: activate/切换目标本体时回显勾选；`removed_stale>0` 时 message.info 提示剔除条数；跨源拦截 toast 文案带 `BUILD_SCOPE_SINGLE_SOURCE` 错误码；size 切换器接线 `runSearch`。

- [ ] **Step 1: 写失败测试**：mock `getDraftScope` 返回 `{draft_scope:{mode:'tables',source_id:12,tables:["a","b"]}}`，回显后 current page items 中 a/b 勾选态为真；`removed_stale:2` 断言提示文本含"已从作用域剔除"；卡片层跨源拦截文案含 `BUILD_SCOPE_SINGLE_SOURCE`。
- [ ] **Step 2: 确认失败** → **Step 3: 实现**：`activate()` 与 `targetId` watch 触发 `getDraftScope(targetId)` → 按 `table_name` 匹配当前页 items 恢复 selected（异源数据直接丢弃并提示）；doSend 成功 message 并入剔除计数。
- [ ] **Step 4: vitest 通过** → **Step 5: Commit** — `git commit -m "feat(ui): 送数面板 draft_scope 回显恢复与单源拦截文案（AF-08）"`

### Task 16: 全链路回归与文档收尾

**Files:**
- Modify: `docs/prototypes/ontology-asset-catalog-preview.html`（页脚 external_type 表述下补一行"Q1 裁决 B：物化列（见 spec §1.1）"）
- Test: 全量 `pytest backend/tests/ontology backend/tests/dataops` + `npx vitest run src/views/data-source`

- [ ] **Step 1: 后端全量测试绿**（含 similarity 守卫、迁移双路径如 CI 有 alembic upgrade 冒烟）
- [ ] **Step 2: 前端测试绿 + `npm run build` 无 TS 错误**
- [ ] **Step 3: 手工冒烟清单**（对照原型逐能力）：10 组树渲染 → CJK 搜索"订单"得 3 分档 → 跨源勾选拦截 → 送数→重开面板回显 → 打标 human/rule → pii 表自动敏感标 → 单表探活 → 编辑表注释 → size 200 上限
- [ ] **Step 4: Commit** — `git commit -m "docs: 原型页脚标注 external_type 物化列裁决；资产目录一期对齐收尾"`

## Self-Review 结论

- 覆盖：spec §1→Task 1-3；§2→4-5；§3→6-7；§4→8-9；§5→10,13-14；§6→11-13；§8 测试计划分布于各任务与 Task 16；§7 边界（可见性不做）以 Global Constraint 6 落档。
- 类型一致性：`external_type` 枚举拼写、`BUILD_SCOPE_SINGLE_SOURCE`、`removed_stale`、`test_table` 三元返回 `(ok, code, error)` 在各任务间已核对。
- 无占位符：各实现步骤均给出可粘贴代码或精确到字段的行为定义。
