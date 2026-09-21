"""toolkit_builder：MCPAdapter 工具 schema → AgentScope ToolBase 包装。"""
import pytest

from app.duplex.voice.toolkit_builder import build_toolkit, McpToolWrapper


@pytest.mark.asyncio
async def test_wrapper_calls_fn_and_returns_chunk():
    calls = []

    async def fake_call(name, args):
        calls.append((name, args))
        return {"ok": True, "rows": 3}

    tool = McpToolWrapper(
        schema={"name": "database_query", "description": "查询",
                "inputSchema": {"type": "object",
                                "properties": {"query": {"type": "string"}}}},
        call_fn=fake_call)
    chunk = await tool.call(query="select 1")
    assert calls == [("database_query", {"query": "select 1"})]
    assert chunk.is_last is True


@pytest.mark.asyncio
async def test_wrapper_error_returns_error_chunk():
    async def bad_call(name, args):
        raise RuntimeError("boom")

    tool = McpToolWrapper(
        schema={"name": "t", "description": "d", "inputSchema": {"type": "object"}},
        call_fn=bad_call)
    chunk = await tool.call()
    assert "boom" in str(chunk.content)


@pytest.mark.asyncio
async def test_build_toolkit_registers_all_schemas():
    async def fake_call(name, args):
        return {}

    schemas = [
        {"name": "t1", "description": "d1", "inputSchema": {"type": "object"}},
        {"name": "t2", "description": "d2", "inputSchema": {"type": "object"}},
    ]
    tk = build_toolkit(schemas, call_fn=fake_call)
    names = {t.name for g in tk.tool_groups for t in g.tools}
    assert names == {"t1", "t2"}
