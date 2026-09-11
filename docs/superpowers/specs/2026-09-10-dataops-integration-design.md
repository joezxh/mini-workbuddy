# P2 · 业务数据集成与处理（移植 ontomind DataOps）设计

> 状态：待评审
> 日期：2026-09-10
> 目标项目：MinWorkBuddy（风险管控系统，FastAPI + PostgreSQL17/pgvector + Neo4j + AgentScope 2.x）
> 前端（管理台）设计：见 `2026-09-10-knowledge-governance-frontend-design.md` §7（菜单项：知识治理 → 数据源）
> 参考实现：`d:\projects\github\ontomind`（`backend/app/services/dataops_*.py`、`meta_*_service.py`、`db/models/{data_source,meta}_model.py`、`api/v1/dataops.py`）

---

## 1. 背景与目标

MinWorkBuddy 目前缺少"企业业务数据接入与元数据治理"能力：

- 现有 `app/ai/knowledge/` 只有 `WikiRAGIngestor`（文章级）与 `PGVectorStore`（给已有业务表挂向量列），没有面向**外部数据源**的接入、扫描、画像能力
- 现有 `WikiOwlEngine` 是**进程内内存单例**（`routers/wiki/wiki_owl.py` 的 `_owl_engine` 全局变量），本体无持久化、无租户隔离
- 本体构建缺少"业务语义来源"：没有表/列画像、没有主外键候选、没有字段↔标准绑定

本子项目把 ontomind 的 DataOps 能力移植进来，作为**本体构建与知识库的原料供给层**。

**目标（按用户确认的 5 项）**：
1. 数据源管理（CRUD + 探活）
2. 元数据扫描（库/表/列）
3. 列画像（Column Profiling）
4. 元数据标准绑定
5. SQL 执行/取样（读写分离 + 审批）

---

## 2. 范围

### 2.1 包含

- 数据源连接管理、探活、库/表/列导航
- 元数据扫描任务（异步、带进度、幂等）
- 列画像（null_rate / distinct_ratio / min-max / Top-K 值分布）
- 列重叠率（用于推测可关联字段 → 本体关系类型候选）
- 元数据标准项（含版本快照）+ 字段↔标准绑定（含变更审计）
- 只读 SQL 执行 + 取样
- 写操作：申请 → 批准 → 一次性令牌执行（全链路审计）
- 方言无关连接器抽象，首批实装 MySQL / Doris / PostgreSQL
- 暴露为 AgentScope 2.x Tool

### 2.2 不包含（明确排除）

| 排除项 | 原因 |
|---|---|
| `annotations` 独立标注表 | 与 `meta_column` 的 `biz_name/semantic_type/pii_level` 双重存储；评审语义已由 `meta_column_standard.status/source/evidence_json` 覆盖 |
| `glossary_terms` 业务术语表 | 不在本次 5 项范围；`meta_standard.aliases_json` 已能做别名匹配 |
| `meta_database_briefs` 库级智能概况 | 属 LLM 增值功能，后续单独立项 |
| `platform_llm_settings` | MinWorkBuddy 已有自己的模型配置体系 |
| 数据同步/ETL/调度 | 本子项目只做元数据与只读访问，不做数据搬运 |
| 本体构建本身 | 属 P4；本子项目只产出原料与导出接口 |

### 2.3 前置假设

- MinWorkBuddy 已有异步任务设施（`app/services/sys/async_task_service.py`、`models/agent/agent_async_task.py`）
- MinWorkBuddy 已有审计中间件（`app/middleware/audit_logger.py`）
- 数据库为 PostgreSQL 17，新表需同步 `docs/sql/init.sql` 并在 `app/db/init_models.py` 注册

---

## 3. 参考实现分析（ontomind）

### 3.1 可复用的算法语义

| 能力 | ontomind 实现 | 移植决策 |
|---|---|---|
| `profile_column` | 采样 100–50000 行 → `total/non_null/distinct_count/min/max`；非数值型额外算 Top10 值分布 | **保留语义，重写 SQL** |
| `overlap_ratio` | 两列去重值集合的重叠比例 → 推测主外键 | **保留语义，重写 SQL** |
| `sample` / `execute` | 单条 SQL、`max_rows ≤ 1000`、禁多语句 | **保留语义，大幅加固** |
| 扫描任务 | `meta_scan_jobs` 带 `progress / stats_json / duration_ms` | **保留结构** |
| 标准绑定链 | `meta_standards` + `versions` + `meta_column_standards` + `history` | **完整保留** |

### 3.2 必须修正的缺陷

| 缺陷 | ontomind 现状 | 本设计处理 |
|---|---|---|
| 密码明文 | `DataSource.password = Column(Text)` | 改 `password_enc`，Fernet 加密 |
| 无租户隔离 | 全部 10 张表无 `tenant_id` | 全部继承 `TenantMixin` |
| SQL 方言耦合 | `SHOW DATABASES`、反引号 `` ` ``、MySQL 专有 `information_schema` 列 | 方言适配器 + `identifier_preparer.quote()` |
| SQL 执行不设防 | 仅禁多语句，`DROP/DELETE/UPDATE` 无拦截，无超时、无审计 | 三层校验 + 只读事务 + 审批链 |
| 无容量上限 | 无 | 扫描上限 + profile 采样上限 |

---

## 4. 架构

```
┌────────────────────────────────────────────────────────────┐
│ API 层  /api/v1/dataops/*                                   │
│   sources · scans · standards · query · write-requests      │
└──────────────┬─────────────────────────────────────────────┘
               │
┌──────────────▼─────────────────────────────────────────────┐
│ 服务层                                                       │
│   DataOpsService        数据源 CRUD / 探活 / 库表列导航        │
│   MetaScanService       扫描编排（异步 + 进度 + 限流 + 幂等）   │
│   MetaStandardService   标准项 / 绑定 / 版本 / 历史            │
│   SqlExecutor           只读执行 / 写操作审批链                │
└──────────────┬─────────────────────────────────────────────┘
               │
┌──────────────▼─────────────────────────────────────────────┐
│ 连接器层（方言无关）                                          │
│   DialectAdapter 协议                                        │
│     list_databases / list_tables / list_columns              │
│     profile_column / overlap_ratio / sample_rows / dry_run   │
│   MySQLAdapter · DorisAdapter · PostgresAdapter              │
│   ConnectionPool：read 池 / write 池（分离）                  │
└────────────────────────────────────────────────────────────┘
```

**分层原则**：服务层不感知方言；新增数据源类型只需加一个 `DialectAdapter` 实现，不动上层。

---

## 5. 数据模型

全部继承 `TenantMixin`（`tenant_id BigInteger nullable index`），遵循 MinWorkBuddy 现有约定：
`Base` 来自 `app.db.database`、审计列为 `creator_id/updater_id/created_at/updated_at`、
状态用 `String(32)` + `comment` 或 `Integer` + `comment`（**不用 SAEnum**，避免 PG ENUM 类型变更困难）、
`__table_args__` 具名索引、表名单数。

### 5.1 `data_source` — 数据源连接

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | BigInteger PK | |
| `name` | String(128) unique | 显示名称 |
| `source_type` | String(32) | `mysql` / `doris` / `postgresql` |
| `host` / `port` | String(256) / Integer | |
| `username` | String(128) | |
| `password_enc` | Text | Fernet 密文；API 永不返回，仅回 `has_password: bool` |
| `database` | String(128) | 默认库 |
| `charset` | String(32) default `utf8mb4` | |
| `status` | String(32) default `unknown` | `unknown`/`online`/`offline` |
| `is_default` | Boolean default false | |

### 5.2 `meta_scan_job` — 扫描任务

`source_id(FK) · database · job_kind(scan/profile) · status(pending/running/succeeded/failed) · progress(Float) · with_profile(Boolean) · tables_json(JSONB) · stats_json(JSONB) · error_detail(Text) · duration_ms(Integer) · started_at · finished_at`

### 5.3 `meta_table` — 表快照

`source_id(FK) · database · table_name · table_type · table_comment · row_count · engine · column_count · biz_name · biz_description · domain · profiled_at`

唯一约束 `uq_meta_table (source_id, database, table_name)` —— **幂等重扫的基础**。

### 5.4 `meta_column` — 列快照

`table_id(FK) · column_name · ordinal · data_type · column_type · nullable · column_key · column_default · extra · column_comment · biz_name · biz_description · semantic_type · pii_level · profile_json(JSONB)`

唯一约束 `uq_meta_column (table_id, column_name)`。
索引：`idx_meta_column_table (table_id)`、`idx_meta_column_semantic (semantic_type)`。

### 5.5 `meta_standard` — 标准项

`code(unique) · name · aliases_json(JSONB) · description · semantic_type · data_type_expect · length_rule_json(JSONB) · security_level(String8, L0–L3) · quality_rule_json(JSONB) · mask_rule · domain · status(draft/published) · current_version(Integer)`

### 5.6 `meta_column_standard` — 字段↔标准绑定

`column_id(unique, 字段侧 1:1) · standard_id(FK RESTRICT) · standard_version · security_level_override · status(suggested/accepted/rejected) · source(rule/llm/human) · confidence(Float) · evidence_json(JSONB) · reviewed_by · reviewed_at`

> `source` 的 `llm` 取值在本阶段保留但**不实现**（智能标注已排除在范围外，见 §2.2）；本阶段实际只会产生 `rule`（按 `aliases_json` / `data_type_expect` 匹配出的建议）与 `human`（人工绑定）。标准绑定的评审语义集中在这张表，替代被砍掉的独立 `annotations` 表。

### 5.7 `data_write_request` — 写操作申请单（新增）

| 列 | 类型 | 说明 |
|---|---|---|
| `source_id` | BigInteger FK | |
| `database` | String(128) | |
| `sql_text` | Text | 申请时提交的原文 |
| `sql_sha256` | String(64) | **审批与执行一致性的锚点** |
| `statement_type` | String(32) | `update`/`delete`/`insert`/`ddl` |
| `impact_json` | JSONB | dry-run 影响预估 |
| `status` | String(32) | `pending`/`approved`/`rejected`/`executed`/`expired` |
| `applicant_id` / `approver_id` | BigInteger | |
| `token_consumed` | Boolean | 防重放 |
| `expires_at` / `executed_at` | TIMESTAMP | |
| `result_json` | JSONB | 执行结果（行数、耗时） |

### 5.8 版本与审计表

- `meta_standard_version`：`standard_id + version` 唯一，`snapshot_json`、`change_note`、`author_user_id`
- `meta_column_standard_history`：`column_id`、`standard_id`、`standard_version`、`action`、`snapshot_json`、`actor_user_id`

---

## 6. 方言无关连接器层

### 6.1 `DialectAdapter` 协议

```python
class DialectAdapter(Protocol):
    name: str                       # 'mysql' | 'doris' | 'postgresql'

    def list_databases(self, conn) -> list[str]: ...
    def list_tables(self, conn, database: str) -> list[TableMeta]: ...
    def list_columns(self, conn, database: str, tables: list[str]) -> dict[str, list[ColumnMeta]]: ...
    def profile_column(self, conn, database: str, table: str, column: str,
                       sample_rows: int) -> ColumnProfile: ...
    def overlap_ratio(self, conn, database: str, left: ColRef, right: ColRef) -> float: ...
    def sample_rows(self, conn, database: str, table: str, limit: int) -> QueryResult: ...
    def dry_run(self, conn, sql: str) -> WriteImpact: ...
```

### 6.2 必须抽象的三处方言差异

| 能力 | MySQL / Doris | PostgreSQL |
|---|---|---|
| 库列表 | `information_schema.SCHEMATA`（替代 `SHOW DATABASES`） | `pg_database WHERE datistemplate = false` |
| 表/列注释 | `information_schema` 自带 `*_COMMENT` 列 | information_schema **无注释**，须 `obj_description()` / `col_description()` 从 `pg_catalog` 取 |
| 标识符引用 | 反引号 `` `col` `` | 双引号 `"col"` |

标识符统一走 `dialect.identifier_preparer.quote()`，**不手写 `_ident()`**。
首批三方言均支持 `LIMIT`，暂不引入 Oracle `ROWNUM`。

### 6.3 画像与重叠率

沿用 ontomind 语义，仅重写 SQL 生成：

- `profile_column`：采样 `100 ≤ sample_rows ≤ 50000` → `total / non_null / distinct_count` → `null_rate`、`distinct_ratio`；数值与日期时间型保留 `min/max`；其余类型改取 Top-10 值分布
- `overlap_ratio`：左列去重采样值中命中右列的比例，**采样估算而非精确值**，仅作为"关系候选"提示，不做强断言

### 6.4 连接池

按 `(source_id, mode)` 缓存，`mode ∈ {read, write}`：

- **read 池**：MySQL/Doris `SET SESSION TRANSACTION READ ONLY`；PG `default_transaction_read_only = on`
- **write 池**：仅 `SqlExecutor` 校验一次性令牌通过后获取，空闲超时即回收

---

## 6A. 业务语义推断（v2 新增）

> v1 遗漏了这一整块。经对比 Qoder 方案与 ontomind 代码，以下三项**不依赖 LLM、成本低、价值高**，且能直接落在 §5 已有表结构上（**不新增表**）。

### 6A.1 规则标注引擎（纯规则，不含 LLM）

新增 `app/services/meta_rule_engine.py`，在扫描时（或按需）为列计算业务语义候选：

| 规则 | 输出 |
|---|---|
| `expand_name_to_biz()` | 缩写词典展开（`amt` → `金额`、`cust` → `客户`…），写 `meta_column.biz_name` |
| `detect_layer_domain()` | 数仓分层识别（`ods_` / `dwd_` / `dws_` / `ads_`），写 `meta_table.domain` |
| `detect_pii_level()` | PII 等级（正则 + 样本验证），写 `meta_column.pii_level` |
| `is_join_key_candidate()` | 连接键识别（`_id` / `_no` 后缀 + 高基数验证），写 `meta_column.semantic_type` |
| `is_entity_table_candidate()` | 实体表识别（单主键 + 非日志表），写 `meta_table.biz_*` 候选 |

产出同时写入 `meta_column_standard`（`source=rule`, `status=suggested`, `confidence=<值>`, `evidence_json=<命中规则>`），与人工绑定共用同一张表，**不新增表**。

> 边界：本阶段**仍不实现 LLM 通道**。规则引擎是纯确定性计算，与 §2.2 排除 LLM 标注的决定不冲突。

### 6A.2 置信度分层（统一阈值，避免实施时各写各的）

```python
CONF_AUTO_ACCEPT = 0.85   # ≥ 自动采纳 → status=accepted
CONF_SUGGEST_MIN = 0.65   # 0.65 ~ 0.85 建议   → status=suggested（需人工评审）
                          # < 0.65      丢弃
```

适用于：规则标注候选、`meta_column_standard` 绑定、P4 本体元素候选。**三处共用同一常量与同一函数**（`confidence_tier()`），不得各模块自定义阈值。

### 6A.3 三方投票关系推断

用于从 P2 的列画像结果推导"哪些列对可关联"，供 P4 的关系类型候选消费。

| 信号 | 权重 | 说明 |
|---|---|---|
| 命名匹配 | 0.4 | 列名 `xxx_id` → 目标表 `xxx` |
| 数据重叠度 | 0.0 – 0.4 | `overlap_ratio()` 实测值 |
| LLM 判断 | 0.0 – 0.2 | **本阶段不实现**（权重记为 0，其余按 0.4+0.4 归一化） |
| **Veto** | — | `overlap_ratio < 0.5` 直接否决，最终分置 0 |

实现为**计算型接口、不落库**：`POST /sources/{id}/relation-candidates` 返回
`[{left, right, name_score, overlap, llm_score, final, vetoed, evidence}]`；
由 P4 决定是否落成 `ontology_link_type`（`status=suggested`）。

> 不落库的理由：候选是元数据派生结果，随重扫变化；落库会产生大量需清理的陈旧候选。

### 6A.4 测试

- 规则引擎：缩写词典、分层识别、PII 检测、连接键识别各有正反用例
- 置信度：0.9 / 0.7 / 0.5 三档分别落到 accepted / suggested / 丢弃
- 关系推断：Veto 生效（overlap=0.3 → final=0）；无 LLM 时权重归一化正确

---

## 7. 安全设计

### 7.1 凭据加密

- 新增独立配置项 `DATAOPS_ENCRYPTION_KEY`
  **不复用** JWT 的 `SECRET_KEY`（其默认值为硬编码的 `your-secret-key-change-this-in-production-min-32-chars`，且密钥混用违反隔离原则）
- 使用 `cryptography.Fernet` 做列级加密，存 `password_enc`
- 未配置 `DATAOPS_ENCRYPTION_KEY` 时服务启动即报错，**拒绝降级为明文**
- API 响应不返回密码，只回 `has_password: bool`

### 7.2 只读执行三层校验

1. **解析层** —— 引入 `sqlglot` 做 AST 解析（正则黑名单不可靠，注释/换行/大小写均可绕过）。
   白名单只放行 `Select / With / Explain / Show / Describe`，以 AST 节点类型判定；
   显式拒绝多语句、DDL/DML、`INTO OUTFILE`、`COPY`、`pg_sleep`。
2. **连接层** —— 只读事务兜底；即使解析被绕过，数据库侧也拒绝写入。
3. **限制层** —— 语句超时（默认 30s，可配）、返回行数上限（≤1000）、单行大小上限。

### 7.3 写操作：申请 → 批准 → 一次性令牌

```
申请人 ──提交──► dry_run 影响预估（EXPLAIN / 行数估算）
        └──────► 落 data_write_request(pending, sql_sha256, impact_json)

管理员 ──批准──► 生成一次性令牌
                Redis: key=token → {request_id, sql_sha256, user_id, exp}

执行时 ──► 校验：令牌存在 && 未消费 && 未过期 && sql_sha256 与申请单一致
        └──► 原子消费（Redis DELETE 返回值判定，防并发重放）→ 才取 write 池执行
```

- `sql_sha256` 绑定堵住"批准一份 SQL、执行另一份"的绕过路径
- 令牌默认有效期 15 分钟，可配
- 全链路写 `audit_logger`
- `dry_run` 实现：DML 用只读连接执行 `EXPLAIN`（MySQL 5.6+ / PG / Doris 均支持 `EXPLAIN UPDATE|DELETE`）取估算行数；`INSERT` 与 DDL 退化为"语句类型 + 目标表行数 + 结构性变更告警"

---

### 7.4 AgentScope Tool 侧权限（v2 新增）

本地 `agentscope 2.0.7.post1` 已内置权限系统：

```
agentscope/permission/
  _engine.py    PermissionEngine.check_permission() / add_rule()
  _rule.py      PermissionRule（allow / deny / ask 三类）
  _types.py     PermissionMode（default / explore / accept_edits / bypass / dont_ask）
  _engine.py    _check_read_only_fast_path（只读快速路径）
```

**采用双轨，且两轨策略必须对齐**：

| 路径 | 机制 |
|---|---|
| REST API（人直接操作 SQL 工作台） | §7.2 只读三层校验 + §7.3 申请-批准-一次性令牌（**自研，保留**） |
| AgentScope Tool（智能体调 `query_readonly` 等） | `PermissionEngine` + `PermissionRule`（**原生复用**） |

**实施要求**：§7.2 的语句白名单（只放行 `Select/With/Explain/Show/Describe`）**同时注册为 `PermissionRule` 的 ask/deny 规则**，一处定义、两处生效。否则会出现"人受限、智能体不受限"的绕过路径。

---

## 8. 任务编排与数据流

```
POST /sources/{id}/scans
  └─► 建 meta_scan_job(pending) → 投递 async_task_service
       ├─ 阶段1  list_databases / list_tables       progress 0 → 30%
       ├─ 阶段2  list_columns（分批，每批 200 表）    progress 30 → 70%
       ├─ 阶段3  profile_column（仅 when with_profile）progress 70 → 100%
       └─ upsert meta_table / meta_column（按唯一键幂等）
       终态 succeeded | failed（error_detail + duration_ms）
```

- 每批 commit 一次，避免长事务
- 失败保留已完成部分，支持断点续扫
- 扫描全程使用 read 池，不可能污染源库
- **容量上限**：单库表数 2000、列数 20000、profile 采样 ≤ 50000 行；超限中止并置 `stats_json.truncated = true`
- `profile_json` 只存画像结果，**不存样本数据**

### 8.1 下游供给（不阻塞本子项目）

暴露 `AssetDescriptor` 导出接口，把表/列转为结构化资产描述（业务名、语义类型、PII 等级、画像摘要、绑定到的标准项）：

- P1（pgvector 知识库）就绪后 → 调 ingest 接口入湖
- P4（本体层）就绪后 → `meta_table` → 对象类型、`meta_column` → 属性、`overlap_ratio` 高的列对 → 关系类型候选

---

## 9. API

前缀 `/api/v1/dataops`，在 `app/core/router_registry.py` 注册。

```
数据源   GET  /sources                        列表（不含密码）
         POST /sources                        创建
         GET  /sources/{id}                   详情
         PUT  /sources/{id}                   更新
         DEL  /sources/{id}                   删除
         POST /sources/test                   探活（返回 latency_ms / server_info）

导航     GET  /sources/{id}/databases
         GET  /sources/{id}/tables?database=
         GET  /sources/{id}/columns?database=&table=

取样     POST /sources/{id}/sample            按表取样（limit ≤ 50）
只读查询  POST /sources/{id}/query             只读 SQL（rows ≤ 1000）

写操作   POST /sources/{id}/write-requests    提交申请（附 dry-run 影响）
         GET  /write-requests                 申请列表（可按 status 过滤）
         POST /write-requests/{id}/approve    管理员批准（生成令牌）
         POST /write-requests/{id}/reject     管理员驳回
         POST /write-requests/{id}/execute    执行（body 带一次性令牌）

扫描     POST /sources/{id}/scans             触发扫描
         GET  /scans/{job_id}                 查询进度与结果

标准     GET  /standards                      标准项列表
         POST /standards                      创建标准项
         GET  /standards/{id}
         PUT  /standards/{id}
         DEL  /standards/{id}
         POST /standards/bind                 单字段绑定
         POST /standards/batch-bind           批量绑定
         DEL  /standards/bindings/{binding_id} 解绑

画像     GET  /columns/{id}/profile           列画像
         POST /columns/overlap                两列重叠率
```

---

## 10. AgentScope 2.x 集成

MinWorkBuddy 已在 AgentScope 2.x 上（`agentscope>=2.0.7,<3.0.0`），本模块把能力注册为 Tool：

| Tool | 能力 | 底层 |
|---|---|---|
| `scan_database` | 触发 / 查询库扫描 | MetaScanService |
| `list_tables` | 查库内表清单 | meta_table |
| `describe_column` | 查字段画像与业务含义 | meta_column |
| `find_join_candidates` | 推测可关联字段 | `overlap_ratio` |
| `lookup_standard` | 查标准项与已绑定字段 | meta_standard |
| `query_readonly` | 只读查数 | SqlExecutor |

**约束**：`query_readonly` 必须走与人工操作**完全相同**的校验链（解析层 + 只读池 + 限制层 + 审计），不因调用方是智能体而放宽。

**权限**：所有 Tool 注册后需经 `PermissionEngine` 判定（见 §7.4）。写操作类 Tool 默认应落入 `ask` 规则（触发 HITL 人工确认），不得默认 `allow`。

---

## 11. 测试策略

### 11.1 方言适配器契约测试

同一 fixture 在三个方言下返回结构一致。
- PostgreSQL 复用 `docker-compose.infra.yml` 现有 PG17
- MySQL / Doris 新增测试容器

### 11.2 安全用例（必须覆盖）

- 多语句 `SELECT 1; DROP TABLE t`
- 注释绕过 `SELECT 1 -- x`、`/* c */ SELECT 1`
- 大小写变形 `sElEcT * FROM t`
- DDL `DROP TABLE` / `TRUNCATE`
- `SELECT ... INTO OUTFILE`
- `pg_sleep()` / 慢查询
- 令牌重放（同一令牌执行两次）
- 令牌换 SQL（批准后篡改 SQL 再执行）

### 11.3 功能用例

- **幂等性**：同一库连扫两次，`meta_table` / `meta_column` 不增行
- **断点续扫**：中途失败后重扫能补齐
- **画像正确性**：已知 fixture 上校验 `null_rate` / `distinct_ratio` / Top-K
- **审批链**：申请 → 批准 → 执行 全链路状态流转与审计留痕
- **租户隔离**：租户 A 不能访问/修改租户 B 的数据源与元数据

---

## 12. 影响面

| 项 | 说明 |
|---|---|
| 新增依赖 | `sqlglot`（SQL AST 解析）、`pymysql`（MySQL/Doris 驱动） |
| 已有依赖 | `psycopg2-binary>=2.9.10`（PG 驱动）、`python-jose[cryptography]==3.3.0`（`cryptography` 随其引入，Fernet 可直接使用，**无需新增**） |
| 新增表 | 7 张主表 + 2 张版本/审计表，同步 `docs/sql/init.sql` 并在 `app/db/init_models.py` 注册 |
| 路由 | `app/core/router_registry.py` 注册 `/api/v1/dataops` |
| 配置新增 | `DATAOPS_ENCRYPTION_KEY`、扫描上限（表/列/采样）、语句超时、令牌有效期 |
| **不受影响** | `wiki_rag`、`WikiOwlEngine`、`PGVectorStore`、AgentScope 运行时 —— 纯新增模块，不改动既有代码 |

---

## 13. 风险与已知限制

1. **sqlglot 对 Doris 方言支持有限** —— Doris 按 MySQL 方言解析，需实测验证；若不可靠则退化为"只读事务兜底 + 严格白名单正则"，安全性下降但可用
2. **大库全量 profile 代价高** —— 默认关闭 `with_profile`，按需按列触发
3. **`overlap_ratio` 是采样估算** —— 非精确值，仅作关系候选提示
4. **写操作审批需管理员在线** —— 无管理员时申请单会过期（默认 15 分钟），属预期行为
5. **扫描只读连接需源库授权** —— 需在源库侧为扫描账号授予 `SELECT` 与 `information_schema` 读权限

---

## 14. 未决事项

- 元数据标准项是否预置行业种子（当前设计：不预置，支持手工创建与后续导入）
- 是否需要对 `profile_json` 设置保留期限或自动清理策略
- Doris 与 MySQL 差异较大时是否拆分为独立 adapter（当前设计：Doris 复用 MySQL adapter，差异点在 adapter 内部按 `dialect.name` 分支）
