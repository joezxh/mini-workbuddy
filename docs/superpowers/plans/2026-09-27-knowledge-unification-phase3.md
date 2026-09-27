# 知识库统一化 Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 spec §10 Phase 3 与 §8 Phase 3——table/qa/multimodal/proxy 全量形态、pipeline dry-run、HNSW 索引、Redis 缓存、RBAC 权限点、`/ask` 性能与流式、连接器调度。

**Architecture:** 全部形态复用 Phase 2 的 `/api/v1/kb` 认证路由与 `KbIngestService/KbRetrievalService`（AgentScope 2.0.8 五模块抽象不变：table 行与 qa 对仍是 `Chunk`/`SegmentInput`，差异只在 `chunk_type` 与检索分支）；多模态 embedding 走 `supports_multimodal` 门控（AgentScope 语义）；外部代理（proxy）仅转发检索。性能项（HNSW/Redis/SSE）独立可回滚。

**Tech Stack:** 同 Phase 2 + Redis（既有 `app.core.redis_client`）+ APScheduler / `job_runner` + sqlglot（已用于 sql_guard）。

## Global Constraints

- 同 Phase 2 全部约束；`kb_format` 不可切换约束对本阶段 table/qa/proxy 同样生效
- multimodal 仅在配置了 Vision embedding（`supports_multimodal=True`）时可选，无供应商时端点 422 显式失败
- proxy `endpoint_url` 强制 https 且禁内网地址段（SSRF 防护，spec §11 风险表）
- 每个形态一个独立测试文件；pytest 基线（Phase 2 结束值）只增不减

---

### Task 1: table 形态（字段映射 + 行级 CRUD + 元数据过滤检索）

**Files:**
- Modify: `backend/app/routers/kb/kb.py`（+ `/collections/{name}/table-records/import|preview`、行级 `GET/PUT/DELETE /kb/segments/{id}`）
- Create: `backend/app/services/kb/table_service.py`
- Test: `backend/tests/unit/test_kb_table.py`

**Interfaces:**
- Consumes: `kb_collection.schema_config`（`[{name,type,enabled,embedding,filterable}]`，Phase 1 已有列）、`KbIngestService`（`chunk_type` 语义经 `SegmentInput.metadata` 落 `chunk_type='table_row'`——若 `SegmentInput` 无该字段则为其增加 `chunk_type: str = "text"`）
- Produces: `import_table_records(db, tenant_id, collection, rows: list[dict], schema_config: list[dict]) -> int`；检索过滤 `filters=[{field,op,value}]` 作用于整行 metadata

- [ ] **Step 1: 失败测试**（schema 校验：embedding 字段必须单选；行内容=embedding 列值，其余列进 metadata；过滤检索命中）
- [ ] **Step 2: 实现 table_service**（openpyxl 读 Excel；`ExcelProcessor` 参考 `app/ai/tool_manager/document_tools`）
- [ ] **Step 3: store 层 `metadata_filters` 下推 SQL**（`kb_segment.metadata_` JSONB `->>` 比较，替代 Phase 2 内存过滤；`pgvector_store.search/hybrid_search` 增加可选参数）
- [ ] **Step 4: 路由接线 + Commit** `feat(kms): table 形态（字段映射/行级 CRUD/元数据过滤检索，spec §10.3）`

### Task 2: qa 形态（Q&A 条目 + 批量导入导出）

**Files:**
- Modify: `backend/app/routers/kb/kb.py`（`POST .../qa-records`、`POST .../qa-records/import`、`GET .../qa-records/export`）
- Modify: `backend/app/services/kb/document_pipeline.py`（qa 行 → `SegmentInput(content=question, metadata={answer, tags, chunk_type:'qa'})`，只 embed question——`KbIngestService` 天然满足）
- Test: `backend/tests/unit/test_kb_qa.py`

**Interfaces:** 检索分支 `chunk_type='qa'` 过滤 + 返回 `answer`；批量导入支持 CSV/Excel（question/answer/tags 四列约定）；导出同构。
**Commit:** `feat(kms): qa 形态（问题向量/答案直返/批量导入导出，spec §10.3）`

### Task 3: multimodal 形态（Vision 门控 + 图搜）

**Files:**
- Create: `backend/app/services/kb/multimodal_service.py`
- Modify: `backend/app/routers/kb/kb.py`（`POST /collections/{name}/assets`；retrieve 支持 image 查询）
- Test: `backend/tests/unit/test_kb_multimodal.py`

**Interfaces:**
- 门控：`embed_fn` 供应商能力声明 `supports_multimodal`（对齐 `agentscope.embedding.*.supports_multimodal` 语义）；未配置时 `POST assets` → 422 `multimodal_unsupported`
- 图片入库：`KbSegmentAsset`（≤2MB、单切片 ≤10 张）+ `kb_segment(chunk_type='image', embedding=图向量, content=caption)`
- 图搜：客户端上传图片 → 嵌入 → `search_by_vector`
**Commit:** `feat(kms): multimodal 图文（Vision 门控/资产表/图搜，spec §10.3）`

### Task 4: proxy 外部知识库（转发检索 + SSRF 防护）

**Files:**
- Create: `backend/app/routers/kb/external.py`（`/api/v1/external-kb-endpoints` CRUD + `POST {id}/test` + `POST {id}/retrieve`）
- Test: `backend/tests/unit/test_kb_proxy.py`

**Interfaces:**
- URL 校验：`https://` 白名单 + `ipaddress` 拒绝私网/环回/链路本地（SSRF）
- 转发契约：`POST {endpoint_url}` body `{query, top_k, index}` → 归一化 `{results:[{content, score, metadata}]}`；超时 10s、响应体 ≤ 1MB、失败结构化返回
- Fernet 解密 `auth_key` 注入 `Authorization` 头
**Commit:** `feat(kms): proxy 外部知识库（CRUD/连通测试/转发检索 + SSRF 防护，spec §10.4）`

### Task 5: pipeline_config 摄取编排 + dry-run

**Files:**
- Modify: `backend/app/services/kb/document_pipeline.py`（读 `kms_knowledge.pipeline_config`：`clean` 步骤串 / `chunker` 覆盖）
- Modify: `backend/app/routers/kb/kb.py`（`POST /api/v1/kb/pipelines/dry-run`：样例文件 + config → 各步中间产物，不落库）
- Test: `backend/tests/unit/test_kb_pipeline.py`

**Interfaces:** `dry_run(file, config) -> {parse: n_sections, clean: n_cleaned, chunk: [样例切片前 5 条]}`；每步错误写 `kb_document.error_detail`（含步骤名，spec §10.7）。
**Commit:** `feat(kms): pipeline 声明式编排 + dry-run 单步调试（spec §10.7）`

### Task 6: HNSW 索引迁移（m=16, ef_construction=64）

**Files:**
- Modify: `backend/app/db/startup_migrations.py`（幂等：先 DROP 旧索引再 CREATE HNSW）
- Test: `backend/tests/unit/test_hnsw_index.py`（`pg_indexes` 中 `am='hnsw'`）

```sql
DROP INDEX IF EXISTS ix_kb_segment_embedding ON kb_segment;
CREATE INDEX IF NOT EXISTS ix_kb_segment_embedding_hnsw
  ON kb_segment USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
```
**验收**：10 万切片注入（假向量）P95 < 100ms（spec §4.4.1）。
**Commit:** `feat(kms): kb_segment 向量索引迁移 HNSW（spec §4.4.1）`

### Task 7: Redis 缓存（分类树 / 知识库列表）

**Files:**
- Modify: `backend/app/services/wiki/category_service.py`、`knowledge_service.py`
- Test: `backend/tests/unit/test_kb_cache.py`（fakeredis 或 monkeypatch）

**Interfaces:** `cache_get/cache_set/cache_invalidate(prefix)` 装饰器式工具（`app/core/kb_cache.py`，TTL 1h，key `kms:{tenant}:{kind}:{id}`）；写路径（分类/知识库/文章 CRUD）失效对应 key；Redis 不可用时静默直查（可观察日志，不伪装成功）。
**Commit:** `feat(kms): 分类树/知识库列表 Redis 缓存（TTL 1h 写失效，spec §4.4.2）`

### Task 8: RBAC 权限点（Wiki / SQL / ExternalKb）

**Files:**
- Modify: `backend/app/routers/wiki/wiki.py`、`backend/app/routers/dataops/*`、`backend/app/routers/connectors/connector.py`、`backend/app/routers/kb/*`（写端点挂权限依赖）
- Test: `backend/tests/unit/test_kb_rbac.py`

**Interfaces:** 权限码 `kms:wiki:write` / `kms:sql:execute` / `kms:external:manage` / `kms:kb:write`，挂在 `get_current_user` 后的新依赖 `require_perm(code)`（实现见现有 sys 权限体系；无权限 403）。前端菜单/按钮态由既有 sys_menu 权限串驱动。
**Commit:** `feat(kms): 三模块 RBAC 权限点（kms:* 码，spec §4.1 权限项）`

### Task 9: `/ask` 消 N+1 + SSE 流式

**Files:**
- Modify: `backend/app/routers/wiki/wiki.py`（`/ask` 引用文章 `select(WikiArticle).where(slug.in_(...))` 批量查；`StreamingResponse` SSE）
- Test: `backend/tests/unit/test_ask_no_n1.py`（SQL 计数断言）、`tests/unit/test_ask_sse.py`

**Interfaces:** SSE 事件 `event: citation|token|done`；前端 `LLMAnswerPanel.vue` 改 `EventSource`/fetch-stream 消费（Phase 3 前端项一并做）。
**Commit:** `feat(kms): /ask 批量引用消 N+1 + SSE 流式输出（spec §4.4.3）`

### Task 10: 连接器调度（sync_interval_min）+ 语雀/Notion 连接器

**Files:**
- Create: `backend/app/services/connectors/scheduler.py`（APScheduler/线程轮询 `kms_connector_instance.sync_enabled=1` 到期实例 → `run_connector` + `ConnectorSyncLog`）
- Create: `backend/app/connectors/types/yuque.py`（OAuth2ApiConnector 模式，参照 dingtalk.py）
- Test: `backend/tests/unit/test_connector_scheduler.py`、`tests/connectors/test_yuque.py`（respx mock——需先补装 `respx` 并声明进依赖清单）

**Commit:** `feat(connectors): sync_interval 调度消费 + 语雀连接器（spec P1.5/1.6）`

### Task 11: 前端去重与收口（spec P3.14-17）

- `r.data || r` 归一化下沉 `utils/request.ts` 拦截器；`DataSourceSelect.vue` + `useDataSources()` 抽取（6 处）；4 个根面板抽 `PanelTabs.vue`；`window.prompt` 改 modal；`index.vue` 拆 `CategoryTree/ArticleListTable`；死代码清理（SearchBar.vue、types/wiki.ts 未用类型）。
- lint/build 验收：kms 域零新增错误。
**Commit:** `refactor(kms): 前端去重收口（拦截器/DataSourceSelect/PanelTabs，spec P3.14-17）`

### Task 12: Phase 3 验收

- 全量 pytest（排除清单同前）+ 前端 lint/build
- spec §11.8 逐项核对：table 导入→映射→行编辑→过滤检索；qa 批量往返；multimodal 图搜；proxy 真实转发一次；pipeline dry-run 中间产物不落库
- spec 状态行 →「Phase 3 已实施」
