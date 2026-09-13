<!-- frontend/src/views/admin/workflow/components/WorkflowExecutionTable.vue -->
<template>
  <div>
    <a-space style="margin-bottom: 16px">
      <a-select v-model:value="filterStatus" placeholder="状态" allowClear style="width: 140px" @change="loadData">
        <a-select-option v-for="it in statusItems" :key="it.item_code" :value="it.item_code">{{ it.item_name }}</a-select-option>
      </a-select>
    </a-space>
    <a-table :columns="columns" :data-source="data" :loading="loading" :pagination="pagination"
             @change="handleTableChange" row-key="id">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="dictColor(DictType.WORKFLOW_EXEC_STATUS, record.status)">{{ dictLabel(DictType.WORKFLOW_EXEC_STATUS, record.status) }}</a-tag>
        </template>
        <template v-if="column.key === 'latency_ms'">
          {{ record.latency_ms ? `${record.latency_ms} ms` : '-' }}
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { listExecutions } from '@/api/workflow'
import { DictType } from '@/api/dictionary'
import { loadAdminDicts, dictItems, dictLabel, dictColor } from '@/composables/useAdminDict'

const data = ref<any[]>([])
const loading = ref(false)
const filterStatus = ref<string | undefined>(undefined)
const statusItems = computed(() => dictItems(DictType.WORKFLOW_EXEC_STATUS))
const pagination = reactive({ current: 1, pageSize: 20, total: 0 })

const columns = [
  { title: 'ID', dataIndex: 'id', width: 80 },
  { title: 'Flow ID', dataIndex: 'flow_id', width: 100 },
  { title: '状态', key: 'status', width: 100 },
  { title: '耗时', key: 'latency_ms', width: 120 },
  { title: '重试', dataIndex: 'retry_count', width: 80 },
  { title: '创建时间', dataIndex: 'created_at', width: 180 },
]

async function loadData() {
  loading.value = true
  try {
    const res = await listExecutions({ status: filterStatus.value, page: pagination.current, page_size: pagination.pageSize })
    data.value = res.data.items
    pagination.total = res.data.total
  } finally { loading.value = false }
}

function handleTableChange(pag: any) {
  pagination.current = pag.current; pagination.pageSize = pag.pageSize; loadData()
}

onMounted(() => {
  loadAdminDicts([DictType.WORKFLOW_EXEC_STATUS])
  loadData()
})
</script>
