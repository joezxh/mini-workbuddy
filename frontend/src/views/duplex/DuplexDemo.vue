<template>
  <div class="voice-demo">
    <!-- 顶部标题 + 配置区 -->
    <div class="demo-header">
      <div class="header-left">
        <h1 class="demo-title">🛒 可插拔全双工语音交互 — 电商跨境贸易</h1>
        <span class="demo-badge">多 Agent 编排 · 意图+状态双触发 · 热切换</span>
      </div>
      <div class="header-right">
        <a-select
          v-model:value="provider"
          style="width: 180px"
          size="small"
          :options="providerOptions"
          placeholder="选择语音厂商"
        />
        <a-select
          v-model:value="selectedModel"
          style="width: 220px"
          size="small"
          placeholder="语音模型"
          :options="modelOptions"
          :loading="modelLoading"
          show-search
          option-filter-prop="label"
        />
        <a-button
          type="primary"
          size="small"
          :disabled="!selectedModel || creatingSession"
          :loading="creatingSession"
          @click="enterVoiceChannel"
        >
          进入语音通道
        </a-button>
      </div>
    </div>

    <!-- 无可用模型提示 -->
    <a-alert
      v-if="!modelLoading && providerOptions.length === 0"
      type="warning"
      show-icon
      class="model-warn"
      message="暂无可用的全双工语音模型"
      description="请先在「语音模型配置」中为厂商配置 API Key 与全双工语音模型。仅展示已配置可用全双工语音大模型的厂商。"
    />

    <!-- 模型可用性提示 -->
    <a-alert
      v-if="showChannel && selectedModelInfo && !selectedModelInfo.usable"
      type="warning"
      show-icon
      class="model-warn"
      message="当前语音模型不可用"
      :description="`模型「${selectedModelInfo.name}」缺少有效 API Key 或模型标识不在官方实时目录，请在「语音模型配置」中修复。`"
    />

    <div v-if="showChannel" class="demo-grid">
      <!-- 左：语音通道 -->
      <div class="panel voice-main">
        <div class="panel-title">
          <span class="dot" :class="{ active: status === 'open' }"></span>
          语音通道 (VoiceChannel)
        </div>

        <div class="voice-stage" :class="stageState">
          <div class="agent-ring">
            <div class="ring"></div>
            <div class="ring" :class="{ active: status === 'open' }"></div>
            <div class="core">{{ currentAgent.icon }}</div>
          </div>
          <div class="agent-label">
            <div class="name">{{ activeAgent.name }}</div>
            <div class="status-text">{{ statusText }}</div>
          </div>
          <div class="waveform">
            <div
              v-for="i in 24"
              :key="i"
              class="bar"
              :style="{ height: barHeight(i) + 'px' }"
            ></div>
          </div>
        </div>

        <div class="transcript-area">
          <div
            v-for="t in transcripts"
            :key="t.id"
            class="turn"
            :class="t.role"
          >
            <div class="role">
              <span class="tag">{{ t.role === 'user' ? '客户' : activeAgent.name }}</span>
              <span class="time">{{ formatTime(t.started_at) }}</span>
            </div>
            <div class="text">{{ t.text }}</div>
          </div>
          <div v-if="!transcripts.length" class="empty-hint">
            点击「开启麦克风」开始对话，或在下方输入文字
          </div>
        </div>

        <div class="controls">
          <a-button
            v-if="status !== 'open'"
            type="primary"
            @click="connect"
          >
            🔌 连接
          </a-button>
          <a-button v-else danger @click="disconnect">⏹ 断开</a-button>

          <a-button
            :type="micOn ? 'default' : 'primary'"
            :disabled="status !== 'open'"
            @click="onToggleMic"
          >
            {{ micOn ? '🎤 关闭麦克风' : '🎤 开启麦克风' }}
          </a-button>

          <a-button
            :disabled="status !== 'open'"
            @click="sendInterrupt"
          >
            ⏹ 打断
          </a-button>

          <a-input
            v-model:value="textInput"
            placeholder="输入文字与助手对话，回车发送"
            style="flex: 1; max-width: 360px"
            :disabled="status !== 'open'"
            @pressEnter="onSendText"
          />
          <a-button
            type="primary"
            :disabled="status !== 'open' || !textInput.trim()"
            @click="onSendText"
          >
            发送
          </a-button>

          <span v-if="ready" class="caps">
            {{ ready.input_sample_rate }}/{{ ready.output_sample_rate }}Hz · {{ ready.vad_mode }}
          </span>
        </div>

        <a-alert v-if="errorMsg" type="error" :message="errorMsg" show-icon class="error-alert" />
      </div>

      <!-- 右：Agent 编排器 + 输出渠道 + 会话列表（Tab 切换） -->
      <div class="panel agent-panel">
        <div class="tab-bar">
          <div
            class="tab"
            :class="{ active: activeTab === 'agents' }"
            @click="activeTab = 'agents'"
          >
            🧩 Agent 编排器
          </div>
          <div
            class="tab"
            :class="{ active: activeTab === 'channels' }"
            @click="activeTab = 'channels'"
          >
            📡 输出渠道
            <span class="tab-badge">{{ activeChannelCount }}</span>
          </div>
          <div
            class="tab"
            :class="{ active: activeTab === 'sessions' }"
            @click="activeTab = 'sessions'; loadSessions()"
          >
            📋 会话列表
          </div>
        </div>

        <!-- Agent 编排 Tab -->
        <div v-show="activeTab === 'agents'" class="tab-pane">
          <div class="agent-list">
            <div
              v-for="a in agents"
              :key="a.key"
              class="agent-card"
              :class="{ active: activeAgent.key === a.key }"
            >
              <div class="head">
                <span class="icon">{{ a.icon }}</span>
                <span class="name">{{ a.name }}</span>
              </div>
              <div class="desc">{{ a.desc }}</div>
              <div class="switch-hint">
                {{ activeAgent.key === a.key ? '← 活跃中' : '' }}
              </div>
            </div>
          </div>
        </div>

        <!-- 输出渠道 Tab -->
        <div v-show="activeTab === 'channels'" class="tab-pane">
          <div class="channel-list">
            <div
              v-for="ch in channels"
              :key="ch.key"
              class="channel-card"
              :class="{ active: ch.active }"
              @click="toggleChannel(ch)"
            >
              <div class="ch-icon">{{ ch.icon }}</div>
              <div class="ch-info">
                <div class="ch-name">{{ ch.name }}</div>
                <div class="ch-desc">{{ ch.desc }}</div>
              </div>
              <a-select
                :value="ch.output"
                size="small"
                class="ch-output"
                :options="outputModeOptions"
                @click.stop
                @change="onChannelOutputChange(ch)"
              />
              <div class="ch-toggle" :class="{ on: ch.active }"></div>
            </div>
          </div>
          <div class="channel-summary">
            <span>已选中 <span class="active-count">{{ activeChannelCount }}</span> 个输出渠道</span>
            <span class="summary-text">{{ channelSummaryText }}</span>
          </div>
        </div>

        <!-- 会话列表 Tab -->
        <div v-show="activeTab === 'sessions'" class="tab-pane">
          <div class="session-list">
            <div v-if="sessionLoading" class="session-loading">加载中...</div>
            <a-empty v-else-if="sessionList.length === 0" description="暂无会话" />
            <div
              v-for="s in sessionList"
              :key="s.session_id"
              class="session-item"
              @click="openSessionDetail(s)"
            >
              <div class="session-item-head">
                <span class="session-title">{{ s.session_title || '未命名会话' }}</span>
                <span class="session-count">{{ s.message_count }} 条</span>
              </div>
              <div class="session-item-meta">
                <span>ID: {{ s.session_id }}</span>
                <span>{{ formatDate(s.updated_at) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 下：架构分层 -->
      <div class="panel arch-panel">
        <div class="panel-title">🏗️ 架构分层 (可插拔多 Agent 编排)</div>
        <div class="arch-content">
          <div class="arch-layers">
            <div class="arch-layer" v-for="layer in archLayers" :key="layer.label">
              <span class="layer-label" :style="{ color: layer.highlight ? '#f59e0b' : '#9ca3af' }">
                {{ layer.label }}
              </span>
              <div class="layer-body">
                <template v-for="(node, idx) in layer.nodes" :key="idx">
                  <span
                    class="arch-node"
                    :class="node.kind"
                  >{{ node.name }}</span>
                  <span v-if="idx < layer.nodes.length - 1" class="arch-arrow">→</span>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 下：运行时事件流 -->
      <div class="panel arch-panel">
        <div class="panel-title">📜 运行时事件流</div>
        <div class="event-log">
          <div v-for="(e, i) in eventLog" :key="i" class="event-line">
            <span class="ts">{{ e.ts }}</span>
            <span class="evt">{{ e.evt }}</span>
            <span class="msg">{{ e.msg }}</span>
          </div>
        </div>
      </div>
    </div>

    <a-empty v-else description="选择语音模型后进入语音通道" />

    <!-- 会话详情弹窗 -->
    <a-modal
      v-model:open="sessionDetailVisible"
      :title="`会话详情 #${selectedSession?.session_id ?? ''}`"
      :width="640"
      :footer="null"
      destroy-on-close
    >
      <div v-if="selectedSession" class="session-detail">
        <div class="detail-row">
          <span class="detail-label">标题</span>
          <span class="detail-value">{{ selectedSession.session_title || '未命名会话' }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">类型</span>
          <span class="detail-value">{{ selectedSession.session_type }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">状态</span>
          <span class="detail-value">{{ selectedSession.status }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">消息数</span>
          <span class="detail-value">{{ selectedSession.message_count }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">创建时间</span>
          <span class="detail-value">{{ formatDate(selectedSession.created_at) }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">更新时间</span>
          <span class="detail-value">{{ formatDate(selectedSession.updated_at) }}</span>
        </div>

        <div class="detail-messages">
          <div class="detail-messages-title">消息记录</div>
          <div v-if="detailMessagesLoading" class="session-loading">加载消息中...</div>
          <a-empty v-else-if="detailMessages.length === 0" description="暂无消息" />
          <div
            v-for="m in detailMessages"
            :key="m.message_id"
            class="detail-msg"
            :class="m.role"
          >
            <span class="msg-role">{{ m.role === 'user' ? '用户' : m.role === 'assistant' ? '助手' : '系统' }}</span>
            <span class="msg-content">{{ m.content }}</span>
            <span class="msg-time">{{ formatDate(m.created_at) }}</span>
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useVoiceChannel } from '@/composables/useVoiceChannel'
import type { VoiceModel, VoiceProvider, VoiceProviderCatalog } from '@/types/voice'
import { listVoiceModels, getVoiceModelDefault, getVoiceProviderCatalog } from '@/api/voice'
import {
  createSession,
  getMySessions,
  getSession,
  getSessionMessages,
  type AiChatSession,
  type AiChatMessage,
} from '@/api/aiSession'

// ── 配置 ──
const provider = ref<VoiceProvider>('dashscope')
const showChannel = ref(false)
const creatingSession = ref(false)
// 后端自动生成的会话编号（AiChatSession.session_id）
const backendSessionId = ref<number | null>(null)

const voiceModels = ref<VoiceModel[]>([])
const providerCatalog = ref<VoiceProviderCatalog>({} as VoiceProviderCatalog)
const selectedModel = ref<number | undefined>(undefined)
const modelLoading = ref(false)

// Provider 下拉：仅展示已配置有「可用」全双工语音模型的厂商
const providerOptions = computed(() => {
  const usableProviders = new Set(
    voiceModels.value
      .filter((m) => m.usable && m.provider_key)
      .map((m) => m.provider_key as string),
  )
  return (Object.values(providerCatalog.value) as VoiceProviderCatalog[keyof VoiceProviderCatalog][])
    .filter((p) => usableProviders.has(p.key))
    .map((p) => ({
      label: p.label,
      value: p.key as VoiceProvider,
    }))
})

function modelsFor(p: VoiceProvider): VoiceModel[] {
  return voiceModels.value.filter((m) => m.provider_key === p && m.usable)
}

const modelOptions = computed(() =>
  modelsFor(provider.value).map((m) => ({
    label: m.is_default ? `${m.name}（默认）` : m.name,
    value: m.id,
  })),
)

const selectedModelInfo = computed(() =>
  voiceModels.value.find((m) => m.id === selectedModel.value),
)

watch(provider, () => {
  const pool = modelsFor(provider.value)
  if (!pool.some((m) => m.id === selectedModel.value)) {
    selectedModel.value = pool[0]?.id
  }
})

// 归一化平台名（与后端 normalize_provider_key 保持一致）
function normalizeProviderKey(platform?: string): VoiceProvider {
  const p = (platform || '').trim().toLowerCase()
  const aliases: Record<string, VoiceProvider> = {
    dashscope: 'dashscope', '通义千问': 'dashscope', 'aliyun': 'dashscope', '阿里云': 'dashscope',
    openai: 'openai',
    google: 'google', 'gemini': 'google',
    volcengine: 'volcengine', 'bytedance': 'volcengine', '字节跳动': 'volcengine', 'doubao': 'volcengine', '豆包': 'volcengine',
    iflytek: 'iflytek', '讯飞': 'iflytek', 'xfyun': 'iflytek', 'spark': 'iflytek',
  }
  return aliases[p] || ('dashscope' as VoiceProvider)
}

async function loadVoiceModels() {
  modelLoading.value = true
  try {
    const [models, def, catalog] = await Promise.all([
      listVoiceModels(),
      getVoiceModelDefault(),
      getVoiceProviderCatalog(),
    ])
    voiceModels.value = models
    providerCatalog.value = catalog

    const applyDefault = (model: VoiceModel) => {
      provider.value = model.provider_key
        ? (model.provider_key as VoiceProvider)
        : normalizeProviderKey(model.platform)
      selectedModel.value = model.id
    }
    // 优先选可用的默认模型
    const defaultModel = def?.configured
      ? models.find((m) => m.id === def.model_id && m.usable)
      : undefined
    if (defaultModel) {
      applyDefault(defaultModel)
    } else {
      // 否则选第一个可用模型
      const firstUsable = models.find((m) => m.usable)
      if (firstUsable) applyDefault(firstUsable)
      else selectedModel.value = undefined
    }
  } finally {
    modelLoading.value = false
  }
}

onMounted(loadVoiceModels)

// ── 5 个 Agent 定义（与后端插件一一对应）──
const agents = [
  { key: 'ecommerce_sales', name: '电商销售顾问', icon: '🛒', desc: '默认活跃 Agent，推荐商品、促成交易、提升转化率' },
  { key: 'product_catalog', name: '商品知识库助手', icon: '📦', desc: '检索商品详情、规格、价格、库存' },
  { key: 'cross_border', name: '跨境贸易助手', icon: '🌍', desc: '跨境物流、关税计算、清关、海外仓' },
  { key: 'marketing', name: '市场推广助手', icon: '🎯', desc: '促销活动、优惠券、会员权益、积分' },
  { key: 'dispute_resolution', name: '销售纠纷解决助手', icon: '⚖️', desc: 'AI 自动处理投诉：分类、方案、补偿、升级人工' },
]

const currentAgent = computed(() =>
  agents.find((a) => a.key === activeAgent.value.key) || agents[0],
)

// ── 输出渠道（与后端 ChannelRegistry / 设计文档 11.2 节对齐）──
type OutputMode = 'text' | 'voice' | 'both'
interface ChannelItem {
  key: string
  name: string
  icon: string
  desc: string
  active: boolean
  output: OutputMode
}
const channels = reactive<ChannelItem[]>([
  { key: 'wechat', name: '微信', icon: '💬', desc: '国内主流即时通信', active: true, output: 'voice' },
  { key: 'whatsapp', name: 'WhatsApp', icon: '🟢', desc: '全球 180+ 国家', active: true, output: 'text' },
  { key: 'telegram', name: 'Telegram', icon: '✈️', desc: '海外加密即时通信', active: false, output: 'voice' },
  { key: 'messenger', name: 'Messenger', icon: '💙', desc: 'Meta 旗下即时通信', active: false, output: 'text' },
  { key: 'line', name: 'LINE', icon: '🟢', desc: '日韩/东南亚主流', active: false, output: 'text' },
  { key: 'sms', name: '短信', icon: '📱', desc: '全球短信触达', active: false, output: 'text' },
])

const outputModeOptions = [
  { value: 'text', label: '文字' },
  { value: 'voice', label: '语音' },
  { value: 'both', label: '文字+语音' },
]
const outputModeLabel: Record<OutputMode, string> = { text: '文字', voice: '语音', both: '文字+语音' }

const activeChannelCount = computed(() => channels.filter((c) => c.active).length)
const channelSummaryText = computed(() => {
  const active = channels.filter((c) => c.active)
  if (active.length === 0) return '未选中任何渠道，Agent 将仅在语音通道回复'
  return active.map((c) => `${c.name}(${outputModeLabel[c.output]})`).join(' + ')
})

// 右侧面板 Tab：agents / channels / sessions
const activeTab = ref<'agents' | 'channels' | 'sessions'>('agents')

function toggleChannel(ch: ChannelItem) {
  ch.active = !ch.active
  pushLog('channel_toggle', `${ch.name} ${ch.active ? '已选中' : '已取消'}`)
  syncChannelConfig()
}

function onChannelOutputChange(ch: ChannelItem) {
  pushLog('channel_output_mode', `${ch.name} → ${outputModeLabel[ch.output]}`)
  syncChannelConfig()
}

function syncChannelConfig() {
  sendChannelConfig(
    channels.map((c) => ({ key: c.key, active: c.active, output: c.output })),
  )
}

// ── 会话列表 ──
const sessionList = ref<AiChatSession[]>([])
const sessionLoading = ref(false)
async function loadSessions() {
  sessionLoading.value = true
  try {
    const res = await getMySessions({ page_size: 50 })
    sessionList.value = res.items || []
  } catch (e) {
    pushLog('session_error', `加载会话失败：${(e as Error).message}`)
  } finally {
    sessionLoading.value = false
  }
}

// ── 会话详情 ──
const sessionDetailVisible = ref(false)
const selectedSession = ref<AiChatSession | null>(null)
const detailMessages = ref<AiChatMessage[]>([])
const detailMessagesLoading = ref(false)

async function openSessionDetail(s: AiChatSession) {
  selectedSession.value = s
  sessionDetailVisible.value = true
  detailMessages.value = []
  detailMessagesLoading.value = true
  try {
    const [sess, msgs] = await Promise.all([
      getSession(s.session_id),
      getSessionMessages(s.session_id, { page_size: 100 }),
    ])
    if (sess) selectedSession.value = sess
    detailMessages.value = msgs.items || []
  } catch (e) {
    pushLog('session_detail_error', `加载详情失败：${(e as Error).message}`)
  } finally {
    detailMessagesLoading.value = false
  }
}

// 日期格式化
function formatDate(val?: string | null): string {
  if (!val) return '-'
  const d = new Date(val)
  if (isNaN(d.getTime())) return val
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// ── 架构分层数据 ──
const archLayers = [
  {
    label: '前端',
    highlight: false,
    nodes: [
      { name: 'useVoiceChannel', kind: 'existing' },
      { name: 'DSP (去直流/噪声门/重采样)', kind: 'existing' },
      { name: 'WebSocket PCM16', kind: 'existing' },
    ],
  },
  {
    label: '网关',
    highlight: false,
    nodes: [
      { name: 'websocket_gateway.py', kind: 'existing' },
      { name: '能力协商 + 事件归一化', kind: 'existing' },
    ],
  },
  {
    label: '编排层 (新)',
    highlight: true,
    nodes: [
      { name: 'VoiceAgentOrchestrator', kind: 'new' },
      { name: 'IntentRouter (意图分类)', kind: 'new' },
      { name: 'ContextSync (含购物车状态)', kind: 'new' },
      { name: 'PluginRegistry', kind: 'new' },
    ],
  },
  {
    label: '可插拔 Agent (新)',
    highlight: true,
    nodes: [
      { name: 'EcommerceSales', kind: 'new' },
      { name: 'ProductCatalog', kind: 'new' },
      { name: 'CrossBorder', kind: 'new' },
      { name: 'Marketing', kind: 'new' },
      { name: 'DisputeResolution', kind: 'new' },
    ],
  },
  {
    label: '执行器',
    highlight: false,
    nodes: [
      { name: 'AgentscopeRealtimeProvider', kind: 'existing' },
      { name: 'RealtimeAgent (Qwen-Omni)', kind: 'existing' },
      { name: 'server VAD + barge-in + 流式 STT/TTS', kind: 'existing' },
    ],
  },
]

// ── 语音通道 ──
// 用响应式配置对象；会话编号由后端 createSession() 自动生成（AiChatSession.session_id）
const channelConfig = reactive({
  caseNumber: '' as string,
  participantId: 'party_a' as const,
  provider: provider.value,
  modelId: selectedModel.value,
})
watch([provider, selectedModel, backendSessionId], () => {
  channelConfig.caseNumber = backendSessionId.value ? String(backendSessionId.value) : ''
  channelConfig.provider = provider.value
  channelConfig.modelId = selectedModel.value
})

const {
  status,
  ready,
  errorMsg,
  transcripts,
  audioLevel,
  micOn,
  activeAgent,
  connect,
  disconnect,
  sendInterrupt,
  sendText,
  sendChannelConfig,
  startMic,
  stopMic,
} = useVoiceChannel(channelConfig)

// 进入语音通道：先调用后端 createSession() 自动生成会话编号，再连接 WebSocket
async function enterVoiceChannel() {
  if (!selectedModel.value) return
  creatingSession.value = true
  try {
    const sess = await createSession({
      session_title: '全双工语音会话',
      session_type: 'voice',
    })
    backendSessionId.value = sess.session_id
    channelConfig.caseNumber = String(sess.session_id)
    pushLog('session_created', `后端生成会话编号 #${sess.session_id}`)
    showChannel.value = true
    await connect()
    syncChannelConfig()
  } catch (e) {
    errorMsg.value = `创建会话失败：${(e as Error).message}`
  } finally {
    creatingSession.value = false
  }
}

const textInput = ref('')

function onSendText() {
  const t = textInput.value.trim()
  if (!t) return
  sendText(t)
  textInput.value = ''
}

function onToggleMic() {
  if (micOn.value) stopMic()
  else void startMic()
}

// ── 状态展示 ──
const statusText = computed(() => {
  const map: Record<string, string> = {
    idle: '待机中 · 等待语音输入',
    connecting: '连接中...',
    open: micOn.value ? '正在聆听...' : '已连接 · 点击麦克风开始',
    closed: '已断开',
    error: '连接错误',
  }
  return map[status.value] || status.value
})

const stageState = computed(() => {
  if (status.value === 'open' && micOn.value) return 'listening'
  if (status.value === 'open') return 'speaking'
  return ''
})

function barHeight(i: number): number {
  if (status.value !== 'open' || !micOn.value) return 4
  const base = Math.sin(Date.now() / 200 + i * 0.5) * 0.5 + 0.5
  return 4 + base * audioLevel.value * 30
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString()
  } catch {
    return ''
  }
}

// ── 事件日志 ──
interface LogEntry { ts: string; evt: string; msg: string }
const eventLog = ref<LogEntry[]>([
  { ts: '[00:00]', evt: 'init', msg: '页面就绪，等待进入语音通道' },
])
let logTs = 0

function pushLog(evt: string, msg: string) {
  const mm = String(Math.floor(logTs / 60)).padStart(2, '0')
  const ss = String(logTs % 60).padStart(2, '0')
  eventLog.value.push({ ts: `[${mm}:${ss}]`, evt, msg })
  logTs += 2
  if (eventLog.value.length > 100) eventLog.value.shift()
}

// 监听连接状态变化
watch(status, (val) => {
  if (val === 'open') pushLog('connected', `语音通道已连接，活跃 Agent=${activeAgent.value.key}`)
  else if (val === 'closed') pushLog('disconnected', '语音通道已断开')
  else if (val === 'error') pushLog('error', errorMsg.value || '连接错误')
})

// 监听 Agent 切换
watch(
  () => activeAgent.value.key,
  (newKey, oldKey) => {
    if (oldKey && newKey !== oldKey) {
      pushLog('agent_switch', `${oldKey} → ${newKey}`)
    }
  },
)

// 监听转写
watch(transcripts, (list) => {
  const last = list[list.length - 1]
  if (last && last.finalized) {
    const preview = last.text.slice(0, 30)
    pushLog(last.role === 'user' ? 'speech_stopped' : 'tts_play', preview)
  }
})
</script>

<style scoped>
.voice-demo {
  padding: 16px;
  min-height: 100%;
  background: #0a0e1a;
  color: #e5e7eb;
}

/* ── 顶部 ── */
.demo-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.demo-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.demo-badge {
  background: #1f2937;
  border: 1px solid #374151;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  color: #9ca3af;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.model-warn {
  margin-bottom: 12px;
}

/* ── 网格布局 ── */
.demo-grid {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 16px;
}

/* ── 面板通用 ── */
.panel {
  background: #111827;
  border: 1px solid #374151;
  border-radius: 12px;
  overflow: hidden;
}
.panel-title {
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 600;
  color: #9ca3af;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #374151;
  display: flex;
  align-items: center;
  gap: 8px;
}
.panel-title .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #6b7280;
}
.panel-title .dot.active {
  background: #10b981;
  box-shadow: 0 0 8px #10b981;
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ── 语音主区 ── */
.voice-main {
  display: flex;
  flex-direction: column;
  height: 600px;
}
.voice-stage {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: radial-gradient(ellipse at center, rgba(99, 102, 241, 0.08) 0%, transparent 70%);
}
.agent-ring {
  position: relative;
  width: 120px;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.agent-ring .ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid #374151;
}
.agent-ring .ring.active {
  border-color: #6366f1;
  animation: spin 4s linear infinite;
  border-top-color: transparent;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.agent-ring .core {
  width: 76px;
  height: 76px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  box-shadow: 0 0 32px rgba(99, 102, 241, 0.4);
  transition: transform 0.3s;
}
.voice-stage.listening .core {
  transform: scale(1.1);
  box-shadow: 0 0 48px rgba(16, 185, 129, 0.6);
}
.agent-label {
  margin-top: 16px;
  text-align: center;
}
.agent-label .name {
  font-size: 16px;
  font-weight: 600;
  color: #e5e7eb;
}
.agent-label .status-text {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}
.waveform {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  height: 32px;
  margin-top: 16px;
}
.waveform .bar {
  width: 3px;
  background: #6366f1;
  border-radius: 2px;
  transition: height 0.1s;
}

/* ── 转写区 ── */
.transcript-area {
  max-height: 180px;
  overflow-y: auto;
  padding: 12px 16px;
  border-top: 1px solid #374151;
  background: rgba(0, 0, 0, 0.2);
}
.turn {
  margin-bottom: 10px;
}
.turn .role {
  font-size: 11px;
  color: #9ca3af;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.turn .role .tag {
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  background: #1f2937;
}
.turn.user .role .tag {
  background: #3b82f6;
  color: white;
}
.turn.assistant .role .tag {
  background: #6366f1;
  color: white;
}
.turn .text {
  font-size: 13px;
  line-height: 1.6;
  padding: 6px 10px;
  background: #1f2937;
  border-radius: 8px;
  display: inline-block;
  max-width: 85%;
}
.turn.assistant .text {
  background: rgba(99, 102, 241, 0.15);
}
.empty-hint {
  text-align: center;
  color: #6b7280;
  font-size: 13px;
  padding: 20px;
}

/* ── 控制条 ── */
.controls {
  padding: 12px 16px;
  border-top: 1px solid #374151;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.caps {
  margin-left: auto;
  font-size: 11px;
  color: #6b7280;
  font-family: monospace;
}
.error-alert {
  margin: 8px 16px 12px;
}

/* ── Agent 面板 ── */
.agent-panel {
  display: flex;
  flex-direction: column;
}
.agent-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}
.agent-card {
  padding: 12px;
  background: #1f2937;
  border: 1px solid #374151;
  border-radius: 10px;
  transition: all 0.3s;
  position: relative;
}
.agent-card.active {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.1);
  box-shadow: 0 0 16px rgba(99, 102, 241, 0.2);
}
.agent-card.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: #6366f1;
  border-radius: 3px 0 0 3px;
}
.agent-card .head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.agent-card .name {
  font-weight: 600;
  font-size: 13px;
  color: #e5e7eb;
}
.agent-card .icon {
  font-size: 16px;
}
.agent-card .desc {
  font-size: 11px;
  color: #9ca3af;
  line-height: 1.5;
}
.agent-card .switch-hint {
  font-size: 10px;
  color: #f59e0b;
  margin-top: 4px;
}

/* ── Tab 切换 ── */
.tab-bar {
  display: flex;
  gap: 4px;
  padding: 8px 12px 0;
  border-bottom: 1px solid #374151;
}
.tab-bar .tab {
  padding: 8px 14px;
  font-size: 13px;
  color: #9ca3af;
  cursor: pointer;
  border-radius: 8px 8px 0 0;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
}
.tab-bar .tab:hover {
  color: #e5e7eb;
  background: rgba(55, 65, 81, 0.5);
}
.tab-bar .tab.active {
  color: #818cf8;
  background: rgba(99, 102, 241, 0.1);
  border-bottom: 2px solid #6366f1;
}
.tab-bar .tab .tab-badge {
  background: #6366f1;
  color: #fff;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  min-width: 16px;
  text-align: center;
}
.tab-pane {
  flex: 1;
  overflow-y: auto;
}

/* ── 渠道列表 ── */
.channel-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.channel-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #1f2937;
  border: 1px solid #374151;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}
.channel-card:hover {
  border-color: #4b5563;
}
.channel-card.active {
  border-color: #10b981;
  background: rgba(16, 185, 129, 0.08);
}
.channel-card.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: #10b981;
  border-radius: 3px 0 0 3px;
}
.channel-card .ch-icon {
  font-size: 18px;
}
.channel-card .ch-info {
  flex: 1;
  min-width: 0;
}
.channel-card .ch-name {
  font-weight: 600;
  font-size: 13px;
  color: #e5e7eb;
}
.channel-card .ch-desc {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 2px;
}
.channel-card .ch-output {
  width: 90px;
}
.channel-card .ch-toggle {
  width: 18px;
  height: 18px;
  border: 2px solid #4b5563;
  border-radius: 4px;
  flex-shrink: 0;
  position: relative;
}
.channel-card .ch-toggle.on {
  background: #10b981;
  border-color: #10b981;
}
.channel-card .ch-toggle.on::after {
  content: '✓';
  position: absolute;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  top: -2px;
  left: 2px;
}
.channel-summary {
  padding: 10px 12px;
  border-top: 1px solid #374151;
  font-size: 12px;
  color: #9ca3af;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.channel-summary .active-count {
  color: #10b981;
  font-weight: 600;
}
.channel-summary .summary-text {
  color: #d1d5db;
  font-size: 11px;
}

/* ── 会话列表 ── */
.session-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.session-loading {
  text-align: center;
  color: #9ca3af;
  font-size: 13px;
  padding: 24px 0;
}
.session-item {
  padding: 10px 12px;
  background: #1f2937;
  border: 1px solid #374151;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}
.session-item:hover {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.08);
}
.session-item-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.session-item .session-title {
  font-weight: 600;
  font-size: 13px;
  color: #e5e7eb;
}
.session-item .session-count {
  font-size: 11px;
  color: #818cf8;
  background: rgba(99, 102, 241, 0.12);
  padding: 1px 8px;
  border-radius: 8px;
}
.session-item-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #9ca3af;
  margin-top: 6px;
}

/* ── 会话详情弹窗 ── */
.session-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.detail-row {
  display: flex;
  gap: 12px;
  font-size: 13px;
}
.detail-row .detail-label {
  color: #6b7280;
  width: 70px;
  flex-shrink: 0;
}
.detail-row .detail-value {
  color: #1f2937;
  flex: 1;
}
.detail-messages {
  border-top: 1px solid #e5e7eb;
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.detail-messages-title {
  font-weight: 600;
  font-size: 13px;
  color: #374151;
}
.detail-msg {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  background: #f9fafb;
  border-radius: 8px;
  font-size: 13px;
  align-items: baseline;
}
.detail-msg.user {
  background: #eff6ff;
}
.detail-msg.assistant {
  background: #f0fdf4;
}
.detail-msg.system {
  background: #fef3c7;
}
.detail-msg .msg-role {
  font-weight: 600;
  color: #6366f1;
  flex-shrink: 0;
  width: 36px;
}
.detail-msg .msg-content {
  color: #1f2937;
  flex: 1;
  word-break: break-word;
}
.detail-msg .msg-time {
  font-size: 11px;
  color: #9ca3af;
  flex-shrink: 0;
}

/* ── 架构面板 ── */
.arch-panel {
  grid-column: 1 / -1;
}
.arch-content {
  padding: 16px;
}
.arch-layers {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.arch-layer {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: #1f2937;
  border-radius: 8px;
  border: 1px solid #374151;
}
.arch-layer .layer-label {
  width: 110px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  flex-shrink: 0;
}
.arch-layer .layer-body {
  flex: 1;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.arch-node {
  padding: 6px 12px;
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid #6366f1;
  border-radius: 6px;
  font-size: 12px;
  color: #e5e7eb;
}
.arch-node.existing {
  background: rgba(16, 185, 129, 0.1);
  border-color: #10b981;
}
.arch-node.new {
  background: rgba(245, 158, 11, 0.1);
  border-color: #f59e0b;
}
.arch-arrow {
  color: #9ca3af;
  font-size: 14px;
}

/* ── 事件日志 ── */
.event-log {
  max-height: 180px;
  overflow-y: auto;
  padding: 10px 16px;
  background: rgba(0, 0, 0, 0.3);
  font-family: monospace;
  font-size: 11px;
}
.event-line {
  padding: 2px 0;
  display: flex;
  gap: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}
.event-line .ts {
  color: #6b7280;
  flex-shrink: 0;
}
.event-line .evt {
  color: #6366f1;
  flex-shrink: 0;
  min-width: 80px;
}
.event-line .msg {
  color: #d1d5db;
}

/* ── 滚动条 ── */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #374151;
  border-radius: 3px;
}

/* 暗色模式下覆盖 antd 组件 */
:deep(.ant-btn),
:deep(.ant-select),
:deep(.ant-input) {
  color-scheme: dark;
}
</style>
