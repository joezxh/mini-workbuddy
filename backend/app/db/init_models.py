"""集中登记所有 ORM 模型 —— 建表的单一事实来源。

⚠️ 任何新增 model 必须在此 import，否则不会被 create_all / alembic 识别。
"""
# fmt: off

# --- 系统管理 (sys_) ---
from app.models.sys.sys_tenant import SysTenant, SysTenantPackage               # noqa: F401
from app.models.sys.sys_user import (                                             # noqa: F401
    SysUser, SysRole, SysMenu, SysRegion, SysRoleMenu, SysUserRole,
    SysAuditLog,
)
from app.models.sys.sys_dictionary import SysDictionary, SysDictionaryItem        # noqa: F401
from app.models.sys.sys_user_notification import SysUserNotification              # noqa: F401
from app.models.sys.sys_infra_file import SysInfraFile, SysInfraFileContent             # noqa: F401

# --- AI 会话 / Agent (ai_ / agent_) ---
from app.models.ai.ai_chat import AiChatSession, AiChatMessage               # noqa: F401
from app.models.ai.ai_api_key import AiApiKey, AiChatModel                    # noqa: F401
from app.models.agent.agent_config import AgentConfig                           # noqa: F401
from app.models.agent.agent_team import AgentTeam, AgentTeamMember, AgentTeamEdge  # noqa: F401
from app.models.agent.agent_team_run import AgentTeamRun                        # noqa: F401
from app.models.agent.agent_async_task import AgentAsyncTask                    # noqa: F401
from app.models.agent.agent_scheduled_task import AgentScheduledTask            # noqa: F401
from app.models.agent.agent_execution import AgentExecution                     # noqa: F401
from app.models.agent.agent_execution_event import AgentExecutionEvent          # noqa: F401
from app.models.agent.agent_trace import AgentTrace                             # noqa: F401

# --- 工具 / 技能 / MCP (ai_) ---
from app.models.ai.ai_tool_definition import AiToolDefinition                # noqa: F401
from app.models.ai.ai_tool_group import AiToolGroup, AiToolGroupMember         # noqa: F401
from app.models.ai.ai_skill_package import AiSkillPackage                      # noqa: F401
from app.models.ai.ai_skill_rule import AiSkillRule                              # noqa: F401
from app.models.ai.ai_skill_version import AiSkillVersion                       # noqa: F401
from app.models.ai.ai_skill_metrics import AiSkillMetrics                       # noqa: F401
from app.models.ai.ai_skill_evolution_config import AiSkillEvolutionConfig      # noqa: F401
from app.models.ai.ai_skill_evolution_log import AiSkillEvolutionLog            # noqa: F401
from app.models.ai.ai_skill_script import AiSkillScript                         # noqa: F401
from app.models.ai.ai_mcp_api_key import AiMcpApiKey                              # noqa: F401
from app.models.ai.ai_mcp_client import AiMcpClient                               # noqa: F401
from app.models.ai.ai_mcp_square_template import AiMcpSquareTemplate              # noqa: F401
from app.models.ai.ai_web_search import AiWebSearch, AiWebSearchLog          # noqa: F401
from app.models.ai.ai_skill_hub_repo import AiSkillHubRepo                   # noqa: F401

# --- 工作空间 (ai_) ---
from app.models.ai.ai_workspace import AiWorkspace                              # noqa: F401

# --- LLM-wiki ---
from app.models.wiki.wiki_article import WikiArticle                           # noqa: F401
from app.models.wiki.wiki_article_version import WikiArticleVersion             # noqa: F401
from app.models.wiki.wiki_category import WikiCategory                         # noqa: F401
# fmt: on
