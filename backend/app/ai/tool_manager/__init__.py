"""Tool Manager Module - Tools Registry and Management.

导出:
- ToolManager: 工具管理器（AgentScope ToolBase + DB 元数据缓存）
- ToolExecutor: 反射式工具执行器（供「工具测试」接口）
- get_tool_manager: 进程级单例访问器
- SqlBotTemplateTool / SqlBotToolConfig: 配置化 SQLBot 业务 Tool 及其配置契约
- ToolUserContext / bind_tool_user / get_tool_user: Tool 执行期用户上下文
"""
from app.ai.tool_manager.manager import ToolManager, get_tool_manager
from app.ai.tool_manager.executor import ToolExecutor
from app.ai.tool_manager.models import ToolType
from app.ai.tool_manager.sqlbot_tool_config import (
    CONFIG_VERSION,
    SqlBotToolConfig,
    validate_config,
)
from app.ai.tool_manager.sqlbot_template_tool import SqlBotTemplateTool
from app.ai.tool_manager.ddl_parser import (
    DDLParseError,
    ParsedColumn,
    ParsedTable,
    guess_sensitive_columns,
    parse_ddl,
    parse_ddl_safe,
    parse_ddl_statements,
)
from app.ai.tool_manager.sqlbot_tool_factory import (
    SQLBOT_TEMPLATE_CLASS_PATH,
    build_from_config,
    from_tool_key,
    is_sqlbot_template_tool,
)
from app.ai.tool_manager.tool_context import (
    ToolUserContext,
    bind_tool_user,
    build_user_context,
    get_tool_user,
)

__all__ = [
    "ToolManager",
    "ToolExecutor",
    "get_tool_manager",
    "ToolType",
    # SQLBot 配置化工具
    "CONFIG_VERSION",
    "SqlBotToolConfig",
    "SqlBotTemplateTool",
    "SQLBOT_TEMPLATE_CLASS_PATH",
    "validate_config",
    "build_from_config",
    "from_tool_key",
    "is_sqlbot_template_tool",
    # DDL 解析
    "DDLParseError",
    "ParsedColumn",
    "ParsedTable",
    "guess_sensitive_columns",
    "parse_ddl",
    "parse_ddl_safe",
    "parse_ddl_statements",
    # 用户上下文
    "ToolUserContext",
    "bind_tool_user",
    "build_user_context",
    "get_tool_user",
]
