"""MCP Server - 基于 FastMCP 发布工具端点。"""
import logging

logger = logging.getLogger(__name__)

# 延迟导入 FastMCP（mcp 包可能未安装）
_mcp_server = None


def get_mcp_server():
    """获取 FastMCP Server 单例（延迟初始化）。"""
    global _mcp_server
    if _mcp_server is None:
        try:
            from mcp.server.fastmcp import FastMCP
            from mcp.server.transport_security import TransportSecuritySettings
            _security_settings = TransportSecuritySettings(
                enable_dns_rebinding_protection=False,
            )
            _mcp_server = FastMCP(
                "minworkbuddy",
                host="0.0.0.0",
                streamable_http_path="/",
                transport_security=_security_settings,
            )
            logger.info("FastMCP Server 已创建: minworkbuddy")
        except ImportError:
            logger.warning("mcp 包未安装，FastMCP Server 不可用。请运行: pip install mcp")
            return None
    return _mcp_server
