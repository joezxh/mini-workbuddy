"""图谱库检索端点集成测试（P4）：RRF 融合 + 契约不变 + 降级不 500。

要点：
* 响应既有字段语义不变（score 越大越相关），新增信息只落在 metadata 内；
* type=4 走图通道并标记 graph_enabled；
* 图通道异常时**不得 500**，只降级为基础召回。
"""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_current_user, get_db
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.routers.kb import kb as kb_router
from tests.kb.conftest import TENANT_A
from tests.kb.test_kg_api import _SessionProxy


def _client(db, tenant_id=TENANT_A):
    app = FastAPI()
    app.include_router(kb_router.router)
    user = SimpleNamespace(user_id=1, is_admin=True, tenant_id=tenant_id)
    app.dependency_overrides[get_db] = lambda: _SessionProxy(db, ())
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture
def kb(db):
    obj = WikiKnowledge(name="图谱库", slug="kg-retapi-1", type=4, tenant_id=TENANT_A)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


class FakeRetriever:
    """假图谱检索器：返回固定图通道结果。"""

    enabled = True
    results = [
        {
            "document_id": "doc-1",
            "chunk_index": 7,
            "content": "图谱通道命中的切片",
            "score": 0.42,
            "metadata": {"fusion_sources": ["graph"], "score_type": "graph"},
        }
    ]

    def __init__(self, *a, **kw):
        pass

    def recall(self, query, top_k=20):
        return {"results": list(self.results), "enabled": self.enabled, "reason": None}


@pytest.fixture
def base_hits(monkeypatch):
    """替换基础向量召回为固定结果（避免真实 embedding 依赖）。"""
    def _fake(db, tenant_id, collection, body):
        return {
            "results": [
                {
                    "score": 0.9,
                    "document_id": "doc-1",
                    "chunk_index": 3,
                    "content": "基础召回切片",
                    "metadata": {},
                }
            ],
            "index_mode": "high_quality",
        }

    monkeypatch.setattr(kb_router, "_retrieve_collection", _fake)
    monkeypatch.setattr(
        "app.services.kb.segment_service.knowledge_collection_names",
        lambda db, tid, kid: ["kb_1"],
    )


def test_graph_kb_retrieve_fuses_two_channels(db, kb, monkeypatch, base_hits):
    monkeypatch.setattr(
        "app.services.kb.kg.kg_retriever.KgRetriever", FakeRetriever
    )
    with _client(db) as c:
        r = c.post(f"/api/v1/kb/knowledges/{kb.id}/retrieve",
                   json={"query": "星海", "top_k": 5})
    body = r.json()
    assert r.status_code == 200
    assert body["graph_enabled"] is True
    keys = {(h["document_id"], h["chunk_index"]) for h in body["results"]}
    assert ("doc-1", 3) in keys and ("doc-1", 7) in keys, "两路结果都要出现"
    for h in body["results"]:
        meta = h.get("metadata") or {}
        assert meta.get("fusion_sources")
        assert meta.get("score_type")
        assert isinstance(h["score"], float)


def test_graph_kb_retrieve_keeps_contract_for_existing_fields(db, kb, monkeypatch, base_hits):
    monkeypatch.setattr("app.services.kb.kg.kg_retriever.KgRetriever", FakeRetriever)
    with _client(db) as c:
        r = c.post(f"/api/v1/kb/knowledges/{kb.id}/retrieve",
                   json={"query": "星海", "top_k": 5})
    for h in r.json()["results"]:
        assert set(h.keys()) <= {"score", "document_id", "chunk_index", "content", "metadata"}


def test_graph_channel_failure_degrades_without_500(db, kb, monkeypatch, base_hits):
    class Boom:
        def __init__(self, *a, **kw):
            pass

        def recall(self, query, top_k=20):
            raise RuntimeError("graph channel exploded")

    monkeypatch.setattr("app.services.kb.kg.kg_retriever.KgRetriever", Boom)
    with _client(db) as c:
        r = c.post(f"/api/v1/kb/knowledges/{kb.id}/retrieve",
                   json={"query": "星海", "top_k": 5})
    body = r.json()
    assert r.status_code == 200, "图通道异常不得 500"
    assert body["graph_enabled"] is False
    assert body["results"], "必须保留基础召回结果"


def test_non_graph_kb_has_no_graph_channel(db, monkeypatch, base_hits):
    plain = WikiKnowledge(name="普通库", slug="kg-retapi-2", type=2, tenant_id=TENANT_A)
    db.add(plain)
    db.commit()
    db.refresh(plain)
    monkeypatch.setattr("app.services.kb.kg.kg_retriever.KgRetriever", FakeRetriever)
    with _client(db) as c:
        r = c.post(f"/api/v1/kb/knowledges/{plain.id}/retrieve",
                   json={"query": "星海", "top_k": 5})
    body = r.json()
    assert r.status_code == 200
    assert body.get("graph_enabled") is False
    assert len(body["results"]) == 1
