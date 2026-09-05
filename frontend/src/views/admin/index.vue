<template>
  <div class="admin-page">
    <!-- 左侧菜单 -->
    <div class="admin-sidebar">
      <div class="sidebar-header">
        <SettingOutlined style="font-size: 20px; color: var(--accent-cyan)" />
        <span class="sidebar-title">管理控制台</span>
      </div>
      <a-menu
        v-model:selectedKeys="selectedKeys"
        v-model:openKeys="openKeys"
        mode="inline"
        :style="{ border: 'none', background: 'transparent' }"
      >
        <a-sub-menu v-for="group in menuTree" :key="group.menuKey">
          <template #icon><component v-if="iconMap[group.icon]" :is="iconMap[group.icon]" /></template>
          <template #title>{{ resolveMenuLabel(group) }}</template>
          <template v-for="item in group.children" :key="item.menuKey">
            <!-- 三级菜单：有子项的渲染为 sub-menu -->
            <a-sub-menu v-if="item.children && item.children.length > 0" :key="item.menuKey">
              <template #icon><component v-if="iconMap[item.icon]" :is="iconMap[item.icon]" /></template>
              <template #title>{{ resolveMenuLabel(item) }}</template>
              <a-menu-item
                v-for="subItem in item.children"
                :key="subItem.menuKey"
              >
                <component v-if="iconMap[subItem.icon]" :is="iconMap[subItem.icon]" />
                <span>{{ resolveMenuLabel(subItem) }}</span>
              </a-menu-item>
            </a-sub-menu>
            <!-- 二级菜单：叶子节点渲染为 menu-item -->
            <a-menu-item v-else :key="item.menuKey">
              <component v-if="iconMap[item.icon]" :is="iconMap[item.icon]" />
              <span>{{ resolveMenuLabel(item) }}</span>
            </a-menu-item>
          </template>
        </a-sub-menu>
      </a-menu>
    </div>

    <!-- 右侧内容区 -->
    <div class="admin-content">
      <!-- Tab 页签栏 -->
      <div class="tab-bar" v-if="openTabs.length > 0">
        <div
          v-for="tab in openTabs"
          :key="tab.key"
          class="tab-item"
          :class="{ active: activeTab === tab.key }"
          @click="activateTab(tab.key)"
        >
          <component v-if="tab.icon && iconMap[tab.icon]" :is="iconMap[tab.icon]" class="tab-icon" />
          <span class="tab-title">{{ tab.name }}</span>
          <span
            class="tab-close"
            @click.stop="closeTab(tab.key)"
            title="关闭"
          >&times;</span>
        </div>
      </div>

      <!-- Tab 内容区域 -->
      <div class="tab-content" v-if="openTabs.length > 0">
        <div v-for="tab in openTabs" :key="tab.key" v-show="activeTab === tab.key" class="content-section">
            <component :is="getTabComponent(tab.key)" v-bind="getTabProps(tab.key)" />
        </div>
      </div>

      <!-- 无 Tab 时默认展示控制台门户 -->
      <div v-if="openTabs.length === 0" class="content-section">
        <DashboardPanel />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, markRaw, reactive, provide, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getUserMenus } from '@/api/auth'
import {
  SettingOutlined,
  DashboardOutlined,
  UserOutlined,
  DatabaseOutlined,
  RobotOutlined,
  ApiOutlined,
  ClockCircleOutlined,
  GlobalOutlined,
  ThunderboltOutlined,
  PlayCircleOutlined,
  BarChartOutlined,
  CloudUploadOutlined,
  ApartmentOutlined,
  OrderedListOutlined,
  AlertOutlined,
  BankOutlined,
  EnvironmentOutlined,
  CloudServerOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  MessageOutlined,
  BulbOutlined,
  CommentOutlined,
  TagsOutlined,
  SafetyCertificateOutlined,
  MergeCellsOutlined,
  ReadOutlined,
  ToolOutlined,
  LinkOutlined,
  BookOutlined,
  WarningOutlined,
  MonitorOutlined,
  NodeIndexOutlined,
  KeyOutlined,
  AppstoreOutlined,
  SearchOutlined,
  CloudSyncOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons-vue'
import DashboardPanel from '@/views/admin/system/DashboardPanel.vue'
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

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const selectedKeys = ref(['dashboard'])
const openKeys = ref<string[]>([])

// ---- Tab 管理 ----
interface TabItem {
  key: string
  name: string
  icon: string
  component: Component
  props?: Record<string, any>
}
const openTabs = ref<TabItem[]>([])
const activeTab = ref('')

// menuKey -> 组件映射表
const componentMap: Record<string, Component> = {
  'dashboard': markRaw(DashboardPanel),
  'ai-chat': markRaw(AssistantPanel),
  'ai-sessions': markRaw(AiSessionPanel),
  'async-task-manage': markRaw(AsyncTaskManage),
  'system-management': markRaw(SystemManagement),
  'profile': markRaw(ProfilePanel),
  'dictionary': markRaw(DictionaryPanel),
  'region': markRaw(RegionPanel),
  'skill-management': markRaw(SkillManagement),
  'session-agent': markRaw(AgentExecutionManagement),
  'agent-management': markRaw(AgentManagement),
  'apikey': markRaw(ApiKeyManagement),
  'web-search': markRaw(WebSearchManagement),
  'tool-management': markRaw(ToolManagement),
  'mcp-service': markRaw(McpServiceManagement),
  'agent-team': markRaw(TeamList),
  'agent-team-editor': markRaw(TeamEditor),
  'tenant-management': markRaw(TenantPanel),
  'tenant-package-management': markRaw(TenantPackagePanel),
}



function getTabComponent(key: string): Component | undefined {
  return componentMap[key]
}

// 需要传递特殊 props 的组件
const tabPropsMap: Record<string, Record<string, any>> = {}

function getTabProps(key: string): Record<string, any> {
  const tab = openTabs.value.find(t => t.key === key)
  return tab?.props || tabPropsMap[key] || {}
}

/** 查找菜单项信息（名称、图标）- 支持三级嵌套 */
/** 多语言菜单标签解析：优先 i18nKey 翻译，回退到 name 字段 */
function resolveMenuLabel(menu: MenuItem): string {
  if (menu.i18nKey) {
    const translated = t(menu.i18nKey)
    if (translated !== menu.i18nKey) return translated
  }
  return menu.name
}
function findMenuItem(key: string): MenuItem | undefined {
  for (const group of menuTree.value) {
    if (group.children) {
      for (const item of group.children) {
        // 检查三级子菜单
        if (item.children) {
          const foundInSub = item.children.find(c => c.menuKey === key)
          if (foundInSub) return foundInSub
        }
        // 检查二级菜单
        if (item.menuKey === key) return item
      }
    }
  }
  return undefined
}

/** 打开或激活一个 Tab */
function openOrActivateTab(key: string, options?: { name?: string; icon?: string; props?: Record<string, any> }) {
  const existing = openTabs.value.find(t => t.key === key)
  if (existing) {
    if (options?.props) existing.props = { ...(existing.props || {}), ...options.props }
    activeTab.value = key
    return
  }
  const menuItem = findMenuItem(key)
  const name = options?.name || (menuItem ? resolveMenuLabel(menuItem) : '') || key
  const icon = options?.icon || menuItem?.icon || ''
  const comp = componentMap[key]
  if (!comp) return
  openTabs.value.push({ key, name, icon, component: markRaw(comp), props: options?.props })
  activeTab.value = key
}

/** 激活指定 Tab */
function activateTab(key: string) {
  activeTab.value = key
  selectedKeys.value = [key]
}

// 提供给子组件的调用链路过滤器（来自 AgentManagement「链路」按钮跳转）
const executionFilter = reactive<{ mode?: string; targetId?: string; label?: string }>({})

// 供子组件跳转到「调用记录」Tab 并携带过滤条件
provide('openExecutionTab', (mode?: string, targetId?: string, label?: string) => {
  executionFilter.mode = mode
  executionFilter.targetId = targetId
  executionFilter.label = label
  openOrActivateTab('session-agent')
})
provide('executionFilter', executionFilter)

/** 关闭指定 Tab */
function closeTab(key: string) {
  const idx = openTabs.value.findIndex(t => t.key === key)
  if (idx === -1) return
  openTabs.value.splice(idx, 1)
  // 如果关闭的是当前激活的 Tab，激活相邻 Tab
  if (activeTab.value === key) {
    if (openTabs.value.length === 0) {
      activeTab.value = ''
    } else {
      const newIdx = Math.min(idx, openTabs.value.length - 1)
      activeTab.value = openTabs.value[newIdx].key
      selectedKeys.value = [activeTab.value]
    }
  }
}

// 菜单树数据（从后端接口获取）
interface MenuItem {
  id: number
  name: string
  menuKey: string
  permission: string
  permissionCode: string
  type: number
  parentId: number | null
  icon: string
  component: string
  sortOrder: number
  i18nKey?: string
  children?: MenuItem[]
}
const menuTree = ref<MenuItem[]>([])

// 图标字符串到组件的映射表
// 同时支持 Ant Design 组件名（如 'SettingOutlined'）和数据库短名称（如 'setting'）
const iconMap: Record<string, any> = {
  // Ant Design 组件名
  DashboardOutlined,
  SettingOutlined,
  UserOutlined,
  DatabaseOutlined,
  RobotOutlined,
  ApiOutlined,
  ClockCircleOutlined,
  GlobalOutlined,
  ThunderboltOutlined,
  PlayCircleOutlined,
  BarChartOutlined,
  CloudUploadOutlined,
  ApartmentOutlined,
  OrderedListOutlined,
  AlertOutlined,
  BankOutlined,
  EnvironmentOutlined,
  CloudServerOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  MessageOutlined,
  BulbOutlined,
  CommentOutlined,
  TagsOutlined,
  SafetyCertificateOutlined,
  MergeCellsOutlined,
  ReadOutlined,
  ToolOutlined,
  LinkOutlined,
  BookOutlined,
  WarningOutlined,
  MonitorOutlined,
  NodeIndexOutlined,
  KeyOutlined,
  SearchOutlined,
  CloudSyncOutlined,
  // 数据库短名称 → Ant Design 组件
  setting: SettingOutlined,
  user: UserOutlined,
  peoples: UserOutlined,
  'tree-table': ApartmentOutlined,
  dict: BookOutlined,
  warning: WarningOutlined,
  list: OrderedListOutlined,
  'office-building': BankOutlined,
  location: EnvironmentOutlined,
  'chat-dot-round': MessageOutlined,
  'chat-line-round': CommentOutlined,
  document: FileTextOutlined,
  'data-analysis': BarChartOutlined,
  monitor: MonitorOutlined,
  connection: NodeIndexOutlined,
  robot: RobotOutlined,
  key: KeyOutlined,
  tool: ToolOutlined,
  api: ApiOutlined,
  dashboard: DashboardOutlined,
  appstore: AppstoreOutlined,
  question: QuestionCircleOutlined,
  QuestionCircleOutlined: QuestionCircleOutlined,
}

// 每个 tab 需要展开的父级菜单链（用于自动展开侧边栏）
const tabOpenChainMap = ref<Record<string, string[]>>({})

/**
 * 从后端获取菜单树并构建 tabGroupMap
 */
async function fetchMenus() {
  try {
    const res = await getUserMenus()
    const data = res.data?.data || res.data || []
    menuTree.value = data
    // 构建 tabOpenChainMap: menuKey -> 需要展开的父级菜单链（支持三级嵌套）
    const map: Record<string, string[]> = {}
    for (const group of data) {
      if (group.children) {
        for (const child of group.children) {
          // 二级菜单项：需要展开 [group.menuKey]
          map[child.menuKey] = [group.menuKey]
          // 如果有三级子菜单
          if (child.children) {
            for (const subChild of child.children) {
              // 三级菜单项：需要展开 [group.menuKey, child.menuKey]
              map[subChild.menuKey] = [group.menuKey, child.menuKey]
            }
          }
        }
      }
    }
    tabOpenChainMap.value = map
    // 设置默认展开第一个菜单组
    if (data.length > 0 && openKeys.value.length === 0) {
      openKeys.value = [data[0].menuKey]
    }
  } catch (e) {
    console.error('获取菜单失败', e)
  }
}

onMounted(async () => {
  await fetchMenus()
  // 根据URL参数设置初始tab
  const tab = route.query.tab as string
  const validTabs = Object.keys(tabOpenChainMap.value)
  if (tab && validTabs.includes(tab)) {
    selectedKeys.value = [tab]
    openOrActivateTab(tab)
    const openChain = tabOpenChainMap.value[tab]
    if (openChain) {
      // 展开所有父级菜单
      for (const key of openChain) {
        if (!openKeys.value.includes(key)) {
          openKeys.value.push(key)
        }
      }
    }
  }

  // 监听来自子组件的“打开技能管理”事件（如推理规则页点击 skill_code）
  window.addEventListener('open-skill-tab', handleOpenSkillTab)
  // 监听来自子组件的“打开团队编排”事件
  window.addEventListener('open-agent-team-editor', handleOpenAgentTeamEditor)
  window.addEventListener('close-agent-team-editor', handleCloseAgentTeamEditor)
  window.addEventListener('open-async-task-manage', handleOpenAsyncTaskManage)
})

/** 处理 open-skill-tab 事件：在标签页系统中打开技能管理并定位到指定技能包 */
function handleOpenSkillTab(e: Event) {
  const detail = (e as CustomEvent).detail as { packageId: string }
  if (!detail?.packageId) return
  // 更新路由 query，SkillManagement 会监听此变化自动选中
  router.replace({ query: { ...route.query, package_id: detail.packageId } })
  // 打开或激活技能管理标签页
  openOrActivateTab('skill-management')
  // 展开父菜单
  const openChain = tabOpenChainMap.value['skill-management']
  if (openChain) {
    for (const key of openChain) {
      if (!openKeys.value.includes(key)) {
        openKeys.value.push(key)
      }
    }
  }
}

function handleOpenAgentTeamEditor(e: Event) {
  const detail = (e as CustomEvent).detail as { teamId: number }
  if (!detail?.teamId) return
  openOrActivateTab('agent-team-editor', {
    name: '团队编排',
    icon: 'ApartmentOutlined',
    props: { teamId: detail.teamId }
  })
}

function handleCloseAgentTeamEditor() {
  closeTab('agent-team-editor')
  if (openTabs.value.some(t => t.key === 'agent-team')) {
    activateTab('agent-team')
  }
}

// 打开「我的异步任务」管理界面（来自 AI 助理页按钮）
function handleOpenAsyncTaskManage() {
  openOrActivateTab('async-task-manage', { name: '我的异步任务' })
}

onUnmounted(() => {
  window.removeEventListener('open-skill-tab', handleOpenSkillTab)
  window.removeEventListener('open-agent-team-editor', handleOpenAgentTeamEditor)
  window.removeEventListener('close-agent-team-editor', handleCloseAgentTeamEditor)
  window.removeEventListener('open-async-task-manage', handleOpenAsyncTaskManage)
})

// 监听菜单选择：打开/激活对应 Tab，并展开父级菜单
watch(selectedKeys, (keys) => {
  const key = keys[0]
  if (!key) return
  openOrActivateTab(key)
  // 自动展开该菜单项的所有父级菜单
  const openChain = tabOpenChainMap.value[key]
  if (openChain) {
    for (const parentKey of openChain) {
      if (!openKeys.value.includes(parentKey)) {
        openKeys.value.push(parentKey)
      }
    }
  }
})

watch(() => route.query.tab, (newTab) => {
  const tab = newTab as string
  const validTabs = Object.keys(tabOpenChainMap.value)
  if (tab && validTabs.includes(tab)) {
    selectedKeys.value = [tab]
    openOrActivateTab(tab)
    const openChain = tabOpenChainMap.value[tab]
    if (openChain) {
      // 展开所有父级菜单
      for (const key of openChain) {
        if (!openKeys.value.includes(key)) {
          openKeys.value.push(key)
        }
      }
    }
  }
})
</script>

<style lang="less" scoped>
.admin-page {
  width: 100%;
  height: 100%;
  display: flex;
  overflow: hidden;
  background: transparent;
}

.admin-sidebar {
  width: 240px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(2px);
  border: 1px solid var(--border-glow);
  border-radius: 4px;
  margin: 20px 0 20px 20px;
  padding: 20px 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  position: relative;
  overflow-y: auto;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: var(--accent-cyan);
    opacity: 0.9;
  }
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 20px 20px;
  border-bottom: 1px solid var(--border-glow);
  margin-bottom: 10px;
}

.sidebar-title {
  font-size: 16px;
  font-weight: 700;
  color: #1a1a1a;
}

.admin-content {
  flex: 1;
  overflow: hidden;
  padding: 20px 20px 20px 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.tab-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 0 0 8px 20px;
  border-bottom: 1px solid var(--border-glow);
  margin-bottom: 12px;
  min-height: 36px;
  align-items: center;
}

.tab-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 6px 6px 0 0;
  border: 1px solid var(--border-glow);
  border-bottom: none;
  background: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  font-size: 13px;
  color: #555;
  transition: all 0.2s;
  user-select: none;
  max-width: 180px;

  &:hover {
    background: rgba(24, 144, 255, 0.06);
    color: var(--accent-cyan);
  }

  &.active {
    background: rgba(24, 144, 255, 0.1);
    color: var(--accent-cyan);
    border-color: var(--accent-cyan);
    font-weight: 600;
  }
}

.tab-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.tab-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tab-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  font-size: 14px;
  line-height: 1;
  flex-shrink: 0;
  color: #999;
  transition: all 0.15s;

  &:hover {
    background: rgba(255, 77, 79, 0.15);
    color: #ff4d4f;
  }
}

.tab-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  margin-left: 20px;
}

.tab-content > .content-section {
  height: 100%;
  overflow: auto;
}

.content-section {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

:deep(.ant-menu-item) {
  color: #2d2d2d;
  margin: 4px 8px;
  border-radius: 4px;

  &:hover {
    background: rgba(24, 144, 255, 0.08);
    color: var(--accent-cyan);
  }

  &.ant-menu-item-selected {
    background: rgba(24, 144, 255, 0.12);
    color: var(--accent-cyan);
  }
}

:deep(.ant-menu-item-icon) {
  font-size: 16px;
}
</style>