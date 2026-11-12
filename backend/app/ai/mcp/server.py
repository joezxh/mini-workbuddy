"""MCP Server - 基于 MCP 2.x MCPServer 发布 Streamable HTTP 端点。

版本口径（2026-11-09 迁移）：requirements.txt 锁 mcp>=2.0.0（agentscope 2.0.11 硬依赖，
不可能回落 v1）。v1 的 ``mcp.server.fastmcp.FastMCP`` 在 2.x 改名为
``mcp.server.mcpserver.MCPServer``，且 ``host`` / ``streamable_http_path`` /
``transport_security`` 三个参数从构造函数移到了 ``streamable_http_app()``。

挂载口径：main.py 以 ``app.mount("/mcp", child)`` 挂载，故子应用内部路径取 "/"
（v2 默认 "/mcp"，不显式覆盖会拼成 /mcp/mcp）。

lifespan 口径：Starlette 不会自动触发被 mount 子应用的 lifespan（与 KB 子应用同一约束，
见 main.py 注释）。StreamableHTTP session manager 依赖 lifespan 进入 anyio task group，
不进入则所有 /mcp 请求报 "Task group is not initialized"。因此本模块把子应用实例缓存成
单例，并由 start/stop_mcp_endpoint() 在主应用 lifespan 中显式启停 —— 与
start_audit_writer()/stop_audit_writer() 成对出现的写法保持一致。

开关口径：整个端点受 settings.MCP_SERVER_ENABLED 守卫，默认 False。/mcp 不走 JWT
鉴权且关闭了 DNS rebinding 保护，公网部署属额外攻击面，只在本地/内网显式打开。
"""
from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# 端点对外语义沿用 v1：监听全部网卡、关闭 DNS rebinding 保护（部署于反向代理之后）
_MCP_HOST = "0.0.0.0"
_MCP_STREAMABLE_PATH = "/"

# 单例：server 与子应用都必须缓存，否则 mount 与 lifespan 会拿到两个不同的 session manager
_mcp_server = None
_mcp_asgi_app = None
_mcp_exit_stack: Optional[AsyncExitStack] = None


def get_mcp_server():
    """获取 MCPServer 单例（延迟初始化）；mcp 包不可用时返回 None。"""
    global _mcp_server
    if _mcp_server is None:
        try:
            from mcp.server.mcpserver import MCPServer
        except ImportError as exc:
            # ImportError 有两种成因，日志需能区分：包未安装 / v1→v2 API 漂移
            logger.warning(
                "MCP Server 不可用：mcp 包未安装或 API 不匹配（需 mcp>=2.0.0 的 "
                "mcp.server.mcpserver.MCPServer）: %s", exc)
            return None
        _mcp_server = MCPServer("minworkbuddy")
        logger.info("MCP Server 已创建: minworkbuddy")
    return _mcp_server


def build_mcp_asgi_app():
    """构建供 main.py mount 到 /mcp 的 ASGI 子应用（Streamable HTTP，缺失则回退 SSE）。

    返回同一个缓存实例：mount 与 lifespan 启停必须作用于同一 session manager。
    开关 MCP_SERVER_ENABLED 关闭时返回 None —— 不挂载、也不启 session manager。
    """
    global _mcp_asgi_app
    if _mcp_asgi_app is not None:
        return _mcp_asgi_app

    if not settings.MCP_SERVER_ENABLED:
        logger.info("MCP 端点未启用（settings.MCP_SERVER_ENABLED=False），/mcp 不挂载")
        return None

    server = get_mcp_server()
    if server is None:
        return None

    from mcp.server.transport_security import TransportSecuritySettings

    security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    if hasattr(server, "streamable_http_app"):
        _mcp_asgi_app = server.streamable_http_app(
            streamable_http_path=_MCP_STREAMABLE_PATH,
            transport_security=security,
            host=_MCP_HOST,
        )
    else:
        _mcp_asgi_app = server.sse_app(transport_security=security, host=_MCP_HOST)
    return _mcp_asgi_app


async def start_mcp_endpoint() -> bool:
    """在主应用 lifespan 中启动 MCP 子应用（进入其 anyio task group）。

    未挂载或启动失败均不阻断主应用启动，返回是否已启动。
    """
    global _mcp_exit_stack
    app = build_mcp_asgi_app()
    if app is None:
        return False
    stack = AsyncExitStack()
    try:
        # 子应用的 lifespan 上下文即其 session manager 的 run()
        await stack.enter_async_context(app.router.lifespan_context(app))
    except Exception as exc:
        logger.warning(f"MCP 端点启动失败（不影响主应用）: {exc}")
        await stack.aclose()
        return False
    _mcp_exit_stack = stack
    logger.info("MCP 端点 session manager 已启动: /mcp")
    return True


async def stop_mcp_endpoint() -> None:
    """停止 MCP 子应用（与 start_mcp_endpoint 成对，在主应用 shutdown 段调用）。"""
    global _mcp_exit_stack
    stack, _mcp_exit_stack = _mcp_exit_stack, None
    if stack is None:
        return
    await stack.aclose()
    logger.info("MCP 端点 session manager 已关闭")
