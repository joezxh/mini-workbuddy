# 全栈命名规范统一重命名设计

> 日期：2026-09-05
> 状态：设计中
> 影响范围：models / schemas / services / routers 四层 ~57 个文件

## 1. 背景与目标

MinWorkBuddy 的 **models 层**已经建立了清晰的模块前缀规范：

| 模块 | 文件前缀 | 类名前缀 |
|------|---------|---------|
| 系统管理 | `sys_` | `Sys` |
| AI 配置/工具 | `ai_` | `Ai` |
| Agent 编排 | `agent_` | `Agent` |
| Wiki 知识库 | `wiki_` | `Wiki` |

但 **schemas / services / routers** 层未同步对齐，存在大量无前缀或前缀不一致的文件名和类名。本方案将三层命名严格对齐到 models 规范，确保跨层一致性。

### 设计原则

1. **内层先改**：Models → Schemas → Services → Routers
2. **API 路径不变**：所有 HTTP endpoint URL 保持向后兼容
3. **分阶段执行**：4 个阶段，每阶段可独立验证

## 2. 阶段 1：Models 层修复（1 处）

| 文件 | 当前类名 | 目标类名 |
|------|---------|---------|
| `models/ai_skill_rule.py` | `SkillRule` | `AiSkillRule` |

**受影响文件**：
- `db/init_models.py` — 导入 `SkillRule` → `AiSkillRule`
- `routers/ai/skill_rule.py` — 导入引用
- `services/skill_rule_service.py` — 导入引用
- `schemas/skill_rule.py` — 无直接引用 ORM 类，不受影响

## 3. 阶段 2：Schemas 层重命名

### 3.1 文件名重命名（9 个文件）

| # | 当前文件名 | 目标文件名 | 理由 |
|---|-----------|-----------|------|
| 1 | `schemas/tenant.py` | `schemas/sys_tenant.py` | 系统管理模块加 `sys_` |
| 2 | `schemas/dictionary.py` | `schemas/sys_dictionary.py` | 系统管理模块加 `sys_` |
| 3 | `schemas/user_notification.py` | `schemas/sys_user_notification.py` | 与 models `sys_user_notification.py` 对齐 |
| 4 | `schemas/workspace.py` | `schemas/ai_workspace.py` | 与 models `ai_workspace.py` 对齐 |
| 5 | `schemas/tool.py` | `schemas/ai_tool.py` | 与 models `ai_tool_definition.py` / `ai_tool_group.py` 对齐 |
| 6 | `schemas/mcp.py` | `schemas/ai_mcp.py` | 与 models `ai_mcp_*.py` 对齐 |
| 7 | `schemas/ai_apikey.py` | `schemas/ai_api_key.py` | 与 models `ai_api_key.py` 文件名对齐 |
| 8 | `schemas/scheduled_task.py` | `schemas/agent_scheduled_task.py` | 与 models `agent_scheduled_task.py` 对齐 |
| 9 | `schemas/skill_rule.py` | `schemas/ai_skill_rule.py` | 与 models `ai_skill_rule.py` 对齐 |

**不改动的文件**：`auth.py`（横切关注点）、`common.py`（通用）、`agent.py` / `agent_execution.py` / `agent_team.py` / `agent_async_task.py`（已对齐）、`ai_web_search.py`（已对齐）、`ai_assistant.py`（保留，对应 AI 聊天助手 UI 概念）

### 3.2 类名前缀对齐

#### 系统管理模块（加 `Sys` 前缀）

| 当前类名 | 目标类名 | 所在文件 |
|---------|---------|---------|
| `TenantCreate` | `SysTenantCreate` | sys_tenant.py |
| `TenantUpdate` | `SysTenantUpdate` | sys_tenant.py |
| `TenantResp` | `SysTenantResp` | sys_tenant.py |
| `TenantPackageCreate` | `SysTenantPackageCreate` | sys_tenant.py |
| `TenantPackageUpdate` | `SysTenantPackageUpdate` | sys_tenant.py |
| `TenantPackageResp` | `SysTenantPackageResp` | sys_tenant.py |
| `TenantPackageSimple` | `SysTenantPackageSimple` | sys_tenant.py |
| `DictionaryBase` | `SysDictionaryBase` | sys_dictionary.py |
| `DictionaryCreate` | `SysDictionaryCreate` | sys_dictionary.py |
| `DictionaryUpdate` | `SysDictionaryUpdate` | sys_dictionary.py |
| `DictionaryResponse` | `SysDictionaryResponse` | sys_dictionary.py |
| `DictionaryWithItemsResponse` | `SysDictionaryWithItemsResponse` | sys_dictionary.py |
| `DictionaryItemBase` | `SysDictionaryItemBase` | sys_dictionary.py |
| `DictionaryItemCreate` | `SysDictionaryItemCreate` | sys_dictionary.py |
| `DictionaryItemUpdate` | `SysDictionaryItemUpdate` | sys_dictionary.py |
| `DictionaryItemResponse` | `SysDictionaryItemResponse` | sys_dictionary.py |
| `DictionaryTreeNode` | `SysDictionaryTreeNode` | sys_dictionary.py |
| `NotificationOut` | `SysUserNotificationOut` | sys_user_notification.py |
| `NotificationListResp` | `SysUserNotificationListResp` | sys_user_notification.py |
| `MarkReadReq` | `SysUserNotificationMarkReadReq` | sys_user_notification.py |

#### AI 模块（加 `Ai` 前缀）

| 当前类名 | 目标类名 | 所在文件 |
|---------|---------|---------|
| `WorkspaceCreate` | `AiWorkspaceCreate` | ai_workspace.py |
| `WorkspaceUpdate` | `AiWorkspaceUpdate` | ai_workspace.py |
| `WorkspaceResp` | `AiWorkspaceResp` | ai_workspace.py |
| `WorkspaceSimpleResp` | `AiWorkspaceSimpleResp` | ai_workspace.py |
| `WorkspaceLinkMcpReq` | `AiWorkspaceLinkMcpReq` | ai_workspace.py |
| `WorkspaceLinkSkillReq` | `AiWorkspaceLinkSkillReq` | ai_workspace.py |
| `ToolCreate` | `AiToolCreate` | ai_tool.py |
| `ToolUpdate` | `AiToolUpdate` | ai_tool.py |
| `ToolResp` | `AiToolResp` | ai_tool.py |
| `ToolSimpleResp` | `AiToolSimpleResp` | ai_tool.py |
| `ToolGroupCreate` | `AiToolGroupCreate` | ai_tool.py |
| `ToolGroupUpdate` | `AiToolGroupUpdate` | ai_tool.py |
| `ToolGroupResp` | `AiToolGroupResp` | ai_tool.py |
| `GroupMemberAdd` | `AiToolGroupMemberAdd` | ai_tool.py |
| `ToolTestRequest` | `AiToolTestRequest` | ai_tool.py |
| `ApiKeyBase` | `AiApiKeyBase` | ai_api_key.py |
| `ApiKeyCreate` | `AiApiKeyCreate` | ai_api_key.py |
| `ApiKeyUpdate` | `AiApiKeyUpdate` | ai_api_key.py |
| `ApiKeyResp` | `AiApiKeyResp` | ai_api_key.py |
| `ApiKeySimpleResp` | `AiApiKeySimpleResp` | ai_api_key.py |
| `ApiKeyPageResp` | `AiApiKeyPageResp` | ai_api_key.py |
| `ChatModelBase` | `AiChatModelBase` | ai_api_key.py |
| `ChatModelCreate` | `AiChatModelCreate` | ai_api_key.py |
| `ChatModelUpdate` | `AiChatModelUpdate` | ai_api_key.py |
| `ChatModelResp` | `AiChatModelResp` | ai_api_key.py |
| `McpClientCreate` | `AiMcpClientCreate` | ai_mcp.py |
| `McpClientUpdate` | `AiMcpClientUpdate` | ai_mcp.py |
| `McpClientPageResp` | `AiMcpClientPageResp` | ai_mcp.py |
| `WebSearchBase` | `AiWebSearchBase` | ai_web_search.py |
| `WebSearchCreate` | `AiWebSearchCreate` | ai_web_search.py |
| `RuleConditions` | `AiSkillRuleConditions` | ai_skill_rule.py |
| `SkillRuleBase` | `AiSkillRuleBase` | ai_skill_rule.py |
| `SkillRuleCreate` | `AiSkillRuleCreate` | ai_skill_rule.py |
| `SkillRuleUpdate` | `AiSkillRuleUpdate` | ai_skill_rule.py |
| `SkillRuleResponse` | `AiSkillRuleResponse` | ai_skill_rule.py |
| `SkillRuleListResponse` | `AiSkillRuleListResponse` | ai_skill_rule.py |
| `MatchRuleRequest` | `AiSkillRuleMatchRequest` | ai_skill_rule.py |
| `MatchRuleResponse` | `AiSkillRuleMatchResponse` | ai_skill_rule.py |

#### Agent 模块（加 `Agent` 前缀）

| 当前类名 | 目标类名 | 所在文件 |
|---------|---------|---------|
| `ScheduledTaskBase` | `AgentScheduledTaskBase` | agent_scheduled_task.py |
| `ScheduledTaskCreate` | `AgentScheduledTaskCreate` | agent_scheduled_task.py |
| `ScheduledTaskUpdate` | `AgentScheduledTaskUpdate` | agent_scheduled_task.py |
| `ScheduledTaskOut` | `AgentScheduledTaskOut` | agent_scheduled_task.py |
| `ScheduledTaskListResp` | `AgentScheduledTaskListResp` | agent_scheduled_task.py |
| `TaskExecutionLogOut` | `AgentTaskExecutionLogOut` | agent_scheduled_task.py |
| `TaskExecutionLogListResp` | `AgentTaskExecutionLogListResp` | agent_scheduled_task.py |
| `TaskExecuteRequest` | `AgentTaskExecuteRequest` | agent_scheduled_task.py |
| `TaskStatistics` | `AgentTaskStatistics` | agent_scheduled_task.py |
| `AsyncTaskCreate` | `AgentAsyncTaskCreate` | agent_async_task.py |
| `AsyncTaskOut` | `AgentAsyncTaskOut` | agent_async_task.py |
| `AsyncTaskListResp` | `AgentAsyncTaskListResp` | agent_async_task.py |
| `AsyncTaskCancelResp` | `AgentAsyncTaskCancelResp` | agent_async_task.py |
| `TeamBase` | `AgentTeamBase` | agent_team.py |
| `TeamCreate` | `AgentTeamCreate` | agent_team.py |
| `TeamUpdate` | `AgentTeamUpdate` | agent_team.py |
| `TeamMemberBase` | `AgentTeamMemberBase` | agent_team.py |
| `TeamMemberCreate` | `AgentTeamMemberCreate` | agent_team.py |
| `TeamMemberUpdate` | `AgentTeamMemberUpdate` | agent_team.py |
| `TeamMemberOut` | `AgentTeamMemberOut` | agent_team.py |
| `TeamEdgeBase` | `AgentTeamEdgeBase` | agent_team.py |
| `TeamEdgeCreate` | `AgentTeamEdgeCreate` | agent_team.py |
| `TeamEdgeOut` | `AgentTeamEdgeOut` | agent_team.py |
| `TeamRunConfig` | `AgentTeamRunConfig` | agent_team.py |
| `TeamNodeConfig` | `AgentTeamNodeConfig` | agent_team.py |
| `GraphNodePosition` | `AgentTeamGraphNodePosition` | agent_team.py |
| `GraphViewport` | `AgentTeamGraphViewport` | agent_team.py |
| `TeamGraphLayout` | `AgentTeamGraphLayout` | agent_team.py |

#### AI 聊天助手（加 `Ai` 前缀）

| 当前类名 | 目标类名 | 所在文件 |
|---------|---------|---------|
| `ChatMessageBase` | `AiChatMessageBase` | ai_assistant.py |
| `ChatMessageResponse` | `AiChatMessageResponse` | ai_assistant.py |
| `ChatSessionBase` | `AiChatSessionBase` | ai_assistant.py |
| `ChatSessionCreate` | `AiChatSessionCreate` | ai_assistant.py |
| `ChatSessionResponse` | `AiChatSessionResponse` | ai_assistant.py |
| `SendMessageRequest` | `AiSendMessageRequest` | ai_assistant.py |

## 4. 阶段 3：Services 层重命名

### 4.1 文件名 + 类名重命名

| # | 当前文件 → 目标文件 | 当前类名 → 目标类名 |
|---|---------|---------|
| 1 | `workspace_service.py` → `ai_workspace_service.py` | `WorkspaceService` → `AiWorkspaceService` |
| 2 | `team_service.py` → `agent_team_service.py` | `TeamService` → `AgentTeamService` |
| 3 | `team_run_service.py` → `agent_team_run_service.py` | `RunService` → `AgentTeamRunService` |
| 4 | `skill_admin_service.py` → `ai_skill_admin_service.py` | `SkillAdminService` → `AiSkillAdminService` |
| 5 | `skill_hub_service.py` → `ai_skill_hub_service.py` | `SkillHubService` → `AiSkillHubService` |
| 6 | `skill_rule_service.py` → `ai_skill_rule_service.py` | `SkillRuleService` → `AiSkillRuleService` |
| 7 | `notification_service.py` → `sys_notification_service.py` | 类名不变（`NotificationService` 已足够清晰） |
| 8 | `chat_service.py` → `ai_session_skill_service.py` | `ChatService` → `AiSessionSkillService` |
| 9 | `dictionary_service.py` → `sys_dictionary_service.py` | `DictionaryService` → `SysDictionaryService` |

### 4.2 不改动的文件

- `ai_chat_service.py` — 已对齐 ✓
- `agent_config_service.py` — 已对齐 ✓
- `agent_execution_service.py` — 已对齐 ✓
- `agent_scheduled_task_service.py` — 已对齐 ✓
- `async_task_service.py` — 已对齐 ✓
- `auth_service.py` — 横切关注点
- `embedding_service.py` / `embedding_cache_service.py` — 基础设施层
- `vector_search_service.py` — 基础设施层
- `region_service.py` — 地区字典服务，无模块歧义

## 5. 阶段 4：Routers 层重命名

### 5.1 文件名重命名

| # | 当前 | 目标 | 理由 |
|---|------|------|------|
| 1 | `routers/dictionary.py` | `routers/sys_dictionary.py` | 系统管理 |
| 2 | `routers/admin/tenant.py` | `routers/admin/sys_tenant.py` | 系统管理 |
| 3 | `routers/admin/tenant_package.py` | `routers/admin/sys_tenant_package.py` | 系统管理 |
| 4 | `routers/ai/api_key.py` | `routers/ai/ai_api_key.py` | AI 模块 |
| 5 | `routers/ai/tool.py` | `routers/ai/ai_tool.py` | AI 模块 |
| 6 | `routers/ai/mcp.py` | `routers/ai/ai_mcp.py` | AI 模块 |
| 7 | `routers/ai/workspace.py` | `routers/ai/ai_workspace.py` | AI 模块 |
| 8 | `routers/ai/skill_rule.py` | `routers/ai/ai_skill_rule.py` | AI 模块 |
| 9 | `routers/ai/skill_evolution.py` | `routers/ai/ai_skill_evolution.py` | AI 模块 |
| 10 | `routers/ai/ai_session.py` | `routers/ai/ai_chat.py` | 与 models `ai_chat.py` 对齐 |
| 11 | `routers/ai/web_search.py` | `routers/ai/ai_web_search.py` | AI 模块 |
| 12 | `routers/ai/notification_router.py` | `routers/ai/sys_notification.py` | 系统通知 |

### 5.2 main.py 路由注册更新

所有 `from app.routers.xxx import` 和 `include_router()` 调用需同步更新导入路径。
**HTTP API 路径不变**，仅修改 Python 模块导入路径。

### 5.3 不改动的文件

- `routers/auth.py` — 横切关注点（认证）
- `routers/admin/__init__.py` — 仅更新内部导入路径
- `routers/ai/agent.py` / `ai_agent.py` / `agent_config.py` / `agent_execution.py` / `agent_scheduled_task.py` / `agent_team.py` — 已对齐 ✓
- `routers/ai/ai_skill.py` — 已对齐 ✓
- `routers/kms/wiki.py` / `wiki_owl.py` — 已对齐 ✓

## 6. 不变的部分

以下内容**不在本次重命名范围内**：

- 所有 HTTP API 路径（`/api/v1/...`）保持不变
- `auth.py`（schemas/routers/services）作为横切关注点保留
- `common.py`（schemas）通用分页/响应模型保留
- 基础设施服务（embedding/vector_search）保留当前命名
- 前端代码不在本次范围内

## 7. 执行顺序与验证策略

```
阶段 1: Models (1 文件)
  ↓ 验证: python -c "from app.db.init_models import *"
阶段 2: Schemas (9 文件改名 + ~55 类名 + ~15 导入更新)
  ↓ 验证: python -c "from app.schemas import *"
阶段 3: Services (9 文件改名 + ~9 类名 + ~10 导入更新)
  ↓ 验证: python -c "from app.services import *"
阶段 4: Routers (11 文件改名 + main.py 导入更新)
  ↓ 验证: uvicorn app.main:app --check
```

每个阶段完成后运行 Python 导入检查，确保无遗漏引用。

## 8. 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 遗漏导入引用 | 每阶段用 Grep 全量搜索旧名 |
| 字符串引用断裂 | 搜索 `importlib` 动态导入和字符串形式的模块路径 |
| 前端 API 调用断裂 | API 路径不变，仅 Python 模块路径变更 |
| Alembic 迁移受影响 | ORM 类名变更不影响 `__tablename__`，无需新迁移 |
| 循环依赖 | 严格按内层→外层顺序执行 |
