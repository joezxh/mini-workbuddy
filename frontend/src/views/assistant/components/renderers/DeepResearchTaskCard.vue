<!--
  DeepResearchTaskCard.vue — 深度研究后台异步任务卡片

  职责：
  1. 提交后即渲染，轮询任务状态（queued → running → completed/failed/cancelled），支持取消；
  2. 一旦后端回写 execution_id，持续（每 3s）拉取研究进度事件，实时渲染 DeepResearchExecutionPanel；
  3. 完成后展示研究结论（Markdown）+ 产物卡片（ArtifactCard，可下载报告）。
  进度事件由后端 deep_research handler 经 ExecutionEventService 落库，前端通过
  /agent-execution/{id}/unified-events 拉取，实现「实时在线查看 + 事后回放」。
-->
<template>
  <div class="deep-research-task-card" :class="{ done: isDone }">
    <!-- 头部：状态 + 取消 -->
    <div class="drt-head">
      <FileSearchOutlined class="drt-icon" />
      <span class="drt-title">{{ task.taskName || '深度研究' }}</span>
      <a-tag :color="statusColor" size="small" class="drt-status">{{ statusLabel(task.status) }}</a-tag>
      <span class="drt-progress-pct">{{ task.progress || 0 }}%</span>
      <a-progress :percent="task.progress || 0" :show-info="false" size="small" class="drt-bar" />
      <a-button
        v-if="!isDone"
        size="small" type="text" danger
        :loading="cancelling"
        @click="onCancel"
      >取消</a-button>
      <a-button
        size="small" type="link"
        @click="openDetail"
      ><FullscreenOutlined /> 查看完整过程</a-button>
    </div>

    <!-- 完整执行过程查看（跳转式 Drawer，与「我的异步任务」详情一致，确保三视图全量可追溯） -->
    <a-drawer
      v-model:open="detailOpen"
      :title="`深度研究过程 · ${task.taskName || task.taskNo || ''}`"
      width="760"
      @close="detailOpen = false"
    >
      <a-descriptions :column="2" size="small" bordered>
        <a-descriptions-item label="任务编号">{{ task.taskNo || task.taskId }}</a-descriptions-item>
        <a-descriptions-item label="状态">
          <a-tag :color="statusColor" size="small">{{ statusLabel(task.status) }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="进度">{{ task.progress || 0 }}%</a-descriptions-item>
        <a-descriptions-item label="提交时间">{{ submittedAtText }}</a-descriptions-item>
      </a-descriptions>

      <div v-if="executionId" class="drt-detail-body">
        <DeepResearchExecutionPanel :execution-id="executionId" :streaming="!isDone" full />
      </div>
      <a-empty v-else description="暂无执行过程数据" />

      <div v-if="isDone" class="drt-detail-extra">
        <div v-if="artifacts.length" class="drt-artifacts">
          <div class="drt-section-title">研究成果文件</div>
          <ArtifactCard
            v-for="(a, i) in artifacts"
            :key="a.file_id || i"
            :artifacts="[a]"
          />
        </div>
        <div v-if="answerHtml" class="drt-answer" v-html="answerHtml" />
      </div>
    </a-drawer>

    <!-- 实时进度面板 -->
    <DeepResearchExecutionPanel
      v-if="flatEvents.length || executionId"
      :execution-id="executionId || undefined"
      :events="flatEvents"
      :streaming="!isDone"
    />

    <!-- 完成后：结论 + 产物 -->
    <div v-if="isDone" class="drt-result">
      <div v-if="answerHtml" class="drt-answer" v-html="answerHtml" />
      <div v-if="artifacts.length" class="drt-artifacts">
        <ArtifactCard
          v-for="(a, i) in artifacts"
          :key="a.file_id || i"
          :artifacts="[a]"
        />
      </div>
      <a-empty v-if="!answerHtml && !artifacts.length" description="研究完成，无可用结果" />
    </div>

    <div v-if="task.status === 'failed'" class="drt-error">
      <a-alert type="error" :message="task.errorMessage || '研究失败'" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { FileSearchOutlined, FullscreenOutlined } from '@ant-design/icons-vue'
import MarkdownIt from 'markdown-it'
import type { AsyncTaskInfo } from './../types'
import type { ExecutionEvent } from '@/types/shared'
import { getAsyncTask, cancelAsyncTask } from '@/api/aiAgent'
import { getUnifiedEvents } from '@/api/agentExecution'
import DeepResearchExecutionPanel from './execution/DeepResearchExecutionPanel.vue'
import ArtifactCard from './ArtifactCard.vue'

const props = defineProps<{ task: AsyncTaskInfo; active?: boolean }>()
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

function _fmtTime(t?: string) {
  if (!t) return '—'
  const d = new Date(t)
  if (isNaN(d.getTime())) return t
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

/** 详情抽屉展示的提交时间（预计算，避免在模板内调用函数） */
const submittedAtText = computed(() => _fmtTime(props.task.submittedAt))

const TERMINAL = ['completed', 'failed', 'cancelled']
let taskTimer: number | undefined
let eventTimer: number | undefined
const cancelling = ref(false)
const detailOpen = ref(false)

function openDetail() {
  detailOpen.value = true
  // 确保 executionId 已解析（若尚未从 resultData 拿到，立即补拉一次任务）
  if (!executionId.value && props.task.resultData) parseResultData(props.task.resultData)
  if (!executionId.value) pollTask()
}

const isDone = computed(() => TERMINAL.includes(props.task.status))
const statusColor = computed(() =>
  ({ queued: 'default', running: 'processing', completed: 'success', failed: 'error', cancelled: 'warning' }[props.task.status] || 'default')
)

function statusLabel(s: string) {
  return ({ queued: '排队中', running: '研究中', completed: '已完成', failed: '失败', cancelled: '已取消' } as Record<string, string>)[s] || s
}

// ── 解析后端 result_data（JSON 字符串：{execution_id, artifacts, answer}）──
// 需求①：后端在任务启动时即写入 execution_id（agent_async_task.execution_id），
// 运行中即可拿到并实时回放三视图，无需等待任务完成。
const executionId = ref<string | null>(props.task.executionId ?? null)
// 外部轮询更新 props.task.executionId 时同步拾取
watch(
  () => props.task.executionId,
  (v) => {
    if (v && !executionId.value) executionId.value = String(v)
  },
)
const artifacts = ref<any[]>([])
const answerText = ref('')
const answerHtml = computed(() => (answerText.value ? md.render(answerText.value) : ''))

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

// 与 DeepResearchExecutionPanel 内部 convertToFlatEvent 保持一致
function convertToFlatEvent(raw: any): ExecutionEvent {
  const type = raw.event_type || raw.type
  const ts = raw.timestamp || ''
  if (type === 'llm_think' || type === 'research_plan' || type === 'thinking') {
    return { type: 'thinking', time: ts, message: raw.detail || raw.content || '', step: raw.seq, title: raw.title || `步骤 ${raw.seq}` }
  } else if (type === 'model_call' || type === 'tool_call') {
    return { type: 'tool_call', time: ts, message: raw.title || '调用大模型', data: { tool_name: raw.title || 'model_call', parameters: raw.parameters || raw.input || {} } }
  } else if (type === 'tool_result' || type === 'tool_error') {
    return { type: 'tool_result', time: ts, message: raw.title || '', data: { tool_name: raw.title || '', result: type === 'tool_error' ? (raw.error_message || 'Error') : (typeof raw.detail === 'string' ? raw.detail : JSON.stringify(raw.detail || '')) } }
  } else if (type === 'progress' || type === 'run_start' || type === 'engine_decision' || type === 'artifact') {
    if (type === 'artifact') {
      return { type: 'artifact', time: ts, message: raw.title || raw.detail || '产物' }
    }
    return { type: 'progress', time: ts, message: raw.title || raw.detail || raw.message || '' }
  }
  return { type: 'progress', time: ts, message: raw.title || raw.detail || raw.message || '' }
}

const flatEvents = ref<ExecutionEvent[]>([])
const seenEventIds = reactive(new Set<string>())

async function pollEvents() {
  if (!executionId.value) return
  try {
    const res = await getUnifiedEvents(executionId.value)
    const steps = (res.steps || []) as any[]
    // unified-events 返回扁平 step 数组：{seq, event_type, title, detail, ...}
    for (const s of steps) {
      const key = `${s.seq ?? Math.random()}`
      if (seenEventIds.has(key)) continue
      seenEventIds.add(key)
      flatEvents.value.push(convertToFlatEvent(s))
    }
    flatEvents.value = [...flatEvents.value]
  } catch {
    // 进度拉取失败不阻断，下一轮重试
  }
}

async function pollTask() {
  try {
    const t = await getAsyncTask(props.task.taskId)
    props.task.status = t.status as AsyncTaskInfo['status']
    props.task.progress = t.progress ?? props.task.progress
    props.task.errorMessage = (t as any).errorMessage || props.task.errorMessage
    if ((t as any).executionId && !executionId.value) {
      executionId.value = String((t as any).executionId)
      props.task.executionId = executionId.value
    }
    if (t.resultData) {
      props.task.resultData = t.resultData
      parseResultData(t.resultData)
    }
    if (TERMINAL.includes(t.status)) {
      if (eventTimer) { clearInterval(eventTimer); eventTimer = undefined }
      await pollEvents() // 终态前最后补齐一次进度
      return
    }
    if (!eventTimer && executionId.value) {
      await pollEvents()
      eventTimer = window.setInterval(pollEvents, 3000)
    } else if (executionId.value && !eventTimer) {
      eventTimer = window.setInterval(pollEvents, 3000)
    }
  } catch {
    // 静默重试
  }
}

async function onCancel() {
  cancelling.value = true
  try {
    await cancelAsyncTask(props.task.taskId)
    props.task.status = 'cancelled'
  } catch (e: any) {
    message.error(e?.message || '取消失败')
  } finally {
    cancelling.value = false
  }
}

// 启动轮询
pollTask()
taskTimer = window.setInterval(pollTask, 3000)

onUnmounted(() => {
  if (taskTimer) clearInterval(taskTimer)
  if (eventTimer) clearInterval(eventTimer)
})
</script>

<style scoped>
.deep-research-task-card {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  background: var(--bg-input);
}
.drt-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.drt-icon { color: var(--info); }
.drt-title { font-weight: 600; }
.drt-progress-pct { font-size: 12px; color: var(--fg-secondary); margin-left: auto; }
.drt-bar { flex: 1 1 120px; min-width: 100px; }
.drt-result { margin-top: 12px; }
.drt-answer {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
  font-size: 13px;
  line-height: 1.7;
}
.drt-artifacts { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
.drt-error { margin-top: 10px; }
.drt-detail-body { margin-top: 16px; }
.drt-detail-extra { margin-top: 16px; }
.drt-section-title { font-weight: 600; margin: 12px 0 8px; color: var(--fg); }
</style>
