<template>
  <div class="dashboard-page">
    <div class="page-header">
      <h1 class="page-title">{{ t('userMenu.dashboard') }}</h1>
      <p class="page-subtitle">系统概览与快捷操作</p>
    </div>

    <!-- 快捷操作 -->
    <div class="quick-actions">
      <h3 class="section-title">快捷操作</h3>
      <div class="actions-grid">
        <a-button
          v-for="action in quickActions"
          :key="action.key"
          :type="action.type"
          size="large"
          @click="handleAction(action.key)"
        >
          <component :is="action.icon" />
          {{ action.label }}
        </a-button>
      </div>
    </div>

    <!-- 最近操作 -->
    <div class="recent-activities">
      <div class="section-header">
        <h3 class="section-title">最近操作</h3>
        <a-spin :spinning="auditLoading" size="small" />
      </div>
      <a-empty v-if="!auditLoading && auditLogs.length === 0" description="暂无操作日志" />
      <a-timeline v-else>
        <a-timeline-item
          v-for="log in auditLogs"
          :key="log.logId"
          :color="getOperationColor(log.operationType)"
        >
          <div class="activity-item">
            <div class="activity-main">
              <span class="log-username">{{ log.username || '未知用户' }}</span>
              <a-tag :color="getOperationColor(log.operationType)">
                {{ getOperationTypeLabel(log.operationType) }}
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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  ApartmentOutlined,
  BookOutlined,
  RobotOutlined,
} from '@ant-design/icons-vue'
import { getRecentAuditLogs } from '@/api/admin'
import type { AuditLogItem } from '@/api/admin'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

const { t } = useI18n()
const router = useRouter()

// 快捷操作
const quickActions = [
  { key: 'ai-chat', label: 'AI 助手', icon: RobotOutlined, type: 'primary' as const },
  { key: 'wiki', label: '知识库', icon: BookOutlined, type: 'default' as const },
  { key: 'agent-management', label: '专家管理', icon: ApartmentOutlined, type: 'default' as const },
]

const handleAction = (key: string) => {
  router.push(`/admin?tab=${key}`)
}

// 审计日志
const auditLogs = ref<AuditLogItem[]>([])
const auditLoading = ref(false)

const fetchAuditLogs = async () => {
  auditLoading.value = true
  try {
    const res = await getRecentAuditLogs(10)
    if (res.code === 0 && Array.isArray(res.data)) {
      auditLogs.value = res.data
    }
  } catch {
    // 静默处理
  } finally {
    auditLoading.value = false
  }
}

const getOperationColor = (type: string) => {
  const map: Record<string, string> = {
    create: 'green', update: 'blue', delete: 'red',
    login: 'cyan', logout: 'default', export: 'purple',
  }
  return map[type] || 'default'
}

const getOperationTypeLabel = (type: string) => {
  const map: Record<string, string> = {
    create: '创建', update: '更新', delete: '删除',
    login: '登录', logout: '登出', export: '导出',
  }
  return map[type] || type
}

const formatTime = (ts: string | null) => {
  if (!ts) return ''
  return dayjs(ts).fromNow()
}

onMounted(() => {
  fetchAuditLogs()
})
</script>

<style scoped>
.dashboard-page {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
  margin: 0 0 4px;
}

.page-subtitle {
  font-size: 14px;
  color: var(--text-secondary, #666);
  margin: 0;
}

.quick-actions {
  margin-bottom: 32px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
  margin: 0 0 16px;
}

.actions-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.actions-grid .ant-btn {
  display: flex;
  align-items: center;
  gap: 8px;
}

.recent-activities {
  background: var(--bg-card, #fff);
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.activity-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.activity-main {
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-username {
  font-weight: 500;
  color: var(--text-primary, #1a1a1a);
  font-size: 13px;
}

.activity-desc {
  font-size: 13px;
  color: var(--text-secondary, #666);
  padding-left: 4px;
}

.activity-time {
  font-size: 12px;
  color: var(--text-tertiary, #999);
}
</style>
