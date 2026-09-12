<template>
  <a-modal
    :open="visible"
    :title="t('mcpSquare.clientManageTitle', { name: apiKeyName })"
    width="900px"
    :footer="null"
    @cancel="handleCancel"
  >
    <div class="client-header">
      <a-button type="primary" size="small" @click="showCreate">
        <template #icon><PlusOutlined /></template>
        {{ t('mcpSquare.addClient') }}
      </a-button>
    </div>
    <a-table
      :columns="columns"
      :data-source="list"
      :loading="loading"
      :pagination="false"
      row-key="id"
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-badge :status="record.status === 1 ? 'success' : 'default'" :text="record.status === 1 ? t('skillHub.enabled') : t('skillHub.disabled')" />
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="handleEdit(record)">{{ t('common.edit') }}</a-button>
            <a-popconfirm :title="t('mcpSquare.deleteConfirm')" @confirm="handleDelete(record)">
              <a-button type="link" size="small" danger>{{ t('common.delete') }}</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- Client 表单弹窗 -->
    <McpClientFormModal
      v-model:visible="clientFormVisible"
      :record="currentClient"
      :api-key-id="apiKeyId"
      @success="loadData"
    />
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import McpClientFormModal from './McpClientFormModal.vue'
import { getMcpClientPage, deleteMcpClient, type McpClient } from '@/api/ai-mcp'

const props = defineProps<{
  visible: boolean
  apiKeyId: number
  apiKeyName: string
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const { t } = useI18n()

const loading = ref(false)
const list = ref<McpClient[]>([])
const clientFormVisible = ref(false)
const currentClient = ref<McpClient | null>(null)

const columns = computed(() => [
  { title: t('mcpSquare.name'), key: 'name', dataIndex: 'name', width: 160 },
  { title: t('mcpSquare.clientType'), key: 'client_type', dataIndex: 'client_type', width: 80 },
  { title: t('mcpSquare.mcpType'), key: 'mcp_type', dataIndex: 'mcp_type', width: 80 },
  { title: t('skillHub.version'), key: 'version', dataIndex: 'version', width: 80 },
  { title: t('skillHub.status'), key: 'status', width: 80 },
  { title: t('mcpSquare.creator'), key: 'creator', dataIndex: 'creator', width: 100 },
  { title: t('mcpSquare.action'), key: 'action', width: 140 },
])

async function loadData() {
  if (!props.apiKeyId) return
  loading.value = true
  try {
    const res = await getMcpClientPage({ api_key_id: props.apiKeyId, page: 1, pageSize: 100 })
    list.value = res.data ?? []
  } catch (e) {
    console.error('加载 Client 列表失败', e)
    message.error(t('mcpSquare.loadClientFailed'))
    list.value = []
  } finally {
    loading.value = false
  }
}

function showCreate() {
  currentClient.value = null
  clientFormVisible.value = true
}

function handleEdit(record: McpClient) {
  currentClient.value = record
  clientFormVisible.value = true
}

async function handleDelete(record: McpClient) {
  try {
    await deleteMcpClient(record.id)
    message.success(t('mcpSquare.deleteSuccess'))
    loadData()
  } catch {
    message.error(t('mcpSquare.deleteFailed'))
  }
}

function handleCancel() {
  emit('update:visible', false)
}

watch(() => props.visible, (val) => {
  if (val) loadData()
})
</script>

<style scoped>
.client-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}
</style>
