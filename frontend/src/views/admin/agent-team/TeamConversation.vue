<template>
  <div class="team-conversation">
    <!-- 顶栏 -->
    <div class="conv-header">
      <div class="left">
        <a-button type="link" @click="goBack"><ArrowLeftOutlined /> {{ t('common.back') }}</a-button>
        <span class="title">{{ teamName }}</span>
        <a-tag :color="runState === 'running' ? 'processing' : 'default'">
          {{ runState === 'running' ? t('teamMgmt.stRunning') : runState === 'done' ? t('teamMgmt.stCompleted') : runState === 'error' ? t('teamMgmt.stError') : t('teamMgmt.stIdle') }}
        </a-tag>
      </div>
      <div class="right">
        <a-button v-if="runId" @click="openReplay">
          <HistoryOutlined /> {{ t('teamMgmt.replay') }}
        </a-button>
        <a-button @click="clearChat"><ClearOutlined /> {{ t('teamMgmt.clear') }}</a-button>
      </div>
    </div>

    <div class="conv-body">
      <!-- 左：运行态拓扑 -->
      <div class="topo-panel">
        <div class="panel-title">
          {{ t('teamMgmt.topoTitle') }}
          <a-tooltip :title="t('teamMgmt.topoTip')">
            <InfoCircleOutlined class="tip" />
          </a-tooltip>
        </div>
        <div class="topo-nodes">
          <div
            v-for="node in topoNodes"
            :key="node.node_key"
            class="topo-node"
            :class="node.status"
          >
            <div class="tn-role">{{ node.role }}</div>
            <div class="tn-code">{{ node.node_key }}</div>
            <div class="tn-status">{{ statusLabel(node.status) }}</div>
          </div>
          <a-empty v-if="topoNodes.length === 0" :description="t('teamMgmt.waitingRun')" />
        </div>
        <div class="panel-title" style="margin-top:16px">
          {{ t('teamMgmt.eventStream') }}
          <a-tag v-if="lastEventTime" size="small" color="blue" style="margin-left:8px">
            {{ lastEventTime }}
          </a-tag>
        </div>
        <div class="event-stream">
          <div v-for="(ev, i) in eventLog" :key="i" class="event-line" :class="'ev-' + ev.event_type">
            <span class="ev-type">{{ eventTypeLabel(ev.event_type) }}</span>
            <span class="ev-text">{{ ev.text }}</span>
          </div>
        </div>
      </div>

      <!-- 右：统一对话窗 -->
      <div class="chat-panel">
        <div class="chat-scroll" ref="chatScroll">
          <div v-for="(msg, i) in messages" :key="i" class="chat-msg" :class="msg.role">
            <div class="msg-head">
              <span class="msg-author">{{ msg.author }}</span>
              <a-tag v-if="msg.node_key" size="small" color="blue">{{ msg.node_key }}</a-tag>
              <span class="msg-time">{{ msg.time }}</span>
            </div>
            <div class="msg-body">{{ msg.content }}</div>
          </div>
          <div v-if="streamingText" class="chat-msg agent streaming">
            <div class="msg-head"><span class="msg-author">{{ t('teamMgmt.team') }}</span></div>
            <div class="msg-body">{{ streamingText }}</div>
          </div>
        </div>

        <!-- 干预条 -->
        <div class="intervention-bar">
          <a-dropdown>
            <a-button size="small"><ThunderboltOutlined /> {{ t('teamMgmt.intervene') }}</a-button>
            <template #overlay>
              <a-menu @click="onIntervene">
                <a-menu-item key="pause">{{ t('teamMgmt.actPause') }}</a-menu-item>
                <a-menu-item key="resume">{{ t('teamMgmt.actResume') }}</a-menu-item>
                <a-menu-item key="cancel">{{ t('teamMgmt.actCancel') }}</a-menu-item>
                <a-menu-item key="inject_message">{{ t('teamMgmt.actInject') }}</a-menu-item>
                <a-menu-item key="skip_node">{{ t('teamMgmt.actSkip') }}</a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>

        <!-- 输入区（@提及） -->
        <div class="input-area">
          <div class="mention-hint" v-if="showMentionHint">
            {{ t('teamMgmt.mentionHint') }}{{ members.map(m => '@' + m.role_name).join('  ') }}
          </div>
          <a-textarea
            v-model:value="inputText"
            :rows="3"
            :placeholder="t('teamMgmt.inputPlaceholder')"
            @keydown="onInputKeydown"
            @input="onInput"
          />
          <div class="send-row">
            <a-select
              v-model:value="modelId"
              :options="modelOptions.map(m => ({ label: `${m.name} (${m.model})`, value: m.id }))"
              :placeholder="t('teamMgmt.selectModel')"
              style="width: 240px"
              allow-clear
            />
            <a-button
              type="primary"
              :loading="runState === 'running'"
              @click="sendMessage"
            >
              <SendOutlined /> {{ runState === 'running' ? t('teamMgmt.stRunning') : t('teamMgmt.send') }}
            </a-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 干预弹窗 -->
    <a-modal v-model:open="hintModal" :title="t('teamMgmt.interventionTitle')" @ok="submitIntervention">
      <a-form layout="vertical">
        <a-form-item :label="t('teamMgmt.interventionType')">
          <a-select v-model:value="interventionForm.intervention_type" :options="interventionTypes" />
        </a-form-item>
        <a-form-item v-if="interventionForm.intervention_type === 'skip_node'" :label="t('teamMgmt.targetNode')">
          <a-select
            v-model:value="interventionForm.node_key"
            :options="memberOptions"
            allow-clear
            :placeholder="t('teamMgmt.skipNodePlaceholder')"
          />
        </a-form-item>
        <a-form-item v-if="interventionForm.intervention_type === 'inject_message'" :label="t('teamMgmt.interventionContent')">
          <a-textarea v-model:value="hintText" :rows="4" :placeholder="t('teamMgmt.injectPlaceholder')" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  ArrowLeftOutlined,
  HistoryOutlined,
  ClearOutlined,
  InfoCircleOutlined,
  ThunderboltOutlined,
  SendOutlined
} from '@ant-design/icons-vue'
import * as api from '@/api/agentTeam'
import { getAvailableModels, type AvailableModel } from '@/api/ai-apikey'
import { getToken } from '@/utils/auth'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const teamId = Number(route.params.teamId)
const runId = ref<string>(String(route.params.runId || ''))
const teamName = ref(t('teamMgmt.defaultTeamName'))

const chatScroll = ref<HTMLElement | null>(null)
const messages = ref<{
  role: string
  author: string
  node_key?: string
  content: string
  time: string
}[]>([])
const streamingText = ref('')
const inputText = ref('')
const runState = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const showMentionHint = ref(false)
// 同一运行内最终结论只 push 一次，防止 team_done/done/completed/兜底 重复落库为消息气泡
const finalMessagePushed = ref(false)

const members = ref<api.TeamMember[]>([])
const topoNodes = reactive<{
  node_key: string
  role: string
  status: string
}[]>([])

// AI 模型选择（从 ai_chat_model 表动态加载，透传给后端用于子 agent 直连）
const modelId = ref<number | undefined>()
const modelOptions = ref<Array<{ id: number; name: string; model: string }>>([])
async function loadAvailableModels() {
  try {
    const res = (await getAvailableModels()) as unknown as AvailableModel[]
    const all = Array.isArray(res) ? res : []
    modelOptions.value = all.map((m: AvailableModel) => ({
      id: m.id,
      name: m.name || m.model,
      model: m.model
    }))
  } catch (e) {
    console.warn('加载可用模型失败', e)
  }
}
const eventLog = ref<{ event_type: string; text: string }[]>([])
const lastEventTime = ref('')

const eventTypeLabel = (et: string): string => {
  const map: Record<string, string> = {
    team_start: t('teamMgmt.evTeamStart'),
    team_done: t('teamMgmt.evTeamDone'),
    team_error: t('teamMgmt.evTeamError'),
    dispatch_plan: t('teamMgmt.evDispatchPlan'),
    plan_revised: t('teamMgmt.evPlanRevised'),
    plan_dispatch: t('teamMgmt.evPlanDispatch'),
    plan_execute: t('teamMgmt.evPlanExecute'),
    batch_start: t('teamMgmt.evBatchStart'),
    batch_done: t('teamMgmt.evBatchDone'),
    team_layer_start: t('teamMgmt.evLayerStart'),
    team_layer_done: t('teamMgmt.evLayerDone'),
    worker_start: t('teamMgmt.evWorkerStart'),
    worker_done: t('teamMgmt.evWorkerDone'),
    react_iteration: t('teamMgmt.evReactIteration'),
    thinking: t('teamMgmt.evThinking'),
    text_chunk: t('teamMgmt.evTextChunk'),
    agent_start: t('teamMgmt.evWorkerStart'),
    agent_done: t('teamMgmt.evWorkerDone'),
    error: t('teamMgmt.evError'),
  }
  return map[et] || et
}

const interventionTypes = computed(() => [
  { label: t('teamMgmt.actPause'), value: 'pause' },
  { label: t('teamMgmt.actResume'), value: 'resume' },
  { label: t('teamMgmt.actCancel'), value: 'cancel' },
  { label: t('teamMgmt.actInject'), value: 'inject_message' },
  { label: t('teamMgmt.actSkip'), value: 'skip_node' }
])
const memberOptions = computed(() =>
  members.value.map(m => ({ label: `${m.role_name} (${m.node_key})`, value: m.node_key }))
)
const hintModal = ref(false)
const interventionForm = reactive<api.InterventionV2Create>({
  intervention_type: 'pause', node_key: undefined, payload: { message: '' }
})
const hintText = ref('')

let es: EventSource | null = null

// ── 拓扑节点更新 ─────────────────────────────────────
const upsertNode = (node_key: string, role: string, status: string) => {
  const idx = topoNodes.findIndex(n => n.node_key === node_key)
  if (idx >= 0) {
    topoNodes[idx].status = status
    if (role) topoNodes[idx].role = role
  } else {
    topoNodes.push({ node_key, role: role || node_key, status })
  }
}
const statusLabel = (s: string) => ({
  idle: t('teamMgmt.nodeIdle'), running: t('teamMgmt.nodeRunning'), done: t('teamMgmt.nodeDone'), failed: t('teamMgmt.nodeFailed'),
  paused: t('teamMgmt.nodePaused'), skipped: t('teamMgmt.nodeSkipped'), error: t('teamMgmt.nodeError')
}[s] || s || t('teamMgmt.nodeIdle'))

// ── SSE 解析（POST 流式，替换 EventSource GET）──────────
const fetchChat = async (payload: { message: string; conversation_id?: string }) => {
  if (es) es.close()
  runState.value = 'running'
  streamingText.value = ''
  finalMessagePushed.value = false
  try {
    const resp = await fetch(`/api/v1/ai-team/${teamId}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getToken() || ''}`
      },
      body: JSON.stringify({
        message: payload.message,
        conversation_id: payload.conversation_id,
        session_id: payload.conversation_id,
        trigger_type: 'api',
        model_id: modelId.value
      })
    })
    if (!resp.ok || !resp.body) {
      runState.value = 'error'
      eventLog.value.push({ event_type: 'error', text: t('teamMgmt.requestFailed', { code: resp.status }) })
      return
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) { break }
      buffer += decoder.decode(value, { stream: true })
      // SSE 以双换行分帧
      const frames = buffer.split('\n\n')
      buffer = frames.pop() || ''
      for (const frame of frames) {
        const line = frame.split('\n').find(l => l.startsWith('data:'))
        if (line) handleChunk(line.slice(5).trim())
      }
    }
    if (runState.value === 'running' || runState.value === 'done') {
      runState.value = 'done'
      // 兜底：流结束或已标记 done，若仍有累积文本未落库为消息，强制推送
      if (!finalMessagePushed.value && streamingText.value.trim()) {
        pushMessage('team', t('teamMgmt.team'), streamingText.value)
        streamingText.value = ''
      }
    }
  } catch (e: any) {
    runState.value = 'error'
    eventLog.value.push({ event_type: 'error', text: t('teamMgmt.connectionLost', { msg: e?.message || e }) })
  } finally {
    es = null
  }
}

const handleChunk = (raw: string) => {
  let data: any
  try { data = JSON.parse(raw) } catch { return }
  const meta = data.metadata || {}
  // 调试：写入 eventLog（保证一定能看见，不依赖 console）
  eventLog.value.push({ event_type: 'DEBUG', text: `[${data.event_type}] streamingText=${streamingText.value.length} content前30=${String(data.content||data.answer||'').slice(0,30)}` })
  // agent_status：构建/更新运行态拓扑
  if (data.event_type === 'agent_status') {
    upsertNode(meta.node_key || meta.agent_code, meta.role_name || meta.agent_code, meta.node_status || meta.status || 'running')
    if (meta.channel) { /* 记录通道：leader / worker */ }
    return
  }
  // 统一文本提取：兼容 content / answer / message 三种字段名
  const text = typeof data.content === 'string'
    ? data.content
    : (typeof data.answer === 'string'
      ? data.answer
      : (data.content?.text || data.content?.message || data.message || ''))
  // team_done / done / completed → 结束帧，将累积文本推为消息气泡（每个 run 仅推送一次）
  if (['team_done', 'done', 'completed'].includes(data.event_type)) {
    runState.value = 'done'
    // 只在仍有累积文本且未推送过最终消息时才推送，避免 team_done/done/completed 多个结束帧重复生成气泡
    if (!finalMessagePushed.value && streamingText.value) {
      pushMessage('team', t('teamMgmt.team'), streamingText.value)
      streamingText.value = ''
    }
    return
  }
  if (data.event_type === 'error' || data.event_type === 'team_error') {
    runState.value = 'error'
    const errMsg = String(data.content || data.message || t('teamMgmt.runError'))
    eventLog.value.push({ event_type: 'error', text: errMsg })
    // 明确显示为系统错误消息气泡，避免静默空白
    pushMessage('system', t('teamMgmt.system'), '⚠️ ' + errMsg)
    return
  }
  // 普通文本 / 思考 / 进度事件
  if (text) {
    if (data.event_type === 'text' || data.event_type === 'text_chunk' || data.event_type === 'team_result') {
      streamingText.value += text
    } else if (data.event_type === 'thinking') {
      eventLog.value.push({ event_type: 'thinking', text: String(text).slice(0, 120) })
    } else if (['batch_start', 'batch_done', 'worker_start', 'worker_done', 'team_layer_start', 'team_layer_done', 'dispatch_plan', 'plan_revised', 'react_iteration'].includes(data.event_type)) {
      // 进度类事件：保留完整信息，前端事件流清晰展示执行进度
      eventLog.value.push({ event_type: data.event_type, text: String(text) })
    } else {
      eventLog.value.push({ event_type: data.event_type, text: String(text).slice(0, 120) })
    }
  }
  // 捕获 run_id（首个事件可能携带）——始终更新以支持多轮对话
  if (meta.run_id) {
    runId.value = meta.run_id
    // 同步 URL，确保刷新/分享可恢复到正确的 run
    const url = `/admin/agent-team/${teamId}/run/${meta.run_id}`
    if (window.location.pathname !== url) window.history.replaceState({}, '', url)
  }
  // 记录最近事件时间，便于观察是否存在卡顿（长时间无更新 = 卡住）
  lastEventTime.value = new Date().toLocaleTimeString()
  scrollToBottom()
}

const pushMessage = (role: string, author: string, content: string, node_key?: string) => {
  if (!content) return
  // 连续相同作者+内容去重，防止同一结论被渲染成多个气泡
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === role && last.author === author && last.content === content) {
    return
  }
  messages.value.push({
    role, author, content,
    node_key,
    time: new Date().toLocaleTimeString()
  })
  if (role === 'team') finalMessagePushed.value = true
  scrollToBottom()
}

const scrollToBottom = () => nextTick(() => {
  if (chatScroll.value) chatScroll.value.scrollTop = chatScroll.value.scrollHeight
})

// ── 发送 / @提及 ─────────────────────────────────────
const onInput = () => {
  showMentionHint.value = inputText.value.endsWith('@') || /@\w*$/.test(inputText.value)
}
const onInputKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault()
    sendMessage()
  }
}
const sendMessage = () => {
  const text = inputText.value.trim()
  if (!text) return
  pushMessage('user', t('teamMgmt.me'), text)
  inputText.value = ''
  showMentionHint.value = false
  // 发新消息时清空旧 runId，让后端创建新 run；新 runId 由 SSE 首个事件的 metadata.run_id 带回
  runId.value = ''
  fetchChat({ message: text, conversation_id: undefined })
}

const clearChat = () => {
  messages.value = []
  streamingText.value = ''
  eventLog.value = []
  topoNodes.length = 0
  runId.value = ''
  runState.value = 'idle'
  if (es) { es.close(); es = null }
}

// ── 干预（实时，v2）──────────────────────────────────────────
const onIntervene = ({ key }: { key: string }) => {
  interventionForm.intervention_type = key
  interventionForm.node_key = key === 'skip_node' ? interventionForm.node_key : undefined
  hintText.value = key === 'inject_message' ? hintText.value : ''
  hintModal.value = true
}
const submitIntervention = async () => {
  if (!runId.value) {
    message.warning(t('teamMgmt.needRunFirst'))
    return
  }
  const type = interventionForm.intervention_type
  if (type === 'skip_node' && !interventionForm.node_key) {
    message.warning(t('teamMgmt.needSkipNode'))
    return
  }
  if (type === 'inject_message' && !hintText.value.trim()) {
    message.warning(t('teamMgmt.needInjectContent'))
    return
  }
  const payload = type === 'inject_message' ? { message: hintText.value } : {}
  try {
    await api.createIntervention(teamId, runId.value, {
      intervention_type: type,
      node_key: interventionForm.node_key || null,
      round_no: 1,
      payload,
      operator_name: 'operator'
    })
    message.success(t('teamMgmt.interventionSubmitted'))
    hintModal.value = false
    hintText.value = ''
  } catch (e: any) {
    message.error(t('teamMgmt.interventionFailed', { msg: e?.message || t('agentMgmt.unknownError') }))
  }
}

// ── 回放 ─────────────────────────────────────────────
const openReplay = () => {
  if (!runId.value) { message.warning(t('teamMgmt.noRunToReplay')); return }
  router.push(`/admin/agent-team/run/${runId.value}/replay`)
}
const goBack = () => router.push('/admin/agent-team')

// ── 初始化 ───────────────────────────────────────────
const init = async () => {
  try {
    const res = await api.getTeam(teamId)
    teamName.value = (res as any).team_name || t('teamMgmt.defaultTeamName')
    members.value = (res as any).members || []
  } catch (e: any) {
    message.error(t('teamMgmt.loadFailed', { msg: e?.message || t('agentMgmt.unknownError') }))
  }
  // 若带 runId 进入（刷新 / 从列表/回放重进），恢复历史对话
  if (runId.value) {
    try {
      const hist = await api.getRunMessages(teamId, runId.value)
      messages.value = (hist || []).map((m: any) => ({
        role: m.role,
        author: m.author,
        node_key: m.node_key,
        content: m.content,
        time: ''
      }))
      // 历史 run 视为已完成，便于左侧/右侧状态显示
      if (messages.value.length) runState.value = 'done'
      await nextTick()
      scrollToBottom()
    } catch (e: any) {
      message.error(t('teamMgmt.restoreFailed', { msg: e?.message || t('agentMgmt.unknownError') }))
    }
  }
}

onBeforeUnmount(() => { if (es) es.close() })
init()
loadAvailableModels()
</script>

<style scoped lang="less">
.team-conversation {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-page);
}
.conv-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}
.conv-header .title { font-weight: 700; font-size: 16px; }
.conv-body {
  flex: 1;
  display: flex;
  min-height: 0;
}
.topo-panel {
  width: 300px;
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
  padding: 12px;
  display: flex;
  flex-direction: column;
  overflow: auto;
}
.panel-title {
  font-weight: 600;
  margin-bottom: 10px;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}
.tip { color: var(--fg-muted); cursor: help; }
.topo-nodes {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.topo-node {
  border: 1px solid var(--border);
  border-left: 4px solid var(--accent);
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--accent-soft);
  &.running { border-left-color: var(--warn); background: var(--warn-soft); }
  &.done { border-left-color: var(--ok); background: var(--ok-soft); }
  &.failed, &.error { border-left-color: var(--err); background: var(--err-soft); }
  &.paused { border-left-color: var(--fg-muted); background: var(--bg-base); }
}
.tn-role { font-weight: 700; font-size: 13px; }
.tn-code { font-size: 11px; color: var(--fg-muted); font-family: monospace; }
.tn-status { font-size: 11px; color: var(--text-secondary); margin-top: 2px; }
.event-stream {
  flex: 1;
  overflow: auto;
  font-size: 12px;
  background: var(--bg-base);
  border-radius: 8px;
  padding: 8px;
}
.event-line {
  padding: 4px 6px;
  border-bottom: 1px dashed var(--border);
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
}
.ev-type {
  display: inline-block;
  min-width: 56px;
  font-size: 11px;
  font-weight: 600;
  text-align: center;
  border-radius: 4px;
  padding: 1px 6px;
  margin-right: 8px;
  color: var(--fg-inverse);
  background: var(--fg-muted);
}
.ev-text { color: var(--text-secondary); word-break: break-word; }

/* 进度事件颜色区分，便于一眼看出卡在哪个阶段 */
.event-line.ev-batch_start .ev-type,
.event-line.ev-team_layer_start .ev-type { background: #1677ff; }
.event-line.ev-batch_done .ev-type,
.event-line.ev-team_layer_done .ev-type { background: #52c41a; }
.event-line.ev-worker_start .ev-type { background: #fa8c16; }
.event-line.ev-worker_done .ev-type { background: #13c2c2;; }
.event-line.ev-dispatch_plan .ev-type,
.event-line.ev-plan_dispatch .ev-type,
.event-line.ev-plan_execute .ev-type { background: #722ed1; }
.event-line.ev-react_iteration .ev-type { background: #eb2f96; }
.event-line.ev-team_error .ev-type,
.event-line.ev-error .ev-type { background: #f5222d; }
.event-line.ev-team_done .ev-type { background: #52c41a; }

.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.chat-scroll {
  flex: 1;
  overflow: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.chat-msg {
  max-width: 78%;
  padding: 10px 14px;
  border-radius: 12px;
  &.user {
    align-self: flex-end;
    background: var(--accent-cyan);
    color: var(--fg-inverse);
  }
  &.agent, &.team {
    align-self: flex-start;
    background: var(--bg-surface);
    border: 1px solid var(--border);
  }
  &.streaming { opacity: 0.85; }
}
.msg-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 12px;
}
.msg-author { font-weight: 700; }
.msg-time { color: var(--fg-muted); }
.msg-body { white-space: pre-wrap; line-height: 1.6; word-break: break-word; }

.intervention-bar {
  padding: 6px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg-surface);
}
.input-area {
  padding: 10px 16px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg-surface);
}
.mention-hint {
  font-size: 12px;
  color: var(--accent-cyan);
  margin-bottom: 6px;
}
.send-row {
  margin-top: 8px;
  text-align: right;
}
</style>
