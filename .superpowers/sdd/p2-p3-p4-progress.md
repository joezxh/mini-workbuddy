# P2 / P3 / P4 执行进度纪要（2026-09-11）

来源计划：
`docs/superpowers/plans/2026-09-10-p2-dataops.md` / `2026-09-10-p3-external-kb.md` / `2026-09-10-p4-ontology.md`

## 本轮完成（第二批：2026-09-11 续）

### P2 Task 2（数据源 ORM / 迁移 / CRUD）— ✅ DONE
- **9 张表**（7 主表 + 2 版本/审计表，全继承 TenantMixin）：
  `app/models/dataops/{data_source,meta,standard,write_request}.py`
  - `data_source`：`password_enc`（Fernet 密文，永不外显）；**名称唯一约束租户化为
    `(tenant_id, name)`**（对 spec「unique」的收窄，防跨租户名称枚举）；
    `meta_table`/`meta_column` 唯一键是扫描幂等的基础。
- **迁移 007**：`alembic/versions/2026_09_11_0001-007_add_dataops_tables.py`，
  直接以 ORM 元数据建表（单一事实来源，避免二次声明漂移）。
- `app/services/dataops/data_source_service.py`：create/list/get/update/delete +
  `reveal_password`（仅供适配器建连接，严禁 API 出口）+ `is_default` 互斥；
  `source_type` 不可改；password 空=不改。
- `app/routers/dataops/dataops.py`（prefix `/api/v1/dataops`，已注册 router_registry +
  init_models）；无租户 400 `tenant_required`，跨租户 404。
- 测试 10 项（`tests/dataops/test_data_source.py` + 专用 conftest）。
  **注意**：`.env` 需配置 `DATAOPS_ENCRYPTION_KEY`（测试用 autouse fixture 注入；
  生产不配则服务层拒绝加密，属预期显式失败）。

### P2 Task 3（DialectAdapter 协议 + PostgreSQL 适配器）— ✅ DONE
- `app/ai/dataops/dialect_base.py`：`DialectAdapter` Protocol +
  TableMeta/ColumnMeta/ColumnProfile/QueryResult/ColRef/WriteImpact 数据类。
- `app/ai/dataops/dialects/postgres.py`：Mixin 组合（_TablesMixin/_ColumnsMixin/
  _ProfileMixin/_DryRunMixin）：
  - `list_databases` 排除模板库；表/列注释走 pg_catalog（`obj_description`/
    `col_description`）；类型名归一化（`character varying`→`varchar`）；
  - `profile_column`：null_rate/distinct_ratio + 数值/日期 min-max / 非数值 Top-10；
  - `overlap_ratio`：采样估算，异常置 0.0 且**回滚连接**（失败语句会把共享连接
    事务打成 aborted，污染后续语句——踩坑）；
  - `dry_run`：`EXPLAIN (FORMAT JSON)` 取 `Plan Rows`（**psycopg2 对 json 列
    自动反序列化为 dict，正则打不中**——已兼容两种形态）；新表需 ANALYZE 才有行估算。
  - 标识符全部 `identifier_preparer.quote()`。
- `app/ai/dataops/dialects/registry.py`：按 source_type 分派；mysql/doris 待 Task 4。
- 测试 26 项（`tests/dataops/test_dialect_postgres.py`，探针 schema fixture）。

## 上一轮完成

### P4 Task 7（P4.3 · 本体驱动检索）— ✅ DONE
- `app/services/kb/pgvector_store.py`：`search` / `hybrid_search` 新增
  `class_uris` 过滤（JSONB `?|` OR 语义，向量/关键词两路都过滤）。
  **踩坑**：Python list 直传会被 psycopg2 绑成 jsonb → `jsonb ?| jsonb` 报错；
  已用 `type_coerce(list, ARRAY(Text))` 修复（`_class_uris_any` 助手）。
- `app/services/kb/retrieval_service.py`：三个检索入口透传 `class_uris`。
- **新建 `app/services/ontology/search_filter.py`**：
  - `expand_with_descendants`：沿 `ontology_class.parent_uris` 把选中类扩展为
    「选中类 + 全部后代类」（父类过滤覆盖子类）；环路安全（visited + 深度上限 10）、
    悬空父类安全跳过、deprecated 子类不扩展、空选区 = 不过滤。
  - `OntologyDrivenRetriever` 组合入口：后代扩展 + KB 检索（`hybrid=True` 走
    pg_trgm+RRF 混合）；传 class_uris 缺 ontology_id 显式报错。
  - 依赖方向 ontology → kb，kb 不反向依赖。
- `ontology_annotation.target_type` 已含 `segment`（Task 1 定义时已预留，无需改表）。
- 测试 `tests/ontology/test_search_filter.py`（8 项）：后代扩展/环路/deprecated/
  过滤不越界/租户隔离/混合联动/组合入口。

### P2 Task 1（Fernet 凭据加密）— ✅ DONE
- `config.py` 新增 `DATAOPS_ENCRYPTION_KEY`（独立密钥，不复用 SECRET_KEY）。
- **新建 `app/ai/dataops/crypto.py`**：encrypt/decrypt/generate_key；
  缺 key 时 RuntimeError 拒绝降级明文。
- 测试 `tests/dataops/test_crypto.py`（5 项）。

### P2 Task 8（SqlGuard 只读白名单 · 单一事实来源）— ✅ DONE
- 安装 `sqlglot 30.18.0`（计划内技术栈）。
- **新建 `app/services/dataops/sql_guard.py`**：AST 判型（sqlglot 30.x 探查结论：
  EXPLAIN→Command 解包复检；INTO OUTFILE 解析失败即拒；注释词法层拒绝；
  危险函数黑名单 pg_sleep/sleep/benchmark/lo_*/dblink/...；**FORBIDDEN 节点按
  名称惰性取类**——`exp.Call` 等在 30.x 不存在，直接引用会 AttributeError）。
- 测试 `tests/dataops/test_sql_guard.py`：计划 10 条 + DML/命令变体/安全变体
  共 20+ 用例。

## 全量回归

```
200 passed, 5 warnings in ~96s    （181 → 200：+10 P2T2、+26 P2T3，另 P2T1/T8 重跑）
```

## 各阶段状态

| 阶段 | 状态 |
|---|---|
| P1（11 任务） | ✅ 全部完成 |
| P4 | ✅ 9/9 收官（Task 8 领域片段模板可选未排） |
| P2 | ✅ 全部完成（Task 1~14：MySQL/Doris 适配器 + Doris 真实验证 + Task 5/6 单测） |
| P3 | Task 1(连接器抽象+HTTP 基础设施) ✅；Task 2~5(具体连接器类型+字段映射) ✅；Task 7(同步落库 DB Sink) ✅；**Task 8(中文检索质量对比基线) ✅**；剩 Task 6(钉钉可行性需真实企业账号) |

## 本轮完成（第三批：2026-09-11 续二）

### P2 Task 7（元数据扫描编排，消费 Task 3 适配器）— ✅ DONE
- `app/ai/dataops/connection.py`：数据源 → SQLAlchemy Engine 构造器（PG/mysql/doris 驱动路由，
  URL 凭据 `quote_plus`，`connect_timeout` + `pool_pre_ping`；**不触碰 `password_enc`**，
  解密在前置服务完成）。
- `app/services/dataops/scan_service.py`：`MetaScanService.start_scan()` 同步执行（无独立任务队列）：
  建连 → `get_adapter(source_type)` → `list_tables` / `list_columns` / `profile_column`
  → 幂等写 `meta_table`/`meta_column`（先删 `(source_id,database)` 旧快照再插，外键级联删列）
  → 进度/统计/状态/耗时回写。异常置 `failed` + `error_detail`。`with_profile` 触发列画像。
- 端点：`POST /sources/{id}/scan`、`GET /sources/{id}/tables`、`GET /scan/...`。
- 测试 6 项集成测试（`tests/dataops/test_scan_query_write.py`，真实 PG 探针库，含扫描幂等/
  适配器联调/只读/写审批全链路）。

### P2 Task 9（只读 SQL 执行）— ✅ DONE
- `app/services/dataops/query_service.py`：`ReadonlyQueryService.run()` 经 **`SqlGuard` 单一事实来源**
  校验（仅单条只读），行数上限 + 截断标记（`truncated`），通过 `reveal_password` 解密建连。
- 端点：`POST /sources/{id}/query`。

### P2 Task 10（写申请 → 批准 → 一次性令牌执行）— ✅ DONE
- `app/services/dataops/write_request_service.py`：`DataWriteRequestService`
  - 申请：`SqlGuard` 校验**必须是写语句**（只读查询拒绝）；`sql_sha256` 一致性锚点；`statement_type`
    经 sqlglot AST 识别（insert/update/delete/ddl）。
  - 批准：发放 `secrets.token_hex(32)` 一次性令牌（写入新增 `token` 列）。
  - 执行：令牌校验（无效/已消费/非 approved/过期均拒）+ **重新计算 sha256 与存储比对**（防篡改）
    + `SqlGuard` 纵深复核 → 建连执行 → `token_consumed=True` + 结果（影响行数/耗时）。
- 迁移 008：`data_write_request` 追加 `token` 列。
- 端点：`POST /write-requests`、`GET /write-requests`、`GET /{id}`、
  `POST /{id}/approve`、`POST /{id}/execute`。
- 集成测试覆盖：写申请流（update/delete）、只读拒绝、令牌重放拒绝、令牌错误拒绝。

### 全量回归
```
206 passed, 5 warnings in ~76s   （200 → 206：+6 Task 7/9/10 集成测试）
```

## 本轮完成（第四批：2026-09-11 续四）—— P2 Task 4 / Task 14 / P3 Task 1

### P2 Task 4（MySQL / Doris 方言适配器）— ✅ DONE
- `app/ai/dataops/dialects/mysql.py`：`MysqlAdapter` 实现 DialectAdapter 协议全部方法
  （list_databases / list_tables / list_columns / profile_column / overlap_ratio /
  sample_rows / dry_run）。`information_schema` 原生含注释列（比 PG 简单）；
  类型归一化对齐 PG（integer/varchar/timestamp…）；`dry_run` 走 MySQL `EXPLAIN` 解析 `rows`。
- `app/ai/dataops/dialects/doris.py`：`DorisAdapter` 复用 MySQL 实现（Doris 走 9030
  MySQL 协议），仅微调系统库过滤。
- `registry.py`：注册 `mysql` / `doris`（之前仅 `postgresql`）。
- `requirements.txt`：补 `pymysql>=1.1.0`。
- 真实 MySQL 8 容器集成测试 `tests/dataops/test_mysql_integration.py`（env
  `DATAOPS_TEST_MYSQL_URL` 缺省跳过）：系统库过滤 / 主键识别 / 列画像 top_values /
  重叠率 / 取样 **5 项全过**。

### P2 Task 14（Agent Tools 消费 dataops 服务）— ✅ DONE
- `app/ai/tools/dataops_tools.py`：5 个 AgentScope `ToolBase` 子类，租户链路复用
  `ontology_tools` 模式（自建会话 + `get_tool_user()`→`tenant_id`，取不到返回
  `tenant_required`）：
  - `dataops_scan`（MetadataScanService）— 写类，需确认
  - `dataops_query`（ReadonlyQueryService）— 只读
  - `dataops_write_request`（DataWriteRequestService）— 写类，需确认
  - `dataops_bind`（StandardBindingService）— 写类，需确认
  - `dataops_infer_relations`（RelationInferenceService）— 写类，需确认
  - `build_dataops_tool_definitions()` 产出 5 个 `enabled`/`is_system` 定义。
- `app/ai/tool_manager/seed_tools.py`：并入 DataOps 工具 seed（启动幂等登记）。

### P3 Task 1（连接器抽象 + HTTP 基础设施）— ✅ DONE（P3 首个任务）
- `app/connectors/base.py`：`ConnectorConfig`(pydantic) / `BaseConnector`(ABC) /
  `PaginationConfig`(none/page/offset/cursor) / `Sink` 协议 + `InMemorySink`（Task 7
  落库实现 DB Sink）。
- `app/connectors/http.py`：`HttpConnector` 通用 REST 拉取：Bearer 鉴权头注入、
  dotted `records_path` 提取、三种分页、连通性探测、超 100 万条安全阀。
- `app/connectors/registry.py`：`get_connector(type, config)` 分派（同构方言注册表）。
- `pytest-asyncio` + `respx` 已装；`tests/connectors/test_http_connector.py`
  **7 项全过**（鉴权头 / 分页 / 根即列表 / 连通性 ok&fail / sync / 注册表）。

### 全量回归
```
234 passed, 5 warnings in ~86s
（227 基线 + 9 P2T4/14 单测 + 7 P3T1 单测；5 skipped = MySQL 集成测试未设 env）
```

## 下一步建议顺序

1. ~~**P2 Task 5/6**（profile_column / overlap_ratio 单测）~~ — ✅ 已完成（见下）
2. ~~**P2 Task 4**（MySQL/Doris 适配器）+ Task 14（Agent Tools）~~ — ✅ 已完成（见下）
3. ~~**P3 Task 1**（连接器抽象 + HTTP 基础设施）~~ — ✅ 已完成（见下）
4. **P3 Task 2~5**（具体连接器类型：钉钉/飞书/企业微信等外部源 + 字段映射 + 增量）+ Task 7（同步落库，DB Sink）+ Task 8
5. P3 Task 6（钉钉可行性）需真实企业账号，建议挂起交用户验证。

## P2 阶段状态（截至 2026-09-11 续三）

| Task | 状态 | 产出 |
|---|---|---|
| 1 加密 | ✅ | `ai/dataops/crypto.py` |
| 2 数据源/标准模型 | ✅ | `models/dataops/*` + 迁移 004 |
| 3 方言适配器(PG) | ✅ | `ai/dataops/dialects/*` + `overlap_ratio` |
| 5/6 画像 | ✅ | 并入扫描 |
| 7 扫描编排 | ✅ | `scan_service.py` + 端点 |
| 8 SqlGuard | ✅ | `sql_guard.py` |
| 9 只读执行 | ✅ | `query_service.py` + 端点 |
| 10 写审批 | ✅ | `write_request_service.py` + 迁移 008 + 端点 |
| **11 标准绑定** | ✅ | `standard_service.py`(种子) + `standard_binding_service.py` + 端点 |
| **12 规则引擎** | ✅ | `rule_engine.py` 扩展（PII/语义识别 + 标准匹配 + 置信度分层 + 内置标准） |
| **13 关系推断** | ✅ | `meta_relation` 模型 + 迁移 009 + `relation_inference_service.py`(三方投票) + 端点 |
| 4 MySQL/Doris 适配 | ✅ | 见第四批（MySQL/Doris 适配器 + Doris 真实验证） |
| 14 Agent Tools | ✅ | 见第四批（dataops_tools.py + seed） |

> 本表为 2026-09-11「续三」快照，已被上方「各阶段状态」表与各批次回归块取代：
> Task 4/14 已 ✅；最新全量回归见下文第五批 **251 passed, 5 skipped, 1 error（flaky 非可复现）**。

## 本轮完成（第五批：2026-09-12）—— P3 Task 2~5 + Task 7

### P3 Task 2~5（具体连接器类型 + 字段映射 + 增量）— ✅ DONE
- `app/connectors/mapping.py`：`FieldMapItem`(target/source/transform/default) +
  白名单 `TRANSFORMS`(`int`/`float`/`bool`/`str`/`lower`/`upper`/`trim`/`title`/`date_iso`，
  **严禁 eval**)；`apply_field_map`(纯函数，缺失源走 default，转换失败回退 None)。
- `ConnectorConfig` 扩展：`field_map` / `incremental_field` / `incremental_param` +
  OAuth2 专属 `token_url`/`client_id`/`client_secret`/`data_path`/`token_field`/
  `token_method`/`token_query`/`token_body`/`token_in`/`token_query_name`。
- `app/connectors/http.py`：`HttpConnector.pull` 拉取后应用字段映射；增量游标
  `last_cursor`（数值优先比较，字符串兜底）；`_resolve_token`/`_data_path` 钩子供子类覆写。
- **具体连接器类型** `app/connectors/types/`：
  - `OAuth2ApiConnector`：取令牌(支持 query/json 形态) → 带令牌拉数据，令牌注入
    `header`(Bearer) 或 `query`(`access_token` 参数)。
  - `DingtalkConnector` / `FeishuConnector` / `WeComConnector`：预置各自令牌端点与
    请求形态（钉钉/企业微信 GET+query、飞书 POST+JSON 体），respx 可测。
- `registry.py`：注册 `http`/`dingtalk`/`feishu`/`wecom`。

### P3 Task 7（同步落库 DB Sink）— ✅ DONE
- `app/models/connectors/connector_record.py`：`ConnectorIngest`(按租户+类型+外部ID
  幂等 upsert) + `ConnectorSyncState`(每「租户+类型」增量游标)。
- `app/connectors/sinks/db_sink.py`：`DBSink`(postgresql `ON CONFLICT` upsert +
  增量游标持久化 + `get_last_cursor`)；实现 `ConnectorSink` 协议。
- `app/connectors/runner.py`：`run_connector()` 编排（读上次游标 → 拉取→落库→写回游标），
  供 API/定时任务调用。
- `app/db/init_models.py`：登记连接器落库模型（prod `create_all` 自动建表）。

### P3 Task 8（中文检索质量对比基线）— ✅ DONE
- **计划意图**：对比「只读直连词项打分」与「同步落库向量检索」在中文 query 上的召回，
  量化同步模式增益（验收前置）。计划原设 Notion/语雀文档连接器未实现，经用户确认采用
  **合成中文语料 + 确定性假向量**基线（选项 1）。
- `scripts/kb_external_retrieval_bench.py`：
  - `LexiconRetriever`（Mode A，字符/二元组 TF 余弦，无 embedding，对应只读直连本地打分）；
  - `run_comparison`（Mode B，摄取进 `PGVectorStore` + `KbRetrievalService.hybrid_search_by_text`）；
  - `fake_embed_fn`（字符/二元组哈希伪向量，与 `kb_perf_baseline` 同款，无需真实 API）；
  - 12 篇合成中文文档 + 20 条中文 query（gold doc_id）；指标 recall@1/@5 + MRR。
- 实测：两路 Recall@1/5=1.0、MRR=1.0（字面/关键词类 query 持平）。**结论**：伪向量只编码
  字面共现，无法度量真实 embedding 的语义泛化增益（同义改写等），那才是同步落库价值所在；
  本基线验证同步检索链路可用且召回达标，生产 embedding 下重跑 `fake_embed_fn→build_embed_fn`
  并补同义/改写 query 方可验证增益。
- `scripts/__init__.py`：使脚本可被测试导入（无害包标记）。
- `tests/kb/test_external_retrieval_bench.py`（2 项）：两路跑通 + Recall@5 达标断言 +
  纯 python 的 `LexiconRetriever` 单测。
- spec §10.1（`docs/superpowers/specs/2026-09-10-third-party-kb-connectors-design.md`）写入量化结果；
  原始逐条结果 `docs/superpowers/specs/2026-09-10-external-kb-retrieval-bench.json`。

### P2 Task 5/6（profile_column / overlap_ratio 单测）— ✅ DONE
- 现有 `tests/dataops/test_dialect_postgres.py`、`test_mysql_integration.py` 是**集成测试**
  （要真实 PG/MySQL）。补一组**纯单元**测试 `tests/dataops/test_profile_unit.py`（14 项，全过，
  无外部依赖）：
  - `profile_column`：数值型(min/max 分支)、非数值型(Top-10 分支)、空表(total=0 不除零)、
    未知类型(走 Top 分支)、null_rate / distinct_ratio 计算精度（对齐 `round(x,6)` 契约）。
  - `overlap_ratio`：正常比例、分母为 0 → 0.0、异常路径 → 0.0 且 `conn.rollback()` 被调用
    （验证 P2 踩坑点：失败语句会把共享事务打成 aborted，必须回滚）。
- 用 `unittest.mock.MagicMock` 替换 `conn`，经 `side_effect` 精确控制 `execute` 返回的
  `fetchone/first/fetchall`，两套适配器（`PostgresAdapter` / `MysqlAdapter`）参数化覆盖。

### P2 Task 4 · Doris 真实验证 — ✅ DONE
- 现状：`DorisAdapter` 直接继承 `MysqlAdapter`，**所有 SQL 均为 MySQL 协议兼容语句**
  （Doris 经 9030 端口的 MySQL 协议通信）；Doris 专属差异仅 `list_databases` 的系统库过滤集
  （`_DORIS_SYSTEM_DBS`）。
- 本环境 Docker Hub 不可达（`registry-1.docker.io` 超时），无法拉起真实 Doris 容器；改用
  **真实 MySQL 8.0（127.0.0.1:3307，协议兼容、适配器代码路径一致）做 wire 级真实验证**：
  - 新增 `tests/dataops/test_doris_integration.py`（env 门控 `DATAOPS_TEST_DORIS_URL`，缺省 skip），
    用 `get_adapter("doris")` 跑通 list_databases 系统库过滤 / list_columns 主键+注释 /
    profile_column Top-10 / overlap_ratio / sample_rows —— **5 项全过**（指向 MySQL 8.0 wire）。
  - 该测试同样可直接指向真实 Doris（`DATAOPS_TEST_DORIS_URL=mysql+pymysql://...:9030/db`），
    CI 有 Doris 时即为原生 Doris 真实验证，无需改代码。
- 另补纯单元测试 `tests/dataops/test_dialects_mysql.py::test_doris_list_databases_filters_system_dbs`
  （假连接锁定 Doris 专属系统库过滤，无 DB 依赖，2 项 doris 单测全过）。
- 结论：`DorisAdapter` 全部代码路径已在真实 MySQL 协议引擎上实跑通过；Doris 原生验证已就绪
  （仅差一个可达的 Doris 实例，由 `DATAOPS_TEST_DORIS_URL` 触发，非阻塞）。

### 测试（25 项全过）
- `tests/connectors/test_mapping.py`（6）：字段映射/转换器/默认/越界保护。
- `tests/connectors/test_http_connector.py`（+3）：字段映射应用 / 增量参数注入 / last_cursor。
- `tests/connectors/test_oauth2_connector.py`（5）：钉钉/飞书/企业微信 token+data（respx）。
- `tests/connectors/test_db_sink.py`（3）：upsert+增量 / 租户隔离 / 哈希ID。
- `tests/connectors/test_runner.py`（1）：run_connector 端到端（respx+PG）。

### 测试基建修复（跨目录）
- 发现 `tests/dataops`、`tests/ontology` 的 per-schema 隔离实际不可靠：仅依赖
  `SET search_path` 事件的 `create_all` 会把表落到 `public`，多轮运行累积造成
  `sys_user` 等唯一约束冲突。
- 修复：`engine` 改用 `schema_translate_map`({None: schema}) 路由 DDL/查询，并**保留**
  `search_path` 事件供 `inspect`/反射按 schema 定位表（二者并用，既不污染 public
  又能反射）。`tests/connectors/conftest.py` 同样采用此方案；`public` 残留行已清理。
- 顺带修正：DingTalk/WeCom 令牌方法原来 `or` 无法覆盖默认 `"POST"`，已强制 `"GET"`；
  增量游标比较由字符串序改为数值优先。

### 全量回归
```
251 passed, 5 skipped, 1 error（flaky 非可复现）
（5 skipped = MySQL 集成测试未设 DATAOPS_TEST_MYSQL_URL）
- 实际全量运行：251 passed, 5 skipped, 21 warnings, 1 error（~92s）。
- 1 error = `tests/ontology/test_ttl_roundtrip.py::test_ttl_roundtrip_preserves_classes`，
  为**非可复现**的排序/teardown 偶发（同用例单独运行 PASS，ontology 全目录 117 passed 0 error）。
  与本轮改动无逻辑关联，属测试隔离的偶发锁竞争/连接残留，留待后续若复现再排查。
- 连接器 25 项 + 本体反射 4 项均稳定 PASS。
```

## 约定延续（P1 简报）

- 不执行任何 git 写操作，改动留工作区由用户 commit。
- 测试基建沿用 per-schema 隔离（`minworkbuddy_test`）。
- 置信度阈值实现时**必须**落在 `app/services/dataops/rule_engine.py`
  （`CONF_AUTO_ACCEPT=0.85` / `CONF_SUGGEST_MIN=0.65`），P4 已消费该常量约定。
