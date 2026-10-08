"""Agent RAG 端到端联调（对齐文档 §7 / D16 / 验收标准 7）。

用**假嵌入模型**（确定性向量，不联网）构建完整原生链路：
PgVectorStore → KnowledgeBase.insert_document → KnowledgeBase.search，
并验证 RAGMiddleware 装配（D16）可被构造且暴露检索工具。覆盖 Agent 侧 RAG
数据路径；economy 库不进入向量 RAG（见 agent_factory._rag_kwargs 守卫）。
"""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from agentscope.embedding import EmbeddingModelBase, EmbeddingResponse
from agentscope.message import TextBlock
from agentscope.rag import Chunk, KnowledgeBase
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.kb.kb_collection import KbCollection
from app.services.kb.rag.pg_vector_store import PgVectorStore
from app.services.kb.rag.rag_middleware import build_rag_middleware

DIM = settings.GPUSTACK_EMBEDDING_DIMENSION


class FakeEmbeddingModel(EmbeddingModelBase):
    """确定性嵌入：同一文本恒得同一向量（不联网，仅供测试）。"""

    def __init__(self, dimensions: int = DIM) -> None:
        # EmbeddingModelBase 为普通 Generic 类，直接落属性即可
        self.credential = SimpleNamespace()  # 占位，__call__ 不读取
        self.model = "fake-deterministic"
        self.dimensions = dimensions
        self.parameters = None
        self.context_size = 8192
        self.batch_size = 16
        self.max_retries = 1
        self.retry_delay = 0.0

    async def _call_api(self, inputs, **kwargs) -> EmbeddingResponse:
        vecs = []
        for text in inputs:
            h = hashlib.md5(str(text).encode("utf-8")).digest()
            vec = [((h[i % 16] / 255.0) - 0.5) for i in range(self.dimensions)]
            vecs.append(vec)
        return EmbeddingResponse(embeddings=vecs)


@pytest.fixture
def collection(db: object) -> KbCollection:
    coll = KbCollection(tenant_id=100, name="kb_e2e", dimensions=DIM)
    db.add(coll)
    db.commit()
    db.refresh(coll)
    return coll


@pytest.fixture
def factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _kb(factory, collection_name: str = "kb_e2e", index_mode: str = "high_quality"):
    store = PgVectorStore(factory, tenant_id=100, dimensions=DIM, index_mode=index_mode)
    return KnowledgeBase(
        name=collection_name,
        description="e2e kb",
        embedding_model=FakeEmbeddingModel(),
        vector_store=store,
        collection=collection_name,
        metadata_filter={"tenant_id": 100},
    ), store


@pytest.mark.asyncio
async def test_rag_ingest_search_roundtrip(factory, collection):
    """Agent 检索数据路径端到端：写入→检索命中同内容。"""
    kb, store = _kb(factory)
    async with store:
        await kb.ensure_collection()
        chunks = [
            Chunk(content=TextBlock(text="MinWorkBuddy 知识库检索端到端测试"),
                  source="a.md", chunk_index=0, total_chunks=1,
                  metadata={"chunk_type": "text"}),
            Chunk(content=TextBlock(text="另一段无关内容用于区分"),
                  source="a.md", chunk_index=1, total_chunks=1,
                  metadata={"chunk_type": "text"}),
        ]
        await kb.insert_document(chunks, document_id="doc-e2e",
                                 document_metadata={"source": "a.md"})

        hits = await kb.search(queries=["MinWorkBuddy 知识库检索端到端测试"], top_k=3)
        assert hits, "检索应返回命中"
        assert isinstance(hits[0].score, float)
        assert "端到端测试" in hits[0].chunk.content.text
        assert hits[0].document_id == "doc-e2e"


@pytest.mark.asyncio
async def test_rag_middleware_assembles_with_search_tool(factory, collection):
    """D16：RAGMiddleware 装配暴露检索工具（agentic 模式）。"""
    kb, store = _kb(factory)
    async with store:
        await kb.ensure_collection()
        await kb.insert_document(
            [Chunk(content=TextBlock(text="RAG 中间件检索工具验证"),
                   source="b.md", chunk_index=0, total_chunks=1,
                   metadata={"chunk_type": "text"})],
            document_id="doc-mw", document_metadata={"source": "b.md"})

        mw = build_rag_middleware([kb], rag_cfg={"mode": "agentic", "top_k": 3})
        tools = await mw.list_tools()
        assert tools, "RAGMiddleware 应暴露至少一个检索工具"
        # 工具名包含 knowledge 语义
        names = {getattr(t, "name", None) or getattr(t, "func_name", None) for t in tools}
        assert any("knowledge" in str(n).lower() for n in names if n)


@pytest.mark.asyncio
async def test_economy_kb_writes_null_vector_and_search_empty(factory, collection):
    """AC7：economy 库写 NULL 向量，原生命名检索返回空（由独立关键词服务接管）。"""
    kb, store = _kb(factory, collection_name="kb_e2e", index_mode="economy")
    async with store:
        await kb.ensure_collection()
        await kb.insert_document(
            [Chunk(content=TextBlock(text="economy 关键词命中文本"),
                   source="c.md", chunk_index=0, total_chunks=1,
                   metadata={"chunk_type": "text"})],
            document_id="doc-eco", document_metadata={"source": "c.md"})
        # PgVectorStore 在 economy 下向量分支关闭（D11）
        assert await store.search("kb_e2e", [0.1] * DIM) == []


def test_economy_search_keyword_only(db, collection):
    """AC7：独立关键词检索服务命中子串，零 embedding 依赖（直接写 NULL 向量行）。"""
    from app.models.kb.kb_segment import KbSegment
    from app.services.kb.rag.economy_search import economy_search

    rows = [
        KbSegment(tenant_id=100, collection="kb_e2e", document_id="d1",
                  chunk_index=0, content="MinWorkBuddy 经济模式关键词检索",
                  embedding=None, metadata_={"chunk_type": "text"}),
        KbSegment(tenant_id=100, collection="kb_e2e", document_id="d2",
                  chunk_index=0, content="完全无关的另一段内容",
                  embedding=None, metadata_={"chunk_type": "text"}),
    ]
    db.add_all(rows)
    db.commit()

    hits = economy_search(db, 100, "kb_e2e", "经济模式关键词", top_k=5)
    assert hits, "应命中含子串的行"
    assert "经济模式关键词" in hits[0]["content"]
    assert all("完全无关" not in h["content"] for h in hits)

    # 越靠前命中分越高
    assert hits[0]["score"] >= hits[-1]["score"]
    # 零 embedding：检索不依赖向量列
    assert all(h["score"] > 0 for h in hits)


def test_economy_search_metadata_filter(db, collection):
    """独立关键词服务支持 metadata_filter（JSONB @>）。"""
    from app.models.kb.kb_segment import KbSegment
    from app.services.kb.rag.economy_search import economy_search

    db.add(KbSegment(tenant_id=100, collection="kb_e2e", document_id="d3",
                     chunk_index=0, content="带标签的知识库内容",
                     embedding=None, metadata_={"chunk_type": "text", "tag": "x"}))
    db.commit()

    only_x = economy_search(db, 100, "kb_e2e", "知识库", metadata_filter={"tag": "x"})
    assert only_x and only_x[0]["metadata"]["tag"] == "x"
    none = economy_search(db, 100, "kb_e2e", "知识库", metadata_filter={"tag": "nope"})
    assert none == []

