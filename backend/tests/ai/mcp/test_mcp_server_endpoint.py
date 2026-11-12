"""MCP /mcp 端点的两个历史缺陷的回归测试（纯离线，不需要 DB）。

背景（2026-11-09）：启动日志长期打印 "mcp 包未安装，请运行 pip install mcp"，
但 mcp 2.3.0 实际已安装 —— 真实原因是两处缺陷，本文件各锁一条：

  1. API 漂移：v1 的 mcp.server.fastmcp.FastMCP 在 mcp 2.x 改名为
     mcp.server.mcpserver.MCPServer，代码仍用 v1 路径 → ImportError 被
     `except ImportError` 误判为"包未安装"，端点静默不挂载；
  2. lifespan 缺失：Starlette 不自动触发被 mount 子应用的 lifespan，
     StreamableHTTP session manager 未进入 anyio task group →
     即使挂载成功，所有 /mcp 请求也报 "Task group is not initialized"。

另锁一条路径口径：子应用内部路径必须是 "/"（v2 默认 "/mcp"，与 mount("/mcp")
叠加会变成 /mcp/mcp）。

端点受 settings.MCP_SERVER_ENABLED 守卫（默认关闭），因此除开关用例外，
其余用例需在 fixture 里显式打开。
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI

from app.ai.mcp import server as mcp_server
from app.config._mcp import MCPServerSettings

_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "0"},
    },
}
_HEADERS = {"Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def _reset_server_singletons(monkeypatch):
    """每个用例前后清空模块级单例，并打开端点总开关（用例测的是端点行为本身）。"""
    def _clear():
        mcp_server._mcp_server = None
        mcp_server._mcp_asgi_app = None
        mcp_server._mcp_exit_stack = None

    monkeypatch.setattr(mcp_server.settings, "MCP_SERVER_ENABLED", True)
    _clear()
    yield
    _clear()


def _build_parent_app() -> FastAPI:
    """复刻 main.py 的挂载方式（mount 到 /mcp，路径由 server.py 决定）。"""
    parent = FastAPI()
    child = mcp_server.build_mcp_asgi_app()
    assert child is not None, "MCP 子应用构建失败（缺陷 1 复现：API 漂移被误判为包未安装）"
    parent.mount("/mcp", child)
    return parent


async def _initialize(client: httpx.AsyncClient):
    resp = await client.post("/mcp/", json=_INITIALIZE, headers=_HEADERS)
    return resp


def test_get_mcp_server_works_on_mcp_2x():
    """缺陷 1：mcp>=2.0.0 下 get_mcp_server() 不得返回 None（不得再被误判为未安装）。"""
    server = mcp_server.get_mcp_server()
    assert server is not None
    assert server.name == "minworkbuddy"


def test_asgi_app_is_cached_singleton():
    """mount 与 lifespan 启停必须作用于同一实例，否则进入的是另一个 session manager。"""
    first = mcp_server.build_mcp_asgi_app()
    assert mcp_server.build_mcp_asgi_app() is first


def test_endpoint_answers_initialize_after_lifespan_start():
    """缺陷 2：按 main.py 的 start/stop 成对调用后，/mcp/ 需正常回 initialize。

    同时锁住路径口径：请求打在 /mcp/（而非 v2 默认的 /mcp/mcp）。
    """
    parent = _build_parent_app()

    async def _scenario():
        started = await mcp_server.start_mcp_endpoint()
        assert started is True
        transport = httpx.ASGITransport(app=parent)
        async with httpx.AsyncClient(transport=transport, base_url="http://t", timeout=10) as client:
            resp = await _initialize(client)
            await mcp_server.stop_mcp_endpoint()
        return resp

    resp = asyncio.run(_scenario())
    assert resp.status_code == 200, resp.text
    payload = json.loads(resp.text.split("data: ", 1)[1].strip())
    assert payload["result"]["serverInfo"]["name"] == "minworkbuddy"


def test_endpoint_without_lifespan_start_is_unavailable():
    """锁定缺陷 2 的成因：不进入子应用 lifespan 时请求必定失败（证明启停对是必需的）。"""
    parent = _build_parent_app()

    async def _scenario():
        transport = httpx.ASGITransport(app=parent)
        async with httpx.AsyncClient(transport=transport, base_url="http://t", timeout=10) as client:
            with pytest.raises(RuntimeError, match="Task group is not initialized"):
                await _initialize(client)

    asyncio.run(_scenario())


def test_stop_mcp_endpoint_is_idempotent():
    """未启动/重复关闭均不得抛错（主应用 shutdown 段的兜底语义）。"""
    async def _scenario():
        await mcp_server.stop_mcp_endpoint()
        assert await mcp_server.start_mcp_endpoint() is True
        await mcp_server.stop_mcp_endpoint()
        await mcp_server.stop_mcp_endpoint()

    asyncio.run(_scenario())


def test_switch_defaults_to_off():
    """总开关默认值必须是 False（/mcp 不经 JWT 鉴权，默认对外关闭）。

    读模型字段默认值而非运行时 settings，避免开发机 .env 打开开关时误报。
    """
    assert MCPServerSettings.model_fields["MCP_SERVER_ENABLED"].default is False


def test_endpoint_disabled_when_switch_off(monkeypatch):
    """开关关闭时既不构建子应用（main.py 不挂载），也不启 session manager。"""
    monkeypatch.setattr(mcp_server.settings, "MCP_SERVER_ENABLED", False)

    assert mcp_server.build_mcp_asgi_app() is None
    assert asyncio.run(mcp_server.start_mcp_endpoint()) is False
    # 未启动状态下的关闭同样不得抛错
    asyncio.run(mcp_server.stop_mcp_endpoint())
