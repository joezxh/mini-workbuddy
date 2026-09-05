<template>
  <div class="admin-page">
    <!-- 内容区：仅保留 Tab 方式展示页面；菜单导航统一由左侧全局 rail（AppSidebar）承担，避免重复 -->
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
import DashboardPanel from '@/views/Dashboard.vue' // 默认门户占位（登录后首页，合并自原 dashboard/index + DashboardPanel）
import { componentMap } from './componentMap'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

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

// 组件映射表已抽到 ./componentMap，供本控制台的 Tab 使用
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

/**
 * 从后端获取菜单树（仅用于解析 Tab 的名称/图标；导航菜单由全局 rail 承担）
 */
async function fetchMenus() {
  try {
    const res = await getUserMenus()
    menuTree.value = (res.data?.data || res.data || []) as MenuItem[]
  } catch (e) {
    console.error('获取菜单失败', e)
  }
}

onMounted(async () => {
  await fetchMenus()
  // 根据 URL 参数（来自左侧 rail 的点击）打开初始 Tab
  const tab = route.query.tab as string
  if (tab && componentMap[tab]) {
    openOrActivateTab(tab)
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

// 监听 URL 参数（来自左侧 rail 的点击）：打开/激活对应 Tab
watch(() => route.query.tab, (newTab) => {
  const tab = newTab as string
  if (tab && componentMap[tab]) {
    openOrActivateTab(tab)
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

.admin-content {
  flex: 1;
  overflow: hidden;
  padding: 20px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.tab-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: 0;
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
  background: var(--bg-surface);
  cursor: pointer;
  font-size: 13px;
  color: var(--fg-secondary);
  transition: all 0.2s;
  user-select: none;
  max-width: 180px;

  &:hover {
    background: var(--bg-hover);
    color: var(--accent-cyan);
  }

  &.active {
    background: var(--bg-active);
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
  color: var(--fg-muted);
  transition: all 0.15s;

  &:hover {
    background: var(--err-soft);
    color: var(--err);
  }
}

.tab-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
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

</style>