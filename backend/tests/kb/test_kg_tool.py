"""kg_query Agent 工具测试（P6）：租户 fail-closed + 子命令行为。"""
import json

import pytest

from app.ai.tool_manager.tool_context import ToolUserContext, bind_tool_user
from app.ai.tools.kg_tools import KgQueryTool
from app.models.wiki.wiki_knowledge import WikiKnowledge
from tests.kb.conftest import TENANT_A


@pytest.fixture
def kb(db):
    obj = WikiKnowledge(name="图谱库", slug="kg-tool-1", type=4, tenant_id=TENANT_A)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@pytest.fixture
def tool(db):
    """注入固定租户解析（测试 schema 不含 sys_user）。"""
    return KgQueryTool(
        session_factory=lambda: db,
        tenant_resolver=lambda _db: TENANT_A,
    )


@pytest.fixture
def tool_no_tenant(db):
    """不注入租户解析：走真实的 SysUser 查询路径（无上下文 -> tenant_required）。"""
    return KgQueryTool(session_factory=lambda: db)



def _payload(chunk) -> dict:
    """从 ToolChunk 取出 JSON 负载。"""
    text = chunk.content[0].text
    return json.loads(text)


@pytest.fixture
def chain(db, kb):
    from app.services.kb.kg.kg_service import KgService

    svc = KgService(db, tenant_id=TENANT_A, knowledge_id=kb.id)
    a = svc.create_entity(name="星海科技", type_code="CUS")
    b = svc.create_entity(name="订单B1", type_code="ORD")
    svc.create_triple(from_entity_id=a.id, to_entity_id=b.id, relation_code="PLACES")
    return svc, a, b


@pytest.mark.asyncio
async def test_missing_tenant_context_returns_tenant_required(tool_no_tenant, kb):
    """取不到租户必须返回 tenant_required，绝不落到 NULL 分区。"""
    out = _payload(await tool_no_tenant.call(action="stats", knowledge_id=kb.id))
    assert out["error"] == "tenant_required"


@pytest.mark.asyncio
async def test_entity_search(tool, kb, chain):
    ctx = ToolUserContext(user_id=1, is_admin=True)
    with bind_tool_user(ctx):
        out = _payload(
            await tool.call(action="entity_search", knowledge_id=kb.id,
                            keyword="星海")
        )
    assert out["total"] == 1
    assert out["items"][0]["name"] == "星海科技"


@pytest.mark.asyncio
async def test_entity_search_requires_keyword(tool, kb):
    ctx = ToolUserContext(user_id=1, is_admin=True)
    with bind_tool_user(ctx):
        out = _payload(await tool.call(action="entity_search", knowledge_id=kb.id))
    assert "error" in out


@pytest.mark.asyncio
async def test_neighbors(tool, kb, chain):
    _svc, a, b = chain
    ctx = ToolUserContext(user_id=1, is_admin=True)
    with bind_tool_user(ctx):
        out = _payload(
            await tool.call(action="neighbors", knowledge_id=kb.id, entity_id=b.id)
        )
    assert "nodes" in out and "edges" in out
    assert len(out["edges"]) == 1


@pytest.mark.asyncio
async def test_paths(tool, kb, chain):
    _svc, a, b = chain
    ctx = ToolUserContext(user_id=1, is_admin=True)
    with bind_tool_user(ctx):
        out = _payload(
            await tool.call(action="paths", knowledge_id=kb.id,
                            from_entity_id=a.id, to_entity_id=b.id)
        )
    assert out["paths"] and len(out["paths"][0]["edges"]) == 1


@pytest.mark.asyncio
async def test_stats(tool, kb, chain):
    ctx = ToolUserContext(user_id=1, is_admin=True)
    with bind_tool_user(ctx):
        out = _payload(await tool.call(action="stats", knowledge_id=kb.id))
    assert out["entities"] == 2
    assert out["relations"] == 1


@pytest.mark.asyncio
async def test_unknown_action_rejected(tool, kb):
    ctx = ToolUserContext(user_id=1, is_admin=True)
    with bind_tool_user(ctx):
        out = _payload(await tool.call(action="explode", knowledge_id=kb.id))
    assert "error" in out and "allowed" in out


@pytest.mark.asyncio
async def test_non_graph_kb_is_rejected(tool, db):
    """非图谱库调用图谱工具 -> 结构化错误，不得抛异常。"""
    plain = WikiKnowledge(name="普通库", slug="kg-tool-2", type=2, tenant_id=TENANT_A)
    db.add(plain)
    db.commit()
    db.refresh(plain)
    ctx = ToolUserContext(user_id=1, is_admin=True)
    with bind_tool_user(ctx):
        out = _payload(await tool.call(action="stats", knowledge_id=plain.id))
    assert "error" in out


def test_tool_definition_is_registered():
    from app.ai.tools.kg_tools import build_kg_tool_definitions

    defs = build_kg_tool_definitions()
    assert len(defs) == 1
    d = defs[0]
    assert d.tool_key == "kg_query"
    assert d.class_name == "app.ai.tools.kg_tools.KgQueryTool"
    assert d.status == "enabled"
