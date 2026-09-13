<template>
  <div class="api-key-management">
    <!-- 头部 -->
    <div class="panel-header">
      <div class="header-left">
        <h2>{{ t('apiKeyMgmt.pageTitle') }}</h2>
        <p class="sub">{{ t('apiKeyMgmt.pageSub') }}</p>
      </div>
      <a-button type="primary" @click="showCreateModal">
        <template #icon><PlusOutlined /></template>
        {{ t('apiKeyMgmt.addKey') }}
      </a-button>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <a-input-search
        v-model:value="filters.name"
        :placeholder="t('apiKeyMgmt.searchKey')"
        allow-clear
        style="width:240px"
        @search="handleSearch"
        @clear="handleSearch"
      />
      <a-select
        v-model:value="filters.platform"
        :placeholder="t('webSearch.platformFilter')"
        allow-clear
        style="width:160px"
        @change="handleSearch"
      >
        <a-select-option v-for="p in AI_PLATFORMS" :key="p" :value="p">{{ p }}</a-select-option>
      </a-select>
      <a-select
        v-model:value="filters.status"
        :placeholder="t('webSearch.statusFilter')"
        allow-clear
        style="width:120px"
        @change="handleSearch"
      >
        <a-select-option :value="1">{{ t('apiKeyMgmt.enabled') }}</a-select-option>
        <a-select-option :value="0">{{ t('apiKeyMgmt.disabled') }}</a-select-option>
      </a-select>
      <a-button @click="handleReset"><ReloadOutlined /> {{ t('common.reset') }}</a-button>
    </div>

    <!-- 表格 -->
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
        <a-tag color="blue">{{ record.platform }}</a-tag>
      </template>
      <template #status="{ record }">
        <a-tag :color="record.status === 1 ? 'success' : 'error'">
          {{ record.status === 1 ? t('apiKeyMgmt.enabled') : t('apiKeyMgmt.disabled') }}
        </a-tag>
      </template>
      <template #actions="{ record }">
        <a-space>
          <a-button type="link" size="small" @click="openModelList(record)">
            <RobotOutlined /> {{ t('apiKeyMgmt.models') }}
          </a-button>
          <a-button type="link" size="small" @click="handleEdit(record)">
            <EditOutlined /> {{ t('common.edit') }}
          </a-button>
          <a-button
            type="link"
            size="small"
            @click="toggleStatus(record)"
            :style="{ color: record.status === 1 ? 'var(--warn)' : 'var(--ok)' }"
          >
            {{ record.status === 1 ? t('apiKeyMgmt.disabled') : t('apiKeyMgmt.enabled') }}
          </a-button>
          <a-popconfirm
            :title="t('apiKeyMgmt.deleteConfirm')"
            :ok-text="t('common.confirm')"
            :cancel-text="t('common.cancel')"
            @confirm="handleDelete(record)"
          >
            <a-button type="link" size="small" danger>
              <DeleteOutlined /> {{ t('common.delete') }}
            </a-button>
          </a-popconfirm>
        </a-space>
      </template>
    </BackTable>

    <!-- 新增/编辑弹窗 -->
    <ApiKeyFormModal
      v-model:open="formVisible"
      :api-key="editingKey"
      @success="onFormSuccess"
    />

    <!-- 关联模型子表弹窗 -->
    <ChatModelList
      v-model:open="modelListVisible"
      :api-key="currentKey"
      @success="loadData"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined, EditOutlined, DeleteOutlined, RobotOutlined } from '@ant-design/icons-vue'
import BackTable from '@/components/common/BackTable/index.vue'
import ApiKeyFormModal from './components/ApiKeyFormModal.vue'
import ChatModelList from './components/ChatModelList.vue'
import {
  getApiKeyPage,
  updateApiKey,
  deleteApiKey,
  AI_PLATFORMS,
  type AiApiKey
} from '@/api/ai-apikey'

const { t } = useI18n()

// 列表数据
const loading = ref(false)
const dataList = ref<AiApiKey[]>([])
const pagination = reactive({
  current: 1,
  pageSize: 15,
  total: 0,
  showSizeChanger: true
})

// 筛选
const filters = reactive({
  name: '',
  platform: undefined as string | undefined,
  status: undefined as number | undefined
})

// 表格列
const columns = computed<any[]>(() => [
  { title: t('apiKeyMgmt.colKeyName'), dataIndex: 'name', key: 'name', width: 180, ellipsis: true, align: 'center' as const },
  { title: t('apiKeyMgmt.colPlatform'), dataIndex: 'platform', key: 'platform', width: 120, align: 'center' as const },
  { title: 'API Key', dataIndex: 'api_key', key: 'api_key', width: 180, align: 'center' as const },
  { title: 'URL', dataIndex: 'url', key: 'url', width: 200, ellipsis: true, align: 'center' as const },
  { title: t('apiKeyMgmt.colStatus'), dataIndex: 'status', key: 'status', width: 80, align: 'center' as const },
  { title: t('apiKeyMgmt.colCreatedAt'), dataIndex: 'created_at', key: 'created_at', width: 170, align: 'center' as const },
  { title: t('apiKeyMgmt.colActions'), key: 'actions', width: 280, fixed: 'right', align: 'center' as const }
])

// 新增/编辑弹窗
const formVisible = ref(false)
const editingKey = ref<AiApiKey | null>(null)

// 模型子表弹窗
const modelListVisible = ref(false)
const currentKey = ref<AiApiKey | null>(null)

onMounted(() => {
  loadData()
})

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const res = await getApiKeyPage({
      name: filters.name || undefined,
      platform: filters.platform,
      status: filters.status,
      page: pagination.current,
      pageSize: pagination.pageSize
    })
    dataList.value = res.data
    pagination.total = res.total
  } catch (e: any) {
    message.error(e.message || t('apiKeyMgmt.loadFailed'))
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
  editingKey.value = null
  formVisible.value = true
}

// 编辑
const handleEdit = (record: AiApiKey) => {
  editingKey.value = record
  formVisible.value = true
}

// 切换状态
const toggleStatus = async (record: AiApiKey) => {
  try {
    await updateApiKey({
      id: record.id,
      status: record.status === 1 ? 0 : 1
    })
    message.success(record.status === 1 ? t('apiKeyMgmt.disabledMsg') : t('apiKeyMgmt.enabledMsg'))
    loadData()
  } catch (e: any) {
    message.error(e.message || t('common.error'))
  }
}

// 删除
const handleDelete = async (record: AiApiKey) => {
  try {
    await deleteApiKey(record.id)
    message.success(t('apiKeyMgmt.deleteSuccess'))
    loadData()
  } catch (e: any) {
    message.error(e.message || t('apiKeyMgmt.deleteFailed'))
  }
}

// 打开模型列表
const openModelList = (record: AiApiKey) => {
  currentKey.value = record
  modelListVisible.value = true
}

// 表单成功回调
const onFormSuccess = () => {
  loadData()
}
</script>

<style lang="less" scoped>
.api-key-management {
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

:deep(.ant-table-wrapper) {
  flex: 1;
}

.api-key-management .ant-table-wrapper {
  background: var(--bg-surface) !important;
}

.api-key-management .ant-table {
  background: var(--bg-surface) !important;
}

.api-key-management .ant-table-container {
  background: var(--bg-surface) !important;
}

.api-key-management .ant-table-thead > tr > th {
  background: var(--bg-base) !important;
}

.api-key-management .ant-table-tbody > tr {
  background: var(--bg-surface) !important;
}

.api-key-management .ant-table-tbody > tr > td {
  background: var(--bg-surface) !important;
}

.api-key-management .ant-table-tbody > tr:hover,
.api-key-management .ant-table-tbody > tr:hover > td,
.api-key-management .ant-table-wrapper .ant-table-tbody > tr > td.ant-table-cell-row-hover {
  background: var(--bg-hover) !important;
}
</style>
