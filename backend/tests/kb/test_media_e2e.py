"""媒体摄取端到端测试：校验 → 管线分支 → Chunk 入库 → media_kind 检索命中。

provider/KB 全 fake（不发真实嵌入请求）；检索命中段由测试模拟 KB 落库
（与 test_media_retrieval 同风格），验证整条编排缝。
"""
import uuid as _uuid

import pytest

from app.models.kb.kb_collection import KbCollection
from app.models.kb.kb_document import KbDocument
from app.models.kb.kb_segment import KbSegment
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.services.kb.media import base as media_base
from app.services.kb.media.base import MediaExtraction, MediaSegment
from app.services.kb.media.validation import validate_media_upload
from app.services.kb.pgvector_store import PGVectorStore


class _KB:
    multimodal_enabled = True


class _FakeDxf:
    def __init__(self, extraction):
        self._extraction = extraction

    async def extract(self, data, filename):
        return self._extraction


class _FakeKBCtx:
    def __init__(self, captured):
        self._captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def ensure_collection(self):
        pass

    async def insert_document(self, chunks, document_id=None,
                              document_metadata=None):
        self._captured.append({
            "chunks": chunks, "document_id": document_id,
            "document_metadata": document_metadata,
        })
        return len(chunks)


@pytest.fixture()
def env(db):
    kb = WikiKnowledge(tenant_id=1, name="多模态E2E库", type=2,
                       kb_format="document", multimodal_enabled=True,
                       slug=f"mm-e2e-{_uuid.uuid4().hex[:8]}")
    db.add(kb)
    db.flush()
    coll = f"kb_{kb.id}"
    db.add(KbCollection(tenant_id=1, knowledge_id=kb.id, name=coll,
                        dimensions=768))
    doc = KbDocument(tenant_id=1, knowledge_id=kb.id, collection=coll,
                     name="part.dxf", source_type="upload", file_type="dxf",
                     file_size=1024)
    db.add(doc)
    db.commit()
    return {"coll": coll, "doc": doc}


def test_media_e2e_ingest_and_retrieve(db, env, monkeypatch):
    from app.services.kb.document_pipeline import run_document_ingest

    # ① 上传门禁通过（multimodal_enabled=True，1KB DXF）
    validate_media_upload(_KB(), "part.dxf", 1024)

    # ② fake 提取器：2 个图层段
    extraction = MediaExtraction(kind="drawing", segments=[
        MediaSegment(text="图层 A：轴线标注", locator={"layer": "A"}),
        MediaSegment(text="图层 B：尺寸标注", locator={"layer": "B"}),
    ], meta={"layer_count": 2})
    monkeypatch.setattr(
        media_base, "get_extractor",
        lambda kind, db_, override=None: _FakeDxf(extraction))

    # ③ fake KB：捕获 insert_document 收到的 chunks
    captured: list = []

    def _factory(index_mode=None):
        return _FakeKBCtx(captured)

    # ④ 管线入口：媒体分支自动生效
    count = run_document_ingest(db, 1, env["doc"].id, b"dxf-bytes", "part.dxf",
                                knowledge_factory=_factory)
    assert count == 2
    chunks = captured[0]["chunks"]
    assert [c.metadata["chunk_type"] for c in chunks] == ["drawing", "drawing"]
    assert chunks[0].metadata["media_locator"] == {"layer": "A"}
    assert captured[0]["document_metadata"]["source"] == "media:drawing"
    db.refresh(env["doc"])
    assert env["doc"].status == "completed"
    assert env["doc"].meta["media"]["kind"] == "drawing"

    # ⑤ 模拟 KB 落库后的真实段（内容/元数据与 Chunk 同构）
    texts = ["图层 A：轴线标注", "图层 B：尺寸标注"]
    locators = [{"layer": "A"}, {"layer": "B"}]
    for i, (text, loc) in enumerate(zip(texts, locators)):
        db.add(KbSegment(
            tenant_id=1, collection=env["coll"],
            document_id=env["doc"].uuid_code, chunk_index=i,
            content=text, chunk_type="drawing",
            metadata_={"media_kind": "drawing", "media_locator": loc},
        ))
    db.commit()

    # ⑥ media_kind 检索命中并带定位块
    store = PGVectorStore(db, 1)
    hits = store.hybrid_search(env["coll"], None, "轴线标注", 10,
                               media_kind="drawing")
    assert len(hits) == 1
    assert hits[0].content == "图层 A：轴线标注"
    assert hits[0].media == {"kind": "drawing", "locator": {"layer": "A"}}
    # document 过滤排除媒体段
    assert store.hybrid_search(env["coll"], None, "轴线标注", 10,
                               media_kind="document") == []
