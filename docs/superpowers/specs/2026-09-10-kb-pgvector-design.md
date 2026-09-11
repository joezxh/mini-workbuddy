# P1 · 知识库内核设计（基于 AgentScope 原生 RAG Service）

> 状态：待评审
> 日期：2026-09-10（v2 重写）
> 依赖：无（地基）
> 被依赖：P2（业务数据入湖）、P3（第三方源同步落点）、P4（本体驱动检索）
> 前端（管理台）设计：见 `2026-09-10-knowledge-governance-frontend-design.md` §8（菜单项：知识治理 → 知识库）

---

## 0. v2 变更说明（相对 v1）

v1 假设"知识库需自研"，经核实 **AgentScope 2.0.7.post1 本地已内置完整 RAG Service**，故重写：

| v1 自研内容 | v2 处理 |
|---|---|
| `kb_dataset` / `kb_document` / `kb_segment` / `kb_ingestion_job` 四张表 | **删除** —— RAG Service 用 storage 层持久化 |
| 数据集/文档/切片/任务的完整 REST API | **删除** —— 直接复用 `/knowledge_bases/*` |
| 入库任务编排（分段进度、重试） | **删除** —— RAG Service 自带状态机 + 租约 + 心跳 + 自愈 |
| `MWBEmbeddingAdapter(EmbeddingModelBase)` 代码实现 | **简化为配置映射** —— GPUStack→OpenAI provider，DashScope→原生 provider |
| `PGVectorStore(VectorStoreBase)` | **保留**（唯一必须自研的核心件） |
| `pg_trgm` 中文混合检索 + RRF | **保留** |
| 租户隔离 | **改为 user_id 映射**（机制变了，见 §5） |

**AgentScope 版本策略**：不升级，锁定 `2.0.7.post1`（当前已安装）。

---

## 1. 已核实的事实（本地 `agentscope 2.0.7.post1`）

```
agentscope/app/_app.py:78        create_app(...) -> FastAPI
agentscope/app/rag/
  blob_store/                    LocalBlobStore / S3BlobStore
  index_worker/                  CLI + library 两种启动方式
  knowledge_base_manager/        CollectionPerKbManager / DimensionPolicy
agentscope/rag/
  _parser/                       pdf · word · excel · ppt · text · image
  _chunker/                      ApproxTokenChunker（可扩展）
  _knowledge.py                  KnowledgeBase
  _vdb/                          VectorStoreBase + qdrant/milvus_lite/mongodb/elasticsearch
agentscope/middleware/_rag.py    RAGMiddleware
agentscope/embedding/            openai · dashscope · ollama · gemini
```

### 1.1 `create_app` 关键参数（本地实测）

```python
def create_app(
    storage: StorageBase,                        # 必需
    message_bus: MessageBus,                     # 必需
    workspace_manager: WorkspaceManagerBase,     # 必需
    knowledge_base_manager: KnowledgeBaseManagerBase | None = None,
    knowledge_parsers: list[ParserBase] | dict[str, ParserBase] | None = None,
    knowledge_chunkers: list[Type[ChunkerBase]] | None = None,
    blob_store: BlobStoreBase | None = None,
    enable_index_worker: bool = True,
    ...
) -> FastAPI
```

**挂载方式（官方 docstring 明确支持）**：

```python
root = FastAPI()
agentscope_app = create_app(
    storage=RedisStorage(),
    message_bus=RedisMessageBus(),
    workspace_manager=LocalWorkspaceManager(),
)
root.mount("/agentscope", agentscope_app)
```

### 1.2 `CollectionPerKbManager` 关键行为

- **维度策略 = `DimensionPolicyKind.ANY`** —— 每个知识库可自由选择 embedding 维度
  → 与 MWB 的 768（Qwen3-Embedding-4B）/ 1024（text-embedding-v3）**混用兼容**，无需统一
- **collection 名 = `kb_<uuid_hex>`，不含 user_id**
  → 隔离**不靠 collection 命名**，而靠 manager/storage 层按 `user_id` 过滤（见 §5 风险）
- 所有方法首参为 `user_id: str` → **多租户天然按 user_id 隔离**

### 1.3 Embedding provider 可用性

| MWB 现状 | AgentScope 原生 | 结论 |
|---|---|---|
| `GPUSTACK_API_URL=http://192.168.40.30/v1`、`Qwen3-Embedding-4B`、768 维 | `OpenAIEmbeddingModel`（OpenAI 兼容，可配 base_url） | **直接映射** |
| `DASHSCOPE_EMBEDDING_MODEL=text-embedding-v3`、1024 维 | `DashScopeEmbeddingModel` | **原生支持** |

→ **无需自定义 `EmbeddingModelBase` 实现**，只需配置映射。

---

## 2. 架构

```
┌──────────────────────────────────────────────────────────────┐
│ MinWorkBuddy FastAPI（现有）                                   │
│   app.mount("/agentscope", agentscope_app)                    │
└──────────────┬───────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────┐
│ AgentScope RAG Service（原生，复用）                            │
│   /knowledge_bases/*         CRUD · 上传 · 状态 · 检索          │
│   Index Worker               解析→切片→embedding→写向量         │
│   Index Sweeper              租约过期/卡死任务重派发             │
│   BlobStore                  Local / S3                       │
│   RAGMiddleware              Agent 侧检索注入                   │
└──────────────┬───────────────────────────────────────────────┘
               │ 依赖注入
┌──────────────▼───────────────────────────────────────────────┐
│ 自研（仅两项）                                                  │
│   ① PGVectorStore(VectorStoreBase)  PG 适配 + 中文混合检索       │
│   ② UserIdMapper                    MWB tenant → AS user_id    │
│   （可选③ QaChunker / SemanticChunker）                         │
└──────────────────────────────────────────────────────────────┘
```

**基础设施依赖**：Redis（`RedisStorage` + `RedisMessageBus`）—— MWB 已有 Redis Stack ✓

---

## 3. 自研件一：`PGVectorStore(VectorStoreBase)`

### 3.1 为何必须自研

`agentscope/rag/_vdb/` 仅提供 **qdrant / milvus_lite / mongodb / elasticsearch**，**无 pgvector**。而 MWB 已运行 `pgvector/pgvector:pg17`，引入 Qdrant 等于新增中间件，与"复用现有 PG"的目标冲突。

### 3.2 契约（本地 `VectorStoreBase`）

```python
async def create_collection(name: str, dimensions: int) -> None
async def delete_collection(name: str) -> None
async def has_collection(name: str) -> bool
async def insert(collection: str, records: list[VectorRecord]) -> None
async def delete(collection: str, document_id: str) -> None
async def search(collection: str, query_vector: list[float],
                 top_k: int = 5,
                 metadata_filter: dict | None = None) -> list[VectorSearchResult]
async def list_documents(collection: str) -> list[DocumentSummary]
async def list_chunks(collection: str, document_id: str,
                      limit: int, offset: int) -> list[Chunk]
```

数据模型（`agentscope/rag/_document.py`）：
- `Chunk`: `content(TextBlock|DataBlock) · source · chunk_index · total_chunks · metadata`
- `VectorRecord`: `vector · document_id · chunk`
- `VectorSearchResult`: `score · document_id · chunk`
- `DocumentSummary`: `document_id · source · chunk_count · metadata`

### 3.3 PG 侧实现

> **不做表膨胀**：`create_collection` 不建新表，而是登记一条 collection 元数据；所有切片存在**一张** `kb_segment` 里，用 `collection` 列区分。

| 表 | 字段 |
|---|---|
| `kb_collection` | `name(unique) · dimensions(Integer) · tenant_id(BigInteger) · created_at` |
| `kb_segment` | `collection · document_id(String) · chunk_index(Integer) · content(Text) · embedding(Vector(dim)) · token_count · metadata(JSONB) · tenant_id(BigInteger)` |

唯一约束 `uq_kb_segment (collection, document_id, chunk_index)` —— 幂等重建索引的基础。

**索引**：
```sql
-- 向量（HNSW，无需像 IVFFlat 那样先训练）
CREATE INDEX idx_kb_segment_embedding
  ON kb_segment USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- 中文关键词召回（pg_trgm，PG 内置扩展）
CREATE INDEX idx_kb_segment_content_trgm
  ON kb_segment USING gin (content gin_trgm_ops);

CREATE INDEX idx_kb_segment_collection ON kb_segment (collection);
```

### 3.4 中文混合检索（关键差异化能力）

PG 原生 `to_tsvector` **无中文分词器**，整段中文会被当成一个词，全文检索对中文基本失效。

| 方案 | 代价 | 结论 |
|---|---|---|
| 安装 `zhparser` | 定制镜像（apt + make） | 备选 |
| **`pg_trgm`** | `CREATE EXTENSION pg_trgm`，**PG 内置零编译** | **采用** |
| 不做全文侧 | 混合检索名存实亡 | 否决 |

**流程**（在 `search()` 内部完成，对外契约不变）：

```
query_vector ──► pgvector cosine (<=>) ，HNSW 扫描，取 top_k*3
query 文本   ──► pg_trgm 相似度 / ILIKE，取 top_k*3
              └─► RRF 融合（k=60）→ 排序 → top_k
                  ↓
              list[VectorSearchResult]
```

- `retrieval_mode = vector` 时可只走向量侧（降级开关，通过 `metadata_filter` 或构造参数控制）
- `metadata_filter` 继续生效
- **上层 `KnowledgeBase` / RAG Service / `RAGMiddleware` 零改动**即可享受混合检索

### 3.5 性能

- HNSW `m=16, ef_construction=64`；查询期 `hnsw.ef_search` 可配（默认 40）
- **HNSW 带过滤的召回退化**：带 `collection` 过滤时可能召回不全 →
  单 collection < 10 万切片走"过滤后精确扫描"；超过后按 `collection` 做**分区表**
- 批量 upsert，不逐行写
- embedding 缓存由 AgentScope `embedding/_file_cache.py` + `_cache_base.py` 提供，**不重复实现**

**实测基线（P1 Task 11，2026-09-11）**：`backend/scripts/kb_perf_baseline.py`
在本机 PostgreSQL 17 + pgvector 0.8.6（minworkbuddy_test 库独立 schema）实测，
Qwen3 维度 768，HNSW `m=16, ef_construction=64`，50 条查询取 P50/P95：

| 切片数 | 入库吞吐 | 索引构建 | 纯向量检索 P50/P95 | 混合检索 P50/P95 |
|---|---|---|---|---|
| 20,000 | 134.6s（149 rows/s） | —（随写维护） | 51.6 / 54.3 ms | 64.5 / 78.4 ms |
| 100,000 | 359.0s（279 rows/s） | 264.5s（灌完后建） | 54.5 / 63.6 ms | 60.4 / 63.0 ms |

结论：10 万切片量级 P95 检索延迟 **< 100ms**，纯向量与混合检索同量级
（混合多一次 trigram-GIN 子串查询，本场景下开销可忽略）；满足验收标准
「10 万切片 P95 检索延迟有基线数据」。入库吞吐 ~280 rows/s，百万级需
按 §3.5 分区表策略拆分。

---

## 4. 自研件二：`UserIdMapper`（租户隔离）

AgentScope 的多租户靠 `user_id`，MWB 的多租户靠 `tenant_id`。映射规则：

```
user_id = f"t{tenant_id}"                  # 租户级隔离（推荐默认）
user_id = f"t{tenant_id}:u{user_id}"       # 用户级隔离（可选，按需求开启）
```

**必须在 spec 中明确的三个风险**：

1. **collection 名不含 user_id**（`kb_<uuid>`）→ 隔离**完全依赖 manager/storage 层按 `user_id` 过滤**。一旦绕过 manager 直接调 `PGVectorStore`，隔离即失效
2. **纵深防御**：`PGVectorStore` 保留 `tenant_id` 列与强制过滤，即使上层漏传也能兜底
3. **映射不可逆**：切换隔离粒度会导致既有 KB 归属错乱 → 映射规则**上线即冻结**，变更需数据迁移

---

## 5. 可选自研件三：Chunker

| 策略 | 适用 | 实现 |
|---|---|---|
| `ApproxTokenChunker` | 通用文本（默认） | AgentScope 原生 |
| `SemanticChunker` | 长文、需保持语义完整 | 自研，实现 `ChunkerBase` |
| `QaChunker` | **结构化数据（P2 产出）** | 自研：把表/列资产描述转"问答对"再 embedding，对结构化数据命中率显著更好 |

自定义 Chunker 需注册进 `create_app(knowledge_chunkers=[...])`，前端通过 `GET /knowledge_bases/chunkers` 自动发现（返回 JSON Schema，可动态渲染参数表单）。

---

## 6. API：直接复用，不自研

挂载后可用（前缀 `/agentscope`）：

| 类别 | 端点 |
|---|---|
| 能力发现 | `GET /knowledge_bases/embedding_models`（按维度策略过滤可用模型） |
| | `GET /knowledge_bases/supported_content_types`（已挂载 parser 支持的媒体类型） |
| | `GET /knowledge_bases/chunkers`（可用切片器 + 参数 JSON Schema） |
| | `GET /knowledge_bases/middleware/parameters_schema`（`RAGMiddleware.Parameters` Schema） |
| KB CRUD | `POST/GET/PATCH/DELETE /knowledge_bases` |
| 文档 | `GET/POST/DELETE /knowledge_bases/{kb_id}/documents` |
| 状态轮询 | `GET /knowledge_bases/{kb_id}/documents/status?ids=a,b,c` |
| 检索 | `POST /knowledge_bases/{kb_id}/search` |

**能力发现端点是意外之喜**：前端可据此动态渲染上传 accept 类型、embedding 模型下拉、切片参数表单 —— 与 P3 的声明式表单思路一致，几乎零硬编码。

**MWB 侧仅保留一张轻量映射表**（不替代 RAG Service 的存储，只服务于权限与前端列表）：

| 表 `kb_ref`（继承 `TenantMixin`） | 字段 |
|---|---|
| | `kb_id(String, AgentScope 侧 ID) · name · description · as_user_id(String) · doc_count · segment_count · status` |

---

## 7. 部署拓扑

| 方案 | 说明 | 风险 |
|---|---|---|
| **A. mount 到 MWB FastAPI** | `app.mount("/agentscope", create_app(...))` | 官方 docstring 支持；但需验证 **mount 后子应用 lifespan 是否执行**（`app/_health.py` 注释提到 mounted app 的 lifespan 问题） |
| B. 独立服务 | 单独进程 + 端口 | 隔离彻底，但多一个服务要运维 |

**推荐先验证 A**：单进程启动最省事；若 lifespan 不执行导致 storage/message_bus 未初始化，则退到 B。

**必配项**：
- `RedisStorage` + `RedisMessageBus`（MWB 已有 Redis Stack）
- `LocalWorkspaceManager`（MWB 已有 `WORKSPACE_BASE_DIR` 配置，可直接复用）或 S3
- `LocalBlobStore`（单机）或 `S3BlobStore`（分布式）—— MWB 若有 MinIO 则用 S3 协议
- **CPU 密集型 parser 必须配 `ProcessPoolExecutor`**（官方 Warning：否则阻塞 event loop）

---

## 8. AgentScope 集成

- `RAGMiddleware` 挂载到 Agent，自动注入检索结果（参数 Schema 由 `/middleware/parameters_schema` 暴露）
- 同时可注册为 Tool（`kb_search` 等），二者择一或并存
- **文档状态机**（`pending → parsing → chunking → indexing → ready / error`）由 RAG Service 提供，前端直接消费

---

## 9. 测试

- **契约测试**：`PGVectorStore` 满足 `VectorStoreBase` 全部语义（尤其 `delete` 按文档整体删除、`list_documents` 聚合）
- **中文检索**：中文 query 的向量召回 + trgm 召回 + RRF 融合结果人工抽检
- **幂等**：同文档重复入库不增行
- **维度混用**：768 与 1024 两个 KB 并存时互不影响（`DimensionPolicyKind.ANY` 验证）
- **租户隔离**：租户 A 检索不到租户 B 的切片（即使伪造 collection 名）
- **mount 验证**：子应用 lifespan / 路由可达性 / 静态资源路径
- **性能**：10 万切片规模检索延迟基线

---

## 10. 影响面

| 项 | 说明 |
|---|---|
| 新增扩展 | `CREATE EXTENSION pg_trgm`（PG 内置） |
| 新增表 | **仅 2 张**（`kb_collection` / `kb_segment`）+ MWB 侧 `kb_ref` —— v1 的 4 张表已砍 |
| 新增依赖 | **无**（`pgvector.sqlalchemy`、`sqlalchemy` 已有；Redis 已有） |
| 修改 | `app/main.py` 或应用工厂：`create_app` + `mount` |
| 不受影响 | 现有 `PGVectorStore`（注册制，继续服务既有业务表）、`WikiRAGIngestor` |
| 新增配置 | Redis Storage/MessageBus 连接、blob store 路径、parser executor、`hnsw.ef_search` |

---

## 11. 风险

1. **mount 的 lifespan 问题**（最高优先级）—— 官方注释提示 mounted 子应用 lifespan 不执行，可能导致 storage/message_bus 未初始化。**实施第一步就要验证**，不通过则改独立服务
2. **collection 名不含 user_id** —— 隔离依赖 manager 层；已用 `tenant_id` 列做纵深防御（§4）
3. **HNSW 过滤退化** —— 已给分区表退路（§3.5）
4. **`pg_trgm` 中文召回质量** —— 不如专业分词；保留 `zhparser` 升级路径
5. **AgentScope 契约演进** —— 当前锁定 2.0.7.post1；未来升级需回归 `VectorStoreBase` 与 `KnowledgeBaseManagerBase` 签名
6. **Redis 成为强依赖** —— RAG Service 的 storage 与 message bus 都依赖 Redis；需评估 Redis 不可用时的降级策略
7. **parser 阻塞 event loop** —— CPU 密集 parser 必须配 `ProcessPoolExecutor`（官方 Warning）
