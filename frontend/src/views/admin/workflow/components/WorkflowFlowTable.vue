<template>
  <div>
    <a-space style="margin-bottom: 16px">
      <a-select v-model:value="filters.platform_type" placeholder="平台类型" allowClear style="width: 140px" @change="loadData">
        <a-select-option v-for="it in platformItems" :key="it.item_code" :value="it.item_code">{{ it.item_name }}</a-select-option>
      </a-select>
      <a-select v-model:value="filters.flow_type" placeholder="流程类型" allowClear style="width: 140px" @change="loadData">
        <a-select-option v-for="it in flowTypeItems" :key="it.item_code" :value="it.item_code">{{ it.item_name }}</a-select-option>
      </a-select>
      <a-select v-model:value="filters.workflow_category" placeholder="流程类别" allowClear style="width: 140px" @change="loadData">
        <a-select-option v-for="it in categoryItems" :key="it.item_code" :value="it.item_code">{{ it.item_name }}</a-select-option>
      </a-select>
      <a-button type="primary" @click="$emit('edit', null)">新建工作流</a-button>
    </a-space>
    <a-table :columns="columns" :data-source="data" :loading="loading" :pagination="pagination"
             @change="handleTableChange" row-key="id">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'platform_type'">
          {{ dictLabel(DictType.WORKFLOW_PLATFORM, record.platform_type) }}
        </template>
        <template v-if="column.key === 'workflow_category'">
          <a-tag :color="dictColor(DictType.WORKFLOW_CATEGORY, record.workflow_category)">
            {{ dictLabel(DictType.WORKFLOW_CATEGORY, record.workflow_category) || '-' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'is_active'">
          <a-tag :color="record.is_active ? 'green' : 'default'">{{ record.is_active ? '启用' : '禁用' }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a @click="$emit('edit', record)">编辑</a>
            <a @click="$emit('test', record.id)">测试</a>
            <a-popconfirm title="确认删除？" @confirm="handleDelete(record.id)">
              <a style="color: #ff4d4f">删除</a>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { listFlows, deleteFlow } from '@/api/workflow'
import { DictType } from '@/api/dictionary'
import { loadAdminDicts, dictItems, dictLabel, dictColor } from '@/composables/useAdminDict'
import { message } from 'ant-design-vue'

const emit = defineEmits(['edit', 'test'])

const data = ref<any[]>([])
const loading = ref(false)
const filters = reactive({
  platform_type: undefined as string | undefined,
  flow_type: undefined as string | undefined,
  workflow_category: undefined as string | undefined,
})
const pagination = reactive({ current: 1, pageSize: 20, total: 0 })

const platformItems = computed(() => dictItems(DictType.WORKFLOW_PLATFORM))
const flowTypeItems = computed(() => dictItems(DictType.FLOW_TYPE))
const categoryItems = computed(() => dictItems(DictType.WORKFLOW_CATEGORY))

const columns = [
  { title: '编码', dataIndex: 'flow_code', key: 'flow_code', width: 140 },
  { title: '名称', dataIndex: 'flow_name', key: 'flow_name', width: 160 },
  { title: '平台', key: 'platform_type', width: 90 },
  { title: '类型', dataIndex: 'flow_type', key: 'flow_type', width: 130 },
  { title: '类别', key: 'workflow_category', width: 110 },
  { title: 'API 基地址', dataIndex: 'base_url', key: 'base_url', ellipsis: true },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '状态', key: 'is_active', width: 90 },
  { title: '操作', key: 'action', width: 180, fixed: 'right' },
]

async function loadData() {
  loading.value = true
  try {
    const res = await listFlows({ ...filters, page: pagination.current, page_size: pagination.pageSize })
    data.value = res.items
    pagination.total = res.total
  } finally { loading.value = false }
}

async function loadEnums() {
  loadAdminDicts([DictType.WORKFLOW_PLATFORM, DictType.FLOW_TYPE, DictType.WORKFLOW_CATEGORY])
}

async function handleDelete(id: number) {
  await deleteFlow(id)
  message.success('已删除')
  loadData()
}

function handleTableChange(pag: any) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadData()
}

onMounted(() => { loadData(); loadEnums() })
</script>
