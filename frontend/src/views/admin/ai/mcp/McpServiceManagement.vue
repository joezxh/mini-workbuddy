<template>
  <div class="mcp-service-management">
    <a-tabs v-model:activeKey="activeTab" class="mcp-tabs">
      <!-- ============ Tab 1: 我的 MCP ============ -->
      <a-tab-pane key="my-mcp" :tab="t('mcpSquare.tabMyMcp')">
        <div class="panel-header">
          <div class="header-left">
            <h2>{{ t('mcpSquare.apiKeyTitle') }}</h2>
            <p class="sub">{{ t('mcpSquare.apiKeySubtitle') }}</p>
          </div>
          <div class="header-actions">
            <a-button type="primary" @click="showCreateModal">
              <template #icon><PlusOutlined /></template>
              {{ t('mcpSquare.addApiKey') }}
            </a-button>
          </div>
        </div>

        <!-- 搜索栏 -->
        <div class="search-bar">
          <a-input-search
            v-model:value="filters.name"
            :placeholder="t('mcpSquare.searchName')"
            allow-clear
            style="width: 200px"
            @search="handleSearch"
            @clear="handleSearch"
          />
          <a-select
            v-model:value="filters.service_type"
            :placeholder="t('mcpSquare.serviceType')"
            allow-clear
            style="width: 160px"
            @change="handleSearch"
          >
            <a-select-option value="nacos2">Nacos 2.x</a-select-option>
            <a-select-option value="nacos3">Nacos 3.x</a-select-option>
            <a-select-option value="http">HTTP</a-select-option>
            <a-select-option value="sse">SSE</a-select-option>
          </a-select>
          <a-select
            v-model:value="filters.status"
            :placeholder="t('skillHub.status')"
            allow-clear
            style="width: 120px"
            @change="handleSearch"
          >
            <a-select-option :value="1">{{ t('skillHub.enabled') }}</a-select-option>
            <a-select-option :value="0">{{ t('skillHub.disabled') }}</a-select-option>
          </a-select>
          <a-button @click="handleReset"><ReloadOutlined /> {{ t('common.reset') }}</a-button>
        </div>

        <!-- 表格 -->
        <BackTable
          row-key="id"
          size="small"
          :column="apiKeyColumns"
          :list="apiKeyList"
          :is-loading="loading"
          :total="pagination.total"
          :page-size="pagination.pageSize"
          :current-page="pagination.page"
          @on-page-change="handlePageChange"
          @on-page-size-change="handlePageSizeChange"
        >
          <template #service_type="{ row }">
            <a-tag :color="serviceTypeColor(row.service_type)">
              {{ serviceTypeLabel(row.service_type) }}
            </a-tag>
          </template>
          <template #protocol_type="{ row }">
            <span class="protocol-text">{{ row.protocol_type || '-' }}</span>
          </template>
          <template #status="{ row }">
            <a-badge :status="row.status === 1 ? 'success' : 'default'" :text="row.status === 1 ? t('skillHub.enabled') : t('skillHub.disabled')" />
          </template>
          <template #health="{ row }">
            <a-tooltip :title="row.last_check_at ? t('mcpSquare.checkedAt', { time: row.last_check_at }) : t('mcpSquare.notChecked')">
              <a-badge
                :status="healthBadge(row.health_status)"
                :text="healthLabel(row.health_status)"
              />
            </a-tooltip>
          </template>
          <template #action="{ row }">
            <a-space>
              <a-button type="link" size="small" :loading="testingId === row.id" @click="handleTestConnection(row)">{{ t('mcpSquare.test') }}</a-button>
              <a-button type="link" size="small" @click="handleEdit(row)">{{ t('common.edit') }}</a-button>
              <a-button type="link" size="small" @click="handleClientManage(row)">Client</a-button>
              <a-popconfirm :title="t('mcpSquare.deleteConfirm')" @confirm="handleDelete(row)">
                <a-button type="link" size="small" danger>{{ t('common.delete') }}</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </BackTable>
      </a-tab-pane>

      <!-- ============ Tab 2: MCP 广场 ============ -->
      <a-tab-pane key="mcp-square" :tab="t('mcpSquare.tabSquare')">
        <div class="panel-header">
          <div class="header-left">
            <h2>{{ t('mcpSquare.squareTitle') }}</h2>
            <p class="sub">{{ t('mcpSquare.squareSubtitle') }}</p>
          </div>
          <div class="header-actions">
            <a-button type="primary" @click="handleAddTemplate">
              <template #icon><PlusOutlined /></template>
              {{ t('mcpSquare.addTemplate') }}
            </a-button>
          </div>
        </div>
        <div class="search-bar">
          <a-input-search
            v-model:value="squareFilters.name"
            :placeholder="t('mcpSquare.searchTemplate')"
            allow-clear
            style="width: 200px"
            @search="handleSquareSearch"
            @clear="handleSquareSearch"
          />
          <a-select
            v-model:value="squareFilters.category"
            :placeholder="t('mcpSquare.category')"
            allow-clear
            style="width: 160px"
            @change="handleSquareSearch"
          >
            <a-select-option value="finance">{{ t('mcpSquare.catFinance') }}</a-select-option>
            <a-select-option value="sales">{{ t('mcpSquare.catSales') }}</a-select-option>
            <a-select-option value="legal">{{ t('mcpSquare.catLegal') }}</a-select-option>
            <a-select-option value="office">{{ t('mcpSquare.catOffice') }}</a-select-option>
            <a-select-option value="education">{{ t('mcpSquare.catEducation') }}</a-select-option>
          </a-select>
          <a-select
            v-model:value="squareFilters.status"
            :placeholder="t('skillHub.status')"
            allow-clear
            style="width: 120px"
            @change="handleSquareSearch"
          >
            <a-select-option :value="1">{{ t('skillHub.enabled') }}</a-select-option>
            <a-select-option :value="0">{{ t('skillHub.disabled') }}</a-select-option>
          </a-select>
          <a-button @click="handleSquareReset"><ReloadOutlined /> {{ t('common.reset') }}</a-button>
        </div>
        <a-row :gutter="[16, 16]">
          <a-col v-for="tpl in squareList" :key="tpl.id" :xs="24" :sm="12" :md="8" :lg="6">
            <a-card hoverable class="square-card">
              <template #title>
                <div class="card-title">
                  <span class="card-name">{{ tpl.name }}</span>
                  <a-tag v-if="tpl.is_installed" color="green">{{ t('mcpSquare.installed') }}</a-tag>
                </div>
              </template>
              <p class="card-desc">{{ tpl.description || t('mcpSquare.noDescription') }}</p>
              <div class="card-meta">
                <a-tag :color="serviceTypeColor(tpl.service_type)">
                  {{ serviceTypeLabel(tpl.service_type) }}
                </a-tag>
                <a-tag v-if="tpl.category">{{ categoryLabel(tpl.category) }}</a-tag>
                <a-tag v-if="tpl.status === 0" color="default">{{ t('mcpSquare.disabledTag') }}</a-tag>
              </div>
              <template #actions>
                <a-button type="link" size="small" @click="handleViewDetail(tpl)">{{ t('mcpSquare.detail') }}</a-button>
                <a-button type="link" size="small" @click="handleEditTemplate(tpl)">{{ t('common.edit') }}</a-button>
                <a-button
                  v-if="!tpl.is_installed"
                  type="link"
                  size="small"
                  @click="handleInstall(tpl)"
                >{{ t('skillHub.install') }}</a-button>
                <a-popconfirm
                  v-else
                  :title="t('mcpSquare.uninstallConfirm')"
                  @confirm="handleUninstall(tpl)"
                >
                  <a-button type="link" size="small" danger>{{ t('mcpSquare.uninstall') }}</a-button>
                </a-popconfirm>
                <a-popconfirm
                  :title="t('mcpSquare.deleteTemplateConfirm')"
                  :ok-text="t('mcpSquare.cancelDelete')"
                  :cancel-text="t('mcpSquare.forceDelete')"
                  @confirm="handleSoftDelete(tpl)"
                  @cancel="handleForceDelete(tpl)"
                >
                  <a-button type="link" size="small" danger>{{ t('common.delete') }}</a-button>
                </a-popconfirm>
              </template>
            </a-card>
          </a-col>
        </a-row>
        <a-empty v-if="squareList.length === 0" :description="t('mcpSquare.noTemplates')" />
        <div v-else class="square-pagination">
          <a-pagination
            v-model:current="squarePagination.page"
            v-model:page-size="squarePagination.pageSize"
            :total="squarePagination.total"
            show-size-changer
            :page-size-options="['10', '20', '50']"
            show-quick-jumper
            :show-total="(total: number) => t('common.total', { total })"
            @change="handleSquarePageChange"
            @showSizeChange="handleSquarePageSizeChange"
          />
        </div>
      </a-tab-pane>
    </a-tabs>

    <!-- API Key 表单弹窗 -->
    <McpApiKeyFormModal
      v-model:visible="formModalVisible"
      :record="currentRecord"
      @success="loadData"
    />

    <!-- Client 子表弹窗 -->
    <McpClientList
      v-model:visible="clientListVisible"
      :api-key-id="currentApiKeyId"
      :api-key-name="currentApiKeyName"
    />

    <!-- 安装确认弹窗 -->
    <McpInstallModal
      v-model:visible="installModalVisible"
      :template="installTemplate"
      @success="handleInstallSuccess"
    />

    <!-- 广场模板表单（新增/编辑） -->
    <McpSquareTemplateFormModal
      v-model:visible="templateFormVisible"
      :record="currentTemplate"
      @success="loadSquareData"
    />

    <!-- 广场模板详情 -->
    <McpSquareDetailModal
      v-model:visible="detailModalVisible"
      :template="detailTemplate"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import BackTable from '@/components/common/BackTable/index.vue'
import McpApiKeyFormModal from './components/McpApiKeyFormModal.vue'
import McpClientList from './components/McpClientList.vue'
import McpInstallModal from './components/McpInstallModal.vue'
import McpSquareTemplateFormModal from './components/McpSquareTemplateFormModal.vue'
import McpSquareDetailModal from './components/McpSquareDetailModal.vue'
import {
  getMcpApiKeyPage,
  deleteMcpApiKey,
  getMcpSquarePage,
  deleteMcpSquare,
  uninstallMcpSquare,
  testMcpConnection,
  type McpApiKey,
  type McpSquareTemplate,
} from '@/api/ai-mcp'

const activeTab = ref('my-mcp')
const { t } = useI18n()

// ============= API Key 列表 =============
const loading = ref(false)
const apiKeyList = ref<McpApiKey[]>([])
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })
const filters = reactive({
  name: '',
  service_type: undefined as string | undefined,
  status: undefined as number | undefined,
})

const apiKeyColumns = computed(() => [
  { title: t('mcpSquare.name'), key: 'name', dataIndex: 'name', width: 180, ellipsis: true },
  { title: t('mcpSquare.serviceType'), key: 'service_type', dataIndex: 'service_type', width: 100 },
  { title: t('mcpSquare.protocolType'), key: 'protocol_type', dataIndex: 'protocol_type', width: 130 },
  { title: t('skillHub.status'), key: 'status', dataIndex: 'status', width: 80 },
  { title: t('mcpSquare.health'), key: 'health', dataIndex: 'health_status', width: 100 },
  { title: t('mcpSquare.creator'), key: 'creator', dataIndex: 'creator', width: 90 },
  { title: t('skillHub.createdAt'), key: 'created_at', dataIndex: 'created_at', width: 160 },
  { title: t('mcpSquare.action'), key: 'action', width: 220, fixed: 'right' as const },
])

// 服务类型 → 显示文本/颜色映射（代码值，无需翻译）
const SERVICE_TYPE_LABEL: Record<string, string> = {
  nacos2: 'Nacos 2.x',
  nacos3: 'Nacos 3.x',
  http: 'HTTP',
  sse: 'SSE',
}

function serviceTypeLabel(type: string): string {
  return SERVICE_TYPE_LABEL[type] || type || '-'
}
function serviceTypeColor(type: string): string {
  const map: Record<string, string> = {
    nacos2: 'blue',
    nacos3: 'geekblue',
    http: 'cyan',
    sse: 'green',
  }
  return map[type] || 'default'
}
function categoryLabel(cat: string): string {
  const map: Record<string, string> = {
    finance: t('mcpSquare.catFinance'),
    sales: t('mcpSquare.catSales'),
    legal: t('mcpSquare.catLegal'),
    office: t('mcpSquare.catOffice'),
    education: t('mcpSquare.catEducation'),
  }
  return map[cat] || cat
}

async function loadData() {
  loading.value = true
  try {
    const res = await getMcpApiKeyPage({
      name: filters.name || undefined,
      service_type: filters.service_type,
      status: filters.status,
      page: pagination.page,
      pageSize: pagination.pageSize,
    })
    apiKeyList.value = res.data ?? []
    pagination.total = res.total ?? 0
  } catch (e) {
    console.error('加载 MCP API Key 失败', e)
    message.error(t('mcpSquare.loadFailed'))
    apiKeyList.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  loadData()
}

function handleReset() {
  filters.name = ''
  filters.service_type = undefined
  filters.status = undefined
  handleSearch()
}

function handlePageChange(page: number) {
  pagination.page = page
  loadData()
}

function handlePageSizeChange(size: number) {
  pagination.pageSize = size
  pagination.page = 1
  loadData()
}

// ============= 表单弹窗 =============
const formModalVisible = ref(false)
const currentRecord = ref<McpApiKey | null>(null)

function showCreateModal() {
  currentRecord.value = null
  formModalVisible.value = true
}

function handleEdit(record: McpApiKey) {
  currentRecord.value = record
  formModalVisible.value = true
}

async function handleDelete(record: McpApiKey) {
  try {
    await deleteMcpApiKey(record.id)
    message.success(t('mcpSquare.deleteSuccess'))
    loadData()
  } catch {
    message.error(t('mcpSquare.deleteFailed'))
  }
}

// ============= Client 子表 =============
const clientListVisible = ref(false)
const currentApiKeyId = ref(0)
const currentApiKeyName = ref('')

function handleClientManage(record: McpApiKey) {
  currentApiKeyId.value = record.id
  currentApiKeyName.value = record.name
  clientListVisible.value = true
}

// ============= 广场 =============
const squareList = ref<McpSquareTemplate[]>([])
const squareFilters = reactive({
  name: '',
  category: undefined as string | undefined,
  status: undefined as number | undefined,
})
const squarePagination = reactive({ page: 1, pageSize: 10, total: 0 })

// 安装弹窗
const installModalVisible = ref(false)
const installTemplate = ref<McpSquareTemplate | null>(null)

// 广场模板表单（新增/编辑）
const templateFormVisible = ref(false)
const currentTemplate = ref<McpSquareTemplate | null>(null)

// 广场模板详情
const detailModalVisible = ref(false)
const detailTemplate = ref<McpSquareTemplate | null>(null)

async function loadSquareData() {
  try {
    const res = await getMcpSquarePage({
      name: squareFilters.name || undefined,
      category: squareFilters.category,
      status: squareFilters.status,
      page: squarePagination.page,
      pageSize: squarePagination.pageSize,
    })
    squareList.value = res.data ?? []
    squarePagination.total = res.total ?? 0
  } catch (e) {
    console.error('加载 MCP 广场模板失败', e)
    message.error(t('mcpSquare.loadSquareFailed'))
    squareList.value = []
    squarePagination.total = 0
  }
}

function handleSquareSearch() {
  squarePagination.page = 1
  loadSquareData()
}

function handleSquareReset() {
  squareFilters.name = ''
  squareFilters.category = undefined
  squareFilters.status = undefined
  handleSquareSearch()
}

function handleSquarePageChange(page: number) {
  squarePagination.page = page
  loadSquareData()
}

function handleSquarePageSizeChange(size: number) {
  squarePagination.pageSize = size
  squarePagination.page = 1
  loadSquareData()
}

function handleInstall(tpl: McpSquareTemplate) {
  installTemplate.value = tpl
  installModalVisible.value = true
}

function handleInstallSuccess() {
  installModalVisible.value = false
  loadData()
  loadSquareData()
}

async function handleUninstall(tpl: McpSquareTemplate) {
  try {
    // 找到对应的 apiKeyId
    const key = apiKeyList.value.find(k => k.template_id === tpl.id)
    if (key) {
      await uninstallMcpSquare(key.id)
      message.success(t('mcpSquare.uninstallSuccess'))
      tpl.is_installed = false
      loadData()
      loadSquareData()
    } else {
      message.warning(t('mcpSquare.uninstallNoKey'))
    }
  } catch {
    message.error(t('mcpSquare.uninstallFailed'))
  }
}

// 广场模板 - 新增
function handleAddTemplate() {
  currentTemplate.value = null
  templateFormVisible.value = true
}

// 广场模板 - 编辑
function handleEditTemplate(tpl: McpSquareTemplate) {
  currentTemplate.value = tpl
  templateFormVisible.value = true
}

// 广场模板 - 查看详情
function handleViewDetail(tpl: McpSquareTemplate) {
  detailTemplate.value = tpl
  detailModalVisible.value = true
}

// 广场模板 - 软删除（默认）
async function handleSoftDelete(tpl: McpSquareTemplate) {
  try {
    await deleteMcpSquare(tpl.id, false)
    message.success(t('mcpSquare.deleteSuccess'))
    loadSquareData()
  } catch (e: any) {
    // 后端返回 400 时让用户选择强制删除
    const msg = e?.response?.data?.detail || t('mcpSquare.deleteFailed')
    Modal.confirm({
      title: t('mcpSquare.cannotDeleteTitle'),
      content: t('mcpSquare.cascadeDeleteConfirm', { msg }),
      okText: t('mcpSquare.forceDelete'),
      okType: 'danger',
      cancelText: t('common.cancel'),
      onOk: () => handleForceDelete(tpl, true),
    })
  }
}

// 广场模板 - 强制删除（级联）
async function handleForceDelete(tpl: McpSquareTemplate, silent = false) {
  try {
    await deleteMcpSquare(tpl.id, true)
    message.success(t('mcpSquare.forceDeleteSuccess'))
    loadSquareData()
    loadData()
  } catch {
    if (!silent) message.error(t('mcpSquare.forceDeleteFailed'))
  }
}

// ============= 连接测试 =============
const testingId = ref(0)

async function handleTestConnection(row: McpApiKey) {
  testingId.value = row.id
  try {
    const res = await testMcpConnection(row.id)
    row.health_status = res.health_status
    row.last_check_at = res.checked_at
    if (res.health_status === 'healthy') {
      message.success(t('mcpSquare.connOk', { detail: res.detail }))
    } else {
      message.warning(t('mcpSquare.connBad', { detail: res.detail }))
    }
  } catch {
    message.error(t('mcpSquare.testFailed'))
  } finally {
    testingId.value = 0
  }
}

function healthBadge(status: string): 'success' | 'error' | 'default' {
  if (status === 'healthy') return 'success'
  if (status === 'unhealthy') return 'error'
  return 'default'
}

function healthLabel(status: string): string {
  if (status === 'healthy') return t('mcpSquare.health')
  if (status === 'unhealthy') return t('mcpSquare.unhealthy')
  return t('mcpSquare.unknown')
}

onMounted(() => {
  loadData()
  loadSquareData()
})
</script>

<style scoped>
.mcp-service-management {
  padding: 16px;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.panel-header h2 {
  margin: 0 0 4px;
  font-size: 18px;
}
.panel-header .sub {
  margin: 0;
  color: var(--fg-muted);
  font-size: 13px;
}
.search-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.square-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.square-card :deep(.ant-card-body) {
  flex: 1;
}
.card-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.card-name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-desc {
  color: var(--fg-secondary);
  font-size: 13px;
  margin-bottom: 8px;
  min-height: 38px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.card-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.protocol-text {
  color: var(--fg-secondary);
  font-size: 13px;
}
.square-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
