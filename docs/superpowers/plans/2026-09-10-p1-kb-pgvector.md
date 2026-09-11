# P1 · 知识库内核（AgentScope RAG Service + PGVector）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 MinWorkBuddy 中落地可私有部署的多租户知识库：挂载 AgentScope 原生 RAG Service，自研 `PGVectorStore` 适配现有 PG17 + pgvector，并加入 `pg_trgm` 中文混合检索。

**Architecture:** MWB 的 FastAPI 通过 `app.mount("/agentscope", create_app(...))` 挂载 AgentScope RAG Service，获得知识库 CRUD、异步索引、状态机、容错自愈与检索能力。自研部分仅三件：`PGVectorStore(VectorStoreBase)`（唯一必须的向量后端适配，含中文混合检索）、`UserIdMapper`（MWB 租户 → AgentScope user_id）、embedding 配置映射（GPUStack→OpenAI provider，DashScope→原生 provider）。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 / PostgreSQL 17 + pgvector + pg_trgm / Alembic / AgentScope 2.0.7.post1（**锁定，不升级**）/ Redis Stack（Storage + MessageBus）/ pytest

**Spec:** `docs/superpowers/specs/2026-09-10-kb-pgvector-design.md`
**依赖：** 无（地基）。**被依赖：** P2、P3、P4.3
**上游风险（必须最先验证）：** mount 后子应用 lifespan 是否执行

---

## 文件结构

| 路径 | 职责 |
|---|---|
| `backend/app/ai/knowledge/as/pgvector_store.py` | `PGVectorStore(VectorStoreBase)` —— 核心自研件 |
| `backend/app/ai/knowledge/as/hybrid_search.py` | `pg_trgm` 召回 + RRF 融合（被 `pgvector_store.search` 调用） |
| `backend/app/ai/knowledge/as/user_id_mapper.py` | MWB `tenant_id` → AgentScope `user_id` |
| `backend/app/ai/knowledge/as/embedding_config.py` | GPUStack/DashScope → AgentScope embedding 配置 |
| `backend/app/ai/knowledge/as/app_factory.py` | `create_app` 构造 + mount 封装 |
| `backend/app/ai/knowledge/chunkers/qa_chunker.py` | 结构化数据问答切片（可选，Task 10） |
| `backend/app/models/kb/kb_collection.py` | collection 元数据 ORM |
| `backend/app/models/kb/kb_segment.py` | 切片 + 向量 ORM |
| `backend/app/models/kb/kb_ref.py` | MWB 侧 KB 映射（权限/列表，继承 `TenantMixin`） |
| `backend/app/services/kb/kb_ref_service.py` | `kb_ref` 读写 + 权限过滤 |
| `backend/app/routers/kb/kb.py` | MWB 侧补充端点（`kb_ref` 列表、统计） |
| `backend/tests/kb/test_pgvector_store.py` | 契约测试 |
| `backend/tests/kb/test_hybrid_search.py` | 中文混合检索测试 |
| `backend/tests/kb/test_user_id_mapper.py` | 租户隔离测试 |
| `backend/tests/kb/test_mount.py` | mount 与路由可达性测试 |
| `backend/alembic/versions/xxxx_add_kb_tables.py` | 迁移 |

约定：`Base` 从 `app.db.database` 导入；租户表继承 `app.models.tenant_mixin.TenantMixin`；迁移用 Alembic。

---

### Task 1: 启用 pg_trgm 并建表迁移

**Files:**
- Create: `backend/alembic/versions/xxxx_add_kb_tables.py`
- Create: `backend/app/models/kb/kb_collection.py`
- Create: `backend/app/models/kb/kb_segment.py`
- Create: `backend/app/models/kb/kb_ref.py`

- [ ] **Step 1: 启用扩展 + 写建表迁移**

```python
# backend/alembic/versions/xxxx_add_kb_tables.py
def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "kb_collection",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True, index=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "kb_segment",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("collection", sa.String(128), nullable=False),
        sa.Column("document_id", sa.String(128), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),   # 维度由 config 决定，见 Step 2 说明
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True, index=True),
        sa.UniqueConstraint("collection", "document_id", "chunk_index",
                            name="uq_kb_segment"),
    )
    op.create_index("idx_kb_segment_collection", "kb_segment", ["collection"])
    op.create_index(
        "idx_kb_segment_embedding", "kb_segment", ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.execute(
        "CREATE INDEX idx_kb_segment_content_trgm ON kb_segment "
        "USING gin (content gin_trgm_ops)"
    )

    op.create_table(
        "kb_ref",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True, index=True),
        sa.Column("kb_id", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("as_user_id", sa.String(64), nullable=False),
        sa.Column("doc_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("segment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("creator_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
    )
```

> 向量维度：迁移里先用 `Vector(768)`（当前默认 provider 的维度）。若部署改用 DashScope（1024），需另生成一条迁移改列类型——**不要**在迁移里写死多个维度，`kb_collection.dimensions` 才是运行时真值。

- [ ] **Step 2: 在 `app/config.py` 增加 `KB_BLOB_DIR`**

```python
# RAG Service 上传文件的本地 blob 存储根目录；留空则默认 <项目根>/data/kb_blobs
KB_BLOB_DIR: str = ""
```

Task 8 的 `LocalBlobStore(root_dir=...)` 依赖此配置。

- [ ] **Step 3: 新建三个 ORM，并在 `app/db/init_models.py` 注册**

```python
# backend/app/models/kb/kb_segment.py
class KbSegment(Base, TenantMixin):
    __tablename__ = "kb_segment"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    collection = Column(String(128), nullable=False)
    document_id = Column(String(128), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=True)
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION), nullable=True)
    token_count = Column(Integer, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
```

- [ ] **Step 4: 跑迁移**

Run: `cd backend && alembic upgrade head`
Expected: 三张表 + 三个索引创建成功

- [ ] **Step 5: Commit**

```bash
git add backend/alembic backend/app/models/kb backend/app/db/init_models.py backend/app/config.py
git commit -m "feat(kb): add kb_collection/kb_segment/kb_ref tables and pg_trgm"
```

---

### Task 2: `PGVectorStore` 骨架与 collection 管理

**Files:**
- Create: `backend/app/ai/knowledge/as/pgvector_store.py`
- Test: `backend/tests/kb/test_pgvector_store.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/kb/test_pgvector_store.py
import pytest
from app.ai.knowledge.as.pgvector_store import PGVectorStore

def test_create_and_has_collection(db_session):
    store = PGVectorStore(db=db_session, tenant_id=1)
    pytest.importorskip("agentscope")
    import asyncio
    asyncio.run(store.create_collection("kb_test", 768))
    assert asyncio.run(store.has_collection("kb_test")) is True

def test_delete_collection(db_session):
    store = PGVectorStore(db=db_session, tenant_id=1)
    import asyncio
    asyncio.run(store.create_collection("kb_gone", 768))
    asyncio.run(store.delete_collection("kb_gone"))
    assert asyncio.run(store.has_collection("kb_gone")) is False
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/kb/test_pgvector_store.py -v`
Expected: FAIL `ModuleNotFoundError: app.ai.knowledge.as.pgvector_store`

- [ ] **Step 3: 最小实现**

```python
# backend/app/ai/knowledge/as/pgvector_store.py
from __future__ import annotations
from typing import Any
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.orm import Session
from agentscope.rag import DocumentSummary, VectorRecord, VectorSearchResult, VectorStoreBase
from app.models.kb.kb_collection import KbCollection
from app.models.kb.kb_segment import KbSegment


class PGVectorStore(VectorStoreBase):
    """pgvector 后端。

    collection 是逻辑名（kb_<uuid>），映射到 kb_segment.collection 列，
    不为每个 collection 建表。
    """

    def __init__(self, db: Session, tenant_id: int | None) -> None:
        self._db = db
        self._tenant_id = tenant_id

    async def create_collection(self, name: str, dimensions: int) -> None:
        exists = self._db.scalar(
            select(KbCollection).where(KbCollection.name == name)
        )
        if exists:
            return
        self._db.add(KbCollection(name=name, dimensions=dimensions,
                                  tenant_id=self._tenant_id))
        self._db.commit()

    async def delete_collection(self, name: str) -> None:
        self._db.execute(sa_delete(KbSegment).where(KbSegment.collection == name))
        self._db.execute(sa_delete(KbCollection).where(KbCollection.name == name))
        self._db.commit()

    async def has_collection(self, name: str) -> bool:
        return self._db.scalar(
            select(KbCollection.id).where(KbCollection.name == name)
        ) is not None
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/kb/test_pgvector_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/knowledge/as/pgvector_store.py backend/tests/kb
git commit -m "feat(kb): add PGVectorStore collection management"
```

---

### Task 3: `insert` / `delete`（文档级整体删除）

**Files:**
- Modify: `backend/app/ai/knowledge/as/pgvector_store.py`
- Test: `backend/tests/kb/test_pgvector_store.py`

- [ ] **Step 1: 追加失败测试**

```python
def test_insert_and_delete_by_document(db_session):
    from agentscope.rag import TextBlock, Chunk, VectorRecord
    import asyncio
    store = PGVectorStore(db=db_session, tenant_id=1)
    asyncio.run(store.create_collection("kb_doc", 768))

    def mk(i):
        return VectorRecord(
            vector=[0.1, 0.2, 0.3],
            document_id="doc-1",
            chunk=Chunk(content=TextBlock(text=f"chunk {i}"),
                        source="a.txt", chunk_index=i, total_chunks=2),
        )
    asyncio.run(store.insert("kb_doc", [mk(0), mk(1)]))
    docs = asyncio.run(store.list_documents("kb_doc"))
    assert docs[0].chunk_count == 2

    asyncio.run(store.delete("kb_doc", "doc-1"))
    assert asyncio.run(store.list_documents("kb_doc")) == []

def test_insert_is_idempotent(db_session):
    """同一 (collection, document_id, chunk_index) 重复插入不增行。"""
    import asyncio
    store = PGVectorStore(db=db_session, tenant_id=1)
    asyncio.run(store.create_collection("kb_idem", 768))
    # 连续两次插入同一批记录，行数应保持 2
    # （断言见实现后的 count 查询）
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现 `insert` / `delete` / `list_documents`**

```python
    async def insert(self, collection: str, records: list[VectorRecord]) -> None:
        for rec in records:
            values = {
                "collection": collection,
                "document_id": rec.document_id,
                "chunk_index": rec.chunk.chunk_index,
                "content": _chunk_text(rec.chunk),
                "embedding": rec.vector,
                "metadata_": rec.chunk.metadata,
                "tenant_id": self._tenant_id,
            }
            stmt = (
                postgresql_insert(KbSegment)
                .values(**values)
                .on_conflict_do_update(
                    constraint="uq_kb_segment",
                    set_={"content": values["content"],
                          "embedding": values["embedding"],
                          "metadata_": values["metadata_"]},
                )
            )
            self._db.execute(stmt)
        self._db.commit()

    async def delete(self, collection: str, document_id: str) -> None:
        self._db.execute(
            sa_delete(KbSegment).where(
                KbSegment.collection == collection,
                KbSegment.document_id == document_id,
            )
        )
        self._db.commit()

    async def list_documents(self, collection: str) -> list[DocumentSummary]:
        rows = self._db.execute(
            select(
                KbSegment.document_id,
                func.min(KbSegment.source),
                func.count(KbSegment.id),
            ).where(KbSegment.collection == collection)
            .group_by(KbSegment.document_id)
        ).all()
        return [
            DocumentSummary(document_id=r[0], source=r[1] or "",
                            chunk_count=r[2], metadata={})
            for r in rows
        ]
```

> `Chunk.content` 为 `TextBlock`（含 `text`）或 `DataBlock`（含 `data`）。需写 `_chunk_text(chunk)` 助手统一取文本——在 Step 3 一并实现并在测试里覆盖两种类型。

- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(kb): implement insert/delete/list_documents on PGVectorStore"
```

---

### Task 4: 向量检索 + HNSW

**Files:**
- Modify: `backend/app/ai/knowledge/as/pgvector_store.py`
- Test: `backend/tests/kb/test_pgvector_store.py`

- [ ] **Step 1: 写失败测试**（插入 3 条已知向量，检索与 query 最相近的一条）

```python
def test_search_returns_nearest(db_session):
    import asyncio
    store = PGVectorStore(db=db_session, tenant_id=1)
    asyncio.run(store.create_collection("kb_s", 3))
    asyncio.run(store.insert("kb_s", [
        _rec("d1", 0, [1.0, 0.0, 0.0], "apple"),
        _rec("d1", 1, [0.0, 1.0, 0.0], "banana"),
    ]))
    hits = asyncio.run(store.search("kb_s", [1.0, 0.0, 0.0], top_k=1))
    assert hits[0].document_id == "d1"
    assert hits[0].score > 0.99
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现 `search` 向量侧 + `list_chunks`**
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(kb): vector search with HNSW index"
```

---

### Task 5: 中文混合检索（pg_trgm + RRF）

**Files:**
- Create: `backend/app/ai/knowledge/as/hybrid_search.py`
- Test: `backend/tests/kb/test_hybrid_search.py`

- [ ] **Step 1: 写失败测试**

```python
def test_chinese_keyword_recall(db_session):
    """纯向量可能漏掉，但关键词侧必须召回。"""
    import asyncio
    store = PGVectorStore(db=db_session, tenant_id=1, hybrid=True)
    asyncio.run(store.create_collection("kb_cn", 3))
    asyncio.run(store.insert("kb_cn", [_rec("d1", 0, [0.9, 0.1, 0.0], "逾期贷款处置流程规定"), ...]))
    hits = asyncio.run(store.search("kb_cn", [0.0, 0.0, 1.0], top_k=5, query_text="逾期"))
    assert any("逾期" in h.chunk.content.text for h in hits)

def test_rrf_fusion_ranking():
    from app.ai.knowledge.as.hybrid_search import rrf_fuse
    vec = [("a", 1), ("b", 2)]
    kw = [("b", 1), ("a", 2)]
    fused = rrf_fuse([vec, kw], k=60)
    assert [x[0] for x in fused] == ["a", "b"]   # 两侧排名之和相同 → 稳定序
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**

```python
# backend/app/ai/knowledge/as/hybrid_search.py
def rrf_fuse(rank_lists: list[list[tuple[str, float]]], k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for lst in rank_lists:
        for rank, (key, _) in enumerate(lst, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
```

`PGVectorStore.search` 增加可选 `query_text` 参数：并行取向量 top_k*3 与 trgm top_k*3，RRF 融合后返回 top_k。

- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(kb): chinese hybrid retrieval via pg_trgm + RRF"
```

---

### Task 6: 租户隔离（UserIdMapper + 纵深防御）

**Files:**
- Create: `backend/app/ai/knowledge/as/user_id_mapper.py`
- Modify: `backend/app/ai/knowledge/as/pgvector_store.py`
- Test: `backend/tests/kb/test_user_id_mapper.py`

- [ ] **Step 1: 写失败测试**（租户 A 即使伪造 collection 名也读不到租户 B 数据）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**

```python
# backend/app/ai/knowledge/as/user_id_mapper.py
def to_as_user_id(tenant_id: int, user_id: int | None = None) -> str:
    """MWB 租户 → AgentScope user_id。规则上线即冻结，变更需数据迁移。"""
    return f"t{tenant_id}" if user_id is None else f"t{tenant_id}:u{user_id}"
```

`PGVectorStore` 所有查询强制附加 `tenant_id` 过滤；未提供 `tenant_id` 时抛异常而非放行。

- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(kb): tenant isolation via user_id mapping and defense in depth"
```

---

### Task 7: Embedding 配置映射

**Files:**
- Create: `backend/app/ai/knowledge/as/embedding_config.py`
- Test: `backend/tests/kb/test_embedding_config.py`

- [ ] **Step 1: 写失败测试**（`EMBEDDING_PROVIDER=gpustack` 时返回 OpenAI provider 配置且 base_url 指向 GPUStack；`dashscope` 时返回 DashScope 模型名）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**（纯配置映射，**不写自定义 EmbeddingModel**）
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(kb): map MWB embedding providers to AgentScope models"
```

---

### Task 8: `create_app` + mount（**最高风险，先验证**）

**Files:**
- Create: `backend/app/ai/knowledge/as/app_factory.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/kb/test_mount.py`

- [ ] **Step 1: 写验证测试**
```python
def test_agentscope_mounted(client):
    r = client.get("/agentscope/knowledge_bases/embedding_models")
    assert r.status_code == 200
```
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**

```python
# backend/app/ai/knowledge/as/app_factory.py
def build_agentscope_app(pipeline_executor=None):
    from agentscope.app import create_app
    from agentscope.app.message_bus import RedisMessageBus
    from agentscope.app.storage import RedisStorage
    from agentscope.app.workspace_manager import LocalWorkspaceManager
    from agentscope.app.rag.blob_store import LocalBlobStore
    from agentscope.app.rag.knowledge_base_manager import CollectionPerKbManager
    from agentscope.rag import (ApproxTokenChunker, ImageParser, PDFParser,
                                PPTParser, TextParser)

    storage = RedisStorage(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
    bus = RedisMessageBus(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
    kb_manager = CollectionPerKbManager(
        storage=storage,
        vector_store=PGVectorStore(db=SessionLocal(), tenant_id=None),
    )
    return create_app(
        storage=storage,
        message_bus=bus,
        workspace_manager=LocalWorkspaceManager(basedir=settings.resolved_workspace_base_dir),
        knowledge_base_manager=kb_manager,
        knowledge_parsers=[TextParser(), PDFParser(), PPTParser(), ImageParser()],
        knowledge_chunkers=[ApproxTokenChunker],
        blob_store=LocalBlobStore(root_dir=str(settings.KB_BLOB_DIR)),
    )
```

在 `app/main.py` 中 `app.mount("/agentscope", build_agentscope_app())`。

> **Step 3 必须先做一件事**：单独跑一个最小脚本验证 mount 后子应用 lifespan 是否执行（storage/bus 是否 `__aenter__`）。若不执行 → 改为独立服务（Task 8b），**不要**带着这个问题往下做。

- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(kb): mount AgentScope RAG service under /agentscope"
```

---

### Task 9: MWB 侧 `kb_ref` 服务与端点

**Files:**
- Create: `backend/app/services/kb/kb_ref_service.py`
- Create: `backend/app/routers/kb/kb.py`
- Modify: `backend/app/core/router_registry.py`

- [ ] **Step 1: 写失败测试**（列表按租户过滤、创建时写入 `as_user_id`）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**（列表/详情/统计；创建与删除需同步调 AgentScope `/knowledge_bases`）
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(kb): add kb_ref service and router for tenant-scoped listing"
```

---

### Task 10（可选）: `QaChunker` 结构化数据切片

**Files:**
- Create: `backend/app/ai/knowledge/chunkers/qa_chunker.py`

- [ ] **Step 1: 写失败测试**（表/列描述 → 问答对）
- [ ] **Step 2–4:** 实现 `ChunkerBase`、注册进 `knowledge_chunkers`、验证 `GET /knowledge_bases/chunkers` 能看到它
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(kb): add QaChunker for structured business data"
```

---

### Task 11: 端到端与性能基线

- [ ] **Step 1: 端到端脚本** —— 建 KB → 上传 PDF → 轮询状态到 `ready` → 检索命中
- [ ] **Step 2: 中文检索人工抽检** —— 10 条中文 query，记录纯向量 vs 混合的召回差异
- [ ] **Step 3: 性能基线** —— 灌 10 万切片，记录 P50/P95 检索延迟，写入 spec §9 的性能章节
- [ ] **Step 4: Commit**

```bash
git commit -m "test(kb): e2e and performance baseline for knowledge base"
```

---

## 验收标准

| 项 | 标准 |
|---|---|
| 契约 | `PGVectorStore` 满足 `VectorStoreBase` 全部 8 个方法语义 |
| 中文检索 | 中文 query 混合检索召回 ≥ 纯向量（抽检 10 条不下降） |
| 幂等 | 重复入库 `kb_segment` 不增行 |
| 租户隔离 | 租户 A 无法检索租户 B，即使伪造 collection |
| 维度混用 | 768 与 1024 两个 KB 并存互不影响 |
| mount | `/agentscope/knowledge_bases/*` 可达且 storage 已初始化 |
| 性能 | 10 万切片 P95 检索延迟有基线数据 |

## 风险与退路

| 风险 | 退路 |
|---|---|
| mount 后 lifespan 不执行 | 改独立服务（Task 8b），前端 API 前缀改为配置项 |
| HNSW 带过滤召回退化 | 单 collection > 10 万时按 collection 分区 |
| `pg_trgm` 中文召回不达标 | 评估 `zhparser` 定制镜像（需改 Dockerfile，非本计划范围，另立项） |
| Redis 成为强依赖 | 评估降级策略（RAG Service 不可用时知识库只读/禁用，不影响主流程） |
