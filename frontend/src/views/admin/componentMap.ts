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
// 知识治理（数据源 / 知识库 / 外部知识库 / 本体）
import DataSourcePanel from '@/views/data-source/DataSourcePanel.vue'
import DataAssetPanel from '@/views/data-source/DataAssetPanel.vue'
import OntologyWorkspace from '@/views/data-source/ontology/OntologyWorkspace.vue'
// 推演沙盘（沙箱域 S1–S21）：sys_menu 2408 (/admin/simulation)，与真实路由 /admin/simulation 共用同一组件
import SimulationSandbox from '@/views/sandbox/SimulationSandbox.vue'
// 孪生应用（Plan 2）：sys_menu 2407 (/admin/digital-twin)，与真实路由 /admin/digital-twin 共用同一组件
import TwinWorkspace from '@/views/twin/TwinWorkspace.vue'
import KnowledgeBasePanel from '@/views/kms/KnowledgeBasePanel.vue'
import ExternalKbPanel from '@/views/kms/ExternalKbPanel.vue'
// wiki 知识库（以控制台 Tab 方式展示）
import WikiIndex from '@/views/kms/wiki/index.vue'
// 统一知识库工作台（spec 知识库统一化 §6）
import KnowledgeBaseManager from '@/views/kms/KnowledgeBaseManager.vue'
// 调解语音 RTC（迁移自 risk_control）
import VoiceDemo from '@/views/duplex/VoiceDemo.vue'
import VoiceSessionConfig from '@/views/admin/duplex/config/VoiceSessionConfig.vue'
import VoiceModelConfig from '@/views/admin/duplex/config/VoiceModelConfig.vue'
import AgentConfigPanel from '@/views/admin/ai-config/agents/AgentConfigPanel.vue'
import ToolPolicyEditor from '@/views/admin/ai/components/ToolPolicyEditor.vue'
// Wiki 文章查看 / 编辑 / RAG 测试：带动态参数（slug / id），由外壳 Tab 系统按需打开
import WikiArticleView from '@/views/kms/wiki/ArticleView.vue'
import WikiArticleEdit from '@/views/kms/wiki/ArticleEdit.vue'
import WikiRagTest from '@/views/kms/wiki/RagTest.vue'

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
  // 知识治理（menuKey 与 sys_menu.path 末段一致）
  'kg-data-source': markRaw(DataSourcePanel),
  // 数据资产目录（AF-01~AF-08）：sys_menu 2406 (/admin/data-asset)，与真实路由 /admin/data-asset 共用同一组件
  'data-asset': markRaw(DataAssetPanel),
  // 本体工作台：sys_menu 2405 (/admin/kg-ontology)。与 DataSourcePanel 的「本体工作台」页签共用同一组件，
  // 菜单直达时以独立 Tab 全量渲染（OntologyWorkspace 自带选择器与内部页签，不依赖外层壳）。
  'kg-ontology': markRaw(OntologyWorkspace),
  // 推演沙盘：忠实移植 ontology-simulation-sandbox-preview.html 原型，接沙箱域真实 API
  'simulation': markRaw(SimulationSandbox),
  'kg-kb': markRaw(KnowledgeBasePanel),
  'kg-external-kb': markRaw(ExternalKbPanel),
  'kg-private-kb': markRaw(WikiIndex),
  'kg-knowledge-manager': markRaw(KnowledgeBaseManager),
  // 调解语音 RTC（迁移自 risk_control）
  'voice-demo': markRaw(VoiceDemo),
  'voice-roles': markRaw(VoiceSessionConfig),
  'voice-models': markRaw(VoiceModelConfig),
  'voice-agents': markRaw(AgentConfigPanel),
  'voice-tool-policy': markRaw(ToolPolicyEditor),
  // 孪生应用：sys_menu 2407 (/admin/digital-twin)，path 末段 = menuKey = i18n_key 末段
  'digital-twin': markRaw(TwinWorkspace),
}

/**
 * 动态 Tab 注册表：key 为「组件注册名」，value 为组件。
 * 与 componentMap 不同，这里登记的是需要携带动态参数（slug / id）打开的页面，
 * 由 admin/index.vue 的 open-dynamic-tab 事件按需查表后打开成外壳 Tab。
 */
export const dynamicComponentRegistry: Record<string, Component> = {
  'kg-wiki-view': markRaw(WikiArticleView),
  'kg-wiki-edit': markRaw(WikiArticleEdit),
  'kg-wiki-rag': markRaw(WikiRagTest),
}
