"""原生 RAG 装配层测试（对齐文档 §11：D2/D10/D12/D19）。

复用 tests/kb 的 PG 独立 schema 夹具；PgVectorStore 走真实 kb_segment 表。
"""
from __future__ import annotations

import pytest
from agentscope.rag import (
    Chunk,
    DocumentSummary,
    VectorRecord,
    VectorSearchResult,
    VectorStoreBase,
)
from agentscope.message import TextBlock
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.kb.kb_collection import KbCollection
from app.services.kb.rag import chunker_factory
from app.services.kb.rag.pg_vector_store import PgVectorStore

DIM = settings.GPUSTACK_EMBEDDING_DIMENSION


def _vec(v: float = 0.1):
    return [v] * DIM


def _record(doc_id: str, idx: int, text: str, meta: dict | None = None, v: float = 0.1):
    return VectorRecord(
        vector=_vec(v),
        document_id=doc_id,
        chunk=Chunk(
            content=TextBlock(text=text),
            source="a.md",
            chunk_index=idx,
            total_chunks=1,
            metadata={"chunk_type": "text", **(meta or {})},
        ),
    )


@pytest.fixture
def collection(db) -> KbCollection:
    coll = KbCollection(tenant_id=100, name="kb_native", dimensions=DIM)
    db.add(coll)
    db.commit()
    db.refresh(coll)
    return coll


@pytest.fixture
def factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def test_pgvector_store_implements_native_contract():
    assert issubclass(PgVectorStore, VectorStoreBase)
    assert not PgVectorStore.__abstractmethods__  # 7 个抽象方法全部实现
    for m in ("create_collection", "delete_collection", "has_collection",
              "insert", "delete", "search", "list_documents",
              "__aenter__", "__aexit__"):
        assert hasattr(PgVectorStore, m)


@pytest.mark.asyncio
async def test_insert_list_delete_roundtrip(factory, collection):
    async with PgVectorStore(factory, tenant_id=100, dimensions=DIM) as store:
        await store.insert("kb_native", [
            _record("doc-1", 0, "第一段"),
            _record("doc-1", 1, "第二段"),
        ])
        docs = await store.list_documents("kb_native")
        assert len(docs) == 1 and isinstance(docs[0], DocumentSummary)
        assert docs[0].chunk_count == 2
        await store.delete("kb_native", "doc-1")
        assert await store.list_documents("kb_native") == []


@pytest.mark.asyncio
async def test_search_score_larger_is_better_and_metadata_filter(factory, collection):
    async with PgVectorStore(factory, tenant_id=100, dimensions=DIM) as store:
        # 常数向量方向相同（余弦距离为 0），故第二条用反向向量制造距离差
        await store.insert("kb_native", [
            _record("doc-1", 0, "命中内容", {"tag": "x"}, v=0.1),
            _record("doc-1", 1, "另一段", {"tag": "y"}, v=-0.9),
        ])
        hits = await store.search("kb_native", _vec(0.1), top_k=5)
        assert hits and isinstance(hits[0], VectorSearchResult)
        # 与查询向量同向（0.1）的段距离更小 → score 更大（D12）
        assert hits[0].chunk.content.text == "命中内容"
        assert hits[0].score > hits[-1].score

        filtered = await store.search("kb_native", _vec(0.1), top_k=5,
                                      metadata_filter={"tag": "y"})
        assert len(filtered) == 1 and filtered[0].chunk.content.text == "另一段"


@pytest.mark.asyncio
async def test_create_collection_dimension_mismatch_fails(factory, collection):
    async with PgVectorStore(factory, tenant_id=100, dimensions=DIM) as store:
        with pytest.raises(ValueError):
            await store.create_collection("kb_native", DIM + 1)  # D19


@pytest.mark.asyncio
async def test_economy_mode_writes_null_vector(factory, collection):
    async with PgVectorStore(factory, tenant_id=100, dimensions=DIM,
                             index_mode="economy") as store:
        await store.insert("kb_native", [_record("doc-1", 0, "文本")])
        # economy 关闭向量分支（D11）：search 返回空，不抛错
        assert await store.search("kb_native", _vec(0.1)) == []


def test_build_chunker_and_qa_chunks():
    chunker = chunker_factory.build_chunker("approx_token", {"chunk_size": 32, "overlap": 4})
    assert chunker.chunker_type == "approx_token"
    qa = chunker_factory.build_qa_chunks([{"question": "Q?", "answer": "A", "tags": ["t"]}])
    assert qa[0].metadata["chunk_type"] == "qa" and qa[0].metadata["answer"] == "A"
    rows = chunker_factory.build_table_row_chunks(
        [{"desc": "低价防水", "price": 9}], embed_field="desc")
    assert rows[0].content.text == "低价防水" and rows[0].metadata["price"] == 9
