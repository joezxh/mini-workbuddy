---
name: 向量化策略放宽探测并自动对齐维度
overview: 围绕 lm-studio 向量化策略做两件事：(1) 放宽连通性探测——模型管理里配置的默认向量化模型（如 lm-studio）即使探测不通也优先采用，不再回落到环境变量配置；(2) 维度自动对齐——所有写入/检索 kms_segment 的向量，在落库与查询前按「数据表实际向量字段维度」自动补齐或截断，解决 embedding 输出维度（如 768）与表定义维度（如 2048）不符导致的写入/检索失败。
todos:
  - id: relax-probe
    content: 放宽 resolve_embedding_config_with_fallback 探测回落逻辑
    status: completed
  - id: add-physical-dim-util
    content: 在 vector_utils.py 增加物理列维度读取与缓存
    status: completed
  - id: fix-rag-store
    content: 改造 rag PgVectorStore 写入与查询按物理维度对齐
    status: completed
    dependencies:
      - add-physical-dim-util
  - id: fix-core-store
    content: 改造 kb/pgvector_store 的 insert/search/hybrid_search 按物理维度对齐
    status: completed
    dependencies:
      - add-physical-dim-util
  - id: add-tests
    content: 补充维度对齐单测并运行 tests/kb 验证
    status: completed
    dependencies:
      - fix-rag-store
      - fix-core-store
---

## 用户需求
围绕 lm-studio 向量化策略（模型管理默认向量化模型）继续完善，使其适配所有需要向量化的知识库内容，包含两个核心改动：

## 核心功能
- **放宽连通性探测**：当模型管理已配置完整的默认向量化模型（type=5 + is_default + status=1 + 关联密钥可用 + 维度非空 + url 非空）时，即使对端连通性探测不通，也直接采用该配置（仅记 warning），不再回落到环境变量配置；只有确实未在模型管理配置时才回落环境变量。
- **向量维度自动对齐**：以 `kms_segment.embedding` 物理列维度（pg_attribute.atttypmod）作为唯一目标维度，在「写入」与「检索」两侧自动补齐（过短补零）或截断（过长）向量，覆盖 768 与 2048 维度不一致场景。
  - 写入侧：写入切片前将 embedding 对齐到物理列维度，避免 `expected 2048 dimensions, not 768`。
  - 检索侧：纯向量检索与中文混合检索的查询向量在参与 SQL 余弦运算前先对齐到物理列维度。
  - 物理维度读取带进程级缓存，回落 `settings.EMBEDDING_DIMENSION`。
- **保持既有约束不变**：集合维度（`kb_collection.dimensions`）仍用于 `create_collection` 的 D19 一致性校验；economy 模式行为不变；不改动 `startup_migrations`（空表仍按配置对齐，非空表由运行时归一化兜底）。


## 技术栈
- 后端：Python 3.11 + FastAPI + SQLAlchemy（同步会话）+ pgvector
- RAG：AgentScope `VectorStoreBase` 原生实现
- 复用现有原语：`app.services.kb.vector_utils.fit_vector_dimension`（过长截断/过短补零/None 原样返回）

## 实现方案
**总体策略**：以「数据表物理列维度」为唯一对齐目标，在两套 `PGVectorStore` 的写入与查询路径统一调用 `fit_vector_dimension`，并放宽嵌入配置解析的探测回落。

**关键发现（已核实）**：项目存在两个同名的向量存储类，必须都修正：
1. `app/services/kb/rag/pg_vector_store.py` 的 `PgVectorStore(session_factory, *, tenant_id, dimensions, index_mode, hybrid)` —— AgentScope 实现，被 `knowledge_factory`/`agent_factory` 使用；`insert` 第 137 行用 `fit_vector_dimension(raw_vector, self.dimensions)`（目标是集合配置维度，错误），`search` 第 157 行未对查询向量做适配。
2. `app/services/kb/pgvector_store.py` 的 `PGVectorStore(db: Session, tenant_id)` —— 纯存储层，被 `retrieval_service`/`ingest_service`/`routers/kb/kb.py` 使用（即 Web 端知识库导入与检索的主路径）；`insert` 第 137 行直接写 `s.embedding` 不归一化，`search` 第 219 行与 `hybrid_search` 第 318 行的向量分支均未归一化。

**关键决策与权衡**：
- 目标维度取物理列而非配置维度：因 `startup_migrations` 仅在空表时 ALTER 列，非空表保留旧维度（如 2048），与当前 lm-studio 768 配置产生分歧；运行时按物理列对齐可同时兼容两条写入链路且零迁移风险。
- 物理维度读取用 `engine.connect()` 独立连接 + 进程级缓存（key=id(engine)），避免污染请求事务会话、避免每次构造重复查询 pg_attribute；atttypmod 为 -1 或 None 时回落 `settings.EMBEDDING_DIMENSION`。
- `resolve_embedding_config_with_fallback` 仅去掉「探测不通即回落」的分支，保留 `_probe_cache`/`_PROBE_TIMEOUT` 仅用于 warning 日志，对全部调用方（wiki/ontology/agent）均生效，属期望行为。

## 实现要点
- **性能**：物理维度进程级缓存仅首次访问 pg_attribute；`fit_vector_dimension` 为 O(n) 列表拷贝，单次切片规模可忽略，不会对 hot path 引入额外复杂度。
- **日志**：沿用 `logger.warning` 记录探测不通与维度对齐（不打印向量内容，避免大 payload / PII）。
- **回归控制**：保持 `create_collection` 的 D19 校验、`ingest_document` 对 `coll.dimensions` 的严格校验（768==768 仍通过）、economy 模式写 NULL 行为不变；写入侧对 `None/空` embedding 保持 NULL，不调用 fit（避免空向量写入）。

## 架构设计
两套存储共享同一个物理表 `kms_segment` 与同一个维度适配原语 `fit_vector_dimension`；新增 `get_segment_vector_dimension(engine)` 作为物理维度读取原语，由两套存储在构造期读取并缓存为 `self.physical_dim`。

## 目录结构与文件改动
```
backend/
├── app/services/kb/vector_utils.py              # [MODIFY] 新增 get_segment_vector_dimension(engine)/解析物理列维度，含进程级缓存与 settings.EMBEDDING_DIMENSION 回落；复用已有 fit_vector_dimension。
├── app/services/kb/embedding_config.py          # [MODIFY] resolve_embedding_config_with_fallback：DB 默认配置存在且完整时即便探测不通也返回该 cfg（仅 warning），仅 cfg 为 None 才回落 env。
├── app/services/kb/rag/pg_vector_store.py       # [MODIFY] PgVectorStore 构造期读取并缓存 self.physical_dim；insert 改用 fit_vector_dimension(raw_vector, self.physical_dim)；search 先 fit query_vector 再参与 SQL。self.dimensions 维持不变用于 D19。
├── app/services/kb/pgvector_store.py            # [MODIFY] PGVectorStore 构造期读取并缓存 self.physical_dim；insert 对非空 embedding 做 fit 到 physical_dim；search 与 hybrid_search 向量分支对 query_embedding 先 fit 到 physical_dim。
└── tests/kb/                                    # [NEW/MODIFY] 补充 fit_vector_dimension（768→2048 补零、2048→768 截断、等长、None 原样）单测；get_segment_vector_dimension 回落单测；存储 insert/search 物理维度对齐断言；跑 tests/kb 区分既有环境失败。
```

## 关键代码结构（接口级）
```python
# vector_utils.py
def get_segment_vector_dimension(engine) -> Optional[int]:
    """读取 kms_segment.embedding 物理列维度（pg_attribute.atttypmod）；
    进程级缓存（key=id(engine)）；atttypmod<=-1 或异常时返回 None。"""

# embedding_config.py（改动后语义）
def resolve_embedding_config_with_fallback(provider=None) -> EmbeddingConfig:
    # provider 给定 → 走 env 映射；否则查 DB 默认向量化模型，
    # cfg 存在且完整时即便 probe_embedding_config 返回 False 也返回 cfg（记 warning）；
    # 仅 cfg 为 None 才 resolve_embedding_config(None) 回落 env。
```

