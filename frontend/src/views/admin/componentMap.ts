// menuKey -> 组件映射表（单一事实来源）。
// 供 admin/index.vue 控制台以 Tab 形式渲染各页面组件时查表使用，避免重复维护。
// menuKey = 菜单 path 的末段，必须与后端 sys_menu 一致。
import type { Component } from 'vue'
import { markRaw } from 'vue'
import DashboardPanel from '@/views/Dashboard.vue'
import SystemManagement from '@/views/admin/system/SystemManagement.vue'
import AiSessionPanel from '@/views/assistant/AiSessionPanel.vue'
import ProfilePanel from '@/views/admin/system/ProfilePanel.vue'
import DictionaryPanel from '@/views/admin/system/DictionaryPanel.vue'
import RegionPanel from '@/views/admin/system/RegionPanel.vue'
import AgentManagement from '@/views/admin/agent/AgentManagement.vue'
import ApiKeyManagement from '@/views/admin/ai/apikey/ApiKeyManagement.vue'
import WebSearchManagement from '@/views/admin/ai/websearch/WebSearchManagement.vue'
import ToolManagement from '@/views/admin/ai/tool/ToolManagement.vue'
import McpServiceManagement from '@/views/admin/ai/mcp/McpServiceManagement.vue'
import AgentExecutionManagement from '@/views/admin/agent/AgentExecutionManagement.vue'
import SkillManagement from '@/views/admin/ai/skill/SkillManagement.vue'
import AssistantPanel from '@/views/assistant/components/AssistantPanel.vue'
import AsyncTaskManage from '@/views/assistant/AsyncTaskManage.vue'
import TenantPanel from '@/views/admin/system/TenantPanel.vue'
import TenantPackagePanel from '@/views/admin/system/TenantPackagePanel.vue'
import TeamList from '@/views/admin/agent-team/TeamList.vue'
import TeamEditor from '@/views/admin/agent-team/TeamEditor.vue'
import WorkflowManagement from '@/views/admin/workflow/WorkflowManagement.vue'

export const componentMap: Record<string, Component> = {
  dashboard: markRaw(DashboardPanel),
  'ai-chat': markRaw(AssistantPanel),
  'ai-sessions': markRaw(AiSessionPanel),
  'async-task-manage': markRaw(AsyncTaskManage),
  'system-management': markRaw(SystemManagement),
  profile: markRaw(ProfilePanel),
  dictionary: markRaw(DictionaryPanel),
  region: markRaw(RegionPanel),
  'skill-management': markRaw(SkillManagement),
  'session-agent': markRaw(AgentExecutionManagement),
  'agent-management': markRaw(AgentManagement),
  apikey: markRaw(ApiKeyManagement),
  'web-search': markRaw(WebSearchManagement),
  'tool-management': markRaw(ToolManagement),
  'mcp-service': markRaw(McpServiceManagement),
  'agent-team': markRaw(TeamList),
  'agent-team-editor': markRaw(TeamEditor),
  'tenant-management': markRaw(TenantPanel),
  'tenant-package-management': markRaw(TenantPackagePanel),
  'workflow-management': markRaw(WorkflowManagement),
}
