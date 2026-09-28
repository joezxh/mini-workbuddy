"""文档摄取管线端到端（对齐文档 §8.1 / D4）：原生三步，假 KB 不联网。

复用 tests/kb 的 PG 独立 schema 夹具；注入 fake KnowledgeBase 验证
``ensure_collection`` + ``insert_document(document_id, document_metadata)``
被真实调用，且 kb_document 状态机流转正确。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models.kb.kb_collection import KbCollection
from app.models.kb.kb_document import KbDocument
from app.services.kb.document_pipeline import run_document_ingest

CALLS: list[dict] = []  # 记录 insert_document 调用参数（模块级便于断言）


class _FakeKB:
    def __init__(self):
        CALLS.clear()

    async def ensure_collection(self):
        CALLS.append({"op": "ensure_collection"})

    async def insert_document(self, chunks, document_id=None, document_metadata=None):
        CALLS.append({
            "op": "insert_document",
            "document_id": document_id,
            "document_metadata": document_metadata,
            "chunk_count": len(chunks),
            "first_index": chunks[0].chunk_index,
            "total_chunks": chunks[0].total_chunks,
        })
        return document_id or "doc"


@asynccontextmanager
async def _fake_kb_factory():
    yield _FakeKB()


@pytest.fixture
def kb_collection(db: Session) -> KbCollection:
    from app.config import settings

    coll = KbCollection(
        tenant_id=100, name="kb_pipeline_test",
        dimensions=settings.GPUSTACK_EMBEDDING_DIMENSION,
    )
    db.add(coll)
    db.commit()
    db.refresh(coll)
    return coll


@pytest.fixture
def doc(db: Session, kb_collection: KbCollection) -> KbDocument:
    Base.metadata.create_all(db.bind, tables=[KbDocument.__table__])
    d = KbDocument(
        tenant_id=100, knowledge_id=1, collection="kb_pipeline_test",
        name="a.md", source_type="upload", file_type="md", file_size=100,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


CONTENT = "# 标题\n\n" + "\n\n".join(f"段落{i} " + "内容" * 120 for i in range(4))


def test_pipeline_calls_native_insert_document(db: Session, doc: KbDocument):
    count = run_document_ingest(
        db, 100, doc.id, CONTENT.encode("utf-8"), "a.md",
        chunker_type="approx_token", chunker_params={"chunk_size": 64, "overlap": 8},
        knowledge_factory=_fake_kb_factory,
    )
    assert count >= 2
    insert = [c for c in CALLS if c["op"] == "insert_document"][0]
    assert insert["document_id"] == doc.uuid_code          # document_id 落库依据
    assert insert["chunk_count"] == count
    assert insert["chunk_count"] == insert["total_chunks"]  # 原生约定
    assert insert["document_metadata"]["filename"] == "a.md"

    db.expire_all()
    fresh = db.get(KbDocument, doc.id)
    assert fresh.status == "completed" and fresh.segment_count == count


def test_pipeline_failure_marks_failed(db: Session, doc: KbDocument):
    with pytest.raises(ValueError):
        run_document_ingest(
            db, 100, doc.id, b"content", "a.md",
            chunker_type="nonexistent", knowledge_factory=_fake_kb_factory,
        )
    db.expire_all()
    fresh = db.get(KbDocument, doc.id)
    assert fresh.status == "failed" and fresh.error_detail
