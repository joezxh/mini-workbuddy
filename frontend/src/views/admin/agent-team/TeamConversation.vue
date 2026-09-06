<template>
  <div class="team-conversation">
    <!-- 顶栏 -->
    <div class="conv-header">
      <div class="left">
        <a-button type="link" @click="goBack"><ArrowLeftOutlined /> 返回</a-button>
        <span class="title">{{ teamName }}</span>
        <a-tag :color="runState === 'running' ? 'processing' : 'default'">
          {{ runState === 'running' ? '运行中' : runState === 'done' ? '已完成' : runState === 'error' ? '异常' : '空闲' }}
        </a-tag>
      </div>
      <div class="right">
        <a-button v-if="runId" @click="openReplay">
          <HistoryOutlined /> 回放
        </a-button>
        <a-button @click="clearChat"><ClearOutlined /> 清空</a-button>
      </div>
    </div>

    <div class="conv-body">
      <!-- 左：运行态拓扑 -->
      <div class="topo-panel">
        <div class="panel-title">
          运行态拓扑
          <a-tooltip title="实时反映各节点（agent）状态">
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
          <a-empty v-if="topoNodes.length === 0" description="等待运行" />
        </div>
        <div class="panel-title" style="margin-top:16px">
          事件流
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
            <div class="msg-head"><span class="msg-author">团队</span></div>
            <div class="msg-body">{{ streamingText }}</div>
          </div>
        </div>

        <!-- 干预条 -->
        <div class="intervention-bar">
          <a-dropdown>
            <a-button size="small"><ThunderboltOutlined /> 干预</a-button>
            <template #overlay>
              <a-menu @click="onIntervene">
                <a-menu-item key="pause">暂停运行</a-menu-item>
                <a-menu-item key="resume">恢复运行</a-menu-item>
                <a-menu-item key="cancel">取消运行</a-menu-item>
                <a-menu-item key="inject_message">插话（注入消息）</a-menu-item>
                <a-menu-item key="skip_node">跳过节点</a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>

        <!-- 输入区（@提及） -->
        <div class="input-area">
          <div class="mention-hint" v-if="showMentionHint">
            可用 @ 提及成员：{{ members.map(m => '@' + m.role_name).join('  ') }}
          </div>
          <a-textarea
            v-model:value="inputText"
            :rows="3"
            placeholder="输入指令，使用 @角色名 进行定向 @提及（如 @风险分析师 请优先评估...）"
            @keydown="onInputKeydown"
            @input="onInput"
          />
          <div class="send-row">
            <a-select
              v-model:value="modelId"
              :options="modelOptions.map(m => ({ label: `${m.name} (${m.model})`, value: m.id }))"
              placeholder="选择大模型"
              style="width: 240px"
              allow-clear
            />
            <a-button
              type="primary"
              :loading="runState === 'running'"
              @click="sendMessage"
            >
              <SendOutlined /> {{ runState === 'running' ? '运行中' : '发送' }}
            </a-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 干预弹窗 -->
    <a-modal v-model:open="hintModal" title="人工干预" @ok="submitIntervention">
      <a-form layout="vertical">
        <a-form-item label="干预类型">
          <a-select v-model:value="interventionForm.intervention_type" :options="interventionTypes" />
        </a-form-item>
        <a-form-item v-if="interventionForm.intervention_type === 'skip_node'" label="定向节点 (node_key)">
          <a-select
            v-model:value="interventionForm.node_key"
            :options="memberOptions"
            allow-clear
            placeholder="选择要跳过的节点"
          />
        </a-form-item>
        <a-form-item v-if="interventionForm.intervention_type === 'inject_message'" label="干预内容">
          <a-textarea v-model:value="hintText" :rows="4" placeholder="输入注入消息内容" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
const teamId = Number(route.params.teamId)
const runId = ref<string>(String(route.params.runId || ''))
const teamName = ref('团队对话')

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
    team_start: '团队启动',
    team_done: '团队完成',
    team_error: '团队异常',
    dispatch_plan: '生成计划',
    plan_revised: '修订计划',
    plan_dispatch: '派发计划',
    plan_execute: '执行计划',
    batch_start: '批次开始',
    batch_done: '批次完成',
    team_layer_start: '层开始',
    team_layer_done: '层完成',
    worker_start: '专家启动',
    worker_done: '专家完成',
    react_iteration: '编排轮次',
    thinking: '思考中',
    text_chunk: '文本流',
    agent_start: '专家启动',
    agent_done: '专家完成',
    error: '错误',
  }
  return map[et] || et
}

const interventionTypes = [
  { label: '暂停运行', value: 'pause' },
  { label: '恢复运行', value: 'resume' },
  { label: '取消运行', value: 'cancel' },
  { label: '插话（注入消息）', value: 'inject_message' },
  { label: '跳过节点', value: 'skip_node' }
]
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
  idle: '空闲', running: '执行中', done: '完成', failed: '失败',
  paused: '暂停', skipped: '跳过', error: '错误'
}[s] || s || '空闲')

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
      eventLog.value.push({ event_type: 'error', text: `对话请求失败 (HTTP ${resp.status})` })
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
        pushMessage('team', '团队', streamingText.value)
        streamingText.value = ''
      }
    }
  } catch (e: any) {
    runState.value = 'error'
    eventLog.value.push({ event_type: 'error', text: '对话连接中断：' + (e?.message || e) })
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
      pushMessage('team', '团队', streamingText.value)
      streamingText.value = ''
    }
    return
  }
  if (data.event_type === 'error' || data.event_type === 'team_error') {
    runState.value = 'error'
    const errMsg = String(data.content || data.message || '运行异常')
    eventLog.value.push({ event_type: 'error', text: errMsg })
    // 明确显示为系统错误消息气泡，避免静默空白
    pushMessage('system', '系统', '⚠️ ' + errMsg)
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
  pushMessage('user', '我', text)
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
    message.warning('请先发起一次对话，生成运行记录后再干预')
    return
  }
  const type = interventionForm.intervention_type
  if (type === 'skip_node' && !interventionForm.node_key) {
    message.warning('跳过节点需指定定向节点')
    return
  }
  if (type === 'inject_message' && !hintText.value.trim()) {
    message.warning('插话类型需填写干预内容')
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
    message.success('干预已提交，将在下一轮生效')
    hintModal.value = false
    hintText.value = ''
  } catch (e: any) {
    message.error('干预失败：' + (e?.message || e))
  }
}

// ── 回放 ─────────────────────────────────────────────
const openReplay = () => {
  if (!runId.value) { message.warning('暂无可回放的运行'); return }
  router.push(`/admin/agent-team/run/${runId.value}/replay`)
}
const goBack = () => router.push('/admin/agent-team')

// ── 初始化 ───────────────────────────────────────────
const init = async () => {
  try {
    const res = await api.getTeam(teamId)
    teamName.value = (res as any).team_name || '团队对话'
    members.value = (res as any).members || []
  } catch (e: any) {
    message.error('加载团队失败：' + (e?.message || e))
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
      message.error('恢复历史对话失败：' + (e?.message || e))
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
