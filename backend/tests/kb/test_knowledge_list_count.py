"""知识库列表文档计数（左树叶子徽标）回归测试。

Bug 回归：GET /api/v1/kb/knowledges 的 article_count 此前只统计 kms_article
（type=1 Wiki 文章），导致文档存于 kms_document 的通用知识库
（多模态 document / 表格 table / 问答 qa / 外部 connector / 图谱 graph）
恒显示 0。修复后计数 = Wiki 文章数 + KB 文档数（两类存储按库类型互斥）。
"""
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.kb.kb_document import KbDocument
from app.models.wiki.wiki_article import WikiArticle
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.deps import get_current_user, get_db
from app.routers.kb.knowledge_mgnt import router

TENANT = 0


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


def _make_kb(db: Session, name: str, ktype: int, fmt: str | None = None) -> WikiKnowledge:
    kn = WikiKnowledge(
        tenant_id=TENANT, name=name, slug=name,
        type=ktype, kb_format=fmt, index_mode="high_quality",
    )
    db.add(kn)
    db.commit()
    return kn


def _seed_document(db: Session, knowledge_id: int, name: str = "d.csv") -> KbDocument:
    doc = KbDocument(
        tenant_id=TENANT, uuid_code=uuid.uuid4().hex, knowledge_id=knowledge_id,
        name=name, status="completed", collection=f"kb_{knowledge_id}",
    )
    db.add(doc)
    db.commit()
    return doc


def _counts(client: TestClient) -> dict[int, int]:
    items = client.get("/api/v1/kb/knowledges").json()
    return {i["id"]: i["article_count"] for i in items}


def test_general_kb_document_count_not_zero(client, db: Session):
    """通用库（多模态文档 / 表格）：kms_document 有数据时计数必须大于 0。"""
    doc_kb = _make_kb(db, "mm-kb", 2, "document")
    table_kb = _make_kb(db, "tbl-kb", 2, "table")
    for _ in range(3):
        _seed_document(db, doc_kb.id)
    _seed_document(db, table_kb.id, name="a.xlsx")

    counts = _counts(client)
    assert counts[doc_kb.id] == 3
    assert counts[table_kb.id] == 1


def test_wiki_kb_article_count_kept(client, db: Session):
    """Wiki 库（type=1）：仍按 kms_article 统计（原行为不回退）。"""
    wiki_kb = _make_kb(db, "wiki-kb", 1)
    for i in range(2):
        db.add(WikiArticle(
            tenant_id=TENANT, slug=f"art-{wiki_kb.id}-{i}",
            title=f"t{i}", knowledge_id=wiki_kb.id,
        ))
    db.commit()

    counts = _counts(client)
    assert counts[wiki_kb.id] == 2


def test_empty_kb_count_zero(client, db: Session):
    """空库不报错，计数为 0。"""
    empty_kb = _make_kb(db, "empty-kb", 2, "qa")
    assert _counts(client)[empty_kb.id] == 0
