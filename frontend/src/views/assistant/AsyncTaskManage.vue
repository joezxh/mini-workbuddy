<template>
  <div class="atm">
    <a-tabs v-model:activeKey="activeTab" class="atm-tabs">
      <a-tab-pane key="async" tab="异步任务">
        <div class="atm-toolbar">
          <div class="atm-filters">
            <a-select
              v-model:value="modeFilter"
              :options="modeFilterOptions"
              style="width: 140px"
              placeholder="全部类别"
              allow-clear
              @change="onFilterChange"
            />
            <a-segmented v-model:value="filter" :options="filterOptions" @change="onFilterChange" />
          </div>
          <div class="atm-actions">
            <a-button type="primary" :loading="loading" @click="reload">刷新</a-button>
          </div>
        </div>

        <a-table
      class="atm-table"
      row-key="id"
      :columns="columns"
      :data-source="items"
      :pagination="pagination"
      :loading="loading"
      @change="onTableChange"
      @row-click="onRowClick"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-badge :status="badgeStatus(record.status)" :text="statusLabel(record.status)" />
        </template>
        <template v-else-if="column.key === 'progress'">
          <div class="atm-progress">
            <a-progress :percent="record.progress || 0" size="small" :status="progressStatus(record.status)" />
          </div>
        </template>
        <template v-else-if="column.key === 'targetMode'">
          <a-tag>{{ modeLabel(record.targetMode) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'createdAt'">
          {{ formatTime(record.submittedAt || record.startedAt) }}
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space :size="0">
            <a-button type="link" size="small" @click.stop="openDetail(record)">查看</a-button>
            <a-popconfirm
              v-if="record.status === 'failed' || record.status === 'cancelled'"
              title="复用原参数重新执行该任务？"
              @confirm="onRetry(record)"
            >
              <a-button type="link" size="small" @click.stop>重试</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
      </a-table>
      </a-tab-pane>
      <a-tab-pane key="scheduled" tab="调度任务">
        <ScheduledTaskManage />
      </a-tab-pane>
    </a-tabs>

    <a-drawer
      v-model:open="drawerOpen"
      :title="drawerTitle"
      width="720"
      @close="closeDetail"
    >
      <template v-if="current">
        <div class="atm-detail-head">
          <a-descriptions :column="2" size="small" bordered>
            <a-descriptions-item label="任务编号">{{ current.taskNo || current.id }}</a-descriptions-item>
            <a-descriptions-item label="状态">
              <a-badge :status="badgeStatus(current.status)" :text="statusLabel(current.status)" />
            </a-descriptions-item>
            <a-descriptions-item label="类型">{{ modeLabel(current.targetMode) }}</a-descriptions-item>
            <a-descriptions-item label="进度">{{ current.progress || 0 }}%</a-descriptions-item>
            <a-descriptions-item label="提交时间">{{ formatTime(current.submittedAt) }}</a-descriptions-item>
            <a-descriptions-item label="完成时间">{{ formatTime(current.finishedAt) }}</a-descriptions-item>
          </a-descriptions>

          <div class="atm-detail-ops">
            <a-button v-if="!isTerminal(current.status)" danger size="small" :loading="cancelling" @click="onCancel(current)">取消任务</a-button>
            <a-popconfirm
              v-if="current.status === 'failed' || current.status === 'cancelled'"
              title="复用原参数重新执行该任务？"
              @confirm="onRetry(current)"
            >
              <a-button type="primary" size="small" :loading="retrying">重试执行</a-button>
            </a-popconfirm>
          </div>
          <a-alert
            v-if="current.status === 'failed'"
            type="error"
            :message="current.errorMessage || '任务执行失败'"
            style="margin-bottom: 12px"
          />
        </div>

        <!-- 运行中 / 已结束：复用执行过程面板展示完整执行链路（全量，不截断） -->
        <div v-if="executionId" class="atm-detail-body">
          <DeepResearchExecutionPanel :execution-id="executionId" full />
        </div>
        <div v-else-if="current && ['queued', 'pending'].includes(current.status)" class="atm-detail-body">
          <a-empty description="任务排队中，开始执行后即可实时查看思考过程 / 执行事件 / 时间线" />
        </div>
        <div v-else-if="current && ['completed', 'failed', 'cancelled'].includes(current.status)" class="atm-detail-body">
          <a-empty description="该任务未回写执行过程 ID（多为本次改动前提交的历史任务），仅可查看最终结果" />
        </div>

        <!-- 已完成：展示最终报告 + 产物下载 -->
        <div v-if="current.status === 'completed'" class="atm-detail-body">
          <div v-if="artifacts.length" class="atm-artifacts">
            <div class="atm-section-title">研究成果文件</div>
            <ArtifactCard
              v-for="(a, i) in artifacts"
              :key="a.file_id || i"
              :artifacts="[a]"
            />
          </div>
          <div v-if="answerText" class="atm-answer">
            <div class="atm-section-title">研究结论</div>
            <div class="markdown-body" v-html="answerHtml"></div>
          </div>
        </div>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onUnmounted, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import MarkdownIt from 'markdown-it'
import { listAsyncTasks, getAsyncTask, cancelAsyncTask, retryAsyncTask } from '@/api/aiAgent'
import { getUnifiedEvents } from '@/api/agentExecution'
import type { AsyncTaskInfoDTO } from '@/api/aiAgent'
import type { ExecutionEvent } from '@/types/shared'
import DeepResearchExecutionPanel from './components/renderers/execution/DeepResearchExecutionPanel.vue'
import ArtifactCard from './components/renderers/ArtifactCard.vue'
import ScheduledTaskManage from './ScheduledTaskManage.vue'

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
const TERMINAL = ['completed', 'failed', 'cancelled']

const filter = ref<string>('all')
const filterOptions = [
  { label: '全部', value: 'all' },
  { label: '进行中', value: 'active' },
  { label: '已完成', value: 'completed' },
  { label: '失败/取消', value: 'ended' },
]

/** Tab 切换：异步任务 / 调度任务 */
const activeTab = ref<'async' | 'scheduled'>('async')
/** 任务类别过滤：深度研究 / 单智能体 / 智能体团队（清空 = 全部类别） */
const modeFilter = ref<string | undefined>(undefined)
const modeFilterOptions = [
  { label: '深度研究', value: 'deep_research' },
  { label: '单智能体', value: 'agent' },
  { label: '智能体团队', value: 'team' },
]
const retrying = ref(false)

const loading = ref(false)
const items = ref<AsyncTaskInfoDTO[]>([])
const page = reactive({ current: 1, pageSize: 10, total: 0 })

const columns = [
  { title: '任务编号', dataIndex: 'taskNo', key: 'taskNo', width: 150 },
  { title: '任务名称', dataIndex: 'taskName', key: 'taskName', ellipsis: true },
  { title: '类型', key: 'targetMode', width: 110 },
  { title: '状态', key: 'status', width: 100 },
  { title: '进度', key: 'progress', width: 160 },
  { title: '提交时间', key: 'createdAt', width: 170 },
  { title: '操作', key: 'action', width: 140, align: 'center' as const },
]

const pagination = computed(() => ({
  current: page.current,
  pageSize: page.pageSize,
  total: page.total,
  showSizeChanger: true,
  showTotal: (t: number) => `共 ${t} 条`,
}))

const drawerOpen = ref(false)
const current = ref<AsyncTaskInfoDTO | null>(null)
const cancelling = ref(false)
const executionId = ref<string | null>(null)
const artifacts = ref<any[]>([])
const answerText = ref('')
const answerHtml = computed(() => (answerText.value ? md.render(answerText.value) : ''))
const flatEvents = ref<ExecutionEvent[]>([])
const seenEventIds = reactive(new Set<string>())
let pollTimer: number | undefined

function statusLabel(s: string) {
  return ({ queued: '排队中', running: '研究中', completed: '已完成', failed: '失败', cancelled: '已取消' } as Record<string, string>)[s] || s
}
function badgeStatus(s: string) {
  return ({ queued: 'default', running: 'processing', completed: 'success', failed: 'error', cancelled: 'warning' } as Record<string, string>)[s] || 'default'
}
function progressStatus(s: string) {
  return s === 'failed' ? 'exception' : s === 'completed' ? 'success' : 'active'
}
function modeLabel(m?: string) {
  return ({ deep_research: '深度研究', agent: '智能体', team: '专家团队', skill: '技能' } as Record<string, string>)[m || ''] || (m || '—')
}
function isTerminal(s: string) {
  return TERMINAL.includes(s)
}
function formatTime(t?: string) {
  if (!t) return '—'
  const d = new Date(t)
  if (isNaN(d.getTime())) return t
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

async function reload() {
  loading.value = true
  try {
    const statusParam =
      filter.value === 'active' ? 'queued,running'
      : filter.value === 'completed' ? 'completed'
      : filter.value === 'ended' ? 'failed,cancelled'
      : undefined
    const res = await listAsyncTasks({
      status: statusParam,
      targetMode: modeFilter.value || undefined,
      page: page.current,
      size: page.pageSize,
    })
    items.value = res.items || []
    page.total = res.total || 0
  } catch (e: any) {
    message.error(e?.message || '加载任务失败')
  } finally {
    loading.value = false
  }
}

function onTableChange(p: any) {
  page.current = p.current
  page.pageSize = p.pageSize
  reload()
}

/** 类别 / 状态筛选变更：重置到第一页并刷新 */
function onFilterChange() {
  page.current = 1
  reload()
}

function onRowClick(record: AsyncTaskInfoDTO) {
  openDetail(record)
}

function openDetail(record: AsyncTaskInfoDTO) {
  current.value = { ...record }
  drawerOpen.value = true
  // 需求①：后端任务启动即回写 execution_id，运行中任务直接拾取即可实时回放三视图
  executionId.value = record.executionId ? String(record.executionId) : null
  artifacts.value = []
  answerText.value = ''
  flatEvents.value = []
  seenEventIds.clear()
  parseResultData(record.resultData)
  pollDetail()
  if (!isTerminal(record.status)) {
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = window.setInterval(pollDetail, 3000)
  }
}

function closeDetail() {
  drawerOpen.value = false
  if (pollTimer) { clearInterval(pollTimer); pollTimer = undefined }
  current.value = null
}

async function pollDetail() {
  if (!current.value) return
  try {
    const t = await getAsyncTask(current.value.id)
    current.value = { ...current.value, ...t }
    if ((t as any).executionId && !executionId.value) executionId.value = String((t as any).executionId)
    if (t.resultData) parseResultData(t.resultData)
    if (isTerminal(t.status)) {
      await pollEvents()
      if (pollTimer) { clearInterval(pollTimer); pollTimer = undefined }
    } else {
      await pollEvents()
    }
  } catch {
    // 静默重试
  }
}

async function pollEvents() {
  if (!executionId.value) return
  try {
    const res = await getUnifiedEvents(executionId.value)
    const steps = (res.steps || []) as any[]
    for (const s of steps) {
      for (const ev of (s.events || [])) {
        const key = `${s.step}-${ev.seq ?? ev.timestamp ?? Math.random()}`
        if (seenEventIds.has(key)) continue
        seenEventIds.add(key)
        flatEvents.value.push(convertToFlatEvent(ev))
      }
    }
    flatEvents.value = [...flatEvents.value]
  } catch {
    // 进度拉取失败不阻断
  }
}

function parseResultData(raw: any) {
  if (!raw) return
  let obj = raw
  if (typeof raw === 'string') {
    try { obj = JSON.parse(raw) } catch { return }
  }
  if (obj && typeof obj === 'object') {
    if (obj.execution_id) executionId.value = String(obj.execution_id)
    if (Array.isArray(obj.artifacts)) artifacts.value = obj.artifacts
    if (obj.answer) answerText.value = String(obj.answer)
  }
}

function convertToFlatEvent(raw: any): ExecutionEvent {
  const type = raw.type
  const ts = raw.timestamp || new Date().toISOString()
  if (type === 'thinking') {
    return { type: 'thinking', time: ts, message: raw.content || '', step: raw.step, title: raw.title }
  } else if (type === 'tool_call') {
    return { type: 'tool_call', time: ts, message: raw.tool_name || '', data: { tool_name: raw.tool_name, parameters: raw.parameters || raw.input || {} } }
  } else if (type === 'tool_result' || type === 'tool_error') {
    return { type: 'tool_result', time: ts, message: raw.tool_name || '', data: { tool_name: raw.tool_name, result: type === 'tool_error' ? (raw.error_message || 'Error') : (typeof raw.result === 'string' ? raw.result : JSON.stringify(raw.result)) } }
  } else if (type === 'progress') {
    return { type: 'progress', time: ts, message: raw.message || raw.stage || '' }
  } else if (type === 'artifact') {
    return { type: 'artifact', time: ts, message: raw.filename || raw.message || '' }
  }
  return { type: 'progress', time: ts, message: raw.message || '' }
}

async function onCancel(record: AsyncTaskInfoDTO) {
  cancelling.value = true
  try {
    await cancelAsyncTask(record.id)
    message.success('已发送取消请求')
    await pollDetail()
    await reload()
  } catch (e: any) {
    message.error(e?.message || '取消失败')
  } finally {
    cancelling.value = false
  }
}

/** 手动重试失败/已取消任务：复用原参数重新投递 */
async function onRetry(record: AsyncTaskInfoDTO) {
  retrying.value = true
  try {
    await retryAsyncTask(record.id)
    message.success('已重新提交执行')
    await reload()
    if (current.value && current.value.id === record.id) await pollDetail()
  } catch (e: any) {
    message.error(e?.message || '重试失败')
  } finally {
    retrying.value = false
  }
}

const drawerTitle = computed(() => `任务详情 · ${current.value?.taskName || current.value?.taskNo || ''}`)

onMounted(() => {
  void reload()
  // 列表级轮询：自动刷新进行中任务进度
  const listTimer = window.setInterval(() => {
    if (activeTab.value === 'async' && filter.value !== 'completed' && filter.value !== 'ended') void reload()
  }, 5000)
  onUnmounted(() => {
    clearInterval(listTimer)
    if (pollTimer) clearInterval(pollTimer)
  })
})
</script>

<style scoped>
.atm { padding: 16px 20px; }
.atm-tabs :deep(.ant-tabs-content) { padding-top: 4px; }
.atm-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.atm-filters { display: flex; gap: 12px; align-items: center; }
.atm-actions { display: flex; gap: 12px; align-items: center; }
.atm-table :deep(.ant-table-tbody > tr) { cursor: pointer; }
.atm-progress { width: 130px; }
.atm-detail-head { margin-bottom: 16px; }
.atm-detail-ops { margin: 12px 0; }
.atm-detail-body { margin-top: 16px; }
.atm-section-title { font-weight: 600; margin: 12px 0 8px; color: #333; }
.atm-answer .markdown-body { background: #fafafa; border: 1px solid #f0f0f0; border-radius: 8px; padding: 12px 16px; }
</style>
