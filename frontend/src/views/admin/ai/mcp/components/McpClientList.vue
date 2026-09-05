<template>
  <a-modal
    :open="visible"
    :title="`Client 管理 - ${apiKeyName}`"
    width="900px"
    :footer="null"
    @cancel="handleCancel"
  >
    <div class="client-header">
      <a-button type="primary" size="small" @click="showCreate">
        <template #icon><PlusOutlined /></template>
        新增 Client
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
          <a-badge :status="record.status === 1 ? 'success' : 'default'" :text="record.status === 1 ? '启用' : '禁用'" />
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" size="small" @click="handleEdit(record)">编辑</a-button>
            <a-popconfirm title="确定删除？" @confirm="handleDelete(record)">
              <a-button type="link" size="small" danger>删除</a-button>
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
import { ref, watch } from 'vue'
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

const loading = ref(false)
const list = ref<McpClient[]>([])
const clientFormVisible = ref(false)
const currentClient = ref<McpClient | null>(null)

const columns = [
  { title: '名称', key: 'name', dataIndex: 'name', width: 160 },
  { title: '类型', key: 'client_type', dataIndex: 'client_type', width: 80 },
  { title: '应用类别', key: 'mcp_type', dataIndex: 'mcp_type', width: 80 },
  { title: '版本', key: 'version', dataIndex: 'version', width: 80 },
  { title: '状态', key: 'status', width: 80 },
  { title: '创建人', key: 'creator', dataIndex: 'creator', width: 100 },
  { title: '操作', key: 'action', width: 140 },
]

async function loadData() {
  if (!props.apiKeyId) return
  loading.value = true
  try {
    const res = await getMcpClientPage({ api_key_id: props.apiKeyId, page: 1, pageSize: 100 })
    list.value = res.data ?? []
  } catch (e) {
    console.error('加载 Client 列表失败', e)
    message.error('加载 Client 列表失败')
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
    message.success('删除成功')
    loadData()
  } catch {
    message.error('删除失败')
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
