<!-- HITL 审批列表（spec 步骤三 4.4）—— agent_hitl_pause 只读表格 -->
<template>
  <div class="sa-hitl">
    <div class="sa-hitl__header">
      <div>
        <h2 class="sa-hitl__title">HITL 审批</h2>
        <span class="sa-hitl__sub">Agent 人机交互暂停记录（只读）</span>
      </div>
      <a-space>
        <a-select
          v-model:value="statusFilter"
          style="width: 160px"
          placeholder="全部状态"
          allow-clear
          @change="load(1)"
        >
          <a-select-option value="waiting">waiting（待确认）</a-select-option>
          <a-select-option value="approved">approved（已通过）</a-select-option>
          <a-select-option value="rejected">rejected（已拒绝）</a-select-option>
          <a-select-option value="interrupted">interrupted（已中断）</a-select-option>
        </a-select>
        <a-button :loading="loading" @click="load()">刷新</a-button>
      </a-space>
    </div>

    <a-table
      :columns="columns"
      :data-source="rows"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      size="middle"
      @change="onTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ record.status }}</a-tag>
        </template>
        <template v-else-if="column.key === 'tool_calls'">
          <span v-if="pauseReason(record)">{{ pauseReason(record) }}</span>
          <span v-else style="color: var(--fg-muted)">—</span>
        </template>
        <template v-else-if="column.key === 'timeout_at'">
          {{ record.timeout_at || '—' }}
        </template>
        <template v-else-if="column.key === 'answered_at'">
          {{ record.answered_at || '—' }}
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { listHitlPauses, type HitlPause } from '@/api/super-agent'

const loading = ref(false)
const rows = ref<HitlPause[]>([])
const statusFilter = ref<string>()

const columns = [
  { title: 'ID', key: 'id', dataIndex: 'id', width: 80 },
  { title: '执行 ID', key: 'execution_id', dataIndex: 'execution_id', width: 200 },
  { title: '状态', key: 'status', dataIndex: 'status', width: 110 },
  { title: '暂停原因（待确认工具）', key: 'tool_calls' },
  { title: '超时提示时刻', key: 'timeout_at', dataIndex: 'timeout_at', width: 170 },
  { title: '应答时刻', key: 'answered_at', dataIndex: 'answered_at', width: 170 },
  { title: '创建时间', key: 'created_at', dataIndex: 'created_at', width: 170 },
]

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showTotal: (t: number) => `共 ${t} 条`,
})

function statusColor(status: string): string {
  switch (status) {
    case 'waiting': return 'orange'
    case 'approved': return 'green'
    case 'rejected': return 'red'
    case 'interrupted': return 'default'
    default: return 'blue'
  }
}

/** 暂停原因：从待确认工具调用列表提取可读摘要（工具名 + 参数截断） */
function pauseReason(record: HitlPause): string {
  const calls = record.tool_calls
  if (!Array.isArray(calls) || !calls.length) return ''
  return calls
    .map((c: any) => {
      const name = c?.name || c?.tool || c?.tool_name || '未知工具'
      let args = ''
      const raw = c?.args ?? c?.arguments ?? c?.input
      if (raw !== undefined && raw !== null) {
        try {
          args = JSON.stringify(raw)
        } catch {
          args = String(raw)
        }
      }
      if (args.length > 80) args = args.slice(0, 80) + '…'
      return args ? `${name}(${args})` : name
    })
    .join('；')
}

async function load(page?: number) {
  loading.value = true
  try {
    if (page) pagination.current = page
    const res = await listHitlPauses({
      status: statusFilter.value || undefined,
      page: pagination.current,
      pageSize: pagination.pageSize,
    })
    rows.value = res.data || []
    pagination.total = res.total || 0
  } catch (e: any) {
    rows.value = []
    pagination.total = 0
    console.error('HITL 列表加载失败:', e?.message || e)
  } finally {
    loading.value = false
  }
}

function onTableChange(pag: any) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  load()
}

onMounted(() => load())
</script>

<style scoped lang="less">
.sa-hitl {
  padding: 16px 24px;
  height: 100%;
  overflow-y: auto;
}
.sa-hitl__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.sa-hitl__title {
  margin: 0;
  font-size: 18px;
}
.sa-hitl__sub {
  font-size: 12px;
  color: var(--fg-muted);
}
</style>
