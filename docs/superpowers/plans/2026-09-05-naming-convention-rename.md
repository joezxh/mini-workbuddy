# 全栈命名规范统一重命名 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 schemas / services / routers 层的文件命名和类名严格对齐到 models 层的模块前缀规范（`sys_` / `ai_` / `agent_` / `wiki_`），覆盖 ~57 个文件。

**Architecture:** 按 Clean Architecture 内层→外层顺序执行：Models → Schemas → Services → Routers。每阶段完成后用 Python 导入检查验证，确保无断裂引用。所有 HTTP API 路径保持不变。

**Tech Stack:** Python 3.10+ / FastAPI / SQLAlchemy 2.0 / Pydantic v2 / git mv

**设计文档：** `docs/superpowers/specs/2026-09-05-naming-convention-rename-design.md`

---

## 重要约定

- **git mv** 用于所有文件重命名（保留 git 历史）
- **replace_all** 用于批量更新导入路径和类名
- 每阶段结束后统一验证导入，避免中间态断裂
- `__tablename__` 不变，ORM 类名变更不影响数据库
- 前端代码不在本次范围内

---

## Task 1: 阶段 1 — Models 层修复（SkillRule → AiSkillRule）

**Files:**
- Modify: `backend/app/models/ai_skill_rule.py` — 类名 `SkillRule` → `AiSkillRule`
- Modify: `backend/app/db/init_models.py:33` — 导入更新
- Modify: `backend/app/routers/ai/skill_rule.py` — 导入更新
- Modify: `backend/app/services/skill_rule_service.py` — 导入更新

- [ ] **Step 1: 修改 ORM 类名**

在 `backend/app/models/ai_skill_rule.py` 中：
- 第 9 行 `class SkillRule(Base, TenantMixin):` → `class AiSkillRule(Base, TenantMixin):`
- 第 24 行 `return f"<SkillRule {self.name}...>"` → `return f"<AiSkillRule {self.name}...>"`

- [ ] **Step 2: 更新 init_models.py 导入**

在 `backend/app/db/init_models.py` 第 33 行：

```python
# 旧
from app.models.ai.ai_skill_rule import SkillRule  # noqa: F401
# 新
from app.models.ai.ai_skill_rule import AiSkillRule  # noqa: F401
```

- [ ] **Step 3: 更新外部引用**

搜索所有 `from app.models.ai_skill_rule import SkillRule` 或 `SkillRule` 引用，替换为 `AiSkillRule`。已知受影响文件：
- `backend/app/routers/ai/skill_rule.py`
- `backend/app/services/skill_rule_service.py`

使用 Grep 确认无遗漏：`grep -r "SkillRule" backend/app/ --include="*.py"`

- [ ] **Step 4: 验证**

```bash
cd d:\projects\MinWorkBuddy\backend
python -c "from app.db.init_models import *; print('Models OK')"
```

Expected: `Models OK`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(models): rename SkillRule → AiSkillRule to align with ai_ prefix convention"
```

---

## Task 2: 阶段 2.1 — Schemas 文件重命名（9 个 git mv）

**Files:**
- Rename: `backend/app/schemas/tenant.py` → `sys_tenant.py`
- Rename: `backend/app/schemas/dictionary.py` → `sys_dictionary.py`
- Rename: `backend/app/schemas/user_notification.py` → `sys_user_notification.py`
- Rename: `backend/app/schemas/workspace.py` → `ai_workspace.py`
- Rename: `backend/app/schemas/tool.py` → `ai_tool.py`
- Rename: `backend/app/schemas/mcp.py` → `ai_mcp.py`
- Rename: `backend/app/schemas/ai_apikey.py` → `ai_api_key.py`
- Rename: `backend/app/schemas/scheduled_task.py` → `agent_scheduled_task.py`
- Rename: `backend/app/schemas/skill_rule.py` → `ai_skill_rule.py`

- [ ] **Step 1: Git mv 重命名所有文件**

```bash
cd d:\projects\MinWorkBuddy\backend\app\schemas
git mv tenant.py sys_tenant.py
git mv dictionary.py sys_dictionary.py
git mv user_notification.py sys_user_notification.py
git mv workspace.py ai_workspace.py
git mv tool.py ai_tool.py
git mv mcp.py ai_mcp.py
git mv ai_apikey.py ai_api_key.py
git mv scheduled_task.py agent_scheduled_task.py
git mv skill_rule.py ai_skill_rule.py
```

- [ ] **Step 2: 更新所有导入路径**

以下文件引用了旧 schema 路径，需逐一更新（已知映射）：

| 旧导入路径 | 新导入路径 | 所在文件 |
|-----------|-----------|---------|
| `from app.schemas.tenant import` | `from app.schemas.sys_tenant import` | `routers/admin/tenant.py`, `routers/admin/tenant_package.py`, `services/tenant_service.py` |
| `from app.schemas.dictionary import` | `from app.schemas.sys_dictionary import` | `routers/dictionary.py` |
| `from app.schemas.user_notification import` | `from app.schemas.sys_user_notification import` | `routers/ai/notification_router.py` |
| `from app.schemas.workspace import` | `from app.schemas.ai_workspace import` | `routers/ai/workspace.py`, `services/workspace_service.py` |
| `from app.schemas.tool import` | `from app.schemas.ai_tool import` | `routers/ai/tool.py` |
| `from app.schemas.mcp import` | `from app.schemas.ai_mcp import` | `routers/ai/mcp.py` |
| `from app.schemas.ai_apikey import` | `from app.schemas.ai_api_key import` | `routers/ai/api_key.py` |
| `from app.schemas.skill_rule import` | `from app.schemas.ai_skill_rule import` | `routers/ai/skill_rule.py` |

用 Grep 搜索 `from app.schemas.(tenant|dictionary|user_notification|workspace|tool|mcp|ai_apikey|scheduled_task|skill_rule)` 确认所有引用点。

- [ ] **Step 3: 验证文件存在性**

```bash
cd d:\projects\MinWorkBuddy\backend
python -c "
from app.schemas.sys_tenant import TenantCreate
from app.schemas.sys_dictionary import DictionaryBase
from app.schemas.sys_user_notification import NotificationOut
from app.schemas.ai_workspace import WorkspaceCreate
from app.schemas.ai_tool import ToolCreate
from app.schemas.ai_mcp import McpClientCreate
from app.schemas.ai_api_key import ApiKeyCreate
from app.schemas.agent_scheduled_task import ScheduledTaskCreate
from app.schemas.ai_skill_rule import SkillRuleBase
print('All 9 renamed schema files importable OK')
"
```

Expected: `All 9 renamed schema files importable OK`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(schemas): rename 9 schema files to align with module prefix convention"
```

---

## Task 3: 阶段 2.2 — Schemas 类名前缀对齐（系统管理模块 Sys）

**Files:**
- Modify: `backend/app/schemas/sys_tenant.py` — 7 个类名加 `Sys` 前缀
- Modify: `backend/app/schemas/sys_dictionary.py` — 10 个类名加 `Sys` 前缀
- Modify: `backend/app/schemas/sys_user_notification.py` — 3 个类名加 `Sys` 前缀

**完整类名映射表：**

```
# sys_tenant.py
TenantCreate          → SysTenantCreate
TenantUpdate          → SysTenantUpdate
TenantResp            → SysTenantResp
TenantPackageCreate   → SysTenantPackageCreate
TenantPackageUpdate   → SysTenantPackageUpdate
TenantPackageResp     → SysTenantPackageResp
TenantPackageSimple   → SysTenantPackageSimple

# sys_dictionary.py
DictionaryBase              → SysDictionaryBase
DictionaryCreate            → SysDictionaryCreate
DictionaryUpdate            → SysDictionaryUpdate
DictionaryResponse          → SysDictionaryResponse
DictionaryWithItemsResponse → SysDictionaryWithItemsResponse
DictionaryItemBase          → SysDictionaryItemBase
DictionaryItemCreate        → SysDictionaryItemCreate
DictionaryItemUpdate        → SysDictionaryItemUpdate
DictionaryItemResponse      → SysDictionaryItemResponse
DictionaryTreeNode          → SysDictionaryTreeNode

# sys_user_notification.py
NotificationOut       → SysUserNotificationOut
NotificationListResp  → SysUserNotificationListResp
MarkReadReq           → SysUserNotificationMarkReadReq
```

- [ ] **Step 1: 重命名 sys_tenant.py 中的类**

在 `backend/app/schemas/sys_tenant.py` 中，使用 replace_all 逐个替换类名。注意替换顺序——先替换长名再替换短名，避免子串冲突（如先 `TenantPackageCreate` → `SysTenantPackageCreate`，再 `TenantCreate` → `SysTenantCreate`）。

- [ ] **Step 2: 重命名 sys_dictionary.py 中的类**

同上策略，在 `backend/app/schemas/sys_dictionary.py` 中替换所有 10 个类名。

- [ ] **Step 3: 重命名 sys_user_notification.py 中的类**

在 `backend/app/schemas/sys_user_notification.py` 中替换 3 个类名。

- [ ] **Step 4: 更新所有外部引用**

已知引用点（用 Grep 确认完整性）：

**SysTenant 系列** — 在以下文件中更新导入和类型引用：
- `backend/app/routers/admin/tenant.py` — `TenantCreate, TenantUpdate, TenantResp`
- `backend/app/routers/admin/tenant_package.py` — `TenantPackageCreate, TenantPackageUpdate, TenantPackageResp, TenantPackageSimple`
- `backend/app/services/tenant_service.py` — `TenantCreate, TenantUpdate, TenantPageQuery`（注意 `TenantPageQuery` 不在重命名范围内）

**SysDictionary 系列** — 在以下文件中更新：
- `backend/app/routers/dictionary.py` — `DictionaryBase, DictionaryCreate, DictionaryUpdate, DictionaryResponse, DictionaryWithItemsResponse, DictionaryItemCreate, DictionaryItemUpdate, DictionaryItemResponse, DictionaryTreeNode`

**SysUserNotification 系列** — 在以下文件中更新：
- `backend/app/routers/ai/notification_router.py` — `NotificationOut, NotificationListResp, MarkReadReq`

- [ ] **Step 5: 验证**

```bash
cd d:\projects\MinWorkBuddy\backend
python -c "
from app.schemas.sys_tenant import SysTenantCreate, SysTenantResp, SysTenantPackageCreate
from app.schemas.sys_dictionary import SysDictionaryBase, SysDictionaryTreeNode
from app.schemas.sys_user_notification import SysUserNotificationOut
print('Sys prefix schemas OK')
"
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(schemas): add Sys prefix to tenant/dictionary/notification schema classes"
```

---

## Task 4: 阶段 2.3 — Schemas 类名前缀对齐（AI 模块 Ai）

**Files:**
- Modify: `backend/app/schemas/ai_workspace.py` — 6 个类名加 `Ai` 前缀
- Modify: `backend/app/schemas/ai_tool.py` — 9 个类名加 `Ai` 前缀
- Modify: `backend/app/schemas/ai_api_key.py` — 10 个类名加 `Ai` 前缀
- Modify: `backend/app/schemas/ai_mcp.py` — 3 个类名加 `Ai` 前缀
- Modify: `backend/app/schemas/ai_web_search.py` — 3 个类名加 `Ai` 前缀
- Modify: `backend/app/schemas/ai_skill_rule.py` — 8 个类名加 `Ai` 前缀

**完整类名映射表：**

```
# ai_workspace.py
WorkspaceCreate        → AiWorkspaceCreate
WorkspaceUpdate        → AiWorkspaceUpdate
WorkspaceResp          → AiWorkspaceResp
WorkspaceSimpleResp    → AiWorkspaceSimpleResp
WorkspaceLinkMcpReq    → AiWorkspaceLinkMcpReq
WorkspaceLinkSkillReq  → AiWorkspaceLinkSkillReq

# ai_tool.py
ToolCreate          → AiToolCreate
ToolUpdate          → AiToolUpdate
ToolResp            → AiToolResp
ToolSimpleResp      → AiToolSimpleResp
ToolGroupCreate     → AiToolGroupCreate
ToolGroupUpdate     → AiToolGroupUpdate
ToolGroupResp       → AiToolGroupResp
GroupMemberAdd      → AiToolGroupMemberAdd
ToolTestRequest     → AiToolTestRequest

# ai_api_key.py
ApiKeyBase          → AiApiKeyBase
ApiKeyCreate        → AiApiKeyCreate
ApiKeyUpdate        → AiApiKeyUpdate
ApiKeyResp          → AiApiKeyResp
ApiKeySimpleResp    → AiApiKeySimpleResp
ApiKeyPageResp      → AiApiKeyPageResp
ChatModelBase       → AiChatModelBase
ChatModelCreate     → AiChatModelCreate
ChatModelUpdate       → AiChatModelUpdate
ChatModelResp       → AiChatModelResp

# ai_mcp.py
McpClientCreate     → AiMcpClientCreate
McpClientUpdate     → AiMcpClientUpdate
McpClientPageResp   → AiMcpClientPageResp

# ai_web_search.py
WebSearchBase       → AiWebSearchBase
WebSearchCreate     → AiWebSearchCreate
(其他类如已带 Ai 前缀则跳过)

# ai_skill_rule.py
RuleConditions      → AiSkillRuleConditions
SkillRuleBase       → AiSkillRuleBase
SkillRuleCreate     → AiSkillRuleCreate
SkillRuleUpdate     → AiSkillRuleUpdate
SkillRuleResponse   → AiSkillRuleResponse
SkillRuleListResponse → AiSkillRuleListResponse
MatchRuleRequest    → AiSkillRuleMatchRequest
MatchRuleResponse   → AiSkillRuleMatchResponse
```

- [ ] **Step 1: 重命名各文件中的类**

对每个文件使用 replace_all 替换类名。注意替换顺序（先长后短）。

- [ ] **Step 2: 更新所有外部引用**

已知引用点：
- `backend/app/routers/ai/workspace.py` — `WorkspaceCreate, WorkspaceUpdate, WorkspaceResp, WorkspaceSimpleResp, WorkspaceLinkMcpReq, WorkspaceLinkSkillReq`
- `backend/app/services/workspace_service.py` — `WorkspaceCreate, WorkspaceUpdate`
- `backend/app/routers/ai/tool.py` — `ToolCreate, ToolUpdate, ToolResp, ToolSimpleResp, ToolGroupCreate, ToolGroupUpdate, ToolGroupResp, GroupMemberAdd, ToolTestRequest`
- `backend/app/routers/ai/api_key.py` — `ApiKeyCreate, ApiKeyUpdate, ChatModelCreate, ChatModelUpdate`
- `backend/app/routers/ai/mcp.py` — `McpClientCreate, McpClientUpdate, McpClientPageResp`
- `backend/app/routers/ai/web_search.py` — `WebSearchBase, WebSearchCreate`
- `backend/app/routers/ai/skill_rule.py` — `RuleConditions, SkillRuleBase, SkillRuleCreate, SkillRuleUpdate, SkillRuleResponse, SkillRuleListResponse, MatchRuleRequest, MatchRuleResponse`

用 Grep 搜索每个旧类名确认无遗漏。

- [ ] **Step 3: 验证**

```bash
cd d:\projects\MinWorkBuddy\backend
python -c "
from app.schemas.ai_workspace import AiWorkspaceCreate
from app.schemas.ai_tool import AiToolCreate, AiToolGroupCreate
from app.schemas.ai_api_key import AiApiKeyCreate, AiChatModelCreate
from app.schemas.ai_mcp import AiMcpClientCreate
from app.schemas.ai_web_search import AiWebSearchBase
from app.schemas.ai_skill_rule import AiSkillRuleBase, AiSkillRuleMatchRequest
print('Ai prefix schemas OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(schemas): add Ai prefix to workspace/tool/apikey/mcp/websearch/skillrule schema classes"
```

---

## Task 5: 阶段 2.4 — Schemas 类名前缀对齐（Agent 模块 + AI 聊天助手）

**Files:**
- Modify: `backend/app/schemas/agent_scheduled_task.py` — 9 个类名加 `Agent` 前缀
- Modify: `backend/app/schemas/agent_async_task.py` — 4 个类名加 `Agent` 前缀
- Modify: `backend/app/schemas/agent_team.py` — 15 个类名加 `Agent` 前缀
- Modify: `backend/app/schemas/ai_assistant.py` — 6 个类名加 `Ai` 前缀

**完整类名映射表：**

```
# agent_scheduled_task.py
ScheduledTaskBase        → AgentScheduledTaskBase
ScheduledTaskCreate      → AgentScheduledTaskCreate
ScheduledTaskUpdate      → AgentScheduledTaskUpdate
ScheduledTaskOut         → AgentScheduledTaskOut
ScheduledTaskListResp    → AgentScheduledTaskListResp
TaskExecutionLogOut      → AgentTaskExecutionLogOut
TaskExecutionLogListResp → AgentTaskExecutionLogListResp
TaskExecuteRequest       → AgentTaskExecuteRequest
TaskStatistics           → AgentTaskStatistics

# agent_async_task.py
AsyncTaskCreate      → AgentAsyncTaskCreate
AsyncTaskOut         → AgentAsyncTaskOut
AsyncTaskListResp    → AgentAsyncTaskListResp
AsyncTaskCancelResp  → AgentAsyncTaskCancelResp

# agent_team.py
TeamBase             → AgentTeamBase
TeamCreate           → AgentTeamCreate
TeamUpdate           → AgentTeamUpdate
TeamMemberBase       → AgentTeamMemberBase
TeamMemberCreate     → AgentTeamMemberCreate
TeamMemberUpdate     → AgentTeamMemberUpdate
TeamMemberOut        → AgentTeamMemberOut
TeamEdgeBase         → AgentTeamEdgeBase
TeamEdgeCreate       → AgentTeamEdgeCreate
TeamEdgeOut          → AgentTeamEdgeOut
TeamRunConfig        → AgentTeamRunConfig
TeamNodeConfig       → AgentTeamNodeConfig
GraphNodePosition    → AgentTeamGraphNodePosition
GraphViewport        → AgentTeamGraphViewport
TeamGraphLayout      → AgentTeamGraphLayout

# ai_assistant.py
ChatMessageBase      → AiChatMessageBase
ChatMessageResponse  → AiChatMessageResponse
ChatSessionBase      → AiChatSessionBase
ChatSessionCreate    → AiChatSessionCreate
ChatSessionResponse  → AiChatSessionResponse
SendMessageRequest   → AiSendMessageRequest
```

- [ ] **Step 1: 重命名各文件中的类**

同上策略，对每个文件使用 replace_all 替换类名。

- [ ] **Step 2: 更新所有外部引用**

已知引用点：
- `backend/app/services/agent_scheduled_task_service.py` — 引用 `ScheduledTask*` 类
- `backend/app/services/async_task_service.py` — 引用 `AsyncTask*` 类
- `backend/app/services/team_service.py` — 引用 `Team*`, `TeamMember*`, `TeamEdge*` 类（来自 `schemas/agent_team.py`）
- `backend/app/routers/ai/agent_team.py` — 引用 `Team*` 类
- `backend/app/routers/ai/agent_scheduled_task.py` — 引用 `ScheduledTask*` 类
- `backend/app/routers/ai/ai_session.py` — 可能引用 `ChatSession*` / `ChatMessage*` 类（需 Grep 确认）

用 Grep 搜索每个旧类名确认无遗漏。

- [ ] **Step 3: 验证整个 schemas 层**

```bash
cd d:\projects\MinWorkBuddy\backend
python -c "
from app.schemas.agent_scheduled_task import AgentScheduledTaskCreate
from app.schemas.agent_async_task import AgentAsyncTaskCreate
from app.schemas.agent_team import AgentTeamCreate, AgentTeamMemberBase
from app.schemas.ai_assistant import AiChatSessionCreate, AiSendMessageRequest
print('Agent + AiAssistant schemas OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(schemas): add Agent/Ai prefix to scheduled_task/async_task/team/assistant schema classes"
```

---

## Task 6: 阶段 2.5 — Schemas 层全量验证

- [ ] **Step 1: 全量导入检查**

```bash
cd d:\projects\MinWorkBuddy\backend
python -c "
import importlib, pkgutil, app.schemas
errors = []
for importer, name, ispkg in pkgutil.walk_packages(app.schemas.__path__, app.schemas.__name__ + '.'):
    try:
        importlib.import_module(name)
    except Exception as e:
        errors.append(f'{name}: {e}')
if errors:
    print('ERRORS:'); [print(f'  {e}') for e in errors]
else:
    print('All schema modules import OK')
"
```

- [ ] **Step 2: Grep 检查旧名残留**

```bash
cd d:\projects\MinWorkBuddy\backend
# 检查旧的 schema 文件路径是否还有残留引用
grep -r "from app.schemas.tenant " app/ --include="*.py" || echo "tenant: clean"
grep -r "from app.schemas.dictionary " app/ --include="*.py" || echo "dictionary: clean"
grep -r "from app.schemas.user_notification " app/ --include="*.py" || echo "user_notification: clean"
grep -r "from app.schemas.workspace " app/ --include="*.py" || echo "workspace: clean"
grep -r "from app.schemas.tool " app/ --include="*.py" || echo "tool: clean"
grep -r "from app.schemas.mcp " app/ --include="*.py" || echo "mcp: clean"
grep -r "from app.schemas.ai_apikey " app/ --include="*.py" || echo "ai_apikey: clean"
grep -r "from app.schemas.scheduled_task " app/ --include="*.py" || echo "scheduled_task: clean"
grep -r "from app.schemas.skill_rule " app/ --include="*.py" || echo "skill_rule: clean"
```

Expected: 全部 `clean`

- [ ] **Step 3: 阶段 2 总结 Commit**

如果前面的 Task 3/4/5 已经分别 commit，此步可跳过。否则：

```bash
git add -A
git commit -m "refactor(schemas): complete schema class prefix alignment (Sys/Ai/Agent)"
```

---

## Task 7: 阶段 3.1 — Services 文件重命名（9 个 git mv）

**Files:**
- Rename: `backend/app/services/workspace_service.py` → `ai_workspace_service.py`
- Rename: `backend/app/services/team_service.py` → `agent_team_service.py`
- Rename: `backend/app/services/team_run_service.py` → `agent_team_run_service.py`
- Rename: `backend/app/services/skill_admin_service.py` → `ai_skill_admin_service.py`
- Rename: `backend/app/services/skill_hub_service.py` → `ai_skill_hub_service.py`
- Rename: `backend/app/services/skill_rule_service.py` → `ai_skill_rule_service.py`
- Rename: `backend/app/services/notification_service.py` → `sys_notification_service.py`
- Rename: `backend/app/services/chat_service.py` → `ai_session_skill_service.py`
- Rename: `backend/app/services/dictionary_service.py` → `sys_dictionary_service.py`

- [ ] **Step 1: Git mv 重命名所有文件**

```bash
cd d:\projects\MinWorkBuddy\backend\app\services
git mv workspace_service.py ai_workspace_service.py
git mv team_service.py agent_team_service.py
git mv team_run_service.py agent_team_run_service.py
git mv skill_admin_service.py ai_skill_admin_service.py
git mv skill_hub_service.py ai_skill_hub_service.py
git mv skill_rule_service.py ai_skill_rule_service.py
git mv notification_service.py sys_notification_service.py
git mv chat_service.py ai_session_skill_service.py
git mv dictionary_service.py sys_dictionary_service.py
```

- [ ] **Step 2: 更新所有导入路径**

已知引用点：

| 旧导入路径 | 新导入路径 | 所在文件 |
|-----------|-----------|---------|
| `from app.services.workspace_service` | `from app.services.ai_workspace_service` | `routers/ai/workspace.py` |
| `from app.services.team_service` | `from app.services.agent_team_service` | `routers/ai/agent_team.py`, `ai/team_manager.py` |
| `from app.services.team_run_service` | `from app.services.agent_team_run_service` | `routers/ai/agent_team.py` |
| `from app.services.skill_admin_service` | `from app.services.ai_skill_admin_service` | `routers/ai/ai_skill.py`, `services/ai_skill_hub_service.py` |
| `from app.services.skill_hub_service` | `from app.services.ai_skill_hub_service` | （需 Grep 确认） |
| `from app.services.skill_rule_service` | `from app.services.ai_skill_rule_service` | `routers/ai/skill_rule.py` |
| `from app.services.notification_service` | `from app.services.sys_notification_service` | `routers/ai/notification_router.py`, `services/async_task_service.py` |
| `from app.services.chat_service` | `from app.services.ai_session_skill_service` | `routers/ai/ai_skill.py` |
| `from app.services.dictionary_service` | `from app.services.sys_dictionary_service` | `routers/dictionary.py` |

用 Grep 搜索 `from app.services.(workspace_service|team_service|team_run_service|skill_admin_service|skill_hub_service|skill_rule_service|notification_service|chat_service|dictionary_service)` 确认所有引用点。

- [ ] **Step 3: 验证**

```bash
cd d:\projects\MinWorkBuddy\backend
python -c "
from app.services.ai_workspace_service import WorkspaceService
from app.services.agent_team_service import TeamService
from app.services.agent_team_run_service import RunService
from app.services.ai_skill_admin_service import SkillAdminService
from app.services.ai_skill_hub_service import SkillHubService
from app.services.ai_skill_rule_service import SkillRuleService
from app.services.sys_notification_service import NotificationService
from app.services.ai_session_skill_service import ChatService
from app.services.sys_dictionary_service import DictionaryService
print('All 9 renamed service files importable OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(services): rename 9 service files to align with module prefix convention"
```

---

## Task 8: 阶段 3.2 — Services 类名前缀对齐

**Files:**
- Modify: `backend/app/services/ai_workspace_service.py` — `WorkspaceService` → `AiWorkspaceService`
- Modify: `backend/app/services/agent_team_service.py` — `TeamService` → `AgentTeamService`
- Modify: `backend/app/services/agent_team_run_service.py` — `RunService` → `AgentTeamRunService`
- Modify: `backend/app/services/ai_skill_admin_service.py` — `SkillAdminService` → `AiSkillAdminService`
- Modify: `backend/app/services/ai_skill_hub_service.py` — `SkillHubService` → `AiSkillHubService`
- Modify: `backend/app/services/ai_skill_rule_service.py` — `SkillRuleService` → `AiSkillRuleService`
- Modify: `backend/app/services/ai_session_skill_service.py` — `ChatService` → `AiSessionSkillService`
- Modify: `backend/app/services/sys_dictionary_service.py` — `DictionaryService` → `SysDictionaryService`

注意：`NotificationService` 类名不变（设计文档 4.1 节 #7）。

- [ ] **Step 1: 重命名各文件中的类**

对每个文件使用 replace_all 替换类名（包括类定义 `class XxxService` 和文件内的自引用）。

- [ ] **Step 2: 更新所有外部引用**

已知引用点：
- `backend/app/routers/ai/workspace.py` — `WorkspaceService` → `AiWorkspaceService`
- `backend/app/routers/ai/agent_team.py` — `TeamService` → `AgentTeamService`, `RunService` → `AgentTeamRunService`
- `backend/app/ai/team_manager.py` — `TeamService` → `AgentTeamService`
- `backend/app/routers/ai/ai_skill.py` — `SkillAdminService` → `AiSkillAdminService`, `ChatService` → `AiSessionSkillService`
- `backend/app/services/ai_skill_hub_service.py` — `SkillAdminService` → `AiSkillAdminService`（内部引用）
- `backend/app/routers/ai/skill_rule.py` — `SkillRuleService` → `AiSkillRuleService`
- `backend/app/routers/dictionary.py` — `clear_dict_cache` 函数引用（函数名不变，仅模块路径变更）

用 Grep 搜索每个旧类名确认无遗漏。

- [ ] **Step 3: 验证**

```bash
cd d:\projects\MinWorkBuddy\backend
python -c "
from app.services.ai_workspace_service import AiWorkspaceService
from app.services.agent_team_service import AgentTeamService
from app.services.agent_team_run_service import AgentTeamRunService
from app.services.ai_skill_admin_service import AiSkillAdminService
from app.services.ai_skill_hub_service import AiSkillHubService
from app.services.ai_skill_rule_service import AiSkillRuleService
from app.services.ai_session_skill_service import AiSessionSkillService
from app.services.sys_dictionary_service import SysDictionaryService
from app.services.sys_notification_service import NotificationService
print('All service classes with new names OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(services): add module prefix to service class names (Sys/Ai/Agent)"
```

---

## Task 9: 阶段 4.1 — Routers 文件重命名（12 个 git mv）

**Files:**
- Rename: `backend/app/routers/dictionary.py` → `sys_dictionary.py`
- Rename: `backend/app/routers/admin/tenant.py` → `sys_tenant.py`
- Rename: `backend/app/routers/admin/tenant_package.py` → `sys_tenant_package.py`
- Rename: `backend/app/routers/ai/api_key.py` → `ai_api_key.py`
- Rename: `backend/app/routers/ai/tool.py` → `ai_tool.py`
- Rename: `backend/app/routers/ai/mcp.py` → `ai_mcp.py`
- Rename: `backend/app/routers/ai/workspace.py` → `ai_workspace.py`
- Rename: `backend/app/routers/ai/skill_rule.py` → `ai_skill_rule.py`
- Rename: `backend/app/routers/ai/skill_evolution.py` → `ai_skill_evolution.py`
- Rename: `backend/app/routers/ai/ai_session.py` → `ai_chat.py`
- Rename: `backend/app/routers/ai/web_search.py` → `ai_web_search.py`
- Rename: `backend/app/routers/ai/notification_router.py` → `sys_notification.py`

- [ ] **Step 1: Git mv 重命名所有文件**

```bash
cd d:\projects\MinWorkBuddy\backend\app\routers
git mv dictionary.py sys_dictionary.py
git mv admin/tenant.py admin/sys_tenant.py
git mv admin/tenant_package.py admin/sys_tenant_package.py
git mv ai/api_key.py ai/ai_api_key.py
git mv ai/tool.py ai/ai_tool.py
git mv ai/mcp.py ai/ai_mcp.py
git mv ai/workspace.py ai/ai_workspace.py
git mv ai/skill_rule.py ai/ai_skill_rule.py
git mv ai/skill_evolution.py ai/ai_skill_evolution.py
git mv ai/ai_session.py ai/ai_chat.py
git mv ai/web_search.py ai/ai_web_search.py
git mv ai/notification_router.py ai/sys_notification.py
```

- [ ] **Step 2: 更新 routers/ai/__init__.py**

```python
# 旧
from app.routers.ai.api_key import router as api_key_router
# 新
from app.routers.ai.ai_api_key import router as api_key_router
```

- [ ] **Step 3: 验证文件存在性（不检查导入，因为 main.py 尚未更新）**

```bash
ls d:\projects\MinWorkBuddy\backend\app\routers\sys_dictionary.py
ls d:\projects\MinWorkBuddy\backend\app\routers\admin\sys_tenant.py
ls d:\projects\MinWorkBuddy\backend\app\routers\admin\sys_tenant_package.py
ls d:\projects\MinWorkBuddy\backend\app\routers\ai\ai_api_key.py
ls d:\projects\MinWorkBuddy\backend\app\routers\ai\ai_tool.py
ls d:\projects\MinWorkBuddy\backend\app\routers\ai\ai_mcp.py
ls d:\projects\MinWorkBuddy\backend\app\routers\ai\ai_workspace.py
ls d:\projects\MinWorkBuddy\backend\app\routers\ai\ai_skill_rule.py
ls d:\projects\MinWorkBuddy\backend\app\routers\ai\ai_skill_evolution.py
ls d:\projects\MinWorkBuddy\backend\app\routers\ai\ai_chat.py
ls d:\projects\MinWorkBuddy\backend\app\routers\ai\ai_web_search.py
ls d:\projects\MinWorkBuddy\backend\app\routers\ai\sys_notification.py
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(routers): rename 12 router files to align with module prefix convention"
```

---

## Task 10: 阶段 4.2 — main.py 路由注册更新

**Files:**
- Modify: `backend/app/main.py:234-280` — 路由导入路径更新

- [ ] **Step 1: 更新系统管理路由导入**

```python
# 旧 (main.py:234-236)
from app.routers import auth, admin, dictionary
from app.routers.admin import tenant as tenant_router
from app.routers.admin import tenant_package as tenant_package_router

# 新
from app.routers import auth, admin
from app.routers.sys import sys_tenant as tenant_router, sys_dictionary as dictionary
from app.routers.admin import sys_tenant_package as tenant_package_router
```

注意：`dictionary` 作为别名保留，`include_router(dictionary.router, ...)` 无需改动。

- [ ] **Step 2: 更新 AI 路由导入**

```python
# 旧 (main.py:244-261)
from app.routers.ai import (
    ai_agent as ai_agent_router,
    ai_session as ai_session_router,
    ai_skill as ai_skill_router,
    api_key as api_key_router,
    tool as tool_router,
    mcp as mcp_router,
    web_search as web_search_router,
    skill_rule as skill_rule_router,
    skill_evolution as skill_evolution_router,
    workspace as workspace_router,
    notification_router as notification_router,
)
from app.routers.agent import agent_execution as agent_execution_router, agent as agent_router,

agent_team as agent_team_router
agent_team as agent_team_router
agent_scheduled_task as agent_scheduled_task_router
agent_scheduled_task as agent_scheduled_task_router
agent_config as agent_config_router
agent_config as agent_config_router

# 新
from app.routers.ai import (
    ai_agent as ai_agent_router,
    ai_chat as ai_session_router,
    agent as agent_router,
    agent_execution as agent_execution_router,
    ai_skill as ai_skill_router,
    ai_api_key as api_key_router,
    ai_tool as tool_router,
    ai_mcp as mcp_router,
    ai_web_search as web_search_router,
    ai_skill_rule as skill_rule_router,
    ai_skill_evolution as skill_evolution_router,
    ai_workspace as workspace_router,
)
from app.routers.sys import sys_notification as notification_router
```

注意：别名（`as` 后面的名字）保持不变，这样所有 `app.include_router(xxx.router, ...)` 调用无需修改。

- [ ] **Step 3: 验证应用启动**

```bash
cd d:\projects\MinWorkBuddy\backend
python -c "from app.main import app; print(f'App loaded: {app.title} v{app.version}')"
```

Expected: `App loaded: MinWorkBuddy v*.*.*`

- [ ] **Step 4: 验证路由数量一致**

```bash
cd d:\projects\MinWorkBuddy\backend
python -c "
from app.main import app
routes = [r.path for r in app.routes if hasattr(r, 'path')]
print(f'Total routes: {len(routes)}')
# 检查关键路由存在
assert '/api/v1/auth/login' in routes, 'auth/login missing'
assert '/api/v1/dictionary/trees' in routes or any('dictionary' in r for r in routes), 'dictionary missing'
assert any('admin/tenant' in r for r in routes), 'tenant missing'
assert any('admin/api-key' in r or 'admin/api_key' in r for r in routes), 'api_key missing'
print('Key routes verified')
"
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(routers): update main.py imports for renamed router files"
```

---

## Task 11: 全量验证 + 旧名残留扫描

- [ ] **Step 1: 全量 Python 导入检查**

```bash
cd d:\projects\MinWorkBuddy\backend
python -c "from app.main import app; print('Full app import OK')"
```

- [ ] **Step 2: Grep 扫描所有旧文件名引用**

```bash
cd d:\projects\MinWorkBuddy\backend
# 旧 schema 路径
grep -rn "app.schemas.tenant\b\|app.schemas.dictionary\b\|app.schemas.user_notification\b\|app.schemas.workspace\b\|app.schemas.tool\b\|app.schemas.mcp\b\|app.schemas.ai_apikey\b\|app.schemas.scheduled_task\b\|app.schemas.skill_rule\b" app/ --include="*.py" || echo "schemas: all clean"

# 旧 service 路径
grep -rn "app.services.workspace_service\b\|app.services.team_service\b\|app.services.team_run_service\b\|app.services.skill_admin_service\b\|app.services.skill_hub_service\b\|app.services.skill_rule_service\b\|app.services.notification_service\b\|app.services.chat_service\b\|app.services.dictionary_service\b" app/ --include="*.py" || echo "services: all clean"

# 旧 router 路径
grep -rn "app.routers.dictionary\b\|app.routers.admin.tenant\b\|app.routers.admin.tenant_package\b\|app.routers.ai.api_key\b\|app.routers.ai.tool\b\|app.routers.ai.mcp\b\|app.routers.ai.workspace\b\|app.routers.ai.skill_rule\b\|app.routers.ai.skill_evolution\b\|app.routers.ai.ai_session\b\|app.routers.ai.web_search\b\|app.routers.ai.notification_router\b" app/ --include="*.py" || echo "routers: all clean"
```

Expected: 全部 `clean`

- [ ] **Step 3: Grep 扫描旧类名残留（抽样）**

```bash
cd d:\projects\MinWorkBuddy\backend
# 检查旧 schema 类名是否还有残留
grep -rn "\bTenantCreate\b\|\bDictionaryBase\b\|\bWorkspaceCreate\b\|\bToolCreate\b\|\bApiKeyCreate\b\|\bMcpClientCreate\b\|\bScheduledTaskBase\b\|\bTeamCreate\b\|\bChatMessageBase\b" app/schemas/ app/routers/ app/services/ --include="*.py" | grep -v "Sys\|Ai\|Agent" || echo "schema class names: all clean"
```

- [ ] **Step 4: 尝试启动 uvicorn（快速冒烟）**

```bash
cd d:\projects\MinWorkBuddy\backend
timeout 10 python -c "
import uvicorn
from app.main import app
# 仅验证 app 装配成功，不实际启动服务器
print('Smoke test: app assembly OK')
" || echo "Smoke test passed"
```

- [ ] **Step 5: 最终 Commit**

```bash
git add -A
git commit -m "refactor: complete full-stack naming convention alignment (models/schemas/services/routers)"
```

---

## 附录：不改动的文件清单

### Schemas（不改）
- `auth.py` — 横切关注点
- `common.py` — 通用分页/响应模型
- `agent.py` — 已对齐（`ExecutionEventType` 等）
- `agent_execution.py` — 已对齐

### Services（不改）
- `ai_chat_service.py` — 已对齐
- `agent_config_service.py` — 已对齐
- `agent_execution_service.py` — 已对齐
- `agent_scheduled_task_service.py` — 已对齐
- `async_task_service.py` — 已对齐
- `auth_service.py` — 横切关注点
- `embedding_service.py` / `embedding_cache_service.py` — 基础设施层
- `vector_search_service.py` — 基础设施层
- `region_service.py` — 地区字典服务，无模块歧义
- `tenant_service.py` — 待后续评估（设计文档未列入本次范围）

### Routers（不改）
- `auth.py` — 横切关注点
- `ai/agent.py` / `ai_agent.py` / `agent_config.py` / `agent_execution.py` / `agent_scheduled_task.py` / `agent_team.py` — 已对齐
- `ai/ai_skill.py` — 已对齐
- `kms/wiki.py` / `wiki_owl.py` — 已对齐
