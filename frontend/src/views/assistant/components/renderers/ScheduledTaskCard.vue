<template>
  <div class="task-card" :class="'st-'+task.status">
    <div class="tk-header">
      <span class="tk-icon"><ScheduleOutlined /></span>
      <span class="tk-name">{{ task.taskName || ('异步任务 #'+task.taskId) }}</span>
      <a-tag :color="statusColor(task.status)" class="tk-status">{{ statusLabel(task.status) }}</a-tag>
      <span class="tk-no" v-if="task.taskNo">{{ task.taskNo }}</span>
    </div>

    <a-progress :percent="task.progress" :status="progStatus" size="small" />

    <div class="tk-meta">
      <span>优先级 {{ task.priority ?? '-' }}</span>
      <span v-if="task.submittedAt">提交 {{ task.submittedAt }}</span>
      <span v-if="task.finishedAt">完成 {{ task.finishedAt }}</span>
    </div>

    <div v-if="task.errorMessage && task.status==='failed'" class="tk-error">
      {{ task.errorMessage }}
    </div>

    <div v-if="task.resultData?.answer" class="tk-result">
      <a-collapse ghost>
        <a-collapse-panel key="result" header="查看执行结果">
          <div class="tk-result-body" v-html="md.render(task.resultData.answer)"></div>
        </a-collapse-panel>
      </a-collapse>
    </div>

    <div class="tk-actions" v-if="['queued','running'].includes(task.status)">
      <a-button size="small" danger @click="onCancel">取消任务</a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import { ScheduleOutlined } from '@ant-design/icons-vue'
import MarkdownIt from 'markdown-it'
import type { AsyncTaskInfo } from './../types'
import { getAsyncTask, cancelAsyncTask } from '@/api/aiAgent'

const props = defineProps<{ task: AsyncTaskInfo; active?: boolean }>()
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const TERMINAL = ['completed', 'failed', 'cancelled']
let timer: number | undefined

function statusLabel(s: string) {
  return { queued: '排队中', running: '执行中', completed: '已完成', failed: '失败', cancelled: '已取消' }[s] || s
}
function statusColor(s: string) {
  return { queued: 'default', running: 'processing', completed: 'success', failed: 'error', cancelled: 'default' }[s] || 'default'
}
function progStatus() {
  if (props.task.status === 'failed') return 'exception'
  if (props.task.status === 'completed') return 'success'
  return 'active'
}

async function refresh() {
  if (!props.task?.taskId) return
  if (TERMINAL.includes(props.task.status) && !props.active) return
  try {
    const t = await getAsyncTask(props.task.taskId)
    Object.assign(props.task, {
      status: t.status, progress: t.progress, errorMessage: t.errorMessage,
      resultData: t.resultData, finishedAt: t.finishedAt, priority: t.priority,
    })
  } catch (e) { /* ignore */ }
}

function startPolling() {
  stopPolling()
  if (TERMINAL.includes(props.task.status)) return
  // 仅页面可见时轮询，间隔 3s
  timer = window.setInterval(() => {
    if (document.visibilityState === 'visible') refresh()
  }, 3000)
}
function stopPolling() {
  if (timer) { clearInterval(timer); timer = undefined }
}

async function onCancel() {
  try {
    await cancelAsyncTask(props.task.taskId)
    message.success('任务已取消')
    await refresh()
  } catch (e: any) {
    message.error(e?.message || '取消失败')
  }
}

onMounted(startPolling)
onUnmounted(stopPolling)
watch(() => props.task.status, (s) => { if (TERMINAL.includes(s)) stopPolling() })
</script>

<style scoped lang="less">
.task-card {
  border: 1px solid #e6e8eb; border-radius: 10px; background: #fff; padding: 12px 14px;
  &.st-running { border-color: #91caff; }
  &.st-completed { border-color: #b7eb8f; }
  &.st-failed { border-color: #ffccc7; }
}
.tk-header { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; margin-bottom: 8px; }
.tk-icon { color: #1677ff; }
.tk-name { flex: 1; color: #1a1a1a; }
.tk-no { font-size: 11px; color: #bbb; }
.tk-meta { display: flex; gap: 12px; flex-wrap: wrap; font-size: 11px; color: #999; margin-top: 6px; }
.tk-error { margin-top: 6px; padding: 6px 10px; background: #fff1f0; border: 1px solid #ffccc7; border-radius: 6px; font-size: 12px; color: #cf1322; }
.tk-result { margin-top: 8px; }
.tk-result-body { font-size: 13px; line-height: 1.6; }
.tk-actions { margin-top: 8px; }
</style>
