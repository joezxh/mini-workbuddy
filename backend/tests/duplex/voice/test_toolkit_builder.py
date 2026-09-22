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


@pytest.mark.asyncio
async def test_toolkit_roundtrip_via_real_toolkit():
    """真实 Toolkit 往返：get_tool_schemas + call_tool（RegisteredTool 契约）。"""
    from agentscope.message import ToolCallBlock
    from agentscope.state import AgentState

    state = AgentState()

    async def fake_call(name, args):
        return {"ok": True}

    tk = build_toolkit(
        [{"name": "t1", "description": "d1",
          "inputSchema": {"type": "object",
                          "properties": {"q": {"type": "string"}}}}],
        call_fn=fake_call,
    )
    state = AgentState()
    # schema 导出：RegisteredTool 校验通过（无 ValueError）
    schemas = await tk.get_tool_schemas()
    names = [s["function"]["name"] for s in schemas]
    assert names == ["t1"]
    # 执行：Toolkit.call_tool → ToolBase.__call__ → call()
    call = ToolCallBlock(id="c1", name="t1", input='{"q": "hello"}')
    chunks = [c async for c in tk.call_tool(call, state)]
    assert chunks, "call_tool 未产出任何 chunk"
    assert "ok" in str(chunks[-1].content)


@pytest.mark.asyncio
async def test_wrapper_normalizes_schema_without_properties():
    """schema 缺 properties 时不触发 RegisteredTool ValueError。"""
    async def fake_call(name, args):
        return {}

    tk = build_toolkit(
        [{"name": "t", "description": "d", "inputSchema": {"type": "object"}}],
        call_fn=fake_call,
    )
    schemas = await tk.get_tool_schemas()
    assert [s["function"]["name"] for s in schemas] == ["t"]
