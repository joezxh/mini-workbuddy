"""MCP Server 端点配置（对外暴露 /mcp Streamable HTTP 的开关）"""
from pydantic import BaseModel


class MCPServerSettings(BaseModel):
    """MCP 服务端开关

    默认关闭：/mcp 挂载后不经过 JWT 鉴权（外部 MCP Client 直连），且
    app/ai/mcp/server.py 沿用历史设定关闭了 DNS rebinding 保护，面向公网
    部署时属额外攻击面。本地/内网需要联调时显式置 MCP_SERVER_ENABLED=True；
    开关关闭时 build_mcp_asgi_app() 返回 None，main.py 不挂载、lifespan 也不启 session manager。
    """

    # 总开关：是否挂载 /mcp 端点
    MCP_SERVER_ENABLED: bool = False
