"""MCP stdio 传输层两项缺陷的回归测试（纯离线，不依赖真实 MCP 服务）。

背景：app/superagent 自研 stdio MCPClient 有两项真机验证的修复：
  1. Windows 可执行解析 —— npx / windows-mcp 等是 .cmd 批处理，
     create_subprocess_exec 裸命令会 WinError 2，需 shutil.which() 解析；
  2. 行协议 64KB 限制 —— asyncio StreamReader 默认单行 64KB，截图类工具
     返回 base64 会抛 ValueError: Separator is not found，spawn 需
     limit=32*1024*1024。

分析结论：app/ai/mcp/tool_adapter.py 的 MCPAdapter 是纯进程内注册器
（call_tool 直接调用本地 Python handler），无任何传输层，两项缺陷在其
调用路径上不存在。ai 包内真正做 stdio spawn 的是
app/ai/superagent/tools/mcp_adapter.py 的 MCPClient（两项修复已落地），
本文件针对该层做回归验证，并锁定 MCPAdapter 的"纯进程内"语义。
"""
from __future__ import annotations

import asyncio
import sys

import pytest


class _SpawnProbe(Exception):
    """在 create_subprocess_exec 捕获到 spawn 参数后立即中断的哨兵异常。"""


# ── app/ai/superagent/tools/mcp_adapter.py MCPClient（实际 spawn 层）────────


def _load_stdio_client_module():
    from app.ai.superagent.tools import mcp_adapter as mcp_mod

    return mcp_mod


def test_bare_npx_resolved_to_cmd_absolute_path(monkeypatch):
    """裸命令 npx 须经 shutil.which 解析为 .cmd 绝对路径再 spawn（Windows 语义）。"""
    mcp_mod = _load_stdio_client_module()
    fake_cmd = r"C:\fake\nodejs\npx.cmd"
    captured: dict = {}

    def fake_which(cmd, mode=None):
        return fake_cmd if cmd == "npx" else None

    async def fake_exec(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        captured["args"] = args
        captured["kwargs"] = kwargs
        raise _SpawnProbe()  # 捕获参数后中断，避免真实起子进程

    monkeypatch.setattr(mcp_mod.shutil, "which", fake_which)
    monkeypatch.setattr(mcp_mod.asyncio, "create_subprocess_exec", fake_exec)

    client = mcp_mod.MCPClient(server_cmd="npx", server_args=["-y", "some-server"])
    with pytest.raises(_SpawnProbe):
        asyncio.run(client.connect())

    assert captured["cmd"] == fake_cmd  # 修复 1：解析后的绝对路径
    assert captured["args"] == ("-y", "some-server")
    # 修复 2：spawn 时必须放开 StreamReader 单行 64KB 限制
    assert captured["kwargs"]["limit"] == 32 * 1024 * 1024


def test_unresolvable_command_falls_back_to_raw(monkeypatch):
    """shutil.which 解析失败（返回 None）时回退为原始命令，不抛错。"""
    mcp_mod = _load_stdio_client_module()
    captured: dict = {}

    async def fake_exec(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        raise _SpawnProbe()

    monkeypatch.setattr(mcp_mod.shutil, "which", lambda cmd, mode=None: None)
    monkeypatch.setattr(mcp_mod.asyncio, "create_subprocess_exec", fake_exec)

    client = mcp_mod.MCPClient(server_cmd="definitely-not-exist-cmd")
    with pytest.raises(_SpawnProbe):
        asyncio.run(client.connect())

    assert captured["cmd"] == "definitely-not-exist-cmd"


_FAKE_MCP_SERVER = r'''
"""最小 MCP stdio 假服务：screenshot_tool 返回单行 128KB 载荷（> 默认 64KB）。"""
import json
import sys

for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue
    req = json.loads(raw)
    mid = req.get("id")
    method = req.get("method", "")
    if mid is None:
        continue  # notification（如 notifications/initialized）
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {},
                  "serverInfo": {"name": "fake-mcp", "version": "0.0.0"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "screenshot_tool",
                             "description": "simulate screenshot tool with huge base64",
                             "inputSchema": {"type": "object", "properties": {}}}]}
    elif method == "tools/call":
        # 单行 128KB 文本 —— StreamReader 默认 64KB limit 必抛
        # ValueError: Separator is not found
        result = {"content": [{"type": "text", "text": "B" * (128 * 1024)}],
                  "isError": False}
    else:
        result = None
    if result is None:
        payload = {"jsonrpc": "2.0", "id": mid,
                   "error": {"code": -32601, "message": "unknown method"}}
    else:
        payload = {"jsonrpc": "2.0", "id": mid, "result": result}
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()
'''


def test_oversized_single_line_response_does_not_crash(tmp_path):
    """>64KB 单行 JSON-RPC 响应不崩（若 spawn 丢掉 limit=32MB，readline 会抛
    ValueError: Separator is not found，即回归信号）。"""
    mcp_mod = _load_stdio_client_module()
    script = tmp_path / "fake_mcp_server.py"
    script.write_text(_FAKE_MCP_SERVER, encoding="utf-8")

    client = mcp_mod.MCPClient(server_cmd=sys.executable, server_args=[str(script)])

    async def _scenario():
        tools = await asyncio.wait_for(client.connect(), timeout=30)
        result = await asyncio.wait_for(
            client.call_tool("screenshot_tool", {}), timeout=30)
        await client.close()
        return tools, result

    tools, result = asyncio.run(_scenario())

    assert [t.name for t in tools] == ["screenshot_tool"]
    text = result["content"][0]["text"]
    assert len(text) == 128 * 1024  # 完整收到，未截断未崩溃


# ── app/ai/mcp/tool_adapter.py MCPAdapter（纯进程内，锁分析结论）────────────


def test_mcp_adapter_call_tool_is_pure_in_process(monkeypatch):
    """MCPAdapter.call_tool 不经任何 stdio 传输 —— 若未来引入子进程 spawn，
    两项 stdio 缺陷需重新评估（见 tool_adapter.py 模块注释）。"""
    import app.ai.mcp.tool_adapter as ta_mod

    def _forbidden(*args, **kwargs):
        raise AssertionError("MCPAdapter 是纯进程内适配器，不应 spawn 子进程")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _forbidden)

    adapter = ta_mod.MCPAdapter()

    async def _echo(value: str) -> dict:
        return {"echo": value}

    adapter.register_tool(
        name="echo_tool",
        description="test only",
        input_schema={"type": "object", "properties": {"value": {"type": "string"}}},
        handler=_echo,
    )

    result = asyncio.run(adapter.call_tool("echo_tool", {"value": "hi"}))
    assert result.success is True
    assert result.result == {"echo": "hi"}

    missing = asyncio.run(adapter.call_tool("no_such_tool", {}))
    assert missing.success is False
    assert "no_such_tool" in missing.error

    # 公开 API 契约保持不变
    schemas = adapter.get_tool_schemas()
    assert {"name", "description", "inputSchema"} <= set(schemas[0].keys())
    assert "echo_tool" in adapter.list_tools()
    assert ta_mod.get_mcp_adapter() is ta_mod.get_mcp_adapter()  # 单例
