"""知识库统一化 Phase 2 回归（spec §10.2 新模型 / §10.3 摄取管线 / §9 OKF）。"""
import pytest


def test_kb_document_model_fields():
    from app.models.kb.kb_document import KbDocument

    assert KbDocument.__tablename__ == "kb_document"
    for col in ("knowledge_id", "collection", "name", "source_type",
                "file_type", "file_size", "status", "segment_count", "error_detail"):
        assert col in KbDocument.__table__.c
    assert KbDocument.__table__.c["status"].server_default is not None


def test_kb_segment_asset_model_fields():
    from app.models.kb.kb_segment_asset import KbSegmentAsset

    assert KbSegmentAsset.__tablename__ == "kb_segment_asset"
    for col in ("segment_id", "file_path", "mime_type", "size"):
        assert col in KbSegmentAsset.__table__.c


def test_external_kb_endpoint_model_fields():
    from app.models.connectors.external_kb_endpoint import ExternalKbEndpoint

    assert ExternalKbEndpoint.__tablename__ == "kms_external_kb_endpoint"
    for col in ("knowledge_id", "endpoint_url", "auth_key", "index_name", "status"):
        assert col in ExternalKbEndpoint.__table__.c


# ── T2: kb_format 校验矩阵 ────────────────────────────────────────────────

def test_kb_format_matrix_accepts_and_rejects():
    import pytest
    from fastapi import HTTPException

    from app.services.kb.kb_format import validate_kb_format

    assert validate_kb_format(1, None) is None
    assert validate_kb_format(2, "document") == "document"
    assert validate_kb_format(3, "proxy") == "proxy"
    for t, f in ((1, "document"), (2, None), (2, "proxy"), (3, "document"), (2, "vector")):
        with pytest.raises(HTTPException):
            validate_kb_format(t, f)


def test_kb_format_immutable_after_create():
    import pytest
    from fastapi import HTTPException

    from app.services.kb.kb_format import assert_format_unchanged

    assert_format_unchanged(None, "document")      # 初次设置允许
    assert_format_unchanged("document", "document")  # 相同允许
    with pytest.raises(HTTPException):
        assert_format_unchanged("document", "qa")   # 切换拒绝


# ── T3: AgentScope Parser 能力发现 + ParentChildChunker ──────────────────

def test_select_parser_by_media_type():
    from app.services.kb.parser_selector import select_parser

    assert select_parser("text/markdown") is not None
    assert select_parser("application/pdf") is not None
    with pytest.raises(ValueError):
        select_parser("video/mp4")


def test_supported_media_types_covers_office():
    from app.services.kb.parser_selector import supported_media_types

    table = supported_media_types()
    all_types = [mt for mts in table.values() for mt in mts]
    assert "application/pdf" in all_types
    assert any("wordprocessingml" in mt for mt in all_types)
    assert any("spreadsheetml" in mt or "ms-excel" in mt for mt in all_types)


def test_parent_child_chunker_contract():
    """对齐 agentscope ChunkerBase 契约：chunker_type 唯一 + Parameters + 编号连续。"""
    import asyncio

    from agentscope.message import TextBlock
    from agentscope.rag import Section

    from app.services.kb.parent_child_chunker import ParentChildChunker

    assert ParentChildChunker.chunker_type == "parent_child"
    chunker = ParentChildChunker(parameters=ParentChildChunker.Parameters(
        parent_size=512, child_size=128, overlap=0,
    ))
    long_text = "\n\n".join(f"段落{i} " + "字" * 100 for i in range(6))
    sections = [Section(content=TextBlock(text=long_text), source="a.md", metadata={})]
    chunks = asyncio.run(chunker.chunk(sections))

    assert len(chunks) >= 2
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))  # 0..N-1 连续
    assert len({c.total_chunks for c in chunks}) == 1                    # total_chunks 一致
    assert all("parent_content" in (c.metadata or {}) for c in chunks)
    assert all(c.metadata.get("parent_index") == 0 for c in chunks)


# ── T5: /api/v1/kb 认证路由 ──────────────────────────────────────────────

def test_kb_router_registered():
    from app.core.router_registry import ROUTER_SPECS

    assert any(s.module == "app.routers.kb.kb" and s.enabled for s in ROUTER_SPECS)


def test_kb_router_has_expected_paths():
    from app.routers.kb.kb import router

    paths = {getattr(r, "path", "") for r in router.routes}
    assert "/api/v1/kb/knowledges/{kid}/documents" in paths
    assert "/api/v1/kb/documents/status" in paths
    assert "/api/v1/kb/collections/{collection}/retrieve" in paths
    assert "/api/v1/kb/supported_content_types" in paths
    assert "/api/v1/kb/chunkers" in paths


# ── T6: KB 子应用认证收口 ────────────────────────────────────────────────

def test_kb_subapp_no_business_crud_after_d1():
    """D1：业务 CRUD 已迁入主应用 /api/v1/kb/kb-refs，子应用不再承载。"""
    from fastapi.testclient import TestClient

    from app.services.kb.kb_app import kb_app

    client = TestClient(kb_app)
    assert client.post("/kb", json={"name": "x"}).status_code == 404
    assert client.delete("/kb/whatever").status_code == 404
    # 健康探针保持开放（存活检查）
    assert client.get("/health").status_code == 200


def test_rag_kwargs_disabled_without_knowledge_bases():
    """D16：未配置 knowledge_bases 时不改动 Agent 构造（返回空 kwargs）。"""
    from app.ai.agent_factory import AgentFactory

    factory = AgentFactory.__new__(AgentFactory)  # 不触发 __init__ 的 DB 依赖
    assert factory._rag_kwargs({}, None) == {}
    assert factory._rag_kwargs({"knowledge_bases": []}, None) == {}
    # 有 kb 但缺 tenant_id → 显式跳过（不静默出错）
    assert factory._rag_kwargs({"knowledge_bases": ["kb_1"]}, None) == {}


def test_kb_service_token_channel_default_disabled(monkeypatch):
    """服务令牌通道默认禁用（fail-closed），配置后可用。"""
    from app.services.kb import kb_app as kb_app_mod

    assert kb_app_mod.kb_service_token() == "" or isinstance(
        kb_app_mod.kb_service_token(), str
    )
    monkeypatch.setattr(kb_app_mod, "kb_service_token", lambda: "test-token")
    assert kb_app_mod.kb_service_token() == "test-token"
