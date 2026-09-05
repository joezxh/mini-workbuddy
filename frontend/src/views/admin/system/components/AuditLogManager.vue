<template>
  <div class="audit-log-manager">
    <div class="toolbar">
      <a-form layout="inline">
        <a-form-item label="用户ID">
          <a-input v-model:value="filters.userId" placeholder="输入用户ID" allow-clear />
        </a-form-item>
        <a-form-item label="操作类型">
          <a-select v-model:value="filters.operationType" style="width: 150px" allow-clear placeholder="选择操作类型">
            <a-select-option value="create">创建 (create)</a-select-option>
            <a-select-option value="update">更新 (update)</a-select-option>
            <a-select-option value="delete">删除 (delete)</a-select-option>
            <a-select-option value="query">查询 (query)</a-select-option>
            <a-select-option value="login">登录 (login)</a-select-option>
            <a-select-option value="logout">登出 (logout)</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="只看有附件">
          <a-switch v-model:checked="filters.onlyWithAttachment" @change="fetchLogs" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="fetchLogs">过滤</a-button>
          <a-button style="margin-left: 8px" @click="resetFilters">重置</a-button>
        </a-form-item>
      </a-form>
    </div>

    <a-table
      :columns="columns"
      :data-source="filteredLogs"
      :loading="loading"
      :pagination="pagination"
      @change="handleTableChange"
      row-key="logId"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'description'">
          <a-tooltip :title="record.operationDesc">
            <div style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              {{ record.operationDesc || '-' }}
            </div>
          </a-tooltip>
        </template>
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status >= 200 && record.status < 300 ? 'success' : 'error'">
            {{ record.status || '无' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'attachments'">
          <AttachmentSummary
            :new-data="record.newData"
            :request-params="record.requestParams"
          />
        </template>
        <template v-if="column.key === 'actions'">
          <a-button type="link" size="small" @click="openDetail(record)">详情</a-button>
        </template>
      </template>
    </a-table>

    <!-- 详情弹窗：包含附件明细 -->
    <a-modal
      v-model:open="detailVisible"
      title="审计日志详情"
      :footer="null"
      width="720px"
    >
      <div v-if="currentLog" class="log-detail">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="日志ID">{{ currentLog.logId }}</a-descriptions-item>
          <a-descriptions-item label="用户名">{{ currentLog.username || '-' }}</a-descriptions-item>
          <a-descriptions-item label="操作类型">
            <a-tag color="blue">{{ currentLog.operationType }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="操作模块">{{ currentLog.operationModule }}</a-descriptions-item>
          <a-descriptions-item label="请求 IP" :span="2">{{ currentLog.requestIp || '-' }}</a-descriptions-item>
          <a-descriptions-item label="响应状态" :span="2">
            <a-tag :color="currentLog.status && currentLog.status < 400 ? 'success' : 'error'">
              {{ currentLog.status || '无' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="URL" :span="2">{{ currentLog.requestUrl || currentLog.operationDesc }}</a-descriptions-item>
        </a-descriptions>

        <a-divider>附件明细</a-divider>

        <AttachmentSummary
          v-if="currentLog.newData?.attachment_info || hasAttachmentInParams(currentLog.requestParams)"
          :new-data="currentLog.newData"
          :request-params="currentLog.requestParams"
          :detailed="true"
        />
        <a-empty v-else description="此条日志无附件" />

        <template v-if="currentLog.requestParams">
          <a-divider>请求参数</a-divider>
          <pre class="request-params">{{ formatJson(currentLog.requestParams) }}</pre>
        </template>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import { getAuditLogs, type AuditLogItem } from '@/api/admin'
import AttachmentSummary from './AttachmentSummary.vue'

const props = defineProps<{
  filterUserId: number | null
}>()

const logs = ref<AuditLogItem[]>([])
const loading = ref(false)
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0
})

const filters = reactive({
  userId: '' as string | number,
  operationType: undefined as string | undefined,
  onlyWithAttachment: false,
})

const columns = [
  { title: '日志ID', dataIndex: 'logId', key: 'logId', width: 80 },
  { title: '用户ID', dataIndex: 'userId', key: 'userId', width: 80 },
  { title: '用户名', dataIndex: 'username', key: 'username', width: 120 },
  { title: '操作类型', dataIndex: 'operationType', key: 'operationType', width: 110 },
  { title: '操作模块', dataIndex: 'operationModule', key: 'operationModule', width: 130 },
  { title: '描述', key: 'description' },
  { title: '附件', key: 'attachments', width: 220 },
  { title: '请求 IP', dataIndex: 'requestIp', key: 'requestIp', width: 130 },
  { title: '响应状态', key: 'status', width: 90 },
  { title: '操作时间', dataIndex: 'createdAt', key: 'createdAt', width: 170 },
  { title: '操作', key: 'actions', width: 80, fixed: 'right' as const },
]

const fetchLogs = async () => {
  loading.value = true
  try {
    const params: any = {
      skip: (pagination.current - 1) * pagination.pageSize,
      limit: pagination.pageSize
    }
    if (filters.userId) params.user_id = filters.userId
    if (filters.operationType) params.operation_type = filters.operationType

    const res = await getAuditLogs(params)
    if (res.code === 0) {
      logs.value = res.data
      pagination.total = res.total
    }
  } catch (error) {
    message.error('获取审计日志失败')
  } finally {
    loading.value = false
  }
}

const filteredLogs = computed(() => {
  if (!filters.onlyWithAttachment) return logs.value
  return logs.value.filter(log =>
    log.newData?.attachment_info || hasAttachmentInParams(log.requestParams)
  )
})

function hasAttachmentInParams(p?: Record<string, any> | null) {
  if (!p) return false
  return !!(p.file_ids || p.file_db_ids || p.file_id)
}

const detailVisible = ref(false)
const currentLog = ref<AuditLogItem | null>(null)

function openDetail(log: AuditLogItem) {
  currentLog.value = log
  detailVisible.value = true
}

function formatJson(data: any): string {
  try {
    return JSON.stringify(data, null, 2)
  } catch {
    return String(data)
  }
}

const handleTableChange = (pag: any) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  fetchLogs()
}

const resetFilters = () => {
  filters.userId = ''
  filters.operationType = undefined
  filters.onlyWithAttachment = false
  pagination.current = 1
  fetchLogs()
}

// Watch for prop changes to filter logs dynamically
watch(() => props.filterUserId, (newVal) => {
  if (newVal) {
    filters.userId = newVal
    pagination.current = 1
    fetchLogs()
  }
})

onMounted(() => {
  if (props.filterUserId) {
    filters.userId = props.filterUserId
  }
  fetchLogs()
})
</script>

<style scoped>
.toolbar {
  margin-bottom: 24px;
  background: #fbfbfb;
  padding: 16px;
  border-radius: 4px;
}

.log-detail {
  padding: 4px 0;
}

.request-params {
  font-size: 12px;
  background: #f8f9fa;
  padding: 12px;
  border-radius: 4px;
  max-height: 260px;
  overflow: auto;
  margin: 0;
  font-family: 'SFMono-Regular', Consolas, monospace;
  white-space: pre-wrap;
}
</style>
