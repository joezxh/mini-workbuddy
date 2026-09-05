<template>
  <div class="dashboard-panel">
    <div class="panel-header">
      <h2 class="panel-title">控制台</h2>
      <span class="panel-subtitle">系统概览与操作日志</span>
    </div>

    <!-- 系统审查日志 -->
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
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { getRecentAuditLogs } from '@/api/admin'
import type { AuditLogItem } from '@/api/admin'
import { getDictionaryItems } from '@/api/dictionary'


// ========================
// 审计日志
// ========================
const auditLogs = ref<AuditLogItem[]>([])
const auditLoading = ref(false)

// 操作类型字典（亮色映射）
const operationTypeMap = ref<Record<string, { label: string; color: string }>>({
  create: { label: '创建', color: 'green' },
  update: { label: '更新', color: 'blue' },
  delete: { label: '删除', color: 'red' },
  query: { label: '查询', color: 'default' },
  login: { label: '登录', color: 'cyan' },
  logout: { label: '登出', color: 'orange' },
})

// 操作模块字典
const operationModuleMap = ref<Record<string, string>>({
  user: '用户管理',
  role: '角色管理',
  permission: '权限管理',
  dictionary: '字典管理',
  system: '系统设置',
  auth: '身份认证',
  ai_session: 'AI 会话',
  agent: 'Agent 管理',
  wiki: 'Wiki 管理',
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
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}天前`
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
    message.error('获取审计日志失败')
  } finally {
    auditLoading.value = false
  }
}

onMounted(() => {
  loadDictMappings()
  fetchAuditLogs()
})
</script>

<style lang="less" scoped>
.dashboard-panel {
  width: 100%;
  height: 100%;
  overflow-y: auto;
}

.panel-header {
  margin-bottom: 24px;
}

.panel-title {
  font-size: 24px;
  font-weight: 700;
  color: #1a1a1a;
  margin: 0 0 8px 0;
}

.panel-subtitle {
  font-size: 14px;
  color: #555555;
}

.recent-activities {
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(2px);
  border: 1px solid var(--border-glow);
  border-radius: 4px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
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
  color: #1a1a1a;
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
  color: #444444;
  line-height: 1.5;
  word-break: break-all;
}

.activity-time {
  font-size: 12px;
  color: #888888;
}
</style>


