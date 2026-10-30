# 知识图谱知识库（Graph KB）扩展设计

- 日期：2026-10-30
- 状态：待评审
- 参考：`d:\projects\github\Yuxi` 图知识库设计（`docs/advanced/knowledge-base-graph.md`、
  `backend/yuxi/modules/knowledge/graphs/*`、`modules/knowledge/implementations/milvus.py`）
- 关联：MinWorkBuddy 知识库统一化 spec（2026-09-27）、标准三层语义模型 CDM spec（2026-10-28）、
  semantica 替换 ontology 迁移计划（`docs/semantica-replace-ontology.md`）

---

## 1. 背景与目标

### 1.1 现状

MinWorkBuddy 知识库是三层容器模型：

| 层 | 表 | 职责 |
|---|---|---|
| 容器 | `kms_knowledge`（`WikiKnowledge`） | 顶级容器。`type`=1 llm-wiki / 2 general-kb / 3 external-kb；`kb_format` 为二级形态 |
| 集合 | `kms_collection` | 逻辑集合名 `kb_{kid}`，映射 AgentScope RAG store，承载 `schema_config`/`retrieval_settings` |
| 内容 | `kms_document` → `kms_segment` | 文档状态机 + 切片（pgvector 向量、`chunk_type` text/qa/table_row/image/parent/child、`keywords`、`class_uris`） |

检索在 `app/routers/kb/kb.py:_retrieve_collection` 按 `index_mode` 分流：economy 走
`economy_search` 关键词全文；high_quality 走 AgentScope `KnowledgeBase.search`
（`PgVectorStore` + `embedding_factory`，租户 `metadata_filter` 构造期固化）。
`retrieve_knowledge` 跨该知识库全部集合检索后合并取 Top-K。

### 1.2 局限

1. **只有切片一种语义载体**。document/table/qa 都把语义压扁为文本片段，实体与关系结构丢失，
   多跳问题（"A 的上游 B 的客户 C"）只能靠 chunk 拼接硬扛。
2. **`kms_segment.class_uris` 语义悬空**。它是为"本体驱动检索"预留的列，ontology 正在被清理，
   语义来源将断供。
3. **有模式、无实例**。dataops 标准中心 CDM（`meta_object_standard`=类、`meta_standard`=属性、
   `meta_object_relation`=关系标准）只有模式层；`StandardQueryService.graph()` 返回的
   nodes/edges 全是"对象标准/关系标准"，没有实体实例与关系实例。
4. **抽取与图能力已就位但未被 KB 消费**。`app/services/semantica/` 有薄适配层
   （`TenantScope` 租户隔离、`SemanticaPipelineService` 的 extract→conflicts→dedup→kg→vector、
   `SemanticRetriever`），底座为 PostgreSQL(pgvector) + Neo4j（与 graphiti 共用实例，
   `GRAPHITI_GROUP_ID` 隔离）。kb 模块完全没消费。
5. **检索响应契约只有 chunk 一种粒度**。`RetrieveResult{score, document_id, chunk_index, content, metadata}`
   无法表达"实体 + 关系 + 路径"。

### 1.3 目标

新增**独立的知识图谱知识库类型（type=4）**，以 Neo4j 作为**必需**的图结构存储，
实体与关系实例必须抽取并落库，检索走「向量召回 + Neo4j 多跳 + PPR + RRF 融合」。

### 1.4 非目标（YAGNI）

- 时序图谱（`valid_from`/`valid_until`）
- 推理引擎（Rete / Datalog / 规则推理）
- 跨库 / 跨租户图谱
- Neo4j 作为唯一真相源（PG 仍是权威事实）
- 图谱流水线可视化画布
- 引入 Milvus / 新的向量库（复用既有 pgvector）
- 引入 AntV G6 等新前端依赖（复用既有 ECharts GraphChart）

---

## 2. Yuxi 图知识库的可借鉴模式

Yuxi 已实现一套三存储协同的图知识库，是本设计的直接参照。

### 2.1 三存储职责

| 存储 | Yuxi 承载 | MinWorkBuddy 对应 | 本设计取舍 |
|---|---|---|---|
| PostgreSQL | 权威事实 + 投影（entities/triples/mentions） | PostgreSQL | **一致**：同为 PG，`kms_*` 同库同构 |
| Neo4j 5.26 | 图结构（实体/关系/Chunk 提及） | Neo4j 5.x | **一致**：环境已有 `NEO4J_*` 配置 |
| 向量库 | Milvus 3.0.2（chunk 集合 + `{kb_id}_entity` / `{kb_id}_triple`） | pgvector | **改用 pgvector**：MinWorkBuddy 无 Milvus；实体/三元组向量与 chunk 向量同库同列同模型，空间可比 |

### 2.2 值得直接借鉴的工程约定

| Yuxi 约定 | 位置 | MinWorkBuddy 采纳 |
|---|---|---|
| Neo4j 节点三段式 label：`:Chunk`/`:Entity` + 基础 label + **每知识库 label** | `graphs/graph_utils.py:71-125` | `:Chunk:MwbKG:\`mwb_kb_{kid}\`` / `:Entity:MwbKG:\`mwb_kb_{kid}\`` |
| 关系类型仅 `MENTIONS`(Chunk→Entity) 与 `RELATION`(Entity→Entity)，**语义关系类型存关系属性** | `graph_utils.py:101-125` | 一致（`type` 属性） |
| Cypher 模板集中一处，禁止散落在业务代码 | `graph_utils.py` | `app/services/kb/kg/kg_neo4j_store.py` 集中所有模板 |
| label 名正则校验防 Cypher 注入 | `infrastructure/neo4j/manager.py:12-21` | `safe_neo4j_label()`，白名单 `^mwb_kb_\d+$` |
| 稳定 hash ID（`hashstr` 32 位） | `graph_utils.py:14-36` | `compute_entity_id(kid, normalized_name, label)` / `compute_triple_id(...)` |
| 实体去重键 = (归一名, label)；关系去重键 = (源, 类型, 目标) | `extractors/base.py:52-151` | 一致，落在 PG 唯一约束上 |
| 长度守卫越界**丢弃而非抛错**，并计入 `dropped_entities`/`dropped_relations` | `extractors/base.py:143-146` | 一致（不可信 LLM 输出的工程范式） |
| 丢弃实体的悬空关系一并丢弃 | `extractors/base.py:82,124-126` | 一致 |
| 两阶段状态机 `graph_structure_indexed` / `graph_indexed` | `models.py:201-203` | 一致（对外契约） |
| 向量租约列 + `FOR UPDATE SKIP LOCKED` 认领 | `repositories/graphs.py` | `vector_status` / `vector_attempt_count` / `vector_last_error` / `vector_next_retry_at` / `vector_locked_until` / `vector_lock_token` |
| 复合 FK 让 `kb_id` 参与外键，杜绝跨库串数据 | `models.py:216-359` | 一致，`knowledge_id` 参与复合 FK |
| PG 是**可见性权威**，Neo4j 只是结构；读时回 PG 过滤 | `service.py:1253-1278` | 一致 |
| 多跳**硬封顶 3 跳**，`path_limit = limit*10` | `service.py:770,819` | 一致 |
| PPR：networkx `pagerank(personalization=reset)`，damping 0.85，只对 Chunk 节点出分 | `service.py:886-957` | 一致（damping 可配，钳制 [0.1,0.99]） |
| RRF：`score = weight / (rrf_k + rank)`，rrf_k=60，基础权重 1.0，图权重可配 | `implementations/milvus.py:1293-1324` | 一致 |
| 融合输出带 `fusion_score` / `fusion_sources` / `score_type` | `implementations/milvus.py:1293-1324` | 一致，写入 `metadata`（**不改**既有 `score` 语义） |
| 图召回失败**降级为空**，不阻断主检索 | `implementations/milvus.py:1236-1238` | 一致 |
| LLM 抽取：schema 约束注入 prompt + JSON 容错解析 + 超时上限 + 并发上限 | `extractors/llm.py` | 一致 |
| 后台作业单库互斥（同一 kb 同时只允许一个图谱任务） | `services/graph_build.py:26-103` | 一致（`job_runner.run_in_background` + 进程内锁） |
| 动作分发 `build` / `clear_file` / `reconcile` | `services/background_jobs.py:134-177` | 一致（`clear_file` → `clear_document`） |

### 2.3 Yuxi 的短板 —— MinWorkBuddy 可超越之处

Yuxi **没有形式化本体/Schema 表**，实体类型与关系类型完全来自 LLM 输出 + 自由文本 schema prompt，
类型会漂移（报告原文明确指出）。

MinWorkBuddy 已有 CDM 三层语义模型（`meta_object_standard` 对象标准、`meta_standard` 属性标准、
`meta_object_relation` 关系标准、`meta_standard_catalog` 目录/场景），可作为抽取器的
**类型约束来源**，从源头抑制类型漂移。这是本设计相对 Yuxi 的净增益。

---

## 3. 类型定义与数据模型

### 3.1 类型定义

```python
# app/models/wiki/wiki_knowledge.py
class KnowledgeType(IntEnum):
    LLM_WIKI = 1
    GENERAL_KB = 2
    EXTERNAL_KB = 3
    GRAPH_KB = 4      # 新增：知识图谱形态（独立类型）

# app/services/kb/kb_format.py
VALID_KB_FORMATS: dict[int, tuple[str, ...]] = {
    1: (),
    2: ("document", "table", "qa"),
    3: ("connector", "proxy"),
    4: ("graph",),   # 新增；预留 graph_table / graph_manual
}
```

**DB 层零迁移**：`kms_knowledge.type` 已是 `Integer`，`kb_format` 已是 `VARCHAR(16)`，仅改列注释。

**约束联动**：

| 约束 | 规则 | 落地点 |
|---|---|---|
| `index_mode` 强制 `high_quality` | economy 无向量则实体无法召回 | `knowledge_service` 创建时归一；前端向导隐藏该选项 |
| `multimodal_enabled` 不适用 | type=4 恒 false | 创建时归一 |
| `external_type` 必须为 NULL | 复用 `validate_external_type` 的 type≠3 拒绝分支 | 自动生效 |
| `kb_format` 创建后不可切换 | 复用 `assert_format_unchanged` | 自动生效 |
| 集合 | 建 1 个集合 `kb_{kid}`，命名约定不变 | 复用 `resolve_knowledge_id` 反查链路 |

### 3.2 三层复用 + 一层新增

```
┌─ 模式层（复用 dataops CDM，零新增表）────────────────────────┐
│ meta_standard_catalog          目录/场景（圈定范围）          │
│ meta_object_standard           实体类型（= 类）               │
│ meta_standard                  属性类型（= 属性标准）          │
│ meta_object_standard_attribute 类→属性约束（必填/复用）        │
│ meta_object_relation           关系类型（= 谓词，含基数）      │
└────────────────────────────────────────────────────────────┘
┌─ 实例层（新增 4 张表）──────────────────────────────────────┐
│ kg_entity          实体实例 = 节点（含向量）                │
│ kg_entity_mention  实体↔切片提及（溯源，幂等）              │
│ kg_triple          关系实例 = 边（含向量）                  │
│ kg_triple_mention  关系↔切片提及（溯源，含抽取依据）        │
└────────────────────────────────────────────────────────────┘
┌─ 切片层（复用 kms_*，仅加 3 个状态列）──────────────────────┐
│ kms_segment  溯源锚点 + 最终召回载体（响应契约不变）        │
└────────────────────────────────────────────────────────────┘
```

### 3.3 `kg_entity`（实体实例 = 节点）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | BigInt PK | |
| `tenant_id` | BigInt | TenantMixin，租户隔离 |
| `knowledge_id` | BigInt | → `kms_knowledge.id`，`ondelete=CASCADE` |
| `entity_id` | String(64) | 稳定 hash：`hashstr(f"{kid}:{normalized_name}:{label}", 32)` |
| `normalized_name` | String(512) | 归一名（小写 + 压缩空白），去重键组成部分 |
| `label` | String(128) | 实体类型标签（受 CDM `meta_object_standard.code` 约束时取其 code） |
| `name` | String(512) | 展示名 |
| `aliases` | JSONB | 别名列表 |
| `attributes` | JSONB | 属性实例 `{属性code: 值}` |
| `embedding` | `Vector(settings.EMBEDDING_DIMENSION)` | 实体向量，同 kb embedding 模型 |
| `vector_status` | String(16) | `pending｜done｜failed` |
| `vector_attempt_count` | Integer | 重试计数 |
| `vector_last_error` | Text | 最近失败原因 |
| `vector_next_retry_at` | TIMESTAMP | 下次重试时间 |
| `vector_locked_until` | TIMESTAMP | 租约到期 |
| `vector_lock_token` | String(64) | 租约令牌 |
| `status` | String(16) | `suggested｜accepted｜rejected`（沿用 dataops 评审语义） |
| `source_segment_ids` | JSONB | 溯源切片 id 列表 |
| `created_at` / `updated_at` | TIMESTAMP | |

约束与索引：
- `Unique(tenant_id, knowledge_id, entity_id)`
- `Unique(tenant_id, knowledge_id, normalized_name, label)` —— **实体归一去重在 PG 层保证**（Yuxi 同款）
- `Index(tenant_id, knowledge_id, label)`、`GIN(aliases)`、`GIN(attributes)`
- 向量索引：HNSW（cosine），与 `kms_segment.embedding` 同度量

### 3.4 `kg_entity_mention`（实体 ↔ 切片提及）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | BigInt PK | |
| `tenant_id` / `knowledge_id` | BigInt | 参与复合外键 |
| `kg_entity_id` | BigInt | → `kg_entity.id`，`ondelete=CASCADE` |
| `segment_id` | BigInt | → `kms_segment.id`，`ondelete=CASCADE` |
| `document_id` | String(64) | `kb_document.uuid_code`，冗余便于文件级撤销 |
| `created_at` | TIMESTAMP | |

约束：`Unique(kg_entity_id, segment_id)`（**提及幂等**，Yuxi 同款）；
复合 FK 让 `knowledge_id` 同时约束两端，杜绝跨库串数据。

### 3.5 `kg_triple`（关系实例 = 边）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | BigInt PK | |
| `tenant_id` / `knowledge_id` | BigInt | |
| `triple_id` | String(64) | 稳定 hash：`hashstr(f"{kid}:{src}:{srcLabel}:{relType}:{tgt}:{tgtLabel}", 32)` |
| `source_entity_id` | BigInt | → `kg_entity.id`，`ondelete=CASCADE` |
| `target_entity_id` | BigInt | → `kg_entity.id`，`ondelete=CASCADE` |
| `relation_type` | String(256) | 关系类型（受 CDM `meta_object_relation.code` 约束时取其 code） |
| `content` | Text | 关系自然语言描述，同时是向量内容 `"src → type → tgt"` |
| `weight` | Float | 抽取置信度 0~1 |
| `embedding` | `Vector(settings.EMBEDDING_DIMENSION)` | 三元组向量 |
| `vector_status` 等 6 列 | | 与 `kg_entity` 同款向量租约列 |
| `status` | String(16) | `suggested｜accepted｜rejected` |
| `source_segment_ids` | JSONB | 溯源切片 id 列表 |
| `created_at` / `updated_at` | TIMESTAMP | |

约束：`Unique(tenant_id, knowledge_id, triple_id)`；
`Unique(knowledge_id, source_entity_id, relation_type, target_entity_id)` —— **关系去重在 PG 层保证**。
索引：`Index(tenant_id, knowledge_id, relation_type)`、`Index(source_entity_id)`、`Index(target_entity_id)`。

### 3.6 `kg_triple_mention`（关系 ↔ 切片提及）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | BigInt PK | |
| `tenant_id` / `knowledge_id` | BigInt | |
| `kg_triple_id` | BigInt | → `kg_triple.id`，`ondelete=CASCADE` |
| `segment_id` | BigInt | → `kms_segment.id`，`ondelete=CASCADE` |
| `document_id` | String(64) | 文件级撤销 |
| `text` | Text | 抽取依据原文片段 |
| `extractor_type` | String(32) | 抽取器类型（`llm`/`semantica`/`manual`） |
| `created_at` | TIMESTAMP | |

约束：`Unique(kg_triple_id, segment_id)`（提及幂等）。

### 3.7 `kms_segment` 新增 3 列（两阶段状态机）

| 列 | 类型 | 说明 |
|---|---|---|
| `graph_structure_indexed` | Boolean | 阶段 1 完成：实体/三元组已落 PG 且已投影 Neo4j |
| `graph_indexed` | Boolean | 阶段 2 完成：实体/三元组向量已写入 pgvector |
| `graph_extraction_details` | JSONB | 抽取详情：实体数、关系数、丢弃数、错误、耗时 |

以 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 落地（对齐 `app/db/startup_migrations.py` 既有模式）。

### 3.8 Neo4j 图结构 schema

```
节点：
  (:Chunk:MwbKG:`mwb_kb_{kid}`)   { chunk_id, kb_id, document_id, chunk_index, content_preview }
  (:Entity:MwbKG:`mwb_kb_{kid}`)  { entity_id, kb_id, normalized_name, label, name, attributes }

关系（仅两种固定类型名，语义类型存属性）：
  (:Chunk)-[:MENTIONS { kb_id, chunk_id, document_id }]->(:Entity)
  (:Entity)-[:RELATION { kb_id, triple_id, type, text, chunk_id, extractor_type }]->(:Entity)
```

**为什么语义关系类型放属性而不是 Neo4j 关系类型**：与 Yuxi 一致。优点是 Cypher 简单、写入幂等
（`MERGE` 单一关系类型 + 属性键）；缺点是 Neo4j 原生按关系类型聚合/约束的能力用不上。
本设计接受该代价——类型约束由 CDM 在 PG 侧承担。

**租户隔离**：每个知识库一个 label `mwb_kb_{kid}`；所有 Cypher 必须写
`MATCH (n:MwbKG:\`mwb_kb_{kid}\`)`；label 名经 `safe_neo4j_label()` 白名单校验。
与 graphiti / semantica 的 label 前缀（`minworkbuddy_*`）无交集。

**PG 是可见性权威**：Neo4j 只是结构投影，读路径必须回 PG 做可见性过滤
（`_filter_visible_subgraph` 等价逻辑），Neo4j 未清理完成也不得发布 PG 不可见内容。

---

## 4. 集成方式与兼容策略

### 4.1 兼容策略总表

| 维度 | 现状 | 扩展后 | 破坏性 |
|---|---|---|---|
| `kms_knowledge.type` | 1/2/3 | 1/2/3/**4** | 无 |
| `kb_format` 矩阵 | 3 行 | 4 行 | 无 |
| `kms_segment` 列 | 现有列 | +3 列（可空/默认值） | 无 |
| 切片存储与向量 | `kms_segment.embedding` | 完全复用 | 无 |
| 集合命名 | `kb_{kid}` | 完全复用 | 无 |
| 检索响应 | `RetrieveResult[]` | **字段不变**，`metadata` 内新增可选键 | 无 |
| Agent / 工具链 | 按 `document_id+chunk_index` 消费 | 零改动 | 无 |
| 现有三个 type 行为 | — | 零改动 | 无 |
| 权限模型 | `require_kb_permission` | 完全复用 | 无 |
| 租户隔离 | `tenant_id` 列 + `TenantScope` | 完全复用 + Neo4j label 隔离 | 无 |

### 4.2 后端接入点

```
app/models/wiki/wiki_knowledge.py       +KnowledgeType.GRAPH_KB=4
app/services/kb/kb_format.py            +VALID_KB_FORMATS[4]=("graph",)
app/models/kb/kg_entity.py              新增
app/models/kb/kg_entity_mention.py      新增
app/models/kb/kg_triple.py              新增
app/models/kb/kg_triple_mention.py      新增
app/services/kb/kg/kg_neo4j_store.py    新增：全部 Cypher 模板 + safe_neo4j_label + 幂等 MERGE
app/services/kb/kg/kg_graph_store.py    新增：PG 投影 upsert + 向量租约认领 + 可见性过滤
app/services/kb/kg/kg_extractor.py      新增：LLM 抽取器（schema 约束 + JSON 容错 + 归一化 + 长度守卫）
app/services/kb/kg/kg_build_service.py  新增：两阶段构建编排 + 单库互斥 + 动作分发
app/services/kb/kg/kg_retriever.py      新增：实体/三元组向量召回 + Neo4j 种子子图 + PPR + 回溯
app/services/kb/kg/kg_config.py         新增：KB 级图谱配置（存 pipeline_config["graph"]）
app/routers/kb/kg.py                    新增：图谱端点（独立 router，前缀 /api/v1/kb）
app/services/kb/document_pipeline.py    +阶段 1/2 调度钩子
app/services/kb/knowledge_service.py    +type=4 的 index_mode/multimodal 归一
app/db/init_models.py                   +注册 4 个新模型
alembic/versions/2026_10_30_*.py        新增 4 表 + kms_segment 加列
```

### 4.3 前端接入点

```
views/kms/KnowledgeBaseManager.vue   +类型下拉 type=4；kb_format 固定 graph；隐藏 index_mode / multimodal；树节点专属图标
views/kms/kg/KbGraphPane.vue         新增：图谱形态主面板（总容器：工具栏 + Tabs + 检视面板）
views/kms/kg/KgOverview.vue          新增：概览（统计 / 类型分布 / 构建状态 / CDM 校验摘要）
views/kms/kg/KgDocumentList.vue      新增：图谱库文档（来源）列表
views/kms/kg/KgGraphView.vue         新增：ECharts 力导向图（复用 StdGraphView.vue 的 GraphChart 方案）
views/kms/kg/KgEntityTable.vue       新增：实体表 + 批量操作
views/kms/kg/KgTripleTable.vue       新增：关系表 + 评审
views/kms/kg/KgProvenance.vue        新增：实体/关系 ↔ 切片 双向溯源
views/kms/kg/KgSearchTester.vue      新增：图谱增强检索测试（融合来源 / 命中路径 / 图谱查询）
views/kms/kg/KgBuildConfig.vue       新增：抽取器 + Schema 约束 + 检索参数
views/kms/kg/KgInspector.vue         新增：检视面板（节点/边详情 + 操作 + 下钻）
views/kms/kg/KgEntityFormModal.vue   新增：实体新增/编辑弹窗
views/kms/kg/KgTripleFormModal.vue   新增：关系新增/编辑弹窗
api/kg.ts                            新增：图谱 API 封装（不塞进已重复的 kb.ts / knowledgeBase.ts）
i18n/locales/*.json                   新增 kbMgmt.kg.* 命名空间
```

图渲染**不引入新依赖**：复用 `StdGraphView.vue` 已验证的 `vue-echarts` + `echarts/core`
`GraphChart` 力导向图方案（仅注册用到的 ECharts 模块，避免整包进首屏）。
仅当实测需要万级节点交互（力导向布局性能不足）时，才评估 AntV G6。

---

### 4.4 前端功能设计

#### 4.4.1 信息架构与入口

| 入口 | 改动 |
|---|---|
| 知识库树 | type=4 使用专属图标（`PartitionOutlined`），与 type=1（`ReadOutlined`）/ type=2（`BookOutlined`）/ type=3（`LinkOutlined`）区分 |
| 主区路由分发 | `KnowledgeBaseManager.vue` 按 `selectedKbType` 分发：`selectedKbType === 4` → `<KbGraphPane :knowledge-id :knowledge-name />`，位置与现有 `KbDocumentPane`（type=2）/ `ExternalLinkPane`（type=3）并列 |
| 新建向导 | 类型下拉加 `type=4`（"知识图谱"）；选中后 `kb_format` 固定为 `graph` 并隐藏选择；隐藏 `index_mode`（强制 high_quality）与 `multimodal_enabled`；分类选择保留 |
| 图谱库内导航 | 顶部工具栏 + 主区 Tabs 两级；检视面板为右侧抽屉（`a-drawer` 或固定右栏），由节点/边点击触发 |

#### 4.4.2 KbGraphPane 总体布局

```
┌─ 工具栏 ─────────────────────────────────────────────────────┐
│ [状态徽标：未构建/构建中/就绪/部分失败/已降级]                │
│ [▶ 构建图谱] [重建] [对账] [重置]  │  [统计] [刷新]         │
├─ 主区 Tabs ───────────────────────────┬─ 检视面板 ──────────┤
│ 概览 │ 文档 │ 图谱 │ 实体 │ 关系 │ 溯源 │ 检索测试 │ 配置    │  KbInspector │
│                                        │  （节点/边详情）    │  （可下钻）  │
└────────────────────────────────────────┴─────────────────────┘
```

Tab 分组理由：与 `StandardManagement.vue`（catalog / graph / attributes 三 Tab + 右侧检视面板）
和 `KbDocumentPane.vue`（按 `formatMode` 切 Tab）保持同一套交互范式，检视面板直接复用
`StdInspector.vue` 的「选中 → 拉详情 → a-descriptions + a-divider + a-list」结构。

#### 4.4.3 Tab「概览」与「文档」

**概览**

| 区块 | 内容 |
|---|---|
| 统计卡片 | 实体数、关系数、实体类型数、关系类型数、已索引切片数、失败切片数（`a-statistic` 网格） |
| 类型分布 | 按 `label` 的实体数条形分布（`a-progress` 列表）；按 `relation_type` 的关系数分布 |
| 构建状态 | 两阶段进度：`graph_structure_indexed` 占比（结构写入）、`graph_indexed` 占比（向量索引）；最近构建时间、耗时、失败步骤名 |
| CDM 校验摘要 | hit / missing / conflict 三态计数（沿用 `meta_relation_check` 词表），点击跳转标准中心对应关系 |
| 快捷入口 | 上传文档（跳「文档」Tab）、构建图谱（跳「配置」Tab 并聚焦）、查看失败清单（跳「溯源」Tab 的失败分组） |


**文档**

图谱库的文档 Tab 是图谱的**来源入口**，与 type=2 文档库同构但归属不同：

| 区域 | 功能 |
|---|---|
| 列表 | 复用 `DocumentManagement.vue`（名称、状态、切片数、失败详情、来源）；状态列额外展示图谱阶段徽标（结构 ✓ / 向量 ✓ / 未抽取） |
| 上传 | 复用现有上传链路（`uploadDocument`）；上传后提示「需构建图谱才会生成实体与关系」，并提供「立即构建」按钮 |
| 流程 | 复用 `DocumentFlowDrawer.vue`，在 parse→clean→chunk→vectorize 之后追加 `graph_extract` 节点 |
| 操作 | 重试（复用 `retryDocument`）、重新向量化（`reprocessDocument`）、重新抽取图谱（新增 `POST /graph/documents/{uuid}/rebuild`）、删除（删除时联动撤销其图谱贡献） |

#### 4.4.4 Tab「图谱」（可视化）

| 区域 | 功能 |
|---|---|
| 视图切换 | `a-segmented`：`全库图` / `按类型过滤` / `种子子图`（同 `StandardManagement.vue` 的 `graphViewOptions` 范式） |
| 筛选器 | 实体类型多选、关系类型多选、跳数 `depth`（1–3，硬上限同后端）、节点上限 `limit`、开关「隐藏 Chunk 节点」 |
| 渲染 | ECharts `GraphChart` 力导向布局；`roam` 缩放平移、`emphasis.focus: 'adjacency'` 邻接高亮；节点 `symbolSize` 按度数映射（凸显枢纽实体）；节点颜色按 `label` 稳定映射（同类型同色）；边标签显示 `relation_type` |
| 交互 | 点击节点/边 → 打开检视面板；节点上「以此为种子扩展」→ 切到种子子图模式重查；悬停显示 tooltip（名称 + 类型 + 提及数） |
| 溯源联动 | 检视面板中点击「在图中定位」→ 切到「图谱」Tab 并高亮该节点/边 |
| 空态 | 未构建 → `a-empty` + 「去构建」按钮；构建中 → `a-spin` + 进度；已降级（Neo4j 不可用）→ `a-alert type="warning"` + 说明 |

**节点/边结构复用**：图视图消费后端 `{nodes, edges}`，字段与 `StandardQueryService.graph()`
保持一致（`nodes[].{id,name,code}`、`edges[].{id,from,to,relation_type}`），因此前端图组件
与后端返回体可与标准中心的图视图共享同一套渲染代码。

#### 4.4.5 Tab「实体」

| 区域 | 功能 |
|---|---|
| 表格列 | 名称、类型（label + CDM 关联 code 徽标）、别名、属性摘要（key-value 前 2 项 + `+N`）、提及数、状态（`suggested/accepted/rejected` 彩色 Tag）、向量状态、更新时间 |
| 筛选 | 类型多选、状态、关键词（名称/别名模糊匹配）、仅看 `suggested` |
| 行操作 | 检视、编辑（`KgEntityFormModal`）、溯源（跳「溯源」Tab 并定位）、删除（`a-popconfirm`） |
| 批量 | 批量接受 `suggested`、批量改 label、批量删除（均需二次确认） |
| 新增/编辑弹窗 | 名称、归一名（只读展示）、label（**CDM 下拉 + 自由输入双模式**：`a-auto-complete` 或 `a-select` + `allow-custom`）、别名（`a-select mode="tags"`）、属性（键值编辑行，key 可从 CDM 属性标准 `a-auto-complete` 选取以对齐 schema） |

#### 4.4.6 Tab「关系」

| 区域 | 功能 |
|---|---|
| 表格列 | 源实体、关系类型（+ CDM 关联 code）、目标实体、权重（置信度）、状态、提及数、抽取器类型 |
| 置信度可视化 | 权重用颜色标记：`< 0.5` 红 / `0.5–0.8` 橙 / `> 0.8` 绿（与 `StdInspector.vue` 的 `verdictColor` 同款写法） |
| 筛选 | 关系类型多选、状态、权重区间 |
| 行操作 | 检视、评审（`a-popconfirm` 接受/驳回 → `PATCH .../status`）、溯源、删除 |
| 新增/编辑弹窗 | 源实体（`a-select` 远程搜索）、关系类型（CDM 下拉 + 自由输入）、目标实体、权重、抽取依据原文 |

#### 4.4.7 Tab「溯源」

双向溯源，是图谱可信度的核心 UI：

| 方向 | 功能 |
|---|---|
| 实体/关系 → 切片 | 左列实体或关系（带搜索下拉）；右列其提及的源切片列表（`chunk_index`、`content_preview`、来源文档名、抽取依据 `text`）；点击切片打开现有 `SegmentDetail.vue` 抽屉复用查看 |
| 文档 → 实体/关系 | 选择一篇 `kms_document`，列出该文档贡献的全部实体与关系（按提及表反查），支持批量移除该文档贡献（对应后端 `clear_document`） |
| 失败分组 | 单独分组展示抽取失败切片（`GET /graph/failed-segments`），每条给出失败步骤与原因，提供「重试该文档构建」 |

#### 4.4.8 Tab「检索测试」

在 `SearchTester.vue` 的交互范式上做图谱增强：

| 区域 | 功能 |
|---|---|
| 搜索栏 | 查询输入、`top_k`、`a-switch` 图谱通道开关（`use_graph_retrieval`）、`a-switch` 对比模式 |
| 单结果模式 | 每条结果显示：`score`（融合分）、来源徽标 `fusion_sources`（`chunk` / `graph` 双色 Tag）、`score_type`、来源文档与 `chunk_index`、内容摘要 |
| 对比模式 | 左列「仅向量」、右列「向量 + 图谱融合」，命中差异高亮；直观看出图谱通道的增量贡献 |
| 命中路径 | 图通道命中项可展开「命中路径」：`实体A ─(关系)→ 实体B ─(关系)→ 命中切片`，路径来自后端返回的 `metadata.graph_path` |
| 图谱查询子模式 | `a-segmented` 切「语义检索」/「图谱查询」；后者支持：实体名 → 邻居列表（1–3 跳）、两实体 → 路径列表 |
| 降级提示 | 后端 `graph_enabled=false` 时顶部 `a-alert type="warning"` 说明「图谱通道已降级，仅返回基础召回结果」 |

#### 4.4.9 Tab「配置」

| 分组 | 字段 |
|---|---|
| 抽取器 | `extractor_type`；`model_spec`（复用模型管理的模型下拉，与 `ai-config` 保持同源） |
| Schema 约束 | `a-radio-group`：`不使用` / `CDM 目录` / `自由文本`；CDM 目录 → `a-tree-select` 选 `catalog_id`（复用 `StdCatalogTree.vue`）；自由文本 → `a-textarea`，占位提示「描述实体类型、关系类型和属性约束」（同 Yuxi `KnowledgeGraphSection.vue` 的提示文案） |
| 抽取参数 | `concurrency_count`（1–1000）、`timeout_seconds`（0–600） |
| 检索参数 | `use_graph_retrieval`、`graph_entity_top_k`、`graph_triple_top_k`、`graph_max_nodes`、`graph_top_k`、`graph_weight`、`ppr_damping` |
| 保存 | 提交 `PUT /kb/knowledges/{kid}` 的 `pipeline_config.graph`；字段超范围由后端校验并回显错误 |

#### 4.4.10 检视面板 `KgInspector`

对标 `StdInspector.vue`（props `selected: {kind:'node'|'edge', id}`，emit 操作事件）：

| 选中 | 展示 | 操作 |
|---|---|---|
| 节点（实体） | 名称、label（+ CDM 关联 code）、归一名、别名、属性表（键值 + CDM 属性标准名）、提及数、状态、向量状态、邻接边列表（可点击跳转） | 编辑实体、删除、溯源下钻、在图中定位、跳到标准中心对应对象标准 |
| 边（关系） | 源 → 目标、relation_type（+ CDM 关联）、权重、抽取依据原文 `text`、extractor_type、状态、提及切片列表 | 编辑关系、评审（接受/驳回）、删除、溯源下钻、在图中定位、跳到标准中心对应关系标准 |

#### 4.4.11 构建状态与轮询

构建为异步后台任务（`job_runner.run_in_background`），前端采用轮询：

- 状态徽标五态：`未构建` / `构建中`（阶段 1 x% · 阶段 2 y%）/ `就绪` / `部分失败` / `已降级（Neo4j 不可用）`
- 轮询：进入图谱库后首次拉 `GET /graph-build/status`；状态为构建中时每 3s 轮询，转为终态即停止（组件 `onUnmounted` 清理定时器）
- 提交构建：本地按钮置 loading + 禁用重复提交；后端 409（已有任务在执行）时提示而非报错
- 进度展示：`kb_document.meta.pipeline_steps` 中的 `graph_extract` 摘要 + `graph_extraction_details`（实体数 / 关系数 / 丢弃数 / 耗时）

#### 4.4.12 降级与错误处理

| 场景 | 前端表现 |
|---|---|
| Neo4j 不可用 | 「图谱」Tab 顶部 `a-alert type="warning"`（说明图结构不可用、检索降级为纯向量）；图区空态给出排查提示；工具栏「构建图谱」禁用并提示原因 |
| semantica 不可用 | 配置页抽取器相关字段禁用 + 提示；构建按钮禁用 |
| 抽取失败 | 文档列表状态列显示失败步骤名（复用现有 `DocumentFlowDrawer.vue` 的流程展示范式）；「溯源」Tab 失败分组可重试 |
| 权限不足 | 复用现有 `require_kb_permission` 语义，前端隐藏无权限操作（编辑/删除/评审） |
| 请求失败 | 统一沿用 `request` 封装的错误提示：`e?.response?.data?.detail || t('kbMgmt.kg.<key>')` |

#### 4.4.13 组件复用矩阵

| 复用对象 | 复用点 | 改动量 |
|---|---|---|
| `StdGraphView.vue` 的 ECharts `GraphChart` 方案 | 图谱 Tab 的力导向图 | 新写 `KgGraphView.vue`，沿用 `use([GraphChart, CanvasRenderer, TooltipComponent])` 的按需注册与 `option` computed 写法 |
| `StdInspector.vue` 的检视面板结构 | `KgInspector.vue` | 新写，沿用 `a-descriptions` + `a-divider` + `a-list` + `a-tag` 结构与 `watch(props.selected, {immediate:true})` 拉详情模式 |
| `StandardManagement.vue` 的 Tabs + 工具栏 + `a-segmented` | `KbGraphPane.vue` 骨架 | 新写，布局一致 |
| `SearchTester.vue` 的检索交互 | `KgSearchTester.vue` | 新写，扩展融合来源/命中路径/图谱查询 |
| `SegmentDetail.vue` | 溯源 Tab 点击切片查看详情 | **零改动直接复用** |
| `DocumentManagement.vue` / `DocumentFlowDrawer.vue` | 「文档」Tab | 复用或轻改（绑定 knowledge_id） |
| `StdCatalogTree.vue` | 配置页 CDM 目录选择 | **零改动直接复用** |
| `@/api/dataops` | CDM 对象/关系/属性标准查询 | **零改动直接复用** |
| `utils/request` | 全部请求 | **零改动直接复用** |

#### 4.4.14 i18n

- 沿用现有 `kbMgmt.*` 命名空间，新增 `kbMgmt.kg.*` 子树（约 60–80 个 key）
- 按现有 locales 集合补齐；新增 key 需在 `frontend/src/i18n/_kb_keys.json` 同步登记
- **注意**：本仓 i18n 为自研实现（模块级 `t` 需按 locale 重挂子树才刷新），新增组件的 `t` 调用
  须沿用现有写法，避免在 locale 切换后显示旧文案


---

## 5. 构建、存储与更新机制

### 5.1 存储选型（明确）

| 存储 | 角色 | 理由 |
|---|---|---|
| PostgreSQL + pgvector | **唯一真相源**：实体/关系/提及事实 + 实体/三元组向量 | 与 `kms_*` 同库同构 → 租户隔离、权限、级联删除、事务一致性天然对齐；向量与 chunk 向量同模型同空间，空间可比 |
| Neo4j 5.x | **必需的图结构投影**：实体/关系/Chunk 提及 | 多跳遍历与 PPR 需要原生图；环境已有 `NEO4J_*` 配置与 `GRAPHITI_GROUP_ID` 隔离先例；PG 递归 CTE 表达力与性能不足 |
| — | ~~Milvus~~ | MinWorkBuddy 无 Milvus；pgvector 足够且免新增组件 |

**写入方向单向**：PG → Neo4j。Neo4j 永远可从 PG 重建（`reconcile` / `rebuild` 动作）。
不做 Neo4j → PG 的反向同步。

### 5.2 构建管线（两阶段）

```
上传文档 → parse → clean → chunk → vectorize
                              ├─ 阶段 1 结构写入
                              │   ├─ LLM 抽取（semantica extract_triplets / 或自建 llm 抽取器）
                              │   ├─ 归一化 + 去重 + 长度守卫
                              │   ├─ PG 投影：kg_entity / kg_triple / *_mention（幂等 upsert）
                              │   ├─ Neo4j 投影：MERGE 节点与 MENTIONS/RELATION 关系
                              │   └─ segment.graph_structure_indexed = True
                              └─ 阶段 2 向量索引
                                  ├─ 实体内容 = "{name}｜{label}｜{aliases}"
                                  ├─ 三元组内容 = "{src} → {relation_type} → {tgt}"
                                  ├─ pgvector upsert → kg_entity.embedding / kg_triple.embedding
                                  └─ segment.graph_indexed = True
```

**为什么挂在 `document_pipeline.run_document_ingest` 之后**：抽取需要切片全文（chunk 已产出），
实体向量要复用同一 embedding 模型（`embedding_factory`，与 `kms_segment` 同模型同维度），
顺序上必须先有切片、再抽实体、最后嵌实体。

**为什么分两阶段**：PG 投影成功但 Neo4j 写入失败、或向量写入失败，都需要能断点续跑而不重复抽取。
`graph_structure_indexed` / `graph_indexed` 两个标志是**对外契约**，重跑时据此跳过已完成阶段
（Yuxi `service.py:447-457` 同款）。

### 5.3 抽取器

优先复用 `app/services/semantica/`：

- `SemanticaClient.extract_triplets(text, entities, relations)` → 实体 + 关系
- `SemanticaClient.deduplicate(entities)` → 实体归一去重
- `SemanticaClient.detect_conflicts(entities)` → 冲突检测
- `SemanticaClient.build_graph(entities, relationships)` → 图构建

在此之上补 Yuxi 式的**输出规整层**（`kg_extractor.py`）：

| 规则 | 行为 |
|---|---|
| 归一化 | `normalize_entity_name` = 小写 + 压缩空白 |
| 长度守卫 | `MAX_ENTITY_NAME_LENGTH=512` / `MAX_ENTITY_LABEL_LENGTH=128` / `MAX_RELATION_TYPE_LENGTH=256`，越界**丢弃而非抛错**，计入 `dropped_entities` / `dropped_relations` |
| 悬空关系 | 端点实体被丢弃时，关系一并丢弃 |
| schema 约束 | CDM 来源（`catalog_id` 圈定 `meta_object_standard` / `meta_object_relation`）或自由文本，拼入抽取 prompt；类型取值受 CDM code 约束，抑制 Yuxi 的类型漂移 |
| JSON 容错 | 解析失败重试 + 结构化错误上报（不静默吞掉） |

**为何不直接用 `SemanticaClient.neo4j_store()` 写图**：semantica 的 `Neo4jStore` 无法施加
本设计要求的「每知识库 label 隔离 + `MENTIONS`/`RELATION` 统一关系类型 + 幂等 MERGE 模板 +
PG 可见性回读」四项约束。因此**抽取借用 semantica，落图用自有的 Cypher 模板层**
（`kg_neo4j_store.py`），两者职责分离、边界清晰。

### 5.4 幂等与增量

| 场景 | 行为 |
|---|---|
| 重复构建 | 实体按 `(knowledge_id, normalized_name, label)` upsert；关系按 `(knowledge_id, source, relation_type, target)` upsert；提及按 `(entity, segment)` upsert —— **不产生重复** |
| 文档重处理 / rechunk | 先清该文档贡献的提及与边，再重抽（切片 id 变了需重挂） |
| 文档删除 | `clear_document` 动作：删该文档的 `*_mention` → 删失去全部提及的实体与边 → 从 Neo4j `DETACH DELETE` 对应节点 |
| 全量重建 | `rebuild` 动作：清空该库 `kg_*` + Neo4j 该 label 全部节点，重抽 |
| 对账 | `reconcile` 动作：比对 PG 事实与 Neo4j 投影差异，补写缺失项 |
| 向量重试 | 租约列 + `FOR UPDATE SKIP LOCKED` 认领，`vector_next_retry_at` 到期重试 |

### 5.5 后台作业与互斥

- 提交：`kg_build_service.submit_build(kid, action, ...)` → `job_runner.run_in_background(...)`
- **单库互斥**：进程内 `kg_locks` 登记表（对齐 `job_runner._TASKS` 模式），提交时 try-acquire，
  失败返回 409「该知识库已有图谱任务在执行」（Yuxi `services/graph_build.py:26-103` 同款）
- 任务函数**必须自建并关闭 Session**（`job_runner` 硬约束）
- 动作分发：`build` / `clear_document` / `rebuild` / `reconcile`
- 进度上报：沿用 `kms_document.meta.pipeline_steps` 追加 `{"step": "graph_extract", ...}`，
  并新增 `graph_extraction_details`

### 5.6 失败可观测

- 单步失败抛 `PipelineStepError(step, cause)`（沿用 kb 既有约定，`step` 取 `graph_extract`）
- 失败写 `kms_document.error_detail`（形如 `[graph_extract] …`）与 `meta.failed_step`
- **图谱失败不回滚文档摄取**：文档保持 `completed`（切片可用），图谱标记未就绪——
  降级但**显式**，不静默伪装成功
- `GET /kb/knowledges/{kid}/graph/stats` 暴露实体/关系/类型分布与构建状态
- `GET /kb/knowledges/{kid}/graph/failed-segments` 暴露抽取失败切片（对齐 Yuxi `failed-chunks`）

---

## 6. 检索与查询能力设计

### 6.1 核心兼容点：产物形态不变

**图谱检索的最终产物仍是 chunk 级 `RetrieveResult[]`**。图谱是**内部召回通道**，不是新的响应契约。
Agent 侧、工具侧、现有前端全部零改动。

融合分数写入 `score`（保持"越大越相关"的既有语义），融合来源写入 `metadata.fusion_sources`
与 `metadata.score_type`，**既有字段语义不变**。

### 6.2 检索编排（type=4 走此分支）

```
POST /api/v1/kb/knowledges/{kid}/retrieve   body: {query, top_k, hybrid, metadata_filters}
  │
  ├─ 基础召回（现有）：向量 / 关键词 / hybrid（kb_segment）
  │
  ├─ 图召回（开关 use_graph_retrieval，默认开）：
  │   ├─ 实体向量检索  kg_entity   （top_k = graph_entity_top_k，默认 10）
  │   ├─ 三元组向量检索 kg_triple  （top_k = graph_triple_top_k，默认 10）
  │   ├─ 种子权重 = 实体/三元组向量命中 + 已召回 chunk
  │   ├─ Neo4j 种子子图：(seed:Entity)-[*1..2]-(n)
  │   ├─ PPR：networkx pagerank(personalization=reset, damping=0.85)，仅 Chunk 节点出分
  │   └─ 回 PG 取 chunk 正文 + 可见性过滤
  │
  └─ RRF 融合：score = weight / (rrf_k + rank)，rrf_k=60
       基础召回权重 1.0，图召回权重 graph_weight（默认 1.0）
       → 取 top_k，metadata 附 fusion_sources / score_type
```

**响应契约（type=4）**——既有字段语义不变，仅在 `metadata` 内新增可选键：

```jsonc
{
  "results": [
    {
      "score": 0.032,                    // 融合分，仍是「越大越相关」
      "document_id": "…",
      "chunk_index": 3,
      "content": "…",
      "metadata": {
        "fusion_sources": ["chunk", "graph"],   // 命中通道（前端双色徽标）
        "score_type": "fusion",                 // fusion | chunk
        "graph_path": [                         // 仅图通道命中时存在：命中路径
          { "entity_id": "…", "name": "客户A", "label": "客户" },
          { "entity_id": "…", "name": "订单B", "label": "订单" },
          { "relation_type": "属于" }
        ]
      }
    }
  ],
  "index_mode": "high_quality",
  "graph_enabled": true,               // false = 图通道降级（Neo4j 不可用）
  "graph_stats": { "entities": 128, "relations": 356 }   // 可选，调试用
}
```

**降级链**：Neo4j 不可用 / 图召回异常 → 图通道返回空，**不阻断主检索**，响应标
`graph_enabled=false`。这与 Yuxi `implementations/milvus.py:1236-1238` 同款，也与本仓
`standard_query_service.nl_query` 的"LLM 异常降级不 500"是同一条既有原则。

**多跳硬封顶 3 跳**，`path_limit = limit * 10`，防止无界遍历。

### 6.3 新增图谱专用端点（旁路，不混入 retrieve）

前缀 `/api/v1/kb/knowledges/{kid}/graph`：

| 端点 | 用途 |
|---|---|
| `GET /subgraph?entity_ids=&depth=1&limit=` | 子图；返回 `{nodes, edges}`，**结构对齐 `StandardQueryService.graph()`**，前端图组件可直接复用 |
| `GET /subgraph/seed?seed_ids=&depth=&limit=` | 种子子图（多跳起点） |
| `POST /paths` | 路径查询（A→B→C 两跳路径） |
| `GET /entities` | 实体列表（按 label / status / 关键词过滤，分页） |
| `GET /entities/{entity_id}` | 实体详情 + 属性 + **溯源切片** + 邻接边 |
| `PUT /entities/{entity_id}` | 实体修订（改名 / 改 label / 改属性） |
| `GET /triples` | 关系列表（按 relation_type / status 过滤，分页） |
| `PATCH /triples/{triple_id}/status` | 评审流转（suggested→accepted/rejected） |
| `GET /labels` | 实体类型分布（对齐 Yuxi `/graph/labels`） |
| `GET /stats` | 实体/关系/类型分布 + 构建状态 |
| `GET /failed-segments` | 抽取失败切片清单 |
| `POST /documents/{uuid}/rebuild` | 仅对指定文档重抽图谱（前端「文档」Tab 的「重新抽取图谱」） |
| `POST /build` | 提交构建（`action` = build/clear_document/rebuild/reconcile） |
| `GET /build/status` | 构建状态与进度 |

构建管理端点另设 `/api/v1/kb/knowledges/{kid}/graph-build/*`（对齐 Yuxi 的
`graph-build/status`、`graph-build/index`、`graph-build/files/{file_id}/clear`、`graph-build/reset`、
`graph-build/reconcile`），避免与查询端点混在一个 router。

### 6.4 KB 级图谱配置

存于 `kms_knowledge.pipeline_config["graph"]`（**不新增列**）：

```json
{
  "extractor_type": "llm",
  "model_spec": { "provider": "...", "model": "..." },
  "schema_source": "cdm",
  "catalog_id": 12,
  "schema": "自由文本约束（schema_source=free_text 时生效）",
  "concurrency_count": 8,
  "timeout_seconds": 60,
  "use_graph_retrieval": true,
  "graph_entity_top_k": 10,
  "graph_triple_top_k": 10,
  "graph_max_nodes": 10000,
  "graph_top_k": 20,
  "graph_weight": 1.0,
  "ppr_damping": 0.85
}
```

### 6.5 与 CDM 模式层的双向校验（复用 `MetaRelationCheck` 模式）

图谱实例层的边 → 映射到 `meta_object_relation` 校验，产出 `hit/missing/conflict` 结论：

| verdict | 含义 |
|---|---|
| `hit` | 图谱中的边与标准关系一致 |
| `missing` | 标准声明了关系但图谱实例中缺失（数据覆盖不足） |
| `conflict` | 图谱中的边违反标准约束（如基数 `1:1` 却出现多边） |

沿用 `meta_relation_check` 表结构与 `verdict` 词表，**不新建词表**。

### 6.6 Agent 工具

新增 `kg_query` 工具（`app/ai/tools/kg_tools.py`，仿 `ontology_tools.py` 模式，
**不依赖 ontology 模块任何符号**——它正随 semantica 迁移被删）：

| 子命令 | 用途 |
|---|---|
| `entity_search` | 语义检索实体 |
| `neighbors` | 实体邻接（1~3 跳） |
| `paths` | 两实体间路径 |
| `stats` | 图谱统计 |

租户链路沿用 `ontology_tools` 的做法：`get_tool_user()` → 查 `SysUser.tenant_id`；
取不到租户返回 `tenant_required`，**绝不落到 NULL 分区共享图谱**。

---

## 7. 开发阶段划分与优先级

| 阶段 | 内容 | 优先级 | 依赖 | 验收标准 |
|---|---|---|---|---|
| **P0** 前置对齐 | 确认 semantica 迁移完成、ontology 清理完成、CDM 模式层 API 可用、Neo4j 可连通 | **阻塞项** | 另一进程 | ✅ **已验证（2026-10-30）**：`GET /api/v1/dataops/standards/graph` 返回 nodes/edges；`NEO4J_ENABLED=true` 且 `RETURN 1` 成功 |
| **P1** 类型骨架 + 实例层 | type=4 枚举、`kb_format[4]`、4 张新表 + 迁移 + `kms_segment` 加列、实体/关系 CRUD + 权限；**前端**：向导 type=4 分支、树节点图标、`KbGraphPane` 空壳 + 概览/文档/实体/关系 Tab | **P0** | P0 | 能建图谱库；手工增删实体关系；租户隔离与权限用例通过；存量 3 类 type 行为零变化；前端 `npm run build` 无新增错误 |
| **P2** Neo4j 投影层 | `kg_neo4j_store.py`（Cypher 模板集中 + `safe_neo4j_label` + 幂等 MERGE）、PG→Neo4j 投影、PG 可见性回读 | **P0** | P1 | 手工建的实体/关系在 Neo4j 中可见；label 隔离生效；`DETACH DELETE` 可完整撤销 |
| **P3** 构建管线 | 抽取器 + 两阶段构建编排 + 单库互斥 + 幂等 upsert + 溯源 + 失败可观测；**前端**：构建配置 Tab、构建状态轮询与徽标、失败清单 | **P0** | P2 | 上传文档 → 产生实体/边且溯源可回跳切片；重复构建不产生重复；Neo4j 写入失败可断点续跑；图谱失败不影响文档可用；前端可提交构建并看到两阶段进度 |
| **P4** 检索增强 | 实体/三元组向量召回 + Neo4j 种子子图 + PPR + RRF 融合；**前端**：增强检索测试 Tab（融合来源徽标、对比模式、命中路径、图谱查询子模式） | **P0** | P3 | `retrieve` 响应字段不变；能召回跨文档关系链路的切片；`fusion_sources` 正确；Neo4j 不可用时降级不 500 且前端显示降级提示 |
| **P5** 图谱浏览与治理 | 子图/路径/实体检视面板、ECharts 图视图、评审流转（suggested→accepted）、统计；**前端**：图谱 Tab（筛选/种子扩展/在图中定位）、`KgInspector` 检视面板、溯源 Tab | **P1** | P4 | 图视图可交互下钻；评审闭环；构建状态可见；实体/关系可从检视面板下钻到溯源切片 |
| **P6** Agent 工具与生态对接 | `kg_query` 工具、CDM↔图谱双向校验（hit/missing/conflict）、图谱导出；**前端**：概览 Tab 的 CDM 校验摘要 + 跳转标准中心 | **P2** | P5 | Agent 可多跳问答；校验产出三种结论 |
| **P7（可选）** | KG 流水线可视化画布、时序图谱、GDS 插件替代 networkx PPR | **P3** | P6 | 仅在有实测性能数据支撑时立项 |

### 7.1 实施状态（2026-10-31）

| 阶段 | 状态 | 交付要点 |
|---|---|---|
| P0 | ✅ 已验证 | semantica/ontology/CDM/Neo4j 四项门禁全部通过 |
| P1 | ✅ 已交付 | type=4、4 张实例表、CRUD+评审、12 端点、前端向导与主面板 |
| P2 | ✅ 已交付 | `kg_neo4j_store.py`（Cypher 集中 + label 白名单 + 幂等 MERGE）+ `kg_graph_store.py`（PG→Neo4j 投影/撤销/对账），并接入 CRUD 写入路径（best-effort 降级） |
| P3 | ✅ 已交付 | `kg_extractor.py`（长度守卫/归一化/CDM 约束/容错）、`kg_build_service.py`（两阶段状态机 + 单库互斥 + 四种动作）、`kg_config.py`、切片三列迁移、构建端点；前端配置 Tab + 状态轮询徽标 + 失败清单 |
| P4 | ✅ 已交付 | `kg_retriever.py`（向量召回 → 种子子图 → PPR → 回 PG 过滤）、加权 RRF 融合接入 `retrieve`（type=4 分支）、降级链 `graph_enabled=false`；前端增强检索测试 Tab |
| P5 | ✅ 已交付 | 子图/种子子图/邻接/路径/类型分布端点（PG BFS，跳数封顶 3）、实体溯源端点；前端图谱 Tab（ECharts 力导向）+ `KgInspector` 检视面板 + 溯源 Tab |
| P6 | ✅ 已交付 | `kg_query` Agent 工具（4 子命令，租户 fail-closed，已注册进工具 seed）、CDM↔图谱校验（hit/missing/conflict + uncovered 诊断）、图谱导出（json/csv）；前端概览 CDM 校验摘要 |

**验证**：`tests/kb` **437 passed**（P1 时 313，新增 124 项）；前端 `npm run build` 中本次改动文件 **0 类型错误**。

**明确不做**：时序图谱、推理引擎、跨库图谱、Milvus/新向量库、AntV G6 新依赖。

---

## 8. 潜在风险与应对

| # | 风险 | 影响 | 应对 |
|---|---|---|---|
| R1 | **并行改造冲突**：semantica/ontology 清理正在另一进程进行 | 高 | 设 P0 门禁。本方案**只新增 `kg_*` 文件**，仅改 `KnowledgeType` 枚举、`kb_format` 矩阵、`knowledge_service` 归一两处；不触碰 ontology/semantica 内部。对 `SemanticaClient` 的依赖**只经其公开方法**，便于加适配层 |
| R2 | **Neo4j 不可用或与 graphiti 争抢实例** | 高 | `NEO4J_ENABLED` 开关 + 构造期探测（`RETURN 1`）；图通道失败降级为空不阻断检索；label 前缀 `mwb_kb_*` 与 graphiti / semantica 无交集；连接单例 + 有界卸载线程池（对齐 Yuxi `offload.py`） |
| R3 | 抽取质量与成本（LLM 抽取慢且贵） | 高 | 异步后台任务 + 分批 + 并发上限（1~1000，默认 8）+ 超时上限（600s）+ 仅对 `completed` 文档抽取 + 抽取结果按切片内容哈希缓存；提供"仅对指定文档建图"入口 |
| R4 | 实体合并歧义（同一实体多形态） | 中 | 归一化规则 + PG 唯一约束 `(normalized_name, label)` + `suggested` 评审态 + 溯源可见；冲突检测复用 semantica `detect_conflicts` |
| R5 | **向量维度/模型不一致**（历史故障高发区） | 高 | 实体/三元组向量**复用 kb 的 `embedding_factory`**，物理列 `Vector(settings.EMBEDDING_DIMENSION)`，写入前 `fit_vector_dimension` 对齐；**严禁**另起 embedder；向量内容与 chunk 向量同空间以支持融合 |
| R6 | 图遍历性能（PPR 在 Python 侧算） | 中 | 跳数硬限 ≤3 + `graph_max_nodes` 上限 + `path_limit = limit*10`；规模再大时评估 Neo4j GDS 插件（列为 P7 可选） |
| R7 | PG↔Neo4j 投影不一致 | 中 | PG 为唯一真相源，Neo4j 仅投影；`reconcile` 动作可补齐差异；读取路径回 PG 做可见性过滤，不信任 Neo4j 的存在性 |
| R8 | 权限 / 租户越权 | 高 | `kg_*` 四表全带 `tenant_id`；路由层复用 `require_kb_permission`；复合 FK 让 `knowledge_id` 参与外键；Neo4j label 经白名单校验；Agent 工具取不到租户返回 `tenant_required` |
| R9 | 检索契约破坏 | 高 | 响应**只增不改**（新字段全部落在 `metadata` 内且 optional）；`RetrieveResult` 既有字段语义不变；契约测试锁定 |
| R10 | 前端工具链已损坏（`npm run lint` 全仓 380 Parsing error） | 中 | 验证一律用 `npm run build 2>&1 \| Select-String "<自己改的路径>"` 过滤；不在本方案中修工具链 |
| R11 | `class_uris` 列语义改写影响既有检索 | 中 | 该列当前**无任何写入方**（ontology 清理后为空），改写为"图谱实体类型"无存量数据冲突；改写前后各跑一次检索基线对比 |
| R12 | 类型漂移（Yuxi 的已知短板） | 中 | CDM 作为可选 schema 约束来源；关系/实体类型取值受 `meta_object_standard.code` / `meta_object_relation.code` 约束；未约束时保留自由文本 schema 通道 |
| R13 | 范围蔓延（图谱是无底洞） | 中 | P0–P6 阶段清单 + 明确不做清单；每阶段独立可验收，未验收不进入下一阶段 |
| R14 | **前端 8 个 Tab 交互密度过高**，图谱库变成"第二个标准中心" | 中 | 概览作为唯一"看板"入口，其余 Tab 均为任务视图；检视面板统一承载详情，避免每 Tab 各造一套详情；组件拆分以「一个 Tab 一个文件」为界，不做通用配置驱动 |
| R15 | **ECharts 力导向图在实体规模增大后卡顿** | 中 | 节点上限 `limit`（默认 200，可配）+ `graph_max_nodes` 后端硬限；`label: {show: false}` 在节点数超阈值时自动关闭；仅当实测 >1000 节点仍不可用时才评估 AntV G6 |
| R16 | **前端 i18n locale 刷新** | 低（**已消解**） | **事实更正**：现为标准 `vue-i18n`（`legacy: false`），点号路径（`kbMgmt.kg.*`）与 locale 切换均原生响应式，不存在「模块级 `t` 需重挂子树」的自研陷阱。新增组件沿用 `useI18n()` 写法即可；新增 key 已同步登记 `frontend/src/i18n/_kb_keys.json` |
| R17 | **构建轮询泄漏**（离开页面后仍在轮询） | 低 | 轮询定时器在 `onUnmounted` 清理；状态转终态即停；同一图谱库只允许一个轮询实例（`KbGraphPane` 持有，Tab 子组件通过 props 接收状态而非各自轮询） |

---

## 9. 实施决策清单（待确认）

1. **存储**：PG（权威事实 + pgvector 向量）+ Neo4j（必需，图结构投影），单向下写，Neo4j 可重建。
2. **抽取**：借 semantica 的 extract/dedup/conflicts；落图用自有的 Cypher 模板层（保证 label 隔离与幂等 MERGE）。
3. **检索**：基础召回 + Neo4j 种子子图 + PPR + RRF(rrf_k=60)；产物仍是 chunk 级，契约不变。
4. **两阶段状态机**：`graph_structure_indexed` / `graph_indexed`，支持断点续跑。
5. **类型约束**：CDM 为可选 schema 来源，抑制 Yuxi 的类型漂移短板。
6. **图渲染**：复用既有 ECharts GraphChart，零新前端依赖。

### 9.1 前端关键决策

| # | 决策 | 选择 | 理由 |
|---|---|---|---|
| F1 | 图谱库主面板结构 | 工具栏 + 8 Tab + 右侧检视面板 | 对标 `StandardManagement.vue`（Tabs + 检视面板）与 `KbDocumentPane.vue`（按形态切 Tab），交互范式统一 |
| F2 | 检视面板归属 | 独立 `KgInspector.vue` 组件，**不塞进 8 个 Tab** | 避免每个 Tab 各造详情；点节点/边从任意 Tab 都能唤出同一详情面板 |
| F3 | 图渲染库 | 复用 `vue-echarts` + `echarts/core` 的 `GraphChart` | 零新依赖；`StdGraphView.vue` 已验证。仅 >1000 节点实测不达标才考虑 AntV G6 |
| F4 | 节点/边数据形状 | 与 `StandardQueryService.graph()` 一致（`nodes[].{id,name,code}` / `edges[].{id,from,to,relation_type}`） | 图渲染代码可与标准中心共享；后端两处返回体统一 |
| F5 | 详情组件复用 | `SegmentDetail.vue`、`StdCatalogTree.vue`、`DocumentFlowDrawer.vue`、`@/api/dataops` **零改动复用** | 最大化复用，减少新代码面 |
| F6 | 检索测试 | 新写 `KgSearchTester.vue`，不改造 `SearchTester.vue` | `SearchTester.vue` 服务于旧 `knowledgeBase` API 通道且已有技术债；新写避免污染存量 |
| F7 | API 模块 | 新建 `frontend/src/api/kg.ts` | `api/kb.ts` 与 `api/knowledgeBase.ts` 已存在职责重复，不再加剧 |
| F8 | 轮询归属 | 轮询状态由 `KbGraphPane` 持有并以 props 下发 | 避免 8 个 Tab 各自轮询造成泄漏与重复请求 |
| F9 | 双向溯源 | 「溯源」Tab 同时支持 实体/关系→切片 与 文档→实体/关系 | 后端 `*_mention` 表双向可查；文件级撤销（`clear_document`）需要文档视角 |
| F10 | 前端验收方式 | `npm run build 2>&1 \| Select-String "<自己改的路径>"` 过滤 | 本仓 eslint 工具链已损坏（全仓 380 Parsing error），`npm run lint` 不可用 |

### 9.2 依赖现状核实

| 依赖 | 状态 | 说明 |
|---|---|---|
| `neo4j>=5.23,<6` | **已就位**（`backend/requirements.txt:11`） | Neo4j Python 驱动，无需新增 |
| `semantica[vectorstore-pgvector]==0.7.0` | **已就位**（`requirements.txt:44`） | 抽取 / 去重 / 冲突检测 / 图构建 / pgvector |
| `rdflib>=7.0.0` | **已就位**（`requirements.txt:118`） | semantica 传递依赖保留 |
| `networkx` | **未安装，需显式新增** | Yuxi 的 PPR 用它（`nx.pagerank(personalization=reset)`）。纯 Python、无编译依赖，风险低。**不可依赖 semantica 的传递依赖**，须在 `requirements.txt` 显式声明 `networkx>=3.2` |
| Neo4j 服务端 | 环境已有 | 基础设施 `mwb-neo4j`；`NEO4J_ENABLED` / `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` / `GRAPHITI_GROUP_ID` 已存在于 `app/config/_semantica.py`（实测 `RETURN 1` 成功） |
| Milvus / AntV G6 | **不引入** | 见 §1.4 非目标 |

### 9.2 向量 ANN 索引：当前维度下不建（P1 实测结论）

生效维度实测为 **2048**（`settings.EMBEDDING_DIMENSION`，随 `EMBEDDING_PROVIDER` 解析），
**超出 pgvector HNSW 的 2000 维上限**（`column cannot have more than 2000 dimensions for hnsw index`）。
且既有 `kms_segment.embedding`（同为 `vector(2048)`）在全库**没有** ANN 索引——
本项目在 2048 维下即以顺序扫描做向量检索。

因此 `kg_entity.embedding` / `kg_triple.embedding` **只建列、不建 ANN 索引**，
与既有段表保持同一策略；P3/P4 真正写入向量后，再按实测数据选型
（IVFFlat 支持至 16000 维，或降维 / `halfvec`），避免无性能数据支撑的投机性索引。

### 9.3 租户归属：知识库创建必须落 tenant_id（P1 实测结论）

生产环境在 `main.py` 注册了 SQLAlchemy 租户拦截器
（`app/core/tenant_interceptor.py`，`with_loader_criteria` 按 `tenant_id` 自动追加过滤条件），
而 `get_current_user` 会设置租户上下文。实测：上下文 `tenant=1` 时
`select(WikiKnowledge)` 仅返回 **0/12** 行——因为既有 12 个知识库的 `tenant_id` 均为 NULL，
**对任何租户都不可见**。

结论：知识库创建链路（`knowledge_mgnt.create_knowledge` / `knowledge_service.create`）
必须显式落 `tenant_id`（沿用 `article_service` 的既有写法）。
这既是图谱库「建了却打不开」的前置修复，也同时修正了 type=1/2/3 的既有租户归属缺陷。

### 9.3 范围与拆分结论

本设计跨 7 个阶段，**不适合作为单一实施计划一次性交付**。按 brainstorming 约定，
实施计划从 **P0 → P1** 开始独立成环（P1 交付可用的图谱库容器与实例层 CRUD，
不依赖 Neo4j 即可验收），后续 P2/P3 各自成环。
P0 为**外部依赖门禁**（另一进程的 semantica 迁移与 ontology 清理），不由本方案交付。
