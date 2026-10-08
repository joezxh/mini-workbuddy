# 知识库 RAG 层 · AgentScope 2.0.8 原生对齐技术规格

> 日期：2026-09-27
> 状态：待评审（用于修正并替代 `2026-09-27-knowledge-unification-design.md` 中 §10.3 / §10.4 / §10.7 的 RAG 实现方案）
> 权威来源：
> - <https://docs.agentscope.io/zh/versions/2.0.8/building-blocks/rag>
> - <https://docs.agentscope.io/zh/versions/2.0.8/building-blocks/middleware#rag>
> - 本机已安装包实测：`agentscope==2.0.8`（`backend/requirements.txt:93-95` 锁定），以下所有签名均由 `inspect` 对实际安装版本内省得出，**与文档一致**。
>
> 硬约束：**只使用 AgentScope 2.0.8 原生提供的类、参数名与装配方式。** 唯一允许的自定义是官方文档「自定义拓展」章节明确支持的三个基类继承点（`ParserBase` / `ChunkerBase` / `VectorStoreBase`）；除此之外不得新增自研 RAG 编排层。

---

## 1. 结论先行：原生能力边界

| 能力 | AgentScope 2.0.8 原生 | 本项目落位 |
|---|---|---|
| 文件解析（PDF/PPT/Word/Excel/图片/文本） | ✅ `agentscope.rag.*Parser` | 直接采用，删除自研解析分支 |
| 切块 | ✅ `ApproxTokenChunker` + `ChunkerBase` 扩展点 | 原生为主，`QaChunker` 按原生契约重写 |
| 嵌入模型 | ✅ `agentscope.embedding.DashScopeEmbeddingModel` 等 | 替换 `app/ai/embedding_client.py` 在 RAG 链路中的角色 |
| 向量库 | ⚠️ 官方仅 Qdrant/Milvus-Lite/MongoDB/Elasticsearch | **必须**自定义 `PgVectorStore(VectorStoreBase)`——官方支持的扩展点 |
| 知识库句柄 | ✅ `KnowledgeBase`（4 个方法） | 唯一对外检索入口 |
| 检索 | ✅ 仅 `KnowledgeBase.search(queries, top_k, score_threshold)` | **没有** `metadata_filters` / rerank 之外的检索参数 |
| 重排 | ✅ `RAGMiddleware(rerank_model=...)` | 替换自研 rerank 规划 |
| 智能体集成 | ✅ `RAGMiddleware`（static / agentic） | 替换所有「 Agent 内手工拼检索上下文」做法 |
| 服务化 RAG | ✅ 官方另有 RAG 服务（`deploy/rag`） | 不在本期范围；自研 `kb_app` 子应用**裁剪** |
| 图片作为查询（图搜图） | ❌ 2.0.8 实测不支持（见 §3-D9） | **裁剪**该需求 |

---

## 2. 原生 API 清单（实测内省结果）

### 2.1 `agentscope.rag` 导出

```
ApproxTokenChunker, Chunk, ChunkerBase, DocumentSummary,
ElasticsearchStore, ExcelParser, ImageParser, KnowledgeBase,
MilvusLiteStore, MongoDBStore, PDFParser, PPTParser, ParserBase,
QdrantStore, Section, TextParser, VectorRecord, VectorSearchResult,
VectorStoreBase, WordParser
```

### 2.2 解析器 `ParserBase`

```python
# 类属性
supported_media_types: list[str]        # IANA 媒体类型
# 类方法
supported_extensions() -> list[str]     # 默认由 supported_media_types 反查
# 抽象方法
async def parse(self, file: bytes | str, filename: str) -> list[Section]
```

| 类 | 支持类型 | 产出约定 |
|---|---|---|
| `TextParser` | `text/plain` `text/markdown` `text/csv` `text/html` `text/x-rst` `application/json` `application/xml` `application/x-yaml` | 整文件一个 `Section` |
| `PDFParser` | `application/pdf` | 每页一个 `Section`，`metadata={"page": N}` |
| `PPTParser` | `...presentationml.presentation` | 每片一个 `Section`，`metadata={"slide": N}` |
| `WordParser` | `...wordprocessingml.document` | 相邻段落合并为一个 `Section`，图片作独立 `DataBlock` |
| `ExcelParser` | `...spreadsheetml.sheet` `application/vnd.ms-excel` | 每张表渲染为 Markdown/JSON，`separate_sheet=True` 时 `metadata={"sheet": ...}` |
| `ImageParser` | `image/png` `image/jpeg` `image/gif` `image/bmp` `image/webp` | 整图一个 `Section`，`content` 为 `DataBlock` |

依赖：`pip install agentscope[rag]`。

### 2.3 切块器 `ChunkerBase`

```python
class ChunkerBase:
    chunker_type: str                       # 持久化/重建用，同一应用内必须唯一
    class Parameters(BaseModel): ...        # JSON Schema 直接用于配置表单与校验

    async def chunk(self, sections: list[Section]) -> list[Chunk]
```

原生实现：`ApproxTokenChunker`，`chunker_type = "approx_token"`，
`Parameters(chunk_size: int = 512, overlap: int = 50)`（近似策略 `len(text.encode("utf-8")) // 4`）。

`ChunkerBase.chunk()` **必须遵守的四条约定**（自定义实现同样受约束）：

1. 不跨 `Section` 合并；
2. 多模态 `DataBlock` 整块透传不切分；
3. `chunk_index` 从 0 连续编号；
4. 每个 chunk 的 `total_chunks` 为同一个值。

### 2.4 数据载体

```python
Section(content: TextBlock | DataBlock, source: str, metadata: dict)
Chunk(content: TextBlock | DataBlock, source: str, chunk_index: int,
      total_chunks: int, metadata: dict)
VectorRecord(vector: list[float], document_id: str, chunk: Chunk)
VectorSearchResult(score: float, document_id: str, chunk: Chunk)
DocumentSummary(document_id: str, source: str, chunk_count: int, metadata: dict)
```

> 关键事实：`Chunk` **没有** `parent_id` / `chunk_type` / `answer` / `keywords` 字段。
> 所有业务侧附加语义只能落在 `Chunk.metadata`（原生 `dict`）中，见 §5.3。

### 2.5 嵌入模型 `agentscope.embedding`

```python
DashScopeEmbeddingModel(
    credential: CredentialBase,          # DashScopeCredential(api_key=...)
    model: str,                          # "text-embedding-v4" | "qwen3-vl-embedding" ...
    dimensions: int | None,              # 契约层必填
    parameters: Parameters | None = None,
    embedding_cache: EmbeddingCacheBase | None = None,
    context_size: int = 8192,
    max_retries: int = 3,
    retry_delay: float = 1.0,
)
```

导出：`DashScopeEmbeddingModel` `OpenAIEmbeddingModel` `OllamaEmbeddingModel` `GeminiEmbeddingModel`
`EmbeddingModelBase` `EmbeddingResponse` `EmbeddingUsage` `FileEmbeddingCache` `EmbeddingModelCard`。

文本模型：`text-embedding-v3` / `text-embedding-v4`（1024 维，`supported_dimensions` 含 2048/1536/1024/768/512/256/128/64）。
多模态模型名前缀：`multimodal-embedding-` `tongyi-embedding-vision-` `qwen3-vl-embedding` `qwen2.5-vl-embedding`。

### 2.6 向量库 `VectorStoreBase`

```python
async def __aenter__(self) -> Self
async def __aexit__(self, exc_type, exc_val, exc_tb) -> None
async def create_collection(self, name: str, dimensions: int) -> None
async def delete_collection(self, name: str) -> None
async def has_collection(self, name: str) -> bool
async def insert(self, collection: str, records: list[VectorRecord]) -> None
async def delete(self, collection: str, document_id: str) -> None
async def search(self, collection: str, query_vector: list[float],
                 top_k: int = 5,
                 metadata_filter: dict[str, Any] | None = None,
                 ) -> list[VectorSearchResult]
async def list_documents(self, collection: str,
                         metadata_filter: dict[str, Any] | None = None,
                         ) -> list[DocumentSummary]
```

实现要点（官方）：`delete` 按 `document_id` 删该文档**全部**记录；`search` / `list_documents` 必须把 `metadata_filter` 翻译成后端 payload filter；`insert` 必须持久化 `VectorRecord.document_id` 与 `chunk`。

### 2.7 知识库句柄 `KnowledgeBase`

```python
KnowledgeBase(
    name: str, description: str,
    embedding_model: EmbeddingModelBase,
    vector_store: VectorStoreBase,
    collection: str,
    metadata_filter: dict | None = None,
)

await kb.ensure_collection() -> None
await kb.insert_document(chunks: list[Chunk], document_id: str | None = None,
                         document_metadata: dict | None = None) -> str
await kb.search(queries: list[str | TextBlock | DataBlock], top_k: int = 5,
                score_threshold: float | None = None) -> list[VectorSearchResult]
await kb.delete_document(document_id: str) -> None
await kb.list_documents() -> list[DocumentSummary]
await kb.list_chunks(document_id: str, *, offset: int = 0, limit: int = 30) -> list[Chunk]
```

`search()` 内部行为（官方契约，不可覆盖）：

1. 过滤不可用查询——`embedding_model.supports_multimodal == False` 时**静默丢弃** `DataBlock` 查询；
2. 所有 query **一次性批量嵌入**，再并发检索；
3. 按 `(document_id, chunk_index)` 去重，保留最高分；
4. 按分数降序截断到 `top_k`。

`score` **统一越大越相关**：距离度量的向量库返回前取负，故这类库分数为负、`score_threshold` 也填负数。分数只在**同一知识库内部**可比。

`metadata_filter` 是深度防御：`search` / `list_documents` 严格按 `key == value` 过滤；`insert_document` **强制覆盖**每个 chunk 的同名 metadata 字段。`None` = 每库独占 collection 的部署形态。

`KnowledgeBase` **不创建/关闭**向量库连接——连接生命周期由 `VectorStoreBase` 的 `async with` 负责。

### 2.8 `RAGMiddleware`

```python
RAGMiddleware(
    knowledge_bases: list[KnowledgeBase],
    parameters: RAGMiddleware.Parameters | None = None,
    rerank_model: ChatModelBase | None = None,
)
```

`RAGMiddleware.Parameters`（完整字段，实测内省）：

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `mode` | `Literal["static","agentic"]` | `"agentic"` | 集成模式 |
| `top_k` | `int` | `5` | 跨所有知识库与 query 去重后截断 |
| `score_threshold` | `float \| None` | `None` | 分数下限；距离度量下为负 |
| `rerank_candidate_k` | `int \| None` | `None` | 交重排的候选数；≥ `top_k`，默认 `2×top_k`，上限 50 |
| `emit_hint_event` | `bool` | `True` | static 模式额外发 `HintBlockEvent` 供前端展示命中片段 |
| `persist_hint` | `bool` | `False` | static 模式注入块是否常驻上下文（默认推理后移除） |
| `hint_template` | `str` | 内置 `<system-reminder>…{context}…</system-reminder>` | static 模式包装检索结果的模板，需含 `{context}` |
| `rerank_prompt` | `str` | 内置 `<rerank-task>…` | 重排指令，必须含 `{query}`，可选 `{top_k}` |

实现的 hook（实测：仅三个，未实现其余 4 个 hook，无调用开销）：

- `on_reply` —— **捕获**本次 reply 的输入消息（供 static 模式检索用）；
- `on_reasoning` —— static 模式下 `agent.state.cur_iter == 0` 时执行检索，把结果包装成 `HintBlock` 注入上下文；
- `list_tools` —— agentic 模式下返回 `search_knowledge` 工具（`ToolBase`），**不会被 `Agent.__init__` 自动调用**，必须手动收集进 `Toolkit`。

| 模式 | 触发时机 | 检索关键词 | 注入方式 |
|---|---|---|---|
| `static` | 每次 reply 的**首次推理前**（`cur_iter == 0`） | reply 的输入消息（支持多模态数据） | `HintBlock` 注入上下文 |
| `agentic`（默认） | 模型自主调用检索工具 | 模型自主给出 | 暴露 `search_knowledge` 工具 |

两种模式可**叠加**（同时挂两个实例）。`search_knowledge` 工具参数：`query: str`、`knowledge_bases: list[str] | None`（按 `KnowledgeBase.name` 限定子集），`is_read_only = True`。

重排行为：先取 `rerank_candidate_k` 条候选 → 重排模型读完内容挑出 `top_k` 条；**尽力而为**，失败记警告并回退向量顺序，不中断；模型读不了的候选排最后或剔除。每次检索额外一次大模型调用。

**中间件不拥有嵌入模型或向量库**——它只消费一组已构造好的 `KnowledgeBase` 句柄，可混合使用不同嵌入模型的知识库。

### 2.9 中间件机制（装配基线）

6 个 hook + 1 个工具源：`on_reply` / `on_reasoning` / `on_acting` / `on_model_call` / `on_compress_context`（Onion）、`on_system_prompt`（Transformer）、`list_tools`（Tool source，不在运行时路径）。

执行顺序：`middlewares=[mw1, mw2]` → `mw1 前 → mw2 前 → 内部逻辑 → mw2 后 → mw1 后`；Transformer 从左到右串行接力。

生命周期嵌套：

```
on_reply
  └── 每轮 ReAct：
        ├── on_compress_context
        ├── on_reasoning
        │     ├── _prepare_model_input() → on_system_prompt
        │     └── on_model_call
        └── on_acting（每个工具调用一次）
```

---

## 3. 现有设计的偏差 / 冗余清单（D = Deviation）

| # | 现状 | 判定 | 处置 |
|---|---|---|---|
| D1 | `services/kb/kb_app.py` 自研 FastAPI 子应用，挂载 `/agentscope/knowledge_bases`，无认证、自带 `get_db`、强制 `X-Tenant-Id` | 冗余且偏离原生（原生服务化方案是官方 RAG 服务） | **裁剪**：HTTP 面收口到主应用 `/api/v1/kb/*`（主 `get_db` + `get_current_user`）；仅保留 `/chunkers` 的参数 Schema 能力，下沉为 service 函数 |
| D2 | `PGVectorStore(db, tenant_id)` 自研类，签名 `search(collection, query_embedding, top_k=10, score_threshold=None, class_uris=None)`，**不继承** `VectorStoreBase` | 自研替代逻辑，与原生契约不兼容（无 `document_id` 维度、无 `metadata_filter`、非 async context、无 collection 生命周期） | **替换**为 `PgVectorStore(VectorStoreBase)`，见 §5.1 |
| D3 | `KbRetrievalService.search_by_text / search_by_vector / hybrid_search_by_text` 作为对外服务方法 | 冗余抽象层 | **裁剪**：对外只保留 `KnowledgeBase.search()`；混合检索下沉为 `PgVectorStore.search()` 内部实现 |
| D4 | `KbIngestService.ingest_document(collection, document_id, segments)` 自研落库 | 与 `KnowledgeBase.insert_document(chunks, document_id, document_metadata)` 重复 | **替换**：摄取统一为 `await kb.insert_document(chunks, document_id=..., document_metadata=...)` |
| D5 | `embedding_config.SUPPORTED_PROVIDERS = ("gpustack","nvidia","dashscope")` + `app/ai/embedding_client.embed_batch_sync` | 自研嵌入门面，**非原生** | **替换**为 `agentscope.embedding.*EmbeddingModel`；gpustack/nvidia 走 `OpenAIEmbeddingModel`（OpenAI 兼容协议），dashscope 走 `DashScopeEmbeddingModel` |
| D6 | `CHUNKER_REGISTRY = {ApproxTokenChunker.chunker_type: ..., QaChunker.chunker_type: ...}` 自研注册中心 | 半冗余 | **保留但收敛**：键必须是原生 `chunker_type`，值必须是 `ChunkerBase` 子类；`/chunkers` 端点返回 `cls.Parameters.model_json_schema()`（与原生表单机制一致） |
| D7 | `QaChunker` / 规划中的 `ParentChildChunker` | 合法（原生扩展点） | **按原生契约复核**：`chunker_type` 唯一、`Parameters` 继承 `ChunkerBase.Parameters`、遵守 §2.3 四条约定 |
| D8 | `pipeline_config` 规划为 `{clean, chunker:{type,params}, index}` | 命名未对齐 | **重命名对齐**为 `{parser, chunker, embedding, index, rag}`，见 §6 |
| D9 | §10.4 规划「支持图片作为查询输入」、§10.6「图搜图」 | **原生不支持** | **裁剪**。实测 2.0.8：`DashScopeEmbeddingModel.supports_multimodal` 恒为 `False`（类默认值，DashScope 实现未覆写，即使 `model="qwen3-vl-embedding"` 亦然）→ `KnowledgeBase.search()` 会静默丢弃 `DataBlock` 查询。文搜图（图片入库 + 文本查询）**支持**；图搜图**不支持** |
| D10 | §10.4 检索参数含 `metadata_filters` | 原生 `KnowledgeBase.search()` 只有 `queries/top_k/score_threshold` | **拆分**：租户/知识库级固定过滤 → `KnowledgeBase.metadata_filter`（构造期）；检索测试面板的临时筛选 → 为该组合构造临时 `KnowledgeBase`（复用同一 store）或直接调 `PgVectorStore.search(metadata_filter=...)` |
| D11 | `index_mode = economy`（跳过 embedding、仅关键词） | 原生 `insert_document` 强制嵌入，无跳过开关 | **降级为 store 层策略**并明确代价：economy 下 `PgVectorStore.insert` 写 NULL 向量、只建 pg_trgm 索引，`search` 忽略向量分支；但 `KnowledgeBase.search` 仍会调用嵌入模型产生 query 向量 → **economy 库不应走 `RAGMiddleware`/`KnowledgeBase`，其检索走独立关键词检索服务**。原规格「零 embedding 消耗」仅在后者成立 |
| D12 | `score_threshold` 语义未定 | 原生规定越大越相关、距离度量下为负 | **固定**：`PgVectorStore` 使用余弦距离时返回 `-distance`（或 `1 - distance`），全链路文档化「越大越相关」 |
| D13 | `kb_segment.parent_id` 父子分段，检索时 join 回父块 | 原生 `Chunk` 无父子概念 | **替换**：父块文本随子块写入 `Chunk.metadata["parent_content"]`（原生 dict 允许），检索结果直接携带，无需 join；`parent_id` 列降级为**可选**，仅服务前端树形展示 |
| D14 | `kb_segment.chunk_type / answer / keywords` 作为一等列 | 原生无此概念 | **降级为 `Chunk.metadata` 的冗余投影**：写入源是 `Chunk.metadata`，`chunk_type` 列仅作 SQL 过滤索引优化 |
| D15 | §10.3 隐含「所有摄取必须 parser → chunker」 | 不必要 | **纠正**：Q&A / table_row 形态直接构造 `Chunk` 列表调 `insert_document`，不经过 parser/chunker |
| D16 | `agent_factory.py` 的 `Agent(...)` 未传 `middlewares` | 未接入原生 RAG | **补充**集成点，见 §7 |
| D17 | `app/ai/knowledge/rag_pipeline.py`（`RAGPipeline` / `SimpleTextSplitter` / `IngestRecord`） | 自研 RAG 编排，完全冗余 | **裁剪**，由 §5 原生链路取代 |
| D18 | `routers/wiki/wiki.py:728` `/ask` 自研 RRF + `WikiArticle.content_vector` 单表向量列 | 与 RAG 链路无关 | **边界澄清**：`/ask` 是 HTTP 问答端点，**不走中间件**；`RAGMiddleware` 只服务 Agent 运行时。是否迁移到 `KnowledgeBase` 另案（§9） |
| D19 | `kb_collection.dimensions` 与嵌入维度可能不一致 | 原生由 `embedding_model.dimensions` 决定 collection 维度 | **对齐**：`create_collection` 时校验 `kb_collection.dimensions == embedding_model.dimensions`，不一致直接失败 |

---

## 4. 目标架构与模块职责

```
┌─ 主应用 HTTP 层（/api/v1/kb/*，主 get_db + get_current_user）────────────┐
│  POST /kb/collections/{id}/documents   POST /kb/collections/{id}/retrieve │
│  POST /kb/qa-records   POST /kb/table-records/import   ...                │
└───────────────────────────┬──────────────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────────────┐
│ app/services/kb/rag/  （原生装配层，无自研编排）                          │
│                                                                           │
│  parser_factory.py    → agentscope.rag.*Parser                            │
│  chunker_factory.py   → ApproxTokenChunker | QaChunker | ParentChildChunker│
│  embedding_factory.py → agentscope.embedding.*EmbeddingModel              │
│  pg_vector_store.py   → PgVectorStore(VectorStoreBase)  ← 唯一自定义扩展   │
│  knowledge_factory.py → KnowledgeBase(name, description, embedding_model,  │
│                                       vector_store, collection,           │
│                                       metadata_filter)                    │
│  rag_middleware.py    → RAGMiddleware(knowledge_bases, parameters,         │
│                                       rerank_model)                       │
└───────────────────────────┬──────────────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────────────┐
│ Agent 运行时：Agent(model, toolkit=Toolkit(tools=await mw.list_tools()),   │
│                     middlewares=[mw])                                     │
└──────────────────────────────────────────────────────────────────────────┘
```

职责边界（**严格**）：

| 模块 | 职责 | **不负责** |
|---|---|---|
| `*Parser` | 文件 → `Section[]` | 切块、嵌入、落库 |
| `*Chunker` | `Section[]` → `Chunk[]` | 嵌入、落库 |
| `EmbeddingModelBase` | 输入 → 向量 | 存储、检索 |
| `PgVectorStore` | collection 生命周期 + 向量/元数据存取 + `metadata_filter` 翻译 | 解析、切块、嵌入、重排 |
| `KnowledgeBase` | 绑 embedding + store + collection；`insert_document` / `search` / `delete_document` / `list_documents` | 拥有连接、rerank、权限 |
| `RAGMiddleware` | 在 Agent reply/reasoning 钩子内检索并注入 `HintBlock`；暴露 `search_knowledge` 工具 | 拥有 embedding model / vector store、HTTP 端点、权限 |
| 主应用路由 | 认证、租户、任务编排（`job_runner`）、状态回写 `kb_document` | 检索算法 |

> 权限与租户隔离在**路由 + `KnowledgeBase.metadata_filter`** 两处闭合；前端 UI 隐藏不是授权边界。

---

## 5. 接口定义

### 5.1 `PgVectorStore(VectorStoreBase)` —— 唯一允许的自定义扩展

```python
# backend/app/services/kb/rag/pg_vector_store.py
from agentscope.rag import (
    DocumentSummary, VectorRecord, VectorSearchResult, VectorStoreBase,
)

class PgVectorStore(VectorStoreBase):
    """pgvector 后端。collection → kb_segment.collection；
    document_id → kb_segment.document_id；Chunk.metadata → kb_segment.metadata_。"""

    def __init__(self, session_factory, *, tenant_id: int, dimensions: int): ...

    # ---- 生命周期（原生 contract：async context manager）----
    async def __aenter__(self) -> "PgVectorStore": ...   # 打开 Session
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...  # 关闭 Session

    # ---- collection 生命周期（7 个抽象方法中的 3 个）----
    async def create_collection(self, name: str, dimensions: int) -> None: ...
    async def delete_collection(self, name: str) -> None: ...
    async def has_collection(self, name: str) -> bool: ...

    # ---- 读写 ----
    async def insert(self, collection: str, records: list[VectorRecord]) -> None: ...
    async def delete(self, collection: str, document_id: str) -> None: ...
    async def search(self, collection: str, query_vector: list[float],
                     top_k: int = 5,
                     metadata_filter: dict[str, Any] | None = None,
                     ) -> list[VectorSearchResult]: ...
    async def list_documents(self, collection: str,
                             metadata_filter: dict[str, Any] | None = None,
                             ) -> list[DocumentSummary]: ...
```

强制实现要点：

1. `insert` 必须持久化 `record.document_id` 与 `record.chunk`（否则 `delete` / `list_documents` 不可用）；
2. `delete(collection, document_id)` 删该文档**所有**记录；
3. `search` / `list_documents` 必须把 `metadata_filter` 的 `key == value` 翻译成 `kb_segment.metadata_` 的 JSONB 等值过滤；
4. `search` 返回分数统一**越大越相关**（余弦距离取负），保证 `score_threshold` 语义与原生一致；
5. 混合检索（pg_trgm + 向量 RRF）作为 `search()` 的**内部策略**实现，不对外暴露新方法；
6. `create_collection` 校验 `dimensions == kb_collection.dimensions`，不一致抛错（D19）；
7. `economy` 索引模式下 `insert` 写 NULL 向量、`search` 跳过向量分支（D11）。

### 5.2 解析器工厂

```python
PARSER_REGISTRY: dict[str, type[ParserBase]] = {
    "text":  TextParser,
    "pdf":   PDFParser,
    "pptx":  PPTParser,
    "docx":  WordParser,
    "xlsx":  ExcelParser,
    "image": ImageParser,
}

def select_parser(mime_type: str) -> type[ParserBase]:
    """按 IANA 媒体类型命中 ParserBase.supported_media_types 选中解析器；无命中则报错。"""
```

上传入口统一 `await parser.parse(file=<bytes>, filename=<原始文件名>)`（原生支持 bytes 直传，优先于落盘路径）。

### 5.3 切块器工厂（原生 + 自定义子类）

```python
CHUNKER_REGISTRY: dict[str, type[ChunkerBase]] = {
    ApproxTokenChunker.chunker_type: ApproxTokenChunker,   # "approx_token"
    QaChunker.chunker_type:          QaChunker,            # "qa"
    ParentChildChunker.chunker_type: ParentChildChunker,   # "parent_child"
}

def build_chunker(chunker_type: str, params: dict) -> ChunkerBase:
    cls = CHUNKER_REGISTRY[chunker_type]
    return cls(parameters=cls.Parameters(**params))
```

自定义子类必须：

- `chunker_type` 在同一应用内唯一（原生 `ParentChildChunker` 取 `"parent_child"`，`QaChunker` 保持 `"qa"`）；
- `Parameters` 继承 `ChunkerBase.Parameters`；
- 遵守 §2.3 四条约定；
- **业务语义只写 `Chunk.metadata`**，例如：

```python
Chunk(
    content=TextBlock(text=child_text),
    source=section.source,
    chunk_index=i, total_chunks=n,
    metadata={
        "chunk_type":     "child",                 # 冗余投影到 kb_segment.chunk_type
        "parent_content": parent_text,             # D13：免 join 携带父块
        "parent_index":   parent_section_index,
        "keywords":       [...],                   # D14
    },
)
```

Q&A 形态不经过 chunker（D15），直接构造：

```python
Chunk(content=TextBlock(text=question), source="qa-import",
      chunk_index=i, total_chunks=n,
      metadata={"chunk_type": "qa", "answer": answer, "tags": [...], "enabled": True})
```

表格行同理：`content` = 待嵌入字段值，其余列进 `metadata`。

### 5.4 嵌入模型工厂

```python
def build_embedding_model(cfg: EmbeddingSettings) -> EmbeddingModelBase:
    """provider=openai 兼容协议（gpustack/nvidia）→ OpenAIEmbeddingModel
       provider=dashscope                          → DashScopeEmbeddingModel
    dimensions 必填；可选 embedding_cache=FileEmbeddingCache(...) 复用原生缓存。"""
```

`dimensions` 取自 `kb_collection.dimensions`，与 `create_collection` 强校验。

### 5.5 `KnowledgeBase` 装配

```python
async def build_knowledge_base(db, *, knowledge_id, collection_name,
                               embedding_cfg, tenant_id) -> KnowledgeBase:
    store = PgVectorStore(session_factory, tenant_id=tenant_id,
                          dimensions=embedding_cfg.dimensions)
    await store.__aenter__()                      # 由调用方 with 生命周期托管
    return KnowledgeBase(
        name=...,                                 # 供 search_knowledge 工具展示与限定子集
        description=...,
        embedding_model=build_embedding_model(embedding_cfg),
        vector_store=store,
        collection=collection_name,               # kb_<uuid>
        metadata_filter={"tenant_id": tenant_id}, # 深度防御：insert 强制覆盖，search 严格过滤
    )
```

### 5.6 `RAGMiddleware` 装配

```python
async def build_rag_middleware(kbs: list[KnowledgeBase], rag_cfg: dict,
                               rerank_model=None) -> RAGMiddleware:
    return RAGMiddleware(
        knowledge_bases=kbs,
        parameters=RAGMiddleware.Parameters(
            mode=rag_cfg.get("mode", "agentic"),
            top_k=rag_cfg.get("top_k", 5),
            score_threshold=rag_cfg.get("score_threshold"),
            rerank_candidate_k=rag_cfg.get("rerank_candidate_k"),   # ≥ top_k，默认 2×top_k，≤50
            emit_hint_event=rag_cfg.get("emit_hint_event", True),
            persist_hint=rag_cfg.get("persist_hint", False),
        ),
        rerank_model=rerank_model,                # ChatModelBase，如 DashScopeChatModel
    )
```

---

## 6. 配置结构

### 6.1 `kms_knowledge.pipeline_config`（JSONB）—— 键名对齐原生参数名

```json
{
  "parser": {
    "type": "text",
    "params": {}
  },
  "chunker": {
    "type": "approx_token",
    "params": { "chunk_size": 512, "overlap": 50 }
  },
  "embedding": {
    "provider": "dashscope",
    "model": "text-embedding-v4",
    "dimensions": 1024
  },
  "index": {
    "collection": "kb_3f2a...",
    "metadata_filter": { "tenant_id": 1 },
    "index_mode": "high_quality"
  },
  "rag": {
    "mode": "agentic",
    "top_k": 5,
    "score_threshold": null,
    "rerank_candidate_k": 10,
    "emit_hint_event": true,
    "persist_hint": false
  }
}
```

对应关系（一一对齐原生命名，禁止自造别名）：

| 配置路径 | 原生落点 |
|---|---|
| `parser.type` | `PARSER_REGISTRY` 键 → `agentscope.rag.*Parser` |
| `parser.params` | 对应 Parser 构造参数 |
| `chunker.type` | `ChunkerBase.chunker_type` |
| `chunker.params` | `ChunkerBase.Parameters(**params)` |
| `embedding.provider/model/dimensions` | `agentscope.embedding.*EmbeddingModel(credential, model, dimensions)` |
| `index.collection` | `KnowledgeBase(collection=...)` |
| `index.metadata_filter` | `KnowledgeBase(metadata_filter=...)` |
| `rag.*` | `RAGMiddleware.Parameters(**rag)` |
| `index.index_mode` | `PgVectorStore` 内部索引策略（`high_quality` / `economy`） |

前端创建向导的表单 Schema **直接消费** `ChunkerBase.Parameters.model_json_schema()` 与 `RAGMiddleware.Parameters.model_json_schema()`，不手写字段定义。

### 6.2 DB 列与原生对象的映射

| 原生对象/字段 | DB 落点 | 说明 |
|---|---|---|
| `KnowledgeBase.collection` | `kb_collection.name` | `kb_<uuid>` |
| `KnowledgeBase.metadata_filter` | `kb_segment.metadata_.tenant_id` | 深度防御，insert 强制覆盖 |
| `VectorRecord.document_id` | `kb_segment.document_id` | 文档级删除/列举的依据 |
| `Chunk.chunk_index` | `kb_segment.chunk_index` | 与 `document_id` 组成去重键 |
| `Chunk.content` | `kb_segment.content` | 被嵌入的内容 |
| `Chunk.content`(image) | `kb_segment_asset` | 图片二进制落文件，chunk 存 caption/OCR |
| `Chunk.metadata` | `kb_segment.metadata_` | **业务语义唯一写入源** |
| `Chunk.metadata.chunk_type` | `kb_segment.chunk_type`（冗余列） | 仅供 SQL 过滤/索引（D14） |
| `Chunk.metadata.answer` | `kb_segment.answer`（冗余列） | 同上 |
| `Chunk.metadata.keywords` | `kb_segment.keywords`（冗余列） | 同上 |
| `Chunk.metadata.parent_content` | 不落列 | 直接随检索结果返回（D13） |
| `embedding_model.dimensions` | `kb_collection.dimensions` | 强校验（D19） |

---

## 7. 与 `RAGMiddleware` 的集成（Agent 运行时）

### 7.1 装配位置

`backend/app/ai/agent_factory.py` 的 `_create_general_agent` / `_create_thinking_agent` / `_create_expert_agent` / `_create_react_agent` 等当前只传 `name/system_prompt/model/toolkit`（实测 `_build_model_and_toolkit` 无 middleware 分支）。集成后：

```python
from agentscope.agent import Agent
from agentscope.tool import Toolkit

model, toolkit = self._build_model_and_toolkit(config)

rag_mw = None
if config.get("knowledge_bases"):
    kbs = [await build_knowledge_base(self._db, knowledge_id=kid, ...) for kid in ...]
    rag_mw = await build_rag_middleware(kbs, config.get("rag", {}))
    # agentic 模式：list_tools 不会被 Agent.__init__ 自动调用，必须手动合并
    toolkit = Toolkit(tools=[*toolkit.tools, *await rag_mw.list_tools()])

agent = Agent(
    name=..., system_prompt=..., model=model, toolkit=toolkit,
    middlewares=[rag_mw] if rag_mw else [],
)
```

### 7.2 模式选择约定

| 场景 | `mode` | 说明 |
|---|---|---|
| 知识问答型 Agent（研究/专家/客服） | `agentic`（默认） | 模型自主决定检索时机 |
| 固定背景注入、弱模型、单轮问答 | `static` | `emit_hint_event=True` 供前端展示命中片段；`persist_hint=False` 避免污染下一轮 |
| 两者都要 | 挂两个实例 | 官方支持的叠加方式 |

### 7.3 执行时序（static 模式）

```
agent(msg)
└── on_reply（RAGMiddleware 捕获输入消息）
    └── on_compress_context
    └── on_reasoning  [cur_iter == 0]
        ├── RAGMiddleware 检索 → 结果包装 HintBlock 注入上下文
        │   （emit_hint_event=True 时同时发 HintBlockEvent 给前端）
        ├── on_system_prompt
        └── on_model_call
    └── on_acting（agentic 模式下调用 search_knowledge）
```

### 7.4 与现有中间件的顺序

现有 AgentScope 中间件：`GraphitiMiddleware` / `ConfigTraceMiddleware` / `SkillMetricsMiddleware`（均继承 `agentscope.middleware.MiddlewareBase`）。按洋葱规则，**列表中第一个处于最外层**；建议 `middlewares=[tracing_mw, rag_mw, ...]`，使追踪覆盖 RAG 检索。

---

## 8. 数据流

### 8.1 摄取（type=2 / document）

```
POST /api/v1/kb/collections/{id}/documents (multipart)
  → 建 kb_document(status='pending')
  → job_runner.run_in_background + 独立 Session
      parser = select_parser(mime)                    # 原生 Parser
      sections = await parser.parse(file=bytes, filename=name)
      chunker = build_chunker(cfg.chunker.type, cfg.chunker.params)
      chunks  = await chunker.chunk(sections)
      async with PgVectorStore(...) as store:
          kb = KnowledgeBase(..., vector_store=store, collection=..., metadata_filter=...)
          await kb.ensure_collection()                # 首次操作按 dimensions 自动建
          document_id = await kb.insert_document(chunks,
                            document_metadata={"filename": name, "kb_document_id": ...})
      → kb_document.status = completed / failed（error_detail 记录失败步骤）
```

重处理 = `await kb.delete_document(document_id)` → 重跑上述链路。

### 8.2 检索测试

```
POST /api/v1/kb/collections/{id}/retrieve  {query, top_k, score_threshold, metadata_filters?}
  → async with PgVectorStore(...) as store:
        kb = KnowledgeBase(..., metadata_filter={tenant_id, **metadata_filters})
        results = await kb.search(queries=[query], top_k=top_k, score_threshold=...)
  → 统一返回 {segments[], scores[], citations[]}
```

`metadata_filters` 通过**构造期** `metadata_filter` 生效（D10）；`queries` 只接受 `str` / `TextBlock`（DataBlock 在 2.0.8 被静默丢弃，见 D9）。

### 8.3 Agent 运行时检索

见 §7.3。检索完全由 `RAGMiddleware` 驱动，应用代码**不**手动拼检索上下文。

---

## 9. 依赖与生命周期

### 9.1 依赖

```
agentscope==2.0.8          # 已锁定
agentscope[rag]            # 解析 PDF/PPT/Word/Excel 的额外第三方库（需显式安装 extras）
```

**不需要** `agentscope[vdb-*]`（pgvector 后端由 `PgVectorStore` 自持，依赖项目已有的 SQLAlchemy + psycopg + pgvector 扩展）。
移除：`app/ai/knowledge/rag_pipeline.py`、`services/kb/ingest_service.py` 的落库路径、`services/kb/retrieval_service.py` 对外方法、`embedding_client.embed_batch_sync` 在 RAG 链路中的使用（D3/D4/D5/D17）。

### 9.2 生命周期

| 对象 | 生命周期 | 归属 |
|---|---|---|
| `PgVectorStore` | **请求/任务级**，`async with` 进出 | 调用方（路由或后台任务） |
| `EmbeddingModel` | 随 `KnowledgeBase` 长期存活，进程内可复用 | `knowledge_factory` |
| `KnowledgeBase` | 无状态句柄，可按需构造/缓存 | `knowledge_factory` |
| `RAGMiddleware` | 随 Agent 实例；**实例自身无状态**，运行时状态存 `agent.state.middle_context` | Agent |
| `Chunk` / `Section` | 单次摄取调用内 | 摄取函数 |

⚠️ `KnowledgeBase` 不创建/关闭连接；FastAPI 中必须让 `async with store:` 覆盖到所有 `kb.*` 调用，请求结束即 `__aexit__`。后台任务同理，禁止跨任务共享 store 实例。

---

## 10. 明确不支持 / 推迟项（对齐原生边界）

| 项 | 原因 |
|---|---|
| **图搜图**（图片作为查询输入） | 2.0.8 `DashScopeEmbeddingModel.supports_multimodal` 恒 `False`，`KnowledgeBase.search` 静默丢弃 `DataBlock`（D9）。文搜图支持 |
| **economy 模式零 embedding 消耗** | `KnowledgeBase.search` 必然嵌入 query；economy 库改走独立关键词检索服务，不经 `RAGMiddleware`（D11） |
| 检索期动态 `metadata_filters` | 原生 `KnowledgeBase.search` 无此参数，只能构造期固化（D10） |
| 检索结果 rerank 之外的后处理（父子 join、关键词加权 SQL） | 不属于原生链路；父子内容改为 `metadata.parent_content` 携带（D13），关键词加权限 `PgVectorStore.search` 内部（D14） |
| 官方 RAG 服务（`deploy/rag`，HTTP + 文件托管 + 分布式索引） | 本期不引入；自研 `kb_app` 子应用按 D1 裁剪 |
| `WikiArticle.content_vector` / `/ask` 链路迁移 | 属 HTTP 问答端点，不走中间件（D18），另案评估 |

---

## 11. 验收标准

1. `grep -r "from agentscope.rag\|from agentscope.embedding\|from agentscope.middleware"` 在 `backend/app` 下命中以下且**仅**以下原生符号：`ParserBase/TextParser/PDFParser/PPTParser/WordParser/ExcelParser/ImageParser`、`ChunkerBase/Chunk/Section/ApproxTokenChunker`、`VectorStoreBase/VectorRecord/VectorSearchResult/DocumentSummary`、`KnowledgeBase`、`EmbeddingModelBase/DashScopeEmbeddingModel/OpenAIEmbeddingModel`、`RAGMiddleware`；不得出现自研 RAG 编排类（D17）。
2. `PgVectorStore` 满足 `VectorStoreBase` 全部 7 个抽象方法 + `__aenter__/__aexit__`；`issubclass(PgVectorStore, VectorStoreBase)` 为真；`insert` 后 `delete(document_id)` 能删净、`list_documents` 能列出。
3. `ChunkerBase` 子类通过契约自检：不跨 Section、`DataBlock` 透传、`chunk_index` 连续、`total_chunks` 一致、`chunker_type` 唯一。
4. `POST /kb/collections/{id}/documents` 上传 PDF/MD 走 `parser.parse → chunker.chunk → kb.insert_document` 三步，无自研中间格式；`kb_document` 状态真实流转。
5. `POST /kb/collections/{id}/retrieve` 底层只调用 `KnowledgeBase.search(queries, top_k, score_threshold)`；score 越大越相关；`score_threshold` 生效。
6. Agent 配置 `knowledge_bases` 后，`Agent.middlewares` 含 `RAGMiddleware`；agentic 模式下 `Toolkit` 内存在 `search_knowledge` 工具且 `is_read_only=True`；static 模式下首轮推理前上下文出现 `HintBlock` 且 `emit_hint_event=True` 时前端收到 `HintBlockEvent`。
7. `kms_knowledge.pipeline_config` 的 `chunker.params` 可无转换地传入 `ApproxTokenChunker.Parameters(**params)`；`rag` 段可无转换地传入 `RAGMiddleware.Parameters(**rag)`。
8. `kb_collection.dimensions != embedding_model.dimensions` 时 `create_collection` 明确失败（不静默创建错误维度列）。
9. 多租户：跨租户检索返回空——`KnowledgeBase.metadata_filter={"tenant_id": N}` 在 `search` / `list_documents` 严格生效，`insert_document` 强制覆盖同名 metadata。
10. 现有 pytest 基线只增不减；新增用例覆盖：父子 chunk 的 `metadata.parent_content` 随检索返回、`QaChunker` 契约自检、`PgVectorStore` 抽象方法齐全性。
