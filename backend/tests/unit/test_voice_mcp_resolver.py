from app.duplex.voice.mcp_session_resolver import McpSessionResolver

def test_empty_returns_no_tools():
    import asyncio
    assert asyncio.run(McpSessionResolver([]).resolve_tools()) == []
