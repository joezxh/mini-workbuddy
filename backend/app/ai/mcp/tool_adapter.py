"""MCPAdapter - MCP 工具适配器

注册和调用 MCP 工具，提供统一的工具调用接口。

【传输路径分析】（对照 superagent MCPClient 的两项 stdio 修复）
MCPAdapter 是纯进程内注册器：call_tool() 直接调用本地 Python handler
（DatabaseTools 封装），不 spawn stdio 子进程、也不经 agentscope.mcp
等外部客户端 —— 没有任何传输层。因此 superagent MCPClient 已修复的两项
缺陷在本适配器的调用路径上不存在，无需（也不应）在此修改：
  1. Windows 可执行解析 —— 裸 npx 需 shutil.which() 解析为 .cmd 绝对路径；
  2. asyncio StreamReader 单行 64KB 限制 —— 截图类 base64 响应需
     create_subprocess_exec(..., limit=32MB)。
ai 包内真正做 stdio spawn 的是 app/ai/superagent/tools/mcp_adapter.py
的 MCPClient（两项修复已在该层落地）；经 agentscope AiMcpClient 的外部
MCP 路径（app/ai/workspace/manager.py）属第三方库层。回归测试见
tests/ai/mcp/test_mcp_stdio_transport.py。
"""
from typing import Any, Callable, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel

# DatabaseTools 导入：先探新路径 app.ai.tools.database（2026-11 核对：该模块尚不存在），
# 再回落到当前实际所在的 app.ai.tool_manager.database（存在，为生效分支）；
# 两处均缺失时才置 None，下方默认工具退化为空结果
try:
    # Try new location first
    from app.ai.tools.database import DatabaseTools
except ImportError:
    try:
        # Fallback to old location if exists
        from app.ai.tool_manager.database import DatabaseTools
    except ImportError:
        # DatabaseTools not available - we'll provide simple fallback implementations
        DatabaseTools = None
        logger.warning("DatabaseTools not found - some MCP tools will be disabled")


class MCPTool(BaseModel):
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPToolResult(BaseModel):
    """MCP 工具执行结果"""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None


class MCPAdapter:
    """MCP 工具适配器"""
    
    def __init__(self, db=None):
        self._tools: Dict[str, MCPTool] = {}
        self._handlers: Dict[str, Callable] = {}
        self._db = db
        self._register_default_tools()
    
    def set_db(self, db):
        """设置数据库会话"""
        self._db = db
    
    def _register_default_tools(self):
        """注册默认工具"""
        
        # 创建数据库工具实例（延迟初始化）
        db_tools = None
        if self._db:
            db_tools = DatabaseTools(self._db)
        
        async def database_query(query: str, limit: int = 10) -> Dict[str, Any]:
            """数据库查询工具"""
            if db_tools:
                return await db_tools.query(query, limit=limit)
            return {"query": query, "results": [], "count": 0}
        
        async def event_search(keywords: str, region: Optional[str] = None, risk_level: Optional[str] = None) -> Dict[str, Any]:
            """事件搜索工具"""
            if db_tools:
                return await db_tools.search_events(keywords=keywords, region=region, risk_level=risk_level)
            return {"keywords": keywords, "region": region, "results": [], "count": 0}
        
        async def get_event_detail(event_id: int) -> Dict[str, Any]:
            """获取事件详情"""
            if db_tools:
                return await db_tools.get_event_detail(event_id)
            return {"event_id": event_id, "error": "Database tools not available"}
        
        async def get_event_persons(event_id: int) -> Dict[str, Any]:
            """获取事件关联人员"""
            if db_tools:
                return await db_tools.get_persons_by_event(event_id)
            return {"event_id": event_id, "persons": [], "count": 0}
        
        self.register_tool(
            name="database_query",
            description="执行数据库查询，返回结构化结果",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "SQL查询语句"},
                    "limit": {"type": "integer", "description": "返回结果数量限制", "default": 10},
                },
                "required": ["query"],
            },
            handler=database_query,
        )
        
        self.register_tool(
            name="event_search",
            description="搜索风险事件",
            input_schema={
                "type": "object",
                "properties": {
                    "keywords": {"type": "string", "description": "搜索关键词"},
                    "region": {"type": "string", "description": "区域筛选"},
                    "risk_level": {"type": "string", "description": "风险等级"},
                },
                "required": ["keywords"],
            },
            handler=event_search,
        )
        
        self.register_tool(
            name="get_event_detail",
            description="获取风险事件详情",
            input_schema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "integer", "description": "事件ID"},
                },
                "required": ["event_id"],
            },
            handler=get_event_detail,
        )
        
        self.register_tool(
            name="get_event_persons",
            description="获取事件关联人员列表",
            input_schema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "integer", "description": "事件ID"},
                },
                "required": ["event_id"],
            },
            handler=get_event_persons,
        )
    
    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable,
    ):
        """注册 MCP 工具"""
        self._tools[name] = MCPTool(
            name=name,
            description=description,
            input_schema=input_schema,
        )
        self._handlers[name] = handler
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> MCPToolResult:
        """调用 MCP 工具"""
        if tool_name not in self._handlers:
            return MCPToolResult(
                success=False,
                error=f"Tool not found: {tool_name}"
            )
        
        handler = self._handlers[tool_name]
        try:
            result = await handler(**arguments)
            return MCPToolResult(success=True, result=result)
        except Exception as e:
            return MCPToolResult(success=False, error=str(e))
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具的 Schema"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            }
            for tool in self._tools.values()
        ]
    
    def list_tools(self) -> List[str]:
        """列出所有已注册的工具"""
        return list(self._tools.keys())


# 全局单例
_mcp_adapter: Optional[MCPAdapter] = None


def get_mcp_adapter() -> MCPAdapter:
    """获取全局 MCP 适配器实例"""
    global _mcp_adapter
    if _mcp_adapter is None:
        _mcp_adapter = MCPAdapter()
    return _mcp_adapter
