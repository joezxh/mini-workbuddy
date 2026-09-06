<template>
  <div class="dashboard-panel">
    <!-- 统计概览：5 项指标排一行，点击进入对应页面 -->
    <div class="stat-row">
      <div
        v-for="stat in statList"
        :key="stat.key"
        class="stat-card"
        @click="navigateTo(stat.target)"
      >
        <div class="stat-icon"><component :is="stat.icon" /></div>
        <div class="stat-body">
          <div class="stat-value">{{ formatNumber(stats[stat.key]) }}</div>
          <div class="stat-label">{{ stat.label }}</div>
        </div>
      </div>
    </div>

    <!-- 快捷操作 -->
    <div class="quick-actions">
      <h3 class="section-title">{{ t('dashboard.quickActionsTitle') }}</h3>
      <div class="actions-grid">
        <a-button
          v-for="action in quickActions"
          :key="action.key"
          :type="action.type"
          size="large"
          @click="handleAction(action.to)"
        >
          <component :is="action.icon" />
          {{ action.label }}
        </a-button>
      </div>
    </div>

    <!-- 系统审查日志 -->
    <div class="recent-activities">
      <div class="section-header">
        <h3 class="section-title">{{ t('dashboard.recentOpsTitle') }}</h3>
        <a-spin :spinning="auditLoading" size="small" />
      </div>
      <a-empty v-if="!auditLoading && auditLogs.length === 0" :description="t('dashboard.noAuditLogs')" />
      <a-timeline v-else>
        <a-timeline-item
          v-for="log in auditLogs"
          :key="log.logId"
          :color="getOperationColor(log.operationType)"
        >
          <div class="activity-item">
            <div class="activity-main">
              <span class="log-username">{{ log.username || t('dashboard.unknownUser') }}</span>
              <a-tag :color="getOperationColor(log.operationType)" class="log-op-tag">
                {{ getOperationTypeLabel(log.operationType) }}
              </a-tag>
              <a-tag color="default" class="log-module-tag" v-if="log.operationModule">
                {{ getOperationModuleLabel(log.operationModule) }}
              </a-tag>
            </div>
            <div class="activity-desc" v-if="log.operationDesc">{{ log.operationDesc }}</div>
            <div class="activity-time">{{ formatTime(log.createdAt) }}</div>
          </div>
        </a-timeline-item>
      </a-timeline>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, type Component } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  AppstoreOutlined,
  DashboardOutlined,
  RobotOutlined,
  ApartmentOutlined,
  MessageOutlined,
  ThunderboltOutlined,
  BookOutlined,
} from '@ant-design/icons-vue'
import { getRecentAuditLogs, getDashboardStats } from '@/api/admin'
import type { AuditLogItem } from '@/api/admin'
import { getDictionaryItems } from '@/api/dictionary'


// ========================
// 统计概览
// ========================
const router = useRouter()
const { t } = useI18n()

// 后端返回字段命名不固定（snake/camel 均可能），用候选键名逐个兜底解析
const stats = reactive({
  skills: 0,
  agents: 0,
  agentTeams: 0,
  sessions: 0,
  tokens: 0,
})

const statList = computed(() => [
  { key: 'skills' as const, label: t('dashboard.statSkills'), icon: AppstoreOutlined, target: 'skill-management' },
  { key: 'agents' as const, label: t('dashboard.statAgents'), icon: RobotOutlined, target: 'agent-management' },
  { key: 'agentTeams' as const, label: t('dashboard.statAgentTeams'), icon: ApartmentOutlined, target: 'agent-team' },
  { key: 'sessions' as const, label: t('dashboard.statSessions'), icon: MessageOutlined, target: 'ai-sessions' },
  { key: 'tokens' as const, label: t('dashboard.statTokens'), icon: ThunderboltOutlined, target: 'ai-sessions' },
])

function pickValue(obj: any, keys: string[]): number {
  if (!obj) return 0
  for (const k of keys) {
    const v = obj[k]
    if (v !== undefined && v !== null && v !== '') return Number(v) || 0
  }
  return 0
}

// 首位为后端 /api/v1/admin/dashboard/stats 实际返回的键名，其余为兼容其它命名风格
const NUM_KEYS: Record<string, string[]> = {
  skills: ['skills_total', 'skillCount', 'skill_count', 'installedSkillCount', 'installed_skill_count', 'skillTotal', 'skill_total'],
  agents: ['agents_total', 'agentCount', 'agent_count', 'agentTotal', 'agent_total', 'installedAgentCount', 'installed_agent_count'],
  agentTeams: ['agent_teams_total', 'agentTeamCount', 'agent_team_count', 'teamCount', 'team_count', 'agentTeamTotal'],
  sessions: ['sessions_total', 'sessionCount', 'session_count', 'conversationCount', 'conversation_count', 'sessionTotal', 'conversationTotal'],
  tokens: ['token_total', 'tokenUsage', 'token_usage', 'consumedTokens', 'consumed_tokens', 'totalTokens', 'total_tokens', 'tokenConsumed', 'token_count', 'tokenTotal'],
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'k'
  return String(n)
}

function navigateTo(target: string) {
  router.push({ path: '/admin', query: { tab: target } })
}

const statsLoading = ref(false)
const fetchStats = async () => {
  statsLoading.value = true
  try {
    const res = await getDashboardStats()
    const data: any = (res as any)?.data ?? res
    const d: any = data?.data ?? data
    for (const key of Object.keys(NUM_KEYS)) {
      stats[key as keyof typeof stats] = pickValue(d, NUM_KEYS[key])
    }
  } catch (_) {
    // 统计接口失败不影响审计日志等主功能
  } finally {
    statsLoading.value = false
  }
}


// ========================
// 快捷操作
// ========================
const quickActions = computed(() => [
  { key: 'ai-chat', label: t('dashboard.actionAiChat'), icon: RobotOutlined, to: '/admin?tab=ai-chat', type: 'primary' as const },
  { key: 'wiki', label: t('dashboard.actionWiki'), icon: BookOutlined, to: '/wiki', type: 'default' as const },
  { key: 'agent-management', label: t('dashboard.actionAgentMgmt'), icon: ApartmentOutlined, to: '/admin?tab=agent-management', type: 'default' as const },
])

function handleAction(to: string) {
  router.push(to)
}


// ========================
// 审计日志
// ========================
const auditLogs = ref<AuditLogItem[]>([])
const auditLoading = ref(false)

// 操作类型字典（亮色映射）
const operationTypeMap = ref<Record<string, { label: string; color: string }>>({
  create: { label: t('dashboard.opCreate'), color: 'green' },
  update: { label: t('dashboard.opUpdate'), color: 'blue' },
  delete: { label: t('dashboard.opDelete'), color: 'red' },
  query: { label: t('dashboard.opQuery'), color: 'default' },
  login: { label: t('dashboard.opLogin'), color: 'cyan' },
  logout: { label: t('dashboard.opLogout'), color: 'orange' },
})

// 操作模块字典
const operationModuleMap = ref<Record<string, string>>({
  user: t('dashboard.modUser'),
  role: t('dashboard.modRole'),
  permission: t('dashboard.modPermission'),
  dictionary: t('dashboard.modDictionary'),
  system: t('dashboard.modSystem'),
  auth: t('dashboard.modAuth'),
  ai_session: t('dashboard.modAiSession'),
  agent: t('dashboard.modAgent'),
  wiki: t('dashboard.modWiki'),
})

// 从字典接口加载操作类型和模块映射
const loadDictMappings = async () => {
  try {
    const [typeItems, moduleItems] = await Promise.all([
      getDictionaryItems('audit_operation_type').catch(() => []),
      getDictionaryItems('audit_operation_module').catch(() => [])
    ])
    if (typeItems && typeItems.length > 0) {
      typeItems.forEach((item: any) => {
        const colorMap: Record<string, string> = {
          create: 'green', update: 'blue', delete: 'red',
          query: 'default', login: 'cyan', logout: 'orange'
        }
        operationTypeMap.value[item.item_code] = {
          label: item.item_name,
          color: item.color || colorMap[item.item_code] || 'default'
        }
      })
    }
    if (moduleItems && moduleItems.length > 0) {
      moduleItems.forEach((item: any) => {
        operationModuleMap.value[item.item_code] = item.item_name
      })
    }
  } catch (_) {
    // 字典加载失败不影响主功能，使用默认映射
  }
}

const getOperationTypeLabel = (type: string): string => {
  return operationTypeMap.value[type]?.label ?? type
}

const getOperationColor = (type: string): string => {
  return operationTypeMap.value[type]?.color ?? 'default'
}

const getOperationModuleLabel = (module: string | null): string => {
  if (!module) return ''
  return operationModuleMap.value[module] ?? module
}

// 时间格式化
const formatTime = (isoStr: string | null): string => {
  if (!isoStr) return ''
  const date = new Date(isoStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return t('dashboard.timeJustNow')
  if (minutes < 60) return t('dashboard.timeMinutesAgo', { n: minutes })
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return t('dashboard.timeHoursAgo', { n: hours })
  const days = Math.floor(hours / 24)
  if (days < 7) return t('dashboard.timeDaysAgo', { n: days })
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const fetchAuditLogs = async () => {
  auditLoading.value = true
  try {
    const res = await getRecentAuditLogs(10)
    if (res.code === 0 && Array.isArray(res.data)) {
      auditLogs.value = res.data
    }
  } catch (error) {
    message.error(t('dashboard.fetchAuditFail'))
  } finally {
    auditLoading.value = false
  }
}

onMounted(() => {
  loadDictMappings()
  fetchAuditLogs()
  fetchStats()
})
</script>

<style lang="less" scoped>
.dashboard-panel {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  padding: 20px;
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
  flex-shrink: 0;
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

.dashboard-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px;
}

.panel-header {
  margin-bottom: 24px;
}

.panel-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--fg);
  margin: 0 0 8px 0;
}

.panel-subtitle {
  font-size: 14px;
  color: var(--fg-secondary);
}

/* 统计概览：5 项排一行 */
.stat-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: all var(--transition);

  &:hover {
    border-color: var(--accent);
    box-shadow: var(--shadow);
    transform: translateY(-2px);
  }
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 22px;
  flex-shrink: 0;
}

.stat-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--fg);
  font-family: var(--font-tech);
}

.stat-label {
  font-size: 13px;
  color: var(--fg-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 快捷操作 */
.quick-actions {
  margin-bottom: 24px;
}

.actions-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.actions-grid :deep(.ant-btn) {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.recent-activities {
  background: var(--bg-surface);
  backdrop-filter: blur(2px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  box-shadow: var(--shadow);
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--fg);
  margin: 0 0 16px 0;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;

  .section-title {
    margin: 0;
  }
}

.activity-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-bottom: 4px;
}

.activity-main {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.log-username {
  font-size: 14px;
  font-weight: 600;
  color: var(--fg);
}

.log-op-tag {
  font-size: 12px;
  line-height: 1.4;
}

.log-module-tag {
  font-size: 12px;
  line-height: 1.4;
}

.activity-desc {
  font-size: 13px;
  color: var(--fg-secondary);
  line-height: 1.5;
  word-break: break-all;
}

.activity-time {
  font-size: 12px;
  color: var(--fg-muted);
}

@media (max-width: 1100px) {
  .stat-row {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 560px) {
  .stat-row {
    grid-template-columns: 1fr;
  }
}
</style>
