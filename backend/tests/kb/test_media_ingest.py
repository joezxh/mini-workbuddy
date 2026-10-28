"""媒体摄取编排测试（fake extractor + fake _insert_via_kb，真实 PG schema）。"""
import pytest

from app.models.kb.kb_document import KbDocument
from app.services.kb.media import base as media_base
from app.services.kb.media.base import MediaExtraction, MediaSegment


@pytest.fixture()
def doc(db):
    d = KbDocument(
        tenant_id=1, knowledge_id=1, collection="kb_1", name="a.dxf",
        source_type="upload", file_type="dxf", file_size=10,
    )
    db.add(d)
    db.commit()
    return d


def _patch_extractor(monkeypatch, extraction=None, exc=None):
    class _FakeExt:
        def __init__(self, db_, override=None):
            pass

        async def extract(self, data, filename):
            if exc is not None:
                raise exc
            return extraction

    monkeypatch.setattr(
        media_base, "get_extractor",
        lambda kind, db, override=None: _FakeExt(db, override))


def _patch_insert(monkeypatch, sink: list):
    from app.services.kb.rag import content_service

    def _fake(session_factory, *, db, collection, tenant_id, document_id, chunks,
              kb_factory=None, document_metadata=None):
        sink.append({
            "collection": collection, "tenant_id": tenant_id,
            "document_id": document_id, "chunks": chunks,
            "document_metadata": document_metadata,
        })

    monkeypatch.setattr(content_service, "_insert_via_kb", _fake)


def test_run_media_ingest_success(db, doc, monkeypatch):
    from app.services.kb.media.ingest import run_media_ingest

    extraction = MediaExtraction(kind="drawing", segments=[
        MediaSegment(text="图层 A：标注1", locator={"layer": "A"}),
        MediaSegment(text="图层 B：标注2", locator={"layer": "B"}),
    ], meta={"layer_count": 2})
    _patch_extractor(monkeypatch, extraction=extraction)
    sink: list = []
    _patch_insert(monkeypatch, sink)

    count = run_media_ingest(db, 1, doc.id, b"dxf-bytes", "a.dxf")
    assert count == 2
    assert sink[0]["document_id"] == doc.uuid_code
    assert sink[0]["collection"] == "kb_1"
    assert sink[0]["document_metadata"]["source"] == "media:drawing"
    chunks = sink[0]["chunks"]
    assert len(chunks) == 2
    c0 = chunks[0]
    assert c0.metadata["chunk_type"] == "drawing"
    assert c0.metadata["media_kind"] == "drawing"
    assert c0.metadata["media_locator"] == {"layer": "A"}
    assert c0.chunk_index == 0 and c0.total_chunks == 2
    db.refresh(doc)
    assert doc.status == "completed"
    assert doc.segment_count == 2
    assert doc.meta["media"]["kind"] == "drawing"
    assert doc.meta["failed_step"] is None


def test_run_media_ingest_extract_failure(db, doc, monkeypatch):
    from app.services.kb.media.ingest import run_media_ingest

    _patch_extractor(monkeypatch, exc=ValueError("DXF 损坏"))
    sink: list = []
    _patch_insert(monkeypatch, sink)

    with pytest.raises(Exception):
        run_media_ingest(db, 1, doc.id, b"dxf-bytes", "a.dxf")
    db.refresh(doc)
    assert doc.status == "failed"
    assert doc.meta["failed_step"] == "extract"
    assert "DXF 损坏" in doc.error_detail
    assert sink == []


def test_run_media_ingest_rejects_non_media(db, doc, monkeypatch):
    from app.services.kb.media.ingest import run_media_ingest

    with pytest.raises(ValueError):
        run_media_ingest(db, 1, doc.id, b"x", "a.pdf")
