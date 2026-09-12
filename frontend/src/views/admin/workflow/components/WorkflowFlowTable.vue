<template>
  <div>
    <a-space style="margin-bottom: 16px">
      <a-select v-model:value="filters.platform_type" placeholder="平台类型" allowClear style="width: 140px"
                :options="platformOptions" @change="loadData" />
      <a-select v-model:value="filters.flow_type" placeholder="流程类型" allowClear style="width: 140px"
                :options="flowTypeOptions" @change="loadData" />
      <a-button type="primary" @click="$emit('edit', null)">新建工作流</a-button>
    </a-space>
    <a-table :columns="columns" :data-source="data" :loading="loading" :pagination="pagination"
             @change="handleTableChange" row-key="id">
      <template #bodyCell="{ column, record }">
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
import { ref, reactive, onMounted } from 'vue'
import { listFlows, deleteFlow, getPlatformTypes } from '@/api/workflow'
import { message } from 'ant-design-vue'

const emit = defineEmits(['edit', 'test'])

const data = ref<any[]>([])
const loading = ref(false)
const filters = reactive({ platform_type: undefined as string | undefined, flow_type: undefined as string | undefined })
const pagination = reactive({ current: 1, pageSize: 20, total: 0 })
const platformOptions = ref<any[]>([])
const flowTypeOptions = ref<any[]>([])

const columns = [
  { title: '编码', dataIndex: 'flow_code', key: 'flow_code' },
  { title: '名称', dataIndex: 'flow_name', key: 'flow_name' },
  { title: '平台', dataIndex: 'platform_type', key: 'platform_type' },
  { title: '类型', dataIndex: 'flow_type', key: 'flow_type' },
  { title: '状态', key: 'is_active' },
  { title: '操作', key: 'action', width: 180 },
]

async function loadData() {
  loading.value = true
  try {
    const res = await listFlows({ ...filters, page: pagination.current, page_size: pagination.pageSize })
    data.value = res.data.items
    pagination.total = res.data.total
  } finally { loading.value = false }
}

async function loadEnums() {
  const res = await getPlatformTypes()
  platformOptions.value = res.data.platform_types.map((v: string) => ({ label: v, value: v }))
  flowTypeOptions.value = res.data.flow_types.map((v: string) => ({ label: v, value: v }))
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
