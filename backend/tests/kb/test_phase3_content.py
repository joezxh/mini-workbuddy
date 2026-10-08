"""Phase 3 内容服务 + 代理端点测试（QA/表格/资产/dry-run/SSRF）。

内容服务用 fake KB 验证 Chunk 构造与 kb_document 跟踪；端点走依赖覆盖。
"""
from __future__ import annotations

import io
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_current_user
from app.services.kb.rag import content_service

CALLS: list[dict] = []


class _FakeKB:
    async def ensure_collection(self):
        CALLS.append({"op": "ensure_collection"})

    async def insert_document(self, chunks, document_id=None, document_metadata=None):
        CALLS.append({"op": "insert_document", "n": len(chunks),
                      "first_meta": dict(chunks[0].metadata or {})})
        return document_id or "doc"


@asynccontextmanager
async def _fake_kb_factory(**kwargs):
    yield _FakeKB()


@pytest.fixture(autouse=True)
def _reset_calls(db):
    from app.db.database import Base
    from app.models.kb.kb_document import KbDocument

    Base.metadata.create_all(db.bind, tables=[KbDocument.__table__])
    CALLS.clear()


# ── Q&A（D15）────────────────────────────────────────────────────────────

def test_ingest_qa_records_builds_native_chunks(db):
    count = content_service.ingest_qa_records(
        db, 100, "kb_qa", [{"question": "退款政策？", "answer": "7 天", "tags": ["售后"]}],
        kb_factory=_fake_kb_factory,
    )
    assert count == 1
    insert = CALLS[-1]
    assert insert["first_meta"]["chunk_type"] == "qa"
    assert insert["first_meta"]["answer"] == "7 天"


def test_ingest_qa_empty_records_noop(db):
    assert content_service.ingest_qa_records(
        db, 100, "kb_qa", [], kb_factory=_fake_kb_factory) == 0
    assert not CALLS


# ── 表格行（D15）─────────────────────────────────────────────────────────

def test_parse_table_csv():
    rows = content_service.parse_table_bytes(
        "desc,price\n防水低价,9\n抗压,15\n".encode(), "t.csv")
    assert len(rows) == 2 and rows[0]["desc"] == "防水低价"


def test_ingest_table_rows_embed_field_validation(db):
    with pytest.raises(ValueError, match="不在表头中"):
        content_service.ingest_table_rows(
            db, 100, "kb_t", [{"desc": "x", "price": 1}], "missing",
            kb_factory=_fake_kb_factory)


def test_ingest_table_rows_ok(db):
    count = content_service.ingest_table_rows(
        db, 100, "kb_t", [{"desc": "防水低价", "price": 9}], "desc",
        kb_factory=_fake_kb_factory,
    )
    assert count == 1
    insert = CALLS[-1]
    assert insert["first_meta"]["chunk_type"] == "table_row"
    assert insert["first_meta"]["price"] == 9   # 非嵌入列进 metadata


# ── dry-run（§10.7：不落库不嵌入）────────────────────────────────────────

def _kb_client():
    from app.routers.kb.kb import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        user_id=1, is_admin=True, tenant_id=100)
    return TestClient(app)


def test_pipeline_dry_run_returns_intermediate_products():
    client = _kb_client()
    r = client.post(
        "/api/v1/kb/pipelines/dry-run",
        files={"file": ("a.md", ("# 标题\n\n" + "para " * 300).encode())},
        data={"chunker_type": "approx_token", "chunker_params": '{"chunk_size": 64}'},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["sections"] and body["chunks"]
    assert body["chunks"][0]["total_chunks"] == body["chunks"][-1]["chunk_index"] + 1


def test_pipeline_dry_run_bad_chunker_422():
    client = _kb_client()
    r = client.post(
        "/api/v1/kb/pipelines/dry-run",
        files={"file": ("a.md", b"content")},
        data={"chunker_type": "nonexistent"},
    )
    assert r.status_code == 422


def test_pipeline_dry_run_bad_params_422():
    client = _kb_client()
    r = client.post(
        "/api/v1/kb/pipelines/dry-run",
        files={"file": ("a.md", b"content")},
        data={"chunker_params": "not-json"},
    )
    assert r.status_code == 422


# ── 代理端点 SSRF 防护 ───────────────────────────────────────────────────

def test_validate_endpoint_url_rejects_http_and_private():
    from app.routers.kb.kb_proxy import validate_endpoint_url
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        validate_endpoint_url("http://example.com")           # 非 https
    with pytest.raises(HTTPException):
        validate_endpoint_url("https://localhost/x")          # 环回主机
    with pytest.raises(HTTPException):
        validate_endpoint_url("https://127.0.0.1/x")          # 环回地址


def test_validate_endpoint_url_accepts_public_https(monkeypatch):
    """公网 https 放行。

    ``example.com`` 的解析结果随环境 DNS 而变（曾命中 198.18/15 等保留段被 SSRF
    拦截），故固定解析为公网地址，断言只针对校验逻辑而非真实 DNS。
    """
    import socket

    from app.routers.kb.kb_proxy import validate_endpoint_url

    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, 0, 0, "", ("93.184.216.34", 443))],
    )
    assert validate_endpoint_url("https://example.com/retrieve") == \
        "https://example.com/retrieve"
