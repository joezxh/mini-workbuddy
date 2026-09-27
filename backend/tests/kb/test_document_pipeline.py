"""文档摄取管线端到端（spec §10.3，假向量不联网）。

复用 tests/kb 的 PG 独立 schema 夹具；`embed_fn` 直接注入假向量，
同时验证 KbCollection.dimensions 维度校验路径。
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models.kb.kb_collection import KbCollection
from app.models.kb.kb_document import KbDocument
from app.services.kb.document_pipeline import run_document_ingest


@pytest.fixture
def kb_collection(db: Session) -> KbCollection:
    # 维度必须与 kb_segment.embedding 列 DDL（GPUSTACK_EMBEDDING_DIMENSION=768）一致
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


def _fake_embed(texts):
    from app.config import settings

    return [[0.1] * settings.GPUSTACK_EMBEDDING_DIMENSION for _ in texts]


def test_pipeline_end_to_end_completed(db: Session, doc: KbDocument):
    content = "# 标题\n\n" + "\n\n".join(f"段落{i} " + "内容" * 120 for i in range(4))
    count = run_document_ingest(
        db, 100, doc.id, content.encode("utf-8"), "a.md",
        chunker_type="approx_token",
        chunker_params={"chunk_size": 64, "overlap": 8},
        embed_fn=_fake_embed,
    )

    assert count >= 2
    db.expire_all()
    fresh = db.get(KbDocument, doc.id)
    assert fresh.status == "completed"
    assert fresh.segment_count == count
    assert fresh.error_detail is None


def test_pipeline_idempotent_reingest(db: Session, doc: KbDocument):
    """同文档重复摄取：幂等 upsert，切片数不翻倍。"""
    content = "# 标题\n\n" + "\n\n".join(f"段落{i} " + "内容" * 120 for i in range(4))
    first = run_document_ingest(
        db, 100, doc.id, content.encode("utf-8"), "a.md",
        chunker_type="approx_token", chunker_params={"chunk_size": 64, "overlap": 8},
        embed_fn=_fake_embed,
    )
    second = run_document_ingest(
        db, 100, doc.id, content.encode("utf-8"), "a.md",
        chunker_type="approx_token", chunker_params={"chunk_size": 64, "overlap": 8},
        embed_fn=_fake_embed,
    )
    assert first == second


def test_pipeline_failure_marks_failed(db: Session, doc: KbDocument):
    """未知 chunker_type → 状态 failed 且 error_detail 含步骤信息。"""
    with pytest.raises(ValueError):
        run_document_ingest(
            db, 100, doc.id, b"content", "a.md",
            chunker_type="nonexistent", embed_fn=_fake_embed,
        )
    db.expire_all()
    fresh = db.get(KbDocument, doc.id)
    assert fresh.status == "failed"
    assert fresh.error_detail  # 含步骤/原因，可观测
