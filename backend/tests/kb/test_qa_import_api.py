"""问答(QA) CSV 导入端点 HTTP 冒烟（对齐 test_table_import_api）。

验证：问答知识库(kb_format=qa) + collection 创建 → 上传本地样例 CSV →
import 端点解析 question/answer/tags 并落库 → 可通过 qa-records 列表读回。

``_insert_via_kb`` 被替换为一个**真实写 kms_segment** 的假实现（仅嵌 NULL 向量，
免去联网 embedding），使端到端的「导入→读回」链路可被断言，又不依赖真实嵌入模型。
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import Base
from app.deps import get_current_user, get_db
from app.models.kb.kb_collection import KbCollection
from app.models.kb.kb_document import KbDocument
from app.models.kb.kb_segment import KbSegment
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.routers.kb.kb import router
from app.services.kb.rag import content_service

TENANT = 100
CSV_PATH = Path(__file__).parent / "fixtures" / "qa_sample.csv"


@pytest.fixture
def env(db: Session):
    Base.metadata.create_all(db.bind, tables=[KbDocument.__table__])
    kn = WikiKnowledge(tenant_id=TENANT, name="qa-kb", slug="qa-kb-api",
                       type=2, kb_format="qa", index_mode="high_quality")
    db.add(kn)
    db.commit()
    coll = KbCollection(tenant_id=TENANT, name=f"kb_{kn.id}", dimensions=768,
                         knowledge_id=kn.id)
    db.add(coll)
    db.commit()
    # 路由现按 collection_id 调用；暴露 id 供测试构造 URL（DB 查询仍按 name）
    return SimpleNamespace(id=kn.id, collection_id=coll.id)


@pytest.fixture
def env_no_collection(db: Session):
    """问答库但不创建任何 kms_collection 行（验证知识库级 Q&A 不依赖集合）。"""
    Base.metadata.create_all(db.bind, tables=[KbDocument.__table__])
    kn = WikiKnowledge(tenant_id=TENANT, name="qa-kb-nc", slug="qa-kb-nc-api",
                       type=2, kb_format="qa", index_mode="high_quality")
    db.add(kn)
    db.commit()
    return SimpleNamespace(id=kn.id)


@pytest.fixture
def client(db: Session):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        user_id=1, is_admin=True, tenant_id=TENANT
    )
    with TestClient(app) as c:
        yield c


@pytest.fixture
def fake_insert(monkeypatch):
    """真实写 kms_segment 的假 _insert_via_kb：嵌 NULL 向量，免去联网 embedding。"""

    def _fake(_session_factory, **kwargs):
        db: Session = kwargs["db"]
        coll = kwargs["collection"]
        tenant_id = kwargs["tenant_id"]
        doc_id = kwargs["document_id"]
        for chunk in kwargs["chunks"]:
            meta = dict(chunk.metadata or {})
            seg = KbSegment(
                tenant_id=tenant_id,
                collection=coll,
                document_id=doc_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content.text,
                chunk_type="qa",
                answer=meta.get("answer"),
                metadata_=meta,
                embedding=None,
            )
            db.add(seg)
        db.commit()

    monkeypatch.setattr(
        "app.services.kb.rag.content_service._insert_via_kb", _fake
    )


def _import_csv(client: TestClient, env, data: bytes, name: str = "qa.csv"):
    return client.post(
        f"/api/v1/kb/collections/{env.collection_id}/qa-records/import",
        files={"file": (name, data, "text/csv")},
    )


def test_qa_csv_import_and_readback(db, env, client, fake_insert):
    """样例 Q&A CSV 经 import 端点导入，并能通过列表读回。"""
    data = CSV_PATH.read_bytes()
    expected_rows = sum(
        1 for line in data.decode("utf-8-sig").splitlines()[1:]
        if line.strip() and line.split(",", 1)[0].strip()
    )
    assert expected_rows > 0

    r = _import_csv(client, env, data, "qa_sample.csv")
    assert r.status_code == 201, r.text
    assert r.json()["imported"] == expected_rows

    # 导入后登记了一条文档行（QA 导入文档名约定为 qa-<8hex>，见 ingest_qa_records）
    doc = db.execute(
        select(KbDocument).where(KbDocument.collection == f"kb_{env.id}")
    ).scalar_one()
    assert doc.source_type == "qa_import"
    assert doc.name.startswith("qa-")
    assert doc.segment_count == expected_rows
    assert doc.status == "completed"

    # 列表读回，逐条校验 question/answer/tags 透传正确
    recs = client.get(f"/api/v1/kb/collections/{env.collection_id}/qa-records").json()
    assert len(recs) == expected_rows
    by_q = {x["question"]: x for x in recs}
    assert "如何创建一个问答类型的知识库？" in by_q
    sample = by_q["导入问答 CSV 时支持的列名有哪些？"]
    assert "question" in sample["answer"]
    assert "导入" in sample["tags"] and "CSV" in sample["tags"]


def test_qa_segment_embeds_question_only(db, env, client, fake_insert):
    """需求 3：被嵌入的是「问题」(content=问题)，答案只进 metadata / answer 列。

    检索统一对 content 做向量检索（retrieve → KnowledgeBase.search），故命中依赖
    问题向量；答案不参与嵌入，仅随检索结果返回。此处锚定落库结构，防止回归。
    """
    r = _import_csv(client, env, CSV_PATH.read_bytes(), "qa_sample.csv")
    assert r.status_code == 201, r.text

    segs = db.execute(
        select(KbSegment).where(KbSegment.collection == f"kb_{env.id}")
    ).scalars().all()
    assert segs

    seg = next(s for s in segs if s.content == "如何创建一个问答类型的知识库？")

    # 形态标记为 qa
    assert seg.chunk_type == "qa"
    assert seg.metadata_["chunk_type"] == "qa"
    # 答案仅进 metadata / answer 列，不参与嵌入
    assert seg.metadata_["answer"].startswith("在「知识库管理」新建知识库时")
    assert seg.answer == seg.metadata_["answer"]
    assert seg.content != seg.answer
    # 标签随元数据入库（CSV 内以分号分隔）
    assert seg.metadata_["tags"] == ["知识库", "创建", "问答"]


def test_qa_import_rejects_missing_question_column(db, env, client, fake_insert):
    """缺少 question 列 → 整体拒绝(422)，不落任何数据。"""
    bad = "answer,tags\n只是答案,标签\n".encode()
    r = _import_csv(client, env, bad, "bad.csv")
    assert r.status_code == 422
    assert r.json()["detail"] == "未解析到任何 question 列数据"

    segs = db.execute(
        select(KbSegment).where(KbSegment.collection == f"kb_{env.id}")
    ).scalars().all()
    assert segs == []


def test_qa_import_empty_file_rejected(db, env, client, fake_insert):
    """空文件（无表头/无数据）→ 拒绝。"""
    r = _import_csv(client, env, b"", "empty.csv")
    assert r.status_code == 422


class _FakeKB:
    """假 KB：只记录 insert_document 调用，不做真实嵌入（避免联网）。"""

    def __init__(self) -> None:
        self.inserted: list = []

    async def ensure_collection(self) -> None:
        return None

    async def insert_document(self, chunks, document_id=None, document_metadata=None):
        self.inserted.append((document_id, chunks))


class _FakeKBFactory:
    def __init__(self, kb: _FakeKB) -> None:
        self._kb = kb

    async def __aenter__(self):
        return self._kb

    async def __aexit__(self, *exc):
        return False


def test_ingest_qa_within_running_event_loop(db, env):
    """回归：async 路由（已在事件循环中）调用 ingest_qa_records 不得抛
    ``asyncio.run() cannot be called from a running event loop``（原 500 根因）。

    直接用真实 ``_insert_via_kb``（不 monkeypatch），仅注入假 kb_factory 免去联网。
    """
    kb = _FakeKB()
    factory = lambda index_mode=None: _FakeKBFactory(kb)  # noqa: E731
    records = [
        {"question": "q1", "answer": "a1", "tags": ["x"]},
        {"question": "q2", "answer": "a2"},
    ]

    async def _wrap():
        # 模拟 async 路由：在运行中的事件循环里调用同步的 ingest_qa_records
        return content_service.ingest_qa_records(
            db, TENANT, f"kb_{env.id}", records, kb_factory=factory
        )

    # 此前此处抛 RuntimeError: asyncio.run() cannot be called from a running event loop
    count = asyncio.run(_wrap())

    assert count == 2
    assert len(kb.inserted) == 1
    doc_id, chunks = kb.inserted[0]
    assert len(chunks) == 2
    assert chunks[0].content.text == "q1"
    assert chunks[0].metadata["answer"] == "a1"


def test_knowledge_level_qa_without_collection(db, env_no_collection, client, fake_insert):
    """问答库无 kms_collection 行时，知识库级 Q&A 端点仍可导入/读回/导出（不 404）。"""
    kid = env_no_collection.id
    data = CSV_PATH.read_bytes()

    r = client.post(
        f"/api/v1/kb/knowledges/{kid}/qa-records/import",
        files={"file": ("qa_sample.csv", data, "text/csv")},
    )
    assert r.status_code == 201, r.text
    assert r.json()["imported"] > 0

    recs = client.get(f"/api/v1/kb/knowledges/{kid}/qa-records").json()
    assert len(recs) == r.json()["imported"]
    assert recs[0]["question"]

    c = client.post(
        f"/api/v1/kb/knowledges/{kid}/qa-records",
        json={"records": [{"question": "q", "answer": "a"}]},
    )
    assert c.status_code == 201, c.text
    assert c.json()["ingested"] == 1

    ex = client.get(f"/api/v1/kb/knowledges/{kid}/qa-records/export")
    assert ex.status_code == 200
    assert ex.headers["content-type"].startswith("text/csv")

    # 反向确认：集合级路由在无对应集合行时仍 404（解耦意图）
    assert client.get("/api/v1/kb/collections/999999/qa-records").status_code == 404
