"""摄取管线媒体分支测试：媒体文件走 run_media_ingest，非媒体不分支。"""
import pytest

from app.models.kb.kb_document import KbDocument


@pytest.fixture()
def doc(db):
    d = KbDocument(
        tenant_id=1, knowledge_id=1, collection="kb_1", name="a.mp3",
        source_type="upload", file_type="mp3", file_size=10,
    )
    db.add(d)
    db.commit()
    return d


class _Sentinel(Exception):
    pass


def test_media_file_branches_to_media_ingest(db, doc, monkeypatch):
    from app.services.kb import document_pipeline as dp
    from app.services.kb.media import ingest as media_ingest

    called = {}

    def _fake_media(db_, tenant_id, doc_id, file_bytes, filename,
                    session_factory=None, kb_factory=None):
        called.update(filename=filename, doc_id=doc_id, bytes=file_bytes,
                      kb_factory=kb_factory)
        return 5

    monkeypatch.setattr(media_ingest, "run_media_ingest", _fake_media)
    factory = object()
    count = dp.run_document_ingest(db, 1, doc.id, b"mp3-bytes", "a.mp3",
                                   knowledge_factory=factory)
    assert count == 5
    assert called == {"filename": "a.mp3", "doc_id": doc.id,
                      "bytes": b"mp3-bytes", "kb_factory": factory}


def test_non_media_file_does_not_branch(db, doc, monkeypatch):
    from app.services.kb import document_pipeline as dp
    from app.services.kb.media import ingest as media_ingest

    def _should_not_call(*a, **kw):
        raise AssertionError("非媒体文件不应走媒体摄取")

    monkeypatch.setattr(media_ingest, "run_media_ingest", _should_not_call)

    def _raise(*a, **kw):
        raise _Sentinel()

    monkeypatch.setattr(dp, "run_pipeline_from_config", _raise)
    with pytest.raises(_Sentinel):
        dp.run_document_ingest(db, 1, doc.id, b"md-bytes", "a.md")
