<template>
  <div class="web-search-management">
    <!-- 头部 -->
    <div class="panel-header">
      <div class="header-left">
        <h2>联网搜索管理</h2>
        <p class="sub">管理 AI 联网搜索供应商配置，支持博查、Anspire 等多种搜索平台</p>
      </div>
      <a-button type="primary" @click="showCreateModal">
        <template #icon><PlusOutlined /></template>
        新增供应商
      </a-button>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <a-input-search
        v-model:value="filters.name"
        placeholder="搜索供应商名称"
        allow-clear
        style="width: 220px"
        @search="handleSearch"
        @clear="handleSearch"
      />
      <a-select
        v-model:value="filters.platform"
        placeholder="平台筛选"
        allow-clear
        style="width: 160px"
        @change="handleSearch"
      >
        <a-select-option v-for="it in dictItems(DictType.WEB_SEARCH_PLATFORM)" :key="it.item_code" :value="it.item_code">
          {{ it.item_name }}
        </a-select-option>
      </a-select>
      <a-select
        v-model:value="filters.status"
        placeholder="状态筛选"
        allow-clear
        style="width: 120px"
        @change="handleSearch"
      >
        <a-select-option :value="1">启用</a-select-option>
        <a-select-option :value="0">禁用</a-select-option>
      </a-select>
      <a-button @click="handleReset"><ReloadOutlined /> 重置</a-button>
    </div>

    <!-- 选项卡 -->
    <a-tabs v-model:activeKey="activeTab" @change="handleTabChange">
      <!-- 配置管理 -->
      <a-tab-pane key="config" tab="配置管理">
        <BackTable
          row-key="id"
          size="small"
          :column="columns"
          :list="dataList"
          :is-loading="loading"
          :total="pagination.total"
          :page-size="pagination.pageSize"
          :current-page="pagination.current"
          :show-column="false"
          :border="false"
          @on-page-change="handlePageChange"
          @on-page-size-change="handlePageSizeChange"
        >
          <template #api_key="{ record }">
            <a-tooltip :title="record.api_key">
              <span class="api-key-cell">{{ record.api_key.slice(0, 12) }}***</span>
            </a-tooltip>
          </template>
          <template #platform="{ record }">
            <a-tag color="blue">{{ dictLabel(DictType.WEB_SEARCH_PLATFORM, record.platform) || record.platform }}</a-tag>
          </template>
          <template #daily_quota="{ record }">
            <span>{{ record.daily_quota > 0 ? record.daily_quota : '不限' }}</span>
          </template>
          <template #status="{ record }">
            <a-tag :color="record.status === 1 ? 'success' : 'error'">
              {{ record.status === 1 ? '启用' : '禁用' }}
            </a-tag>
          </template>
          <template #actions="{ record }">
            <a-space>
              <a-button type="link" size="small" @click="openTestModal(record)">
                <ExperimentOutlined /> 测试
              </a-button>
              <a-button type="link" size="small" @click="handleEdit(record)">
                <EditOutlined /> 编辑
              </a-button>
              <a-button
                type="link"
                size="small"
                @click="toggleStatus(record)"
                :style="{ color: record.status === 1 ? 'var(--warn)' : 'var(--ok)' }"
              >
                {{ record.status === 1 ? '禁用' : '启用' }}
              </a-button>
              <a-popconfirm
                title="确定删除该搜索供应商？"
                ok-text="确定"
                cancel-text="取消"
                @confirm="handleDelete(record)"
              >
                <a-button type="link" size="small" danger>
                  <DeleteOutlined /> 删除
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </BackTable>
      </a-tab-pane>

      <!-- 配额用量 -->
      <a-tab-pane key="quota" tab="配额用量">
        <a-card :loading="quotaLoading">
          <a-table
            row-key="id"
            size="small"
            :columns="quotaColumns"
            :data-source="quotaList"
            :pagination="false"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'progress'">
                <a-progress
                  :percent="record.daily_quota > 0 ? Math.min(record.usage_percent, 100) : 0"
                  :status="record.daily_quota > 0 && record.usage_percent >= 90 ? 'exception' : 'active'"
                />
                <span class="quota-text">
                  {{ record.daily_quota > 0 ? `${record.used_count} / ${record.daily_quota}` : '不限额度' }}
                </span>
              </template>
              <template v-else-if="column.dataIndex === 'remaining'">
                <span>{{ record.daily_quota > 0 ? record.remaining : '—' }}</span>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-tab-pane>

      <!-- 健康检查 -->
      <a-tab-pane key="health" tab="健康检查">
        <a-card :loading="healthLoading">
          <template #extra>
            <a-button size="small" @click="loadHealth">
              <ReloadOutlined /> 刷新
            </a-button>
          </template>
          <a-table
            row-key="id"
            size="small"
            :columns="healthColumns"
            :data-source="healthList"
            :pagination="false"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'status'">
                <a-tag :color="record.status === 'normal' ? 'success' : record.status === 'warning' ? 'orange' : 'error'">
                  {{ record.status === 'normal' ? '正常' : record.status === 'warning' ? '警告' : '异常' }}
                </a-tag>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-tab-pane>

      <!-- 搜索日志 -->
      <a-tab-pane key="logs" tab="搜索日志">
        <a-card :loading="logLoading">
          <a-table
            row-key="id"
            size="small"
            :columns="logColumns"
            :data-source="logList"
            :pagination="{
              current: logQuery.page,
              pageSize: logQuery.pageSize,
              total: logTotal,
              showSizeChanger: true,
              onChange: handleLogPageChange,
            }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'success_rate'">
                <a-tag :color="record.success ? 'success' : 'error'">
                  {{ record.success ? '成功' : '失败' }}
                </a-tag>
                <div class="quota-text" v-if="record.error">{{ record.error }}</div>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-tab-pane>
    </a-tabs>

    <!-- 新增/编辑弹窗 -->
    <WebSearchFormModal
      v-model:open="formVisible"
      :web-search="editingItem"
      @success="onFormSuccess"
    />

    <!-- 搜索测试弹窗 -->
    <SearchTestModal
      v-model:open="testVisible"
      :web-search="testingItem"
      @success="onTestSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  PlusOutlined,
  ReloadOutlined,
  EditOutlined,
  DeleteOutlined,
  ExperimentOutlined,
} from '@ant-design/icons-vue'
import BackTable from '@/components/common/BackTable/index.vue'
import WebSearchFormModal from './components/WebSearchFormModal.vue'
import SearchTestModal from './components/SearchTestModal.vue'
import {
  getWebSearchPage,
  updateWebSearch,
  deleteWebSearch,
  getWebSearchQuota,
  getWebSearchHealth,
  getWebSearchLogs,
  type AiWebSearch,
  type WebSearchQuotaItem,
  type WebSearchHealthItem,
  type WebSearchLogItem,
} from '@/api/ai-web-search'
import { loadAdminDicts, dictItems, dictLabel } from '@/composables/useAdminDict'
import { DictType } from '@/api/dictionary'

// 选项卡
const activeTab = ref('config')

// 列表数据
const loading = ref(false)
const dataList = ref<AiWebSearch[]>([])
const pagination = reactive({
  current: 1,
  pageSize: 15,
  total: 0,
  showSizeChanger: true,
})

// 配额
const quotaLoading = ref(false)
const quotaList = ref<WebSearchQuotaItem[]>([])
// 健康
const healthLoading = ref(false)
const healthList = ref<WebSearchHealthItem[]>([])
// 日志
const logLoading = ref(false)
const logList = ref<WebSearchLogItem[]>([])
const logTotal = ref(0)
const logQuery = reactive({ page: 1, pageSize: 20 })

// 筛选
const filters = reactive({
  name: '',
  platform: undefined as string | undefined,
  status: undefined as number | undefined,
})

// 表格列
const columns: any[] = [
  { title: '名称', dataIndex: 'name', key: 'name', width: 160, ellipsis: true, align: 'center' as const },
  { title: 'API Key', dataIndex: 'api_key', key: 'api_key', width: 180, align: 'center' as const },
  { title: '平台', dataIndex: 'platform', key: 'platform', width: 120, align: 'center' as const },
  { title: '超时(s)', dataIndex: 'timeout', key: 'timeout', width: 90, align: 'center' as const },
  { title: '最大结果', dataIndex: 'max_results', key: 'max_results', width: 90, align: 'center' as const },
  { title: '每日配额', dataIndex: 'daily_quota', key: 'daily_quota', width: 100, align: 'center' as const },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80, align: 'center' as const },
  { title: 'URL', dataIndex: 'url', key: 'url', width: 240, ellipsis: true, align: 'center' as const },
  { title: '状态', dataIndex: 'status', key: 'status', width: 80, align: 'center' as const },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170, align: 'center' as const },
  { title: '操作', key: 'actions', width: 260, fixed: 'right', align: 'center' as const },
]

const quotaColumns: any[] = [
  { title: '供应商', dataIndex: 'name', key: 'name', width: 160, align: 'center' as const },
  { title: '平台', dataIndex: 'platform', key: 'platform', width: 120, align: 'center' as const },
  { title: '每日配额', dataIndex: 'daily_quota', key: 'daily_quota', width: 120, align: 'center' as const },
  { title: '已用量', dataIndex: 'used_count', key: 'used_count', width: 100, align: 'center' as const },
  { title: '剩余', dataIndex: 'remaining', key: 'remaining', width: 100, align: 'center' as const },
  { title: '用量进度', key: 'progress', width: 280, align: 'center' as const },
]

const healthColumns: any[] = [
  { title: '供应商', dataIndex: 'name', key: 'name', width: 160, align: 'center' as const },
  { title: '平台', dataIndex: 'platform', key: 'platform', width: 120, align: 'center' as const },
  { title: '状态', key: 'status', width: 120, align: 'center' as const },
  { title: '响应(ms)', dataIndex: 'response_time', key: 'response_time', width: 120, align: 'center' as const },
  { title: '说明', dataIndex: 'message', key: 'message', ellipsis: true, align: 'center' as const },
]

const logColumns: any[] = [
  { title: '供应商', dataIndex: 'service_name', key: 'service_name', width: 160, align: 'center' as const },
  { title: '平台', dataIndex: 'platform', key: 'platform', width: 100, align: 'center' as const },
  { title: '关键词', dataIndex: 'query', key: 'query', width: 200, ellipsis: true, align: 'center' as const },
  { title: '响应(ms)', dataIndex: 'response_time', key: 'response_time', width: 110, align: 'center' as const },
  { title: '结果数', dataIndex: 'results_count', key: 'results_count', width: 90, align: 'center' as const },
  { title: '成功率', key: 'success_rate', width: 120, align: 'center' as const },
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180, align: 'center' as const },
]

// 弹窗状态
const formVisible = ref(false)
const editingItem = ref<AiWebSearch | null>(null)
const testVisible = ref(false)
const testingItem = ref<AiWebSearch | null>(null)

onMounted(() => {
  loadAdminDicts([DictType.WEB_SEARCH_PLATFORM])
  loadData()
})

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const res = await getWebSearchPage({
      name: filters.name || undefined,
      platform: filters.platform,
      status: filters.status,
      page: pagination.current,
      pageSize: pagination.pageSize,
    })
    dataList.value = res.data
    pagination.total = res.total
  } catch (e: any) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  pagination.current = 1
  loadData()
}

// 重置
const handleReset = () => {
  filters.name = ''
  filters.platform = undefined
  filters.status = undefined
  pagination.current = 1
  loadData()
}

// 分页
const handlePageChange = (page: number) => {
  pagination.current = page
  loadData()
}

const handlePageSizeChange = (size: number) => {
  pagination.current = 1
  pagination.pageSize = size
  loadData()
}

// 显示创建弹窗
const showCreateModal = () => {
  editingItem.value = null
  formVisible.value = true
}

// 编辑
const handleEdit = (record: AiWebSearch) => {
  editingItem.value = record
  formVisible.value = true
}

// 切换状态
const toggleStatus = async (record: AiWebSearch) => {
  try {
    await updateWebSearch({
      id: record.id,
      status: record.status === 1 ? 0 : 1,
    })
    message.success(record.status === 1 ? '已禁用' : '已启用')
    loadData()
  } catch (e: any) {
    message.error(e.message || '操作失败')
  }
}

// 删除
const handleDelete = async (record: AiWebSearch) => {
  try {
    await deleteWebSearch(record.id)
    message.success('删除成功')
    loadData()
  } catch (e: any) {
    message.error(e.message || '删除失败')
  }
}

// 打开测试弹窗
const openTestModal = (record: AiWebSearch) => {
  testingItem.value = record
  testVisible.value = true
}

// 选项卡切换
const handleTabChange = (key: string) => {
  activeTab.value = key
  if (key === 'quota') loadQuota()
  else if (key === 'health') loadHealth()
  else if (key === 'logs') loadLogs()
}

// 配额
const loadQuota = async () => {
  quotaLoading.value = true
  try {
    quotaList.value = await getWebSearchQuota()
  } catch (e: any) {
    message.error(e.message || '获取配额失败')
  } finally {
    quotaLoading.value = false
  }
}

// 健康
const loadHealth = async () => {
  healthLoading.value = true
  try {
    healthList.value = await getWebSearchHealth()
  } catch (e: any) {
    message.error(e.message || '健康检查失败')
  } finally {
    healthLoading.value = false
  }
}

// 日志
const loadLogs = async () => {
  logLoading.value = true
  try {
    const res = await getWebSearchLogs({
      page: logQuery.page,
      pageSize: logQuery.pageSize,
    })
    logList.value = res.data || []
    logTotal.value = res.total || 0
  } catch (e: any) {
    message.error(e.message || '获取日志失败')
  } finally {
    logLoading.value = false
  }
}

const handleLogPageChange = (page: number, pageSize: number) => {
  logQuery.page = page
  logQuery.pageSize = pageSize
  loadLogs()
}

// 表单成功回调
const onFormSuccess = () => {
  loadData()
}

// 测试成功后刷新日志
const onTestSuccess = () => {
  if (activeTab.value === 'logs') loadLogs()
}
</script>

<style lang="less" scoped>
.web-search-management {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;

  h2 {
    font-size: 20px;
    font-weight: 700;
    color: var(--fg);
    margin: 0 0 4px 0;
  }

  .sub {
    font-size: 13px;
    color: var(--fg-secondary);
    margin: 0;
  }
}

.search-bar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  background: var(--bg-surface);
  padding: 16px;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.api-key-cell {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--fg-secondary);
  background: var(--bg-input);
  padding: 2px 6px;
  border-radius: 4px;
}

.quota-text {
  display: block;
  font-size: 12px;
  color: var(--fg-secondary);
  margin-top: 2px;
}

:deep(.ant-table-wrapper) {
  flex: 1;
}

.web-search-management .ant-table-wrapper {
  background: var(--bg-surface) !important;
}

.web-search-management .ant-table {
  background: var(--bg-surface) !important;
}

.web-search-management .ant-table-container {
  background: var(--bg-surface) !important;
}

.web-search-management .ant-table-thead > tr > th {
  background: var(--bg-base) !important;
}

.web-search-management .ant-table-tbody > tr {
  background: var(--bg-surface) !important;
}

.web-search-management .ant-table-tbody > tr > td {
  background: var(--bg-surface) !important;
}

.web-search-management .ant-table-tbody > tr:hover,
.web-search-management .ant-table-tbody > tr:hover > td,
.web-search-management .ant-table-wrapper .ant-table-tbody > tr > td.ant-table-cell-row-hover {
  background: var(--bg-hover) !important;
}
</style>
