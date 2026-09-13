<template>
  <a-modal
    v-model:open="visible"
    :title="t('apiKeyMgmt.listTitle', { name: apiKey?.name || '' })"
    width="900px"
    :footer="null"
    @cancel="visible = false"
  >
    <div class="model-list-container">
      <!-- 操作栏 -->
      <div class="action-bar">
        <a-input-search
          v-model:value="filters.name"
          :placeholder="t('apiKeyMgmt.searchModel')"
          allow-clear
          style="width:200px"
          @search="loadData"
          @clear="loadData"
        />
        <a-space>
          <a-button :disabled="dataList.length === 0" @click="openTestModal">
            <ExperimentOutlined /> {{ t('apiKeyMgmt.testModel') }}
          </a-button>
          <a-button type="primary" @click="showCreateModal">
            <template #icon><PlusOutlined /></template>
            {{ t('apiKeyMgmt.addModel') }}
          </a-button>
        </a-space>
      </div>

      <!-- 模型列表 -->
      <a-table
        :columns="columns"
        :data-source="dataList"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        size="small"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'model'">
            <a-tooltip :title="record.model">
              <span class="model-cell">{{ record.model }}</span>
            </a-tooltip>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="record.status === 1 ? 'success' : 'error'">
              {{ record.status === 1 ? t('apiKeyMgmt.enabled') : t('apiKeyMgmt.disabled') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'is_default'">
            <a-tooltip :title="record.is_default ? t('apiKeyMgmt.isDefaultTip') : t('apiKeyMgmt.setDefaultTip')">
              <StarFilled v-if="record.is_default" style="color: var(--warn); font-size: 16px;" />
              <StarOutlined v-else style="color: var(--fg-muted); font-size: 16px; cursor: pointer;" @click="setDefault(record)" />
            </a-tooltip>
          </template>
          <template v-else-if="column.key === 'temperature'">
            {{ record.temperature !== null ? record.temperature : '-' }}
          </template>
          <template v-else-if="column.key === 'max_tokens'">
            {{ record.max_tokens !== null ? record.max_tokens : '-' }}
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-space>
              <a-button type="link" size="small" @click="handleEdit(record)">{{ t('common.edit') }}</a-button>
              <a-button
                type="link"
                size="small"
                @click="setDefault(record)"
                :style="{ color: record.is_default ? 'var(--warn)' : 'var(--accent)' }"
                :disabled="record.is_default"
              >
                <StarFilled v-if="record.is_default" /> {{ record.is_default ? t('apiKeyMgmt.defaultLabel') : t('apiKeyMgmt.setDefaultLabel') }}
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
                :title="t('apiKeyMgmt.deleteModelConfirm')"
                :ok-text="t('common.confirm')"
                :cancel-text="t('common.cancel')"
                @confirm="handleDelete(record)"
              >
                <a-button type="link" size="small" danger>{{ t('common.delete') }}</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 新增/编辑弹窗 -->
    <ChatModelFormModal
      v-model:open="formVisible"
      :model="editingModel"
      :key-id="keyId"
      :platform="apiKey?.platform"
      @success="loadData"
    />

    <!-- 模型测试弹窗 -->
    <ModelTestModal
      v-model:open="testModalVisible"
      :models="dataList"
    />
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { PlusOutlined, ExperimentOutlined, StarFilled, StarOutlined } from '@ant-design/icons-vue'
import { getChatModelPage, updateChatModel, deleteChatModel, setChatModelDefault, type AiChatModel } from '@/api/ai-apikey'
import ChatModelFormModal from './ChatModelFormModal.vue'
import ModelTestModal from './ModelTestModal.vue'
import type { TableProps } from 'ant-design-vue'

const props = defineProps<{
  open: boolean
  apiKey?: AiApiKey | null
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'success'): void
}>()

interface AiApiKey {
  id: number
  name: string
  platform: string
}

const { t } = useI18n()

const visible = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val)
})

const keyId = computed(() => props.apiKey?.id || 0)

// 列表数据
const loading = ref(false)
const dataList = ref<AiChatModel[]>([])
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => t('common.total', { total })
})

// 筛选
const filters = reactive({
  name: ''
})

// 表格列
const columns = computed(() => [
  { title: t('apiKeyMgmt.colModelName'), dataIndex: 'name', key: 'name', width: 150, ellipsis: true },
  { title: t('apiKeyMgmt.colModelId'), dataIndex: 'model', key: 'model', width: 180, ellipsis: true },
  { title: t('apiKeyMgmt.colType'), dataIndex: 'type', key: 'type', width: 80, align: 'center' as const },
  { title: t('apiKeyMgmt.colDefault'), key: 'is_default', width: 70, align: 'center' as const },
  { title: t('apiKeyMgmt.colTemperature'), dataIndex: 'temperature', key: 'temperature', width: 80, align: 'center' as const },
  { title: t('apiKeyMgmt.colMaxTokens'), dataIndex: 'max_tokens', key: 'max_tokens', width: 100, align: 'center' as const },
  { title: t('apiKeyMgmt.colStatus'), key: 'status', width: 80, align: 'center' as const },
  { title: t('apiKeyMgmt.colActions'), key: 'actions', width: 240, align: 'center' as const }
])

// 新增/编辑弹窗
const formVisible = ref(false)
const editingModel = ref<AiChatModel | null>(null)

// 测试弹窗
const testModalVisible = ref(false)

const openTestModal = () => {
  testModalVisible.value = true
}

const loadData = async () => {
  if (!keyId.value) return
  
  loading.value = true
  try {
    const res = await getChatModelPage({
      keyId: keyId.value,
      name: filters.name || undefined,
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

// 监听 open 变化，加载数据
watch(
  () => props.open,
  (val) => {
    if (val && keyId.value) {
      pagination.current = 1
      filters.name = ''
      loadData()
    }
  }
)

// 表格变化
const handleTableChange: TableProps['onChange'] = (pag) => {
  pagination.current = pag.current || 1
  pagination.pageSize = pag.pageSize || 10
  loadData()
}

// 显示创建弹窗
const showCreateModal = () => {
  editingModel.value = null
  formVisible.value = true
}

// 编辑
const handleEdit = (record: AiChatModel) => {
  editingModel.value = record
  formVisible.value = true
}

// 切换状态
const toggleStatus = async (record: AiChatModel) => {
  try {
    await updateChatModel({
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
const handleDelete = async (record: AiChatModel) => {
  try {
    await deleteChatModel(record.id)
    message.success(t('apiKeyMgmt.deleteSuccess'))
    loadData()
  } catch (e: any) {
    message.error(e.message || t('apiKeyMgmt.deleteFailed'))
  }
}

// 设为默认（含连通性检测）
const setDefault = async (record: AiChatModel) => {
  if (record.is_default) return
  try {
    await setChatModelDefault(record.id)
    message.success(t('apiKeyMgmt.setDefaultSuccess'))
    loadData()
  } catch (e: any) {
    message.error(e.message || t('apiKeyMgmt.setDefaultFailed'))
  }
}
</script>

<style lang="less" scoped>
.model-list-container {
  .action-bar {
    display: flex;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .model-cell {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--fg-secondary);
    background: var(--bg-input);
    padding: 2px 6px;
    border-radius: 4px;
  }
}
</style>
