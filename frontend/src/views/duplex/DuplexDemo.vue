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
      <!-- 主工作区：三 Tab -->
      <section class="panel workspace">
        <div class="tab-bar">
          <div class="tab" :class="{ active: activeTab === 'voice' }" @click="activeTab = 'voice'">
            🎙️ 语音通道
          </div>
          <div class="tab" :class="{ active: activeTab === 'channels' }" @click="activeTab = 'channels'">
            📡 输出渠道管理 <span class="tab-badge">{{ channels.length }}</span>
          </div>
          <div class="tab" :class="{ active: activeTab === 'agents' }" @click="activeTab = 'agents'">
            🧩 Agent 编排器设计管理 <span class="tab-badge">{{ agents.length }}</span>
          </div>
        </div>
        <div class="tab-body">
          <div v-show="activeTab === 'voice'" class="tab-pane">
            <VoiceChannelPanel
              :status="status"
              :ready="ready"
              :error-msg="errorMsg"
              :transcripts="transcripts"
              :audio-level="audioLevel"
              :mic-on="micOn"
              :active-agent-name="activeAgent.name"
              :agent-icon="currentAgent.icon"
              v-model:text-input="textInput"
              @connect="connect"
              @disconnect="disconnect"
              @toggle-mic="onToggleMic"
              @interrupt="sendInterrupt"
              @send-text="onSendText"
            />
          </div>
          <div v-show="activeTab === 'channels'" class="tab-pane">
            <ChannelManagerPanel
              :channels="channels"
              :sync-state="channelSyncState"
              @toggle="toggleChannel"
              @change-output="onChannelOutputChange"
              @add="addChannel"
              @remove="removeChannel"
              @update="updateChannel"
              @test="testChannel"
            />
          </div>
          <div v-show="activeTab === 'agents'" class="tab-pane">
            <AgentOrchestratorManagerPanel
              :agents="agents"
              :active-key="activeAgent.key"
              @activate="activateAgent"
              @toggle="toggleAgent"
              @add="addAgent"
              @remove="removeAgent"
              @update="updateAgent"
              @save="saveAgent"
              @reorder="reorderAgent"
            />
          </div>
        </div>
      </section>

      <!-- 右侧：会话列表 -->
      <SessionListPanel
        :sessions="sessionList"
        :loading="sessionLoading"
        :error="sessionError"
        :selected-id="selectedSessionId"
        @select="openSessionDetail"
      />

      <!-- 底部：输入 / 输出流 -->
      <IoStreamPanel
        :source-label="ioSourceLabel"
        :is-history="ioSource !== 'live'"
        :loading="historyLoading"
        :error="historyError"
        :input-messages="inputMessages"
        :output-messages="outputMessages"
        @back-to-live="backToLive"
      />

      <!-- 底部：运行时事件流 -->
      <EventLogPanel :logs="eventLog" />
    </div>

    <a-empty v-else description="选择语音模型后进入语音通道" />

    <!-- 会话详情弹窗（保留既有能力） -->
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
          <span class="detail-value">{{ formatDateTime(selectedSession.created_at) }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">更新时间</span>
          <span class="detail-value">{{ formatDateTime(selectedSession.updated_at) }}</span>
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
            <span class="msg-time">{{ formatDateTime(m.created_at) }}</span>
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { useVoiceChannel } from '@/composables/useVoiceChannel'
import type { VoiceModel, VoiceProvider, VoiceProviderCatalog } from '@/types/voice'
import {
  listVoiceModels,
  getVoiceModelDefault,
  getVoiceProviderCatalog,
  listDuplexAgents,
  listDuplexChannels,
  upsertDuplexAgent,
  upsertDuplexChannel,
  deleteDuplexAgent,
  deleteDuplexChannel,
  type DuplexAgentConfig,
  type DuplexChannelConfig,
} from '@/api/voice'
import {
  createSession,
  getMySessions,
  getSession,
  getSessionMessages,
  type AiChatSession,
  type AiChatMessage,
} from '@/api/aiSession'
import VoiceChannelPanel from './components/VoiceChannelPanel.vue'
import ChannelManagerPanel from './components/ChannelManagerPanel.vue'
import AgentOrchestratorManagerPanel from './components/AgentOrchestratorManagerPanel.vue'
import SessionListPanel from './components/SessionListPanel.vue'
import IoStreamPanel from './components/IoStreamPanel.vue'
import EventLogPanel from './components/EventLogPanel.vue'
import type {
  AgentView,
  ChannelItem,
  IoMessage,
  LogEntry,
  SessionItem,
  ActivationReason,
  BackendOutputMode,
} from './types'
import { formatDateTime, formatClock, ACTIVATION_LABEL, OUTPUT_MODE_LABEL } from './types'

// ── 配置 ──
const provider = ref<VoiceProvider>('dashscope')
const showChannel = ref(false)
const creatingSession = ref(false)
const backendSessionId = ref<number | null>(null)

const voiceModels = ref<VoiceModel[]>([])
const providerCatalog = ref<VoiceProviderCatalog>({} as VoiceProviderCatalog)
const selectedModel = ref<number | undefined>(undefined)
const modelLoading = ref(false)

const providerOptions = computed(() => {
  const usableProviders = new Set(
    voiceModels.value.filter((m) => m.usable && m.provider_key).map((m) => m.provider_key as string),
  )
  return (Object.values(providerCatalog.value) as VoiceProviderCatalog[keyof VoiceProviderCatalog][])
    .filter((p) => usableProviders.has(p.key))
    .map((p) => ({ label: p.label, value: p.key as VoiceProvider }))
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

const selectedModelInfo = computed(() => voiceModels.value.find((m) => m.id === selectedModel.value))

watch(provider, () => {
  const pool = modelsFor(provider.value)
  if (!pool.some((m) => m.id === selectedModel.value)) {
    selectedModel.value = pool[0]?.id
  }
})

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

    const applyDefault = (m: VoiceModel) => {
      provider.value = m.provider_key ? (m.provider_key as VoiceProvider) : normalizeProviderKey(m.platform)
      selectedModel.value = m.id
    }
    const defaultModel = def?.configured
      ? models.find((m) => m.id === def.model_id && m.usable)
      : undefined
    if (defaultModel) applyDefault(defaultModel)
    else {
      const firstUsable = models.find((m) => m.usable)
      if (firstUsable) applyDefault(firstUsable)
      else selectedModel.value = undefined
    }
  } finally {
    modelLoading.value = false
  }
}

onMounted(() => {
  loadVoiceModels()
  loadSessions()
  loadAgentConfig()
  loadChannelConfig()
})

/** 从后端加载 Agent 设计配置（失败时保留本地默认，优雅降级） */
async function loadAgentConfig() {
  try {
    const res = await listDuplexAgents()
    if (!res?.items?.length) return
    const byKey = new Map(res.items.map((c) => [c.key, c]))
    agents.forEach((a) => {
      const cfg = byKey.get(a.key)
      if (!cfg) return
      a.enabled = cfg.enabled
      a.priority = cfg.priority
      a.prompt = cfg.prompt || a.prompt
      a.rules = cfg.rules || a.rules
      a.tools = cfg.tools || a.tools
      a.runtimeStatus = a.enabled ? a.runtimeStatus : 'disabled'
    })
    pushLog('agent_config_loaded', `已从后端加载 ${res.items.length} 个 Agent 配置`)
  } catch (e) {
    pushLog('agent_config_fallback', `Agent 配置加载失败，使用本地默认：${(e as Error).message}`)
  }
}

/** 从后端加载渠道配置（失败时保留本地默认，优雅降级） */
async function loadChannelConfig() {
  try {
    const res = await listDuplexChannels()
    if (!res?.items?.length) return
    const byKey = new Map(res.items.map((c) => [c.key, c]))
    channels.forEach((ch) => {
      const cfg = byKey.get(ch.key)
      if (!cfg) return
      ch.active = cfg.active
      if (cfg.output && cfg.output !== 'off') {
        ch.output = cfg.output
        ch.lastValidOutput = cfg.output
      }
      if (cfg.capability) ch.capability = cfg.capability
    })
    pushLog('channel_config_loaded', `已从后端加载 ${res.items.length} 个渠道配置`)
  } catch (e) {
    pushLog('channel_config_fallback', `渠道配置加载失败，使用本地默认：${(e as Error).message}`)
  }
}

// ── Agent 编排（与后端插件 key 一一对应）──
const agents = reactive<AgentView[]>([
  { key: 'ecommerce_sales', name: '电商销售顾问', icon: '🛒', desc: '默认活跃 Agent，推荐商品、促成交易、提升转化率', enabled: true, priority: 1, prompt: '你是跨境电商销售顾问，熟悉欧盟 CE 认证与海外仓流程。', rules: ['推荐商品', '价格咨询', '促成交易'], tools: ['商品检索', '关税计算'], runtimeStatus: 'running', activationReason: 'default' },
  { key: 'product_catalog', name: '商品知识库助手', icon: '📦', desc: '检索商品详情、规格、价格、库存', enabled: true, priority: 2, prompt: '你是商品知识库助手，基于知识库准确回答商品问题。', rules: ['商品详情', '库存查询'], tools: ['商品检索'], runtimeStatus: 'standby' },
  { key: 'cross_border', name: '跨境贸易助手', icon: '🌍', desc: '跨境物流、关税计算、清关、海外仓', enabled: true, priority: 3, prompt: '你是跨境贸易专家，提供准确的税费估算与物流方案。', rules: ['关税', '清关', '海外仓'], tools: ['关税计算', '物流查询'], runtimeStatus: 'standby' },
  { key: 'marketing', name: '市场推广助手', icon: '🎯', desc: '促销活动、优惠券、会员权益、积分', enabled: false, priority: 4, prompt: '你是市场推广助手，负责促销与会员权益说明。', rules: ['优惠', '会员'], tools: ['优惠券发放'], runtimeStatus: 'disabled' },
  { key: 'dispute_resolution', name: '销售纠纷解决助手', icon: '⚖️', desc: 'AI 自动处理投诉：分类、方案、补偿、升级人工', enabled: true, priority: 5, prompt: '你是纠纷解决助手，对投诉分类并给出补偿方案。', rules: ['投诉', '退款', '纠纷'], tools: ['工单创建', '人工转接'], runtimeStatus: 'standby' },
])

const currentAgent = computed(() => agents.find((a) => a.key === activeAgent.value.key) || agents[0])

// ── 输出渠道 ──
const channels = reactive<ChannelItem[]>([
  { key: 'wechat', name: '微信', icon: '💬', desc: '国内主流即时通信 · 已配置客服消息 API 凭据', active: true, output: 'voice', capability: 'pending_backend', lastValidOutput: 'voice', stats: { dispatched: 128, succeeded: 126, successRate: '98.4%' } },
  { key: 'whatsapp', name: 'WhatsApp', icon: '🟢', desc: '全球 180+ 国家 · 已配置 Business API 凭据', active: true, output: 'text', capability: 'pending_backend', lastValidOutput: 'text', stats: { dispatched: 64, succeeded: 64, successRate: '100%' } },
  { key: 'telegram', name: 'Telegram', icon: '✈️', desc: '海外加密即时通信 · 尚未配置凭据', active: false, output: 'voice', capability: 'configured', lastValidOutput: 'voice', stats: { dispatched: 0, succeeded: 0, successRate: '—' } },
  { key: 'messenger', name: 'Messenger', icon: '💙', desc: 'Meta 旗下即时通信', active: false, output: 'text', capability: 'enabled', lastValidOutput: 'text' },
  { key: 'line', name: 'LINE', icon: '🟢', desc: '日韩/东南亚主流', active: false, output: 'text', capability: 'enabled', lastValidOutput: 'text' },
  { key: 'sms', name: '短信', icon: '📱', desc: '全球短信触达 · 后端无短信网关', active: false, output: 'text', capability: 'unsupported', lastValidOutput: 'text' },
])

const channelSyncState = ref<'idle' | 'pending' | 'acked'>('idle')
let ackTimer: number | null = null

function markChannelPending() {
  channelSyncState.value = 'pending'
  if (ackTimer !== null) window.clearTimeout(ackTimer)
  // 后端暂无 ACK 时，短暂 pending 后回落到本地已下发，不谎称后端确认
  ackTimer = window.setTimeout(() => {
    channelSyncState.value = 'idle'
  }, 800)
}

function syncChannelConfig() {
  sendChannelConfig(
    channels.map((c) => {
      const backendOutput: BackendOutputMode =
        c.output === 'off' ? c.lastValidOutput : c.output
      return { key: c.key, active: c.active && c.output !== 'off', output: backendOutput }
    }),
  )
  markChannelPending()
}

function toggleChannel(key: string) {
  const ch = channels.find((c) => c.key === key)
  if (!ch) return
  ch.active = !ch.active
  pushLog('channel_toggle', `${ch.name} ${ch.active ? '已选中' : '已取消'}`)
  syncChannelConfig()
}

function onChannelOutputChange(p: { key: string; output: ChannelItem['output'] }) {
  const ch = channels.find((c) => c.key === p.key)
  if (!ch) return
  if (p.output !== 'off') ch.lastValidOutput = p.output
  ch.output = p.output
  if (p.output === 'off') ch.active = false
  pushLog('channel_output_mode', `${ch.name} → ${OUTPUT_MODE_LABEL[p.output]}`)
  syncChannelConfig()
}

function toChannelPayload(ch: ChannelItem): DuplexChannelConfig {
  return {
    key: ch.key, name: ch.name, icon: ch.icon, desc: ch.desc,
    active: ch.active && ch.output !== 'off',
    output: ch.output === 'off' ? ch.lastValidOutput : ch.output,
    capability: ch.capability,
  }
}

async function addChannel(ch: ChannelItem) {
  channels.push(ch)
  pushLog('channel_add', `新增渠道 ${ch.name}`)
  syncChannelConfig()
  try { await upsertDuplexChannel(toChannelPayload(ch)) } catch (e) { pushLog('channel_sync_fail', (e as Error).message) }
}

async function removeChannel(key: string) {
  const ch = channels.find((c) => c.key === key)
  channels.splice(channels.findIndex((c) => c.key === key), 1)
  pushLog('channel_remove', `删除渠道 ${ch?.name || key}`)
  syncChannelConfig()
  try { await deleteDuplexChannel(key) } catch (e) { pushLog('channel_sync_fail', (e as Error).message) }
}

async function updateChannel(ch: ChannelItem) {
  const idx = channels.findIndex((c) => c.key === ch.key)
  if (idx >= 0) channels[idx] = ch
  pushLog('channel_update', `更新渠道 ${ch.name}`)
  syncChannelConfig()
  try { await upsertDuplexChannel(toChannelPayload(ch)) } catch (e) { pushLog('channel_sync_fail', (e as Error).message) }
}

function testChannel(key: string) {
  const ch = channels.find((c) => c.key === key)
  pushLog('channel_test', `${ch?.name || key} 测试发送（模拟，未真实外发）`)
  message.info(`${ch?.name || key}：已模拟发送（未真实外发）`)
}

// ── Agent 管理操作（前端本地，后续接 REST）──
const activationReason = ref<ActivationReason>('default')

function activateAgent(key: string) {
  const a = agents.find((x) => x.key === key)
  if (!a) return
  agents.forEach((x) => {
    x.runtimeStatus = x.key === key ? 'running' : x.enabled ? 'standby' : 'disabled'
  })
  activeAgent.value = { key: a.key, name: a.name }
  activationReason.value = 'manual'
  a.activationReason = 'manual'
  a.activationLabel = ACTIVATION_LABEL.manual
  pushLog('agent_manual_switch', `手动切换 → ${a.key}`)
  sendChannelConfig(buildChannelPayload())
}

function toggleAgent(key: string) {
  const a = agents.find((x) => x.key === key)
  if (!a) return
  a.enabled = !a.enabled
  if (!a.enabled) a.runtimeStatus = 'disabled'
  else if (a.key !== activeAgent.value.key) a.runtimeStatus = 'standby'
  pushLog('agent_toggle', `${a.name} ${a.enabled ? '已启用' : '已停用'}`)
}

function toAgentPayload(a: AgentView): DuplexAgentConfig {
  return {
    key: a.key, name: a.name, icon: a.icon, desc: a.desc,
    enabled: a.enabled, priority: a.priority,
    prompt: a.prompt, rules: a.rules, tools: a.tools,
  }
}

async function addAgent(a: AgentView) {
  agents.push(a)
  pushLog('agent_add', `新增 Agent ${a.name}`)
  try { await upsertDuplexAgent(toAgentPayload(a)) } catch (e) { pushLog('agent_sync_fail', (e as Error).message) }
}

async function removeAgent(key: string) {
  const idx = agents.findIndex((x) => x.key === key)
  const a = agents[idx]
  agents.splice(idx, 1)
  pushLog('agent_remove', `删除 Agent ${a?.name || key}`)
  try { await deleteDuplexAgent(key) } catch (e) { pushLog('agent_sync_fail', (e as Error).message) }
}

async function updateAgent(a: AgentView) {
  const idx = agents.findIndex((x) => x.key === a.key)
  if (idx >= 0) agents[idx] = a
  try { await upsertDuplexAgent(toAgentPayload(a)) } catch (e) { pushLog('agent_sync_fail', (e as Error).message) }
}

async function saveAgent(a: AgentView) {
  pushLog('agent_save', `保存 Agent 设计 ${a.name}（规则 ${a.rules.length} / 工具 ${a.tools.length}）`)
  try {
    await upsertDuplexAgent(toAgentPayload(a))
    message.success(`${a.name} 设计已保存并同步后端`)
  } catch (e) {
    message.success(`${a.name} 设计已保存（本地，后端同步失败：${(e as Error).message}）`)
  }
}

function reorderAgent(p: { key: string; delta: number }) {
  const idx = agents.findIndex((x) => x.key === p.key)
  const target = idx + p.delta
  if (idx < 0 || target < 0 || target >= agents.length) return
  const [item] = agents.splice(idx, 1)
  agents.splice(target, 0, item)
  agents.forEach((a, i) => { a.priority = i + 1 })
  pushLog('agent_reorder', `调整优先级：${item.name} → ${item.priority}`)
}

function buildChannelPayload() {
  return channels.map((c) => ({
    key: c.key,
    active: c.active && c.output !== 'off',
    output: c.output === 'off' ? c.lastValidOutput : c.output,
  }))
}

// ── 会话列表 ──
const sessionList = ref<SessionItem[]>([])
const sessionLoading = ref(false)
const sessionError = ref<string | null>(null)

async function loadSessions() {
  sessionLoading.value = true
  sessionError.value = null
  try {
    const res = await getMySessions({ page_size: 50 })
    sessionList.value = (res.items || []).filter((s) => s.session_type === 'voice').map(toSessionItem)
  } catch (e) {
    sessionError.value = `加载会话失败：${(e as Error).message}`
    pushLog('session_error', sessionError.value!)
  } finally {
    sessionLoading.value = false
  }
}

function toSessionItem(s: AiChatSession): SessionItem {
  return {
    session_id: s.session_id,
    session_title: s.session_title,
    message_count: s.message_count,
    updated_at: s.updated_at,
    session_type: s.session_type,
    status: s.status,
  }
}

// ── 会话详情（保留既有弹窗）──
const sessionDetailVisible = ref(false)
const selectedSession = ref<AiChatSession | null>(null)
const selectedSessionId = ref<number | null>(null)
const detailMessages = ref<AiChatMessage[]>([])
const detailMessagesLoading = ref(false)

// ── 底部 IO 流 ──
const ioSource = ref<'live' | number>('live')
const historyMessages = ref<AiChatMessage[]>([])
const historyLoading = ref(false)
const historyError = ref<string | null>(null)

const ioSourceLabel = computed(() =>
  ioSource.value === 'live'
    ? '当前语音会话 · 实时'
    : `历史会话 #${ioSource.value} · ${sessionList.value.find((s) => s.session_id === ioSource.value)?.session_title || ''}`,
)

const inputMessages = computed<IoMessage[]>(() => {
  if (ioSource.value !== 'live') {
    return historyMessages.value
      .filter((m) => m.role === 'user')
      .map((m, i) => ({
        key: `h-in-${m.message_id ?? i}`,
        role: 'user',
        text: m.content,
        time: formatClock(m.created_at),
        source: 'history',
        statusLabel: '用户输入',
      }))
  }
  return transcripts.value
    .filter((t) => t.role === 'user')
    .map((t) => ({
      key: t.id,
      role: 'user',
      text: t.text,
      time: formatClock(t.started_at),
      source: 'live',
      statusLabel: t.finalized ? 'STT 已定稿' : '识别中…',
    }))
})

const outputMessages = computed<IoMessage[]>(() => {
  if (ioSource.value !== 'live') {
    return historyMessages.value
      .filter((m) => m.role === 'assistant' || m.role === 'system')
      .map((m, i) => ({
        key: `h-out-${m.message_id ?? i}`,
        role: m.role === 'system' ? 'system' : 'assistant',
        text: m.content,
        time: formatClock(m.created_at),
        source: 'history',
        voiceStatus: m.message_type === 'voice' ? 'done' : 'none',
      }))
  }
  const list = transcripts.value.filter((t) => t.role === 'assistant' || t.role === 'system')
  return list.map((t, idx) => ({
    key: t.id,
    role: t.role === 'system' ? 'system' : 'assistant',
    text: t.text,
    time: formatClock(t.started_at),
    source: 'live',
    voiceStatus: liveVoiceStatus(idx, list.length),
    channelTargets: activeChannelTargets.value,
  }))
})

/** 播放状态：仅最新 assistant 且正在播放时标 playing，其余已完成；无文本则 none */
function liveVoiceStatus(idx: number, total: number): 'playing' | 'done' | 'none' {
  const isLatest = idx === total - 1
  if (isLatest && isPlaying.value) return 'playing'
  return 'done'
}

const isPlaying = computed(() => turn.isPlaying.value || turn.voiceState.value === 'speaking')
const activeChannelTargets = computed(() =>
  channels.filter((c) => c.active && c.output !== 'off').map((c) => `${c.name}(${OUTPUT_MODE_LABEL[c.output]})`),
)

async function openSessionDetail(s: SessionItem) {
  selectedSessionId.value = s.session_id
  sessionDetailVisible.value = true
  detailMessages.value = []
  detailMessagesLoading.value = true

  // 底部 IO 流同步切换到该会话
  ioSource.value = s.session_id
  historyMessages.value = []
  historyError.value = null
  historyLoading.value = true

  try {
    const [sess, msgs] = await Promise.all([
      getSession(s.session_id),
      getSessionMessages(s.session_id, { page_size: 100 }),
    ])
    if (sess) selectedSession.value = sess
    detailMessages.value = msgs.items || []
    historyMessages.value = msgs.items || []
  } catch (e) {
    const err = `加载详情失败：${(e as Error).message}`
    historyError.value = err
    pushLog('session_detail_error', err)
  } finally {
    detailMessagesLoading.value = false
    historyLoading.value = false
  }
}

function backToLive() {
  ioSource.value = 'live'
  historyMessages.value = []
  historyError.value = null
  selectedSessionId.value = null
  pushLog('io_stream', '切换回实时语音会话')
}

// ── 语音通道 ──
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
  turn,
  connect,
  disconnect,
  sendInterrupt,
  sendText,
  sendChannelConfig,
  startMic,
  stopMic,
} = useVoiceChannel(channelConfig)

async function enterVoiceChannel() {
  if (!selectedModel.value) return
  creatingSession.value = true
  try {
    const sess = await createSession({ session_title: '全双工语音会话', session_type: 'voice' })
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

function onSendText(text?: string) {
  const t = (text ?? textInput.value).trim()
  if (!t) return
  sendText(t)
  textInput.value = ''
  activationReason.value = 'text'
  pushLog('text_input', t.slice(0, 30))
}

function onToggleMic() {
  if (micOn.value) stopMic()
  else void startMic()
}

// ── 三 Tab ──
const activeTab = ref<'voice' | 'channels' | 'agents'>('voice')

// ── 事件日志 ──
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

watch(status, (val) => {
  if (val === 'open') pushLog('connected', `语音通道已连接，活跃 Agent=${activeAgent.value.key}`)
  else if (val === 'closed') pushLog('disconnected', '语音通道已断开')
  else if (val === 'error') pushLog('error', errorMsg.value || '连接错误')
})

watch(
  () => activeAgent.value.key,
  (newKey, oldKey) => {
    if (oldKey && newKey !== oldKey) {
      pushLog('agent_switch', `${oldKey} → ${newKey}`)
      const a = agents.find((x) => x.key === newKey)
      if (a) {
        a.activationReason = activationReason.value
        a.activationLabel = ACTIVATION_LABEL[activationReason.value]
      }
    }
  },
)

watch(transcripts, (list) => {
  const last = list[list.length - 1]
  if (last && last.finalized) {
    const preview = last.text.slice(0, 30)
    pushLog(last.role === 'user' ? 'speech_stopped' : 'tts_play', preview)
    if (last.role === 'user') activationReason.value = 'voice'
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
.demo-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}
.header-left { display: flex; align-items: center; gap: 12px; }
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
.header-right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.model-warn { margin-bottom: 12px; }

.demo-grid {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 14px;
  align-items: start;
}
.panel {
  background: #111827;
  border: 1px solid #374151;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.04), 0 8px 30px rgba(0, 0, 0, 0.3);
}
.workspace { min-height: 400px; display: flex; flex-direction: column; }
.tab-bar {
  display: flex;
  gap: 4px;
  padding: 8px 12px 0;
  border-bottom: 1px solid #374151;
  flex-shrink: 0;
}
.tab {
  padding: 8px 15px;
  font-size: 13px;
  color: #9ca3af;
  cursor: pointer;
  border-radius: 8px 8px 0 0;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}
.tab:hover { color: #e5e7eb; background: rgba(55, 65, 81, 0.5); }
.tab.active {
  color: #818cf8;
  background: rgba(99, 102, 241, 0.1);
  border-bottom: 2px solid #6366f1;
}
.tab .tab-badge {
  background: #6366f1;
  color: #fff;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  min-width: 16px;
  text-align: center;
}
.tab-body { flex: 1; min-height: 0; overflow-y: auto; }
.tab-pane { min-height: 400px; }

.session-detail { display: flex; flex-direction: column; gap: 12px; }
.detail-row { display: flex; gap: 12px; font-size: 13px; }
.detail-row .detail-label { color: #6b7280; width: 70px; flex-shrink: 0; }
.detail-row .detail-value { color: #1f2937; flex: 1; }
.detail-messages { border-top: 1px solid #e5e7eb; padding-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.detail-messages-title { font-weight: 600; font-size: 13px; color: #374151; }
.session-loading { text-align: center; color: #9ca3af; font-size: 13px; padding: 24px 0; }
.detail-msg { display: flex; gap: 8px; padding: 8px 10px; background: #f9fafb; border-radius: 8px; font-size: 13px; align-items: baseline; }
.detail-msg.user { background: #eff6ff; }
.detail-msg.assistant { background: #f0fdf4; }
.detail-msg.system { background: #fef3c7; }
.detail-msg .msg-role { font-weight: 600; color: #6366f1; flex-shrink: 0; width: 36px; }
.detail-msg .msg-content { color: #1f2937; flex: 1; word-break: break-word; }
.detail-msg .msg-time { font-size: 11px; color: #9ca3af; flex-shrink: 0; }

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #374151; border-radius: 3px; }
:deep(.ant-btn), :deep(.ant-select), :deep(.ant-input), :deep(.ant-input-textarea textarea) { color-scheme: dark; }
</style>
