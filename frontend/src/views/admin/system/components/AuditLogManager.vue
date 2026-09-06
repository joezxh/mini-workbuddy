<template>
  <div class="audit-log-manager">
    <div class="toolbar">
      <a-form layout="inline">
        <a-form-item :label="t('sys.auditLog.labelUserId')">
          <a-input v-model:value="filters.userId" :placeholder="t('sys.auditLog.placeholderUserId')" allow-clear />
        </a-form-item>
        <a-form-item :label="t('sys.auditLog.labelOpType')">
          <a-select v-model:value="filters.operationType" style="width: 150px" allow-clear :placeholder="t('sys.auditLog.placeholderOpType')">
            <a-select-option value="create">{{ t('sys.auditLog.opCreate') }}</a-select-option>
            <a-select-option value="update">{{ t('sys.auditLog.opUpdate') }}</a-select-option>
            <a-select-option value="delete">{{ t('sys.auditLog.opDelete') }}</a-select-option>
            <a-select-option value="query">{{ t('sys.auditLog.opQuery') }}</a-select-option>
            <a-select-option value="login">{{ t('sys.auditLog.opLogin') }}</a-select-option>
            <a-select-option value="logout">{{ t('sys.auditLog.opLogout') }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="t('sys.auditLog.labelAttachment')">
          <a-switch v-model:checked="filters.onlyWithAttachment" @change="fetchLogs" />
        </a-form-item>
        <a-form-item v-if="showTenant" :label="t('sys.auditLog.labelTenant')">
          <TenantFilterSelect v-model="selectedTenantId" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="fetchLogs">{{ t('sys.auditLog.filter') }}</a-button>
          <a-button style="margin-left: 8px" @click="resetFilters">{{ t('sys.auditLog.reset') }}</a-button>
        </a-form-item>
      </a-form>
    </div>

    <a-table
      :columns="columns"
      :data-source="filteredLogs"
      :loading="loading"
      :pagination="tablePagination"
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
            {{ record.status || t('sys.auditLog.none') }}
          </a-tag>
        </template>
        <template v-if="column.key === 'attachments'">
          <AttachmentSummary
            :new-data="record.newData"
            :request-params="record.requestParams"
          />
        </template>
        <template v-if="column.key === 'actions'">
          <a-button type="link" size="small" @click="openDetail(record)">{{ t('sys.auditLog.detail') }}</a-button>
        </template>
      </template>
    </a-table>

    <!-- 详情弹窗：包含附件明细 -->
    <a-modal
      v-model:open="detailVisible"
      :title="t('sys.auditLog.detailTitle')"
      :footer="null"
      width="720px"
    >
      <div v-if="currentLog" class="log-detail">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item :label="t('sys.auditLog.logId')">{{ currentLog.logId }}</a-descriptions-item>
          <a-descriptions-item :label="t('sys.auditLog.username')">{{ currentLog.username || '-' }}</a-descriptions-item>
          <a-descriptions-item :label="t('sys.auditLog.opType')">
            <a-tag color="blue">{{ currentLog.operationType }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item :label="t('sys.auditLog.opModule')">{{ currentLog.operationModule }}</a-descriptions-item>
          <a-descriptions-item :label="t('sys.auditLog.requestIp')" :span="2">{{ currentLog.requestIp || '-' }}</a-descriptions-item>
          <a-descriptions-item :label="t('sys.auditLog.responseStatus')" :span="2">
            <a-tag :color="currentLog.status && currentLog.status < 400 ? 'success' : 'error'">
              {{ currentLog.status || t('sys.auditLog.none') }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item :label="t('sys.auditLog.url')" :span="2">{{ currentLog.requestUrl || currentLog.operationDesc }}</a-descriptions-item>
        </a-descriptions>

        <a-divider>{{ t('sys.auditLog.attachmentDetail') }}</a-divider>

        <AttachmentSummary
          v-if="currentLog.newData?.attachment_info || hasAttachmentInParams(currentLog.requestParams)"
          :new-data="currentLog.newData"
          :request-params="currentLog.requestParams"
          :detailed="true"
        />
        <a-empty v-else :description="t('sys.auditLog.noAttachment')" />

        <template v-if="currentLog.requestParams">
          <a-divider>{{ t('sys.auditLog.requestParams') }}</a-divider>
          <pre class="request-params">{{ formatJson(currentLog.requestParams) }}</pre>
        </template>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { getAuditLogs, type AuditLogItem } from '@/api/admin'
import AttachmentSummary from './AttachmentSummary.vue'
import TenantFilterSelect from './TenantFilterSelect.vue'

const { t } = useI18n()

const props = defineProps<{
  filterUserId: number | null
  /** 超级管理员可见：显示租户筛选与所属租户列 */
  showTenant?: boolean
}>()

// 租户筛选由本组件内部持有：超管可切换具体租户，清空=全部
const selectedTenantId = ref<number | undefined>(undefined)
const tenantParam = () => (props.showTenant && selectedTenantId.value != null ? selectedTenantId.value : null)

const logs = ref<AuditLogItem[]>([])
const loading = ref(false)
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0
})
const tablePagination = computed(() => ({
  ...pagination,
  showTotal: (total: number) => t('common.total', { total })
}))

const filters = reactive({
  userId: '' as string | number,
  operationType: undefined as string | undefined,
  onlyWithAttachment: false,
})

const columns = computed(() => {
  const base: any[] = [
    { title: t('sys.auditLog.colLogId'), dataIndex: 'logId', key: 'logId', width: 80 },
    { title: t('sys.auditLog.colUserId'), dataIndex: 'userId', key: 'userId', width: 80 },
    { title: t('sys.auditLog.colUsername'), dataIndex: 'username', key: 'username', width: 120 },
  ]
  // 超级管理员可见所属租户列
  if (props.showTenant) {
    base.push({ title: t('sys.auditLog.colTenant'), dataIndex: 'tenantName', key: 'tenantName', width: 120 })
  }
  base.push(
    { title: t('sys.auditLog.colOpType'), dataIndex: 'operationType', key: 'operationType', width: 110 },
    { title: t('sys.auditLog.colOpModule'), dataIndex: 'operationModule', key: 'operationModule', width: 130 },
    { title: t('sys.auditLog.colDesc'), key: 'description' },
    { title: t('sys.auditLog.colAttachment'), key: 'attachments', width: 220 },
    { title: t('sys.auditLog.colIp'), dataIndex: 'requestIp', key: 'requestIp', width: 130 },
    { title: t('sys.auditLog.colStatus'), key: 'status', width: 90 },
    { title: t('sys.auditLog.colTime'), dataIndex: 'createdAt', key: 'createdAt', width: 170 },
    { title: t('sys.auditLog.colAction'), key: 'actions', width: 80, fixed: 'right' as const },
  )
  return base
})

const fetchLogs = async () => {
  loading.value = true
  try {
    const params: any = {
      skip: (pagination.current - 1) * pagination.pageSize,
      limit: pagination.pageSize
    }
    const tid = tenantParam()
    if (tid != null) params.tenant_id = tid
    if (filters.userId) params.user_id = filters.userId
    if (filters.operationType) params.operation_type = filters.operationType

    const res = await getAuditLogs(params)
    if (res.code === 0) {
      logs.value = res.data
      pagination.total = res.total
    }
  } catch (error) {
    message.error(t('sys.auditLog.fetchFail'))
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

// 切换租户筛选时重新拉取
watch(selectedTenantId, () => {
  pagination.current = 1
  fetchLogs()
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
  background: var(--bg-surface);
  padding: 16px;
  border-radius: 4px;
}

/* 表格行不换行；操作按钮保持单行 */
:deep(.ant-table-cell) {
  white-space: nowrap;
}

.log-detail {
  padding: 4px 0;
}

.request-params {
  font-size: 12px;
  background: var(--bg-input);
  padding: 12px;
  border-radius: 4px;
  max-height: 260px;
  overflow: auto;
  margin: 0;
  font-family: 'SFMono-Regular', Consolas, monospace;
  white-space: pre-wrap;
}
</style>
