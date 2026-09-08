<template>
  <div class="ai-dispute-panel">
    <!-- ── 左栏 ── -->
    <SessionSidebar
      :sessions="filteredSessions"
      :current-session-id="currentSession?.session_id"
      v-model:search-text="sessionSearch"
      :loading="loadingSessions"
      v-model:editing-title-id="editingTitleId"
      v-model:editing-title-value="editingTitleValue"
      :file-id="currentFileId"
      :file-name="currentFileName"
      :type-label="typeLabel"
      @new-session="handleNewSession"
      @switch-session="switchSession"
      @delete-session="handleDeleteSession"
      @toggle-pin="togglePin"
      @edit-title-start="startEditTitle"
      @edit-title-submit="submitEditTitle"
      @edit-title-cancel="cancelEditTitle"
      @skill-change="handleSkillScriptChange"
      @agent-change="handleAgentChange"
      @team-change="handleTeamChange"
      :selected-agent-id="currentAgentId"
      :selected-team-id="currentTeamId"
    />

    <!-- ── 右栏 ── -->
    <div class="chat-main">
      <div class="chat-main-header">
        <span class="chat-main-title">{{ currentSession ? currentSession.session_title || typeLabel(sessionType) : '智能助手' }}</span>
        <a-button
          class="async-task-btn"
          type="default"
          shape="round"
          size="small"
          @click="openAsyncTaskManage"
        >
          <UnorderedListOutlined /> 我的异步任务
        </a-button>
      </div>
      <ChatContainer
        ref="chatContainerRef"
        :current-session="currentSession"
        :parsed-messages="parsedMessages"
        :messages="messages"
        :streaming="streaming"
        :streaming-parsed="streamingParsed"
        :streaming-active-tab="streamingActiveTab"
        @update:streamingActiveTab="streamingActiveTab = $event"
        :thinking-expanded="thinkingExpanded"
        :msg-active-tab="msgActiveTab"
        :msg-has-more="msgHasMore"
        :loading-msg="loadingMsg"
        :analysis-progress="analysisProgress"
        :skill-progress="skillProgress"
        :execution-agent-groups="agentGroups"
        :execution-agent-order="agentOrder"
        :execution-team-state="teamState"
        :execution-tasks="tasks"
        :execution-progress-history="progressHistory"
        :execution-phase="executionPhase"
        :current-execution-id="currentExecutionId"
        :streaming-flat-events="flatEvents"
        :is-skill-streaming="isSkillStreaming"
        :is-thinking-streaming="isThinkingStreaming"
        :is-agent-streaming="isAgentStreaming"
        :is-team-streaming="isTeamStreaming"
        :is-research-streaming="isResearchStreaming"
        :streaming-research-sources="streamingResearchSources"
        :streaming-unified-steps="streamingUnifiedStepsRef"
        :streaming-unified-artifacts="streamingUnifiedArtifactsRef"
        :streaming-thinking-content="streamingThinkingContent"
        :streaming-tool-history="streamingToolHistory"
        :default-questions="defaultQuestions"
        :type-label="typeLabel"
        :session-type-color="sessionTypeColor"
        :format-time="formatTime"
        :has-attachments="hasAttachments"
        :get-message-attachments="getMessageAttachments"
        :get-message-analysis="getMessageAnalysis"
        :streaming-sqlbot-data="streamingSqlBotData"
        :current-session-type="sessionType"
        :streaming-text="streamingText"
        :streaming-thinking-steps="streamingThinkingSteps"
        :streaming-research-plan="streamingResearchPlan"
        :streaming-research-stage="streamingResearchStage"
        :streaming-research-progress="streamingResearchProgress"
        :streaming-async-task="streamingAsyncTask"
        :react-events="reactEvents"
        :react-goal="reactGoal"
        :react-plan-status="reactPlanStatus"
        :react-confirm-visible="reactConfirmVisible"
        :react-confirm-question="reactConfirmQuestion"
        :react-confirm-options="reactConfirmOptions"
        :is-react-streaming="isReactStreaming"
        @send-message="sendMessage"
        @load-more="loadMoreMessages"
        @clear-messages="clearMessages"
        @delete-session="handleDeleteSession"
        @toggle-thinking="toggleThinking"
        @copy="copyText"
        @react-pause="handleReactPause"
        @react-resume="handleReactResume"
        @react-cancel="handleReactCancel"
        @react-confirm="handleReactConfirm"
        @react-skip="handleReactSkip"
      />

      <ChatInput
        ref="chatInputRef"
        v-model:input-text="inputText"
        :streaming="streaming"
        v-model:session-type="sessionType"
        :session-type-options="sessionTypeOptions"
        v-model:workspace-id="selectedWorkspaceId"
        :workspace-options="workspaceOptions"
        :current-file-id="currentFileId"
        :current-file-name="currentFileName"
        :skill="currentSkill"
        :agent="currentAgent"
        :team="currentTeam"
        v-model:datasource-id="selectedDatasourceId"
        :datasource-options="datasourceOptions"
        :datasource-loading="datasourceLoading"
        v-model:model-id="selectedModelId"
        :model-options="availableModels"
        @send="sendCurrentInput"
        @stop="stopStreaming"
        @file-uploaded="handleFileUploaded"
        @file-removed="handleFileRemoved"
        @clear-file="currentFileId = ''; currentFileName = ''"
      />
      </div>

    <!-- 会话产物抽屉：汇总当前会话所有归一化产物 -->
    <a-button
      v-if="sessionArtifacts.length"
      class="session-artifact-fab"
      type="primary"
      shape="round"
      @click="showArtifactDrawer = true"
    >
      <UnorderedListOutlined /> 产物 ({{ sessionArtifacts.length }})
    </a-button>
    <a-drawer
      v-model:open="showArtifactDrawer"
      title="会话产物"
      placement="right"
      width="480"
    >
      <div v-for="(a, i) in sessionArtifacts" :key="a.artifact_id || i" class="drawer-artifact">
        <UnifiedTimeline :artifacts="[a]" />
      </div>
      <a-empty v-if="!sessionArtifacts.length" description="暂无产物" />
    </a-drawer>
  </div>
</template>


<script setup lang="ts">
import { ref, computed, onMounted, reactive, watch } from 'vue'
import { UnorderedListOutlined } from '@ant-design/icons-vue'
import { message as antMsg } from 'ant-design-vue'
import { parseMsg, DISPUTE_SECTION_DEFS, type ParsedMsg, type ChatMessage, type SkillInfo, type SqlBotData, type ThinkingStep, type ResearchSubQuestion, type ResearchReport, type AsyncTaskInfo, type UnifiedStep, type UnifiedArtifact, MODEL_SELECTABLE_TYPES } from './types'
import {
  getMySessions, createSession, deleteSession as apiDeleteSession,
  pinSession as apiPinSession, updateSession as apiUpdateSession,
  getSessionMessages, clearSessionMessages as apiClearMessages,
  addSessionMessage,
  getSqlbotDatasources, type AiChatSession, type SqlbotDatasource,
} from '@/api/aiSession'
import { getAvailableModels, type AvailableModel } from '@/api/ai-apikey'
import { getWorkspacesSimple, type WorkspaceSimple } from '@/api/workspace'
import { getUnifiedEvents } from '@/api/agentExecution'
import SessionSidebar from './SessionSidebar.vue'
import ChatContainer from './ChatContainer.vue'
import ChatInput from './ChatInput.vue'
import UnifiedTimeline from './UnifiedTimeline.vue'
import { type UploadedFile } from './FileUploader.vue'
import { getToken } from '@/utils/auth'
import { getDictionaryItems, type DictionaryItem } from '@/api/dictionary'
import { submitDeepResearch } from '@/api/agentWorkspace'
import { useExecutionState } from './renderers/execution/useExecutionState'

// ── 状态 ─────────────────────────────────────────────────────────────────────
const sessions     = ref<AiChatSession[]>([])
const loadingSessions = ref(false)
const sessionSearch   = ref('')
const currentSession  = ref<AiChatSession | null>(null)
const sessionType     = ref('dispute')
const sessionTypeOptions = ref<DictionaryItem[]>([])

// ── 数据源选择 ─────────────────────────────────────────────────────────────
const selectedDatasourceId = ref<number | null>(null)
const datasourceOptions = ref<SqlbotDatasource[]>([])
const datasourceLoading = ref(false)

// ── 模型选择 ─────────────────────────────────────────────────────────────
const selectedModelId = ref<number | null>(null)
const availableModels = ref<AvailableModel[]>([])

// ── 工作空间选择 ─────────────────────────────────────────────────────────
const selectedWorkspaceId = ref<number | null>(null)
const workspaceOptions = ref<WorkspaceSimple[]>([])

const messages    = ref<ChatMessage[]>([])
const loadingMsg  = ref(false)
const msgPage     = ref(1)
const msgPageSize = 50
const msgTotal    = ref(0)
const msgHasMore  = computed(() => messages.value.length < msgTotal.value)

// 会话产物汇总（归一化 artifact）：供抽屉查看/下载
const showArtifactDrawer = ref(false)
const sessionArtifacts = computed(() => {
  const out: UnifiedArtifact[] = []
  for (const m of messages.value) {
    if (m.unifiedArtifacts?.length) out.push(...m.unifiedArtifacts)
  }
  return out
})

const inputText    = ref('')
const streaming    = ref(false)
const streamingText = ref('')
const difyConvId   = ref<string | undefined>(undefined)

// 流式阶段的统一执行事件（归一化 step / artifact），实时驱动执行详情的时间线 Tab
const streamingUnifiedStepsRef = ref<UnifiedStep[] | null>(null)
const streamingUnifiedArtifactsRef = ref<UnifiedArtifact[] | null>(null)

// 流式请求中断控制器
let abortController: AbortController | null = null

function stopStreaming() {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  streaming.value = false
  streamingText.value = ''
  setTimeout(() => { analysisProgress.value = null }, 500)
}

defineExpose({ stopStreaming })

// ── ReAct HITL 控制函数 ────────────────────────────────────────────────────
async function handleReactPause() {
  if (!reactRunId.value) return
  try { await (await import('@/api/react')).pauseReact(reactRunId.value) } catch (e) { console.error(e) }
}
async function handleReactResume() {
  if (!reactRunId.value) return
  try { await (await import('@/api/react')).resumeReact(reactRunId.value) } catch (e) { console.error(e) }
}
async function handleReactCancel() {
  if (!reactRunId.value) return
  try { await (await import('@/api/react')).cancelReact(reactRunId.value) } catch (e) { console.error(e) }
  reactConfirmVisible.value = false
}
async function handleReactConfirm(value: string, action: string) {
  if (!reactRunId.value) return
  try { await (await import('@/api/react')).respondReact(reactRunId.value, { answer: value, action }) } catch (e) { console.error(e) }
  reactConfirmVisible.value = false
}
async function handleReactSkip() {
  if (!reactRunId.value) return
  try { await (await import('@/api/react')).respondReact(reactRunId.value, { answer: '', action: 'skip' }) } catch (e) { console.error(e) }
  reactConfirmVisible.value = false
}

// 技能执行 composable（替代旧 streamingSkillEvents）
const executionState = useExecutionState({ streaming: false } as any)
const { enqueueEvent, agentGroups, agentOrder, teamState, tasks, progressHistory, phase: executionPhase, flatEvents, resetFlatEvents } = executionState
// 保留 executionId 变量用于保存到消息
const currentExecutionId = ref<string | undefined>(undefined)

const streamingThinkingContent = ref('')
const streamingToolHistory = ref<Array<{
  name: string
  input: any
  result?: string
}>>([])

const editingTitleId  = ref<number | null>(null)
const editingTitleValue = ref('')

const thinkingExpanded = reactive<Record<number, boolean>>({})
const msgActiveTab = reactive<Record<number, string>>({})
const streamingActiveTab = ref('case_overview')

const streamingParsed = computed<ParsedMsg>(() => parseMsg(streamingText.value))
/**
 * 复用「执行详情」事件链路（事件入队 + completed 保存路径）的会话模式。
 * thinking 与 skill 使用相同的 SSE 事件契约与保存路径；
 * 渲染层面两者分离：thinking 用独立的 ThinkingExecutionPanel（isThinkingStreaming）。
 * team 模式在收到 engine_decision(engine_code 含 'skill:team') 后由
 * isTeamSkillExecution 动态置位，同样走该链路。
 */
const EXECUTION_PANEL_MODES = ['skill', 'thinking', 'agent', 'team', 'deep_research']
/** 是否为执行详情面板模式流式执行（用于 ChatContainer 切换到 SkillExecutionPanel）。 */
const isTeamSkillExecution = ref(false)
const isSkillStreaming = computed(() =>
  streaming.value && (sessionType.value === 'skill' || isTeamSkillExecution.value)
)
/** 思考模式流式执行（渲染走独立的 ThinkingExecutionPanel）。 */
const isThinkingStreaming = computed(() =>
  streaming.value && sessionType.value === 'thinking'
)
/** 智能体模式流式执行（渲染走独立的 AgentExecutionPanel）。 */
const isAgentStreaming = computed(() =>
  streaming.value && sessionType.value === 'agent'
)
/** 智能体团队模式流式执行（渲染走独立的 TeamExecutionPanel）。 */
const isTeamStreaming = computed(() =>
  streaming.value && sessionType.value === 'team'
)
/** 深度研究模式流式执行（渲染走独立的 DeepResearchExecutionPanel）。 */
const isResearchStreaming = computed(() =>
  streaming.value && sessionType.value === 'deep_research'
)
/** 深度研究流式来源列表 */
const streamingResearchSources = ref<Array<{ title: string; url?: string; snippet?: string }>>([])
let userTabSelected = false

// ── 数据分析流式状态 ─────────────────────────────────────────────────────────
const streamingSqlBotData = ref<SqlBotData | null>(null)
// 每个 AI session 对应的 SQLBot chat_id（多轮对话上下文）
const sqlbotChatIdMap = reactive<Record<number, number>>({})

// ── 思考 / 深度研究 / 云端调度 流式状态 ─────────────────────────────────────
const streamingThinkingSteps = ref<ThinkingStep[]>([])
const streamingThinkingActive = ref(false)   // 是否正在思考（未结束）
const streamingResearch = ref<{
  topic?: string
  stage: string
  progress: number
  plan: ResearchSubQuestion[]
  report?: ResearchReport
}>({ stage: '', progress: 0, plan: [] })
const streamingAsyncTask = ref<AsyncTaskInfo | null>(null)

// ── ReAct 模式流式状态 ───────────────────────────────────────────────────────
const reactEvents = ref<Array<{ type: string; [key: string]: any }>>([])
const reactGoal = ref('')
const reactPlanStatus = ref('planning')
const reactRunId = ref<string | null>(null)
const reactConfirmVisible = ref(false)
const reactConfirmQuestion = ref('')
const reactConfirmOptions = ref<Array<{ label: string; value: string; description?: string }>>([])
/** ReAct 模式流式执行（渲染走独立的 ReactTimeline）。 */
const isReactStreaming = computed(() =>
  streaming.value && sessionType.value === 'react'
)

// 便于模板绑定的派生变量
const streamingResearchPlan = computed(() => streamingResearch.value.plan)
const streamingResearchStage = computed(() => streamingResearch.value.stage)
const streamingResearchProgress = computed(() => streamingResearch.value.progress)

// SCHEDULED 模式参数（来自 ChatInput 表单）
const currentScheduledTarget = ref<string>('agent')
const currentScheduledPriority = ref<number>(5)
const currentScheduledTimeout = ref<number>(1800)
const currentScheduledRetries = ref<number>(2)
const currentUserId = ref<number>(Number(localStorage.getItem('userId') || 0))

const parsedMessages = computed<ChatMessage[]>(() =>
  messages.value.map(msg => {
    const parsed = msg.role === 'assistant' ? parseMsg(msg.content) : undefined
    // 从 extra_data 重建 sqlbotData（历史消息）
    let sqlbotData: SqlBotData | undefined
    const extra = (msg as any).extra_data
    if (extra?.nl2sql) {
      sqlbotData = {
        stage: 'done',
        sql: extra.sql || undefined,
        // 历史消息不存储完整 records，仅显示摘要
        records: undefined,
        total: extra.record_count ?? undefined,
      }
    }
    // 从 extra_data 重建技能执行信息（历史消息回放）：
    // 持久化消息的 extra_data 含 execution_id，页面重载后据此渲染 ExecutionPanel 并加载历史事件
    const executionId = (msg as any).executionId || extra?.execution_id
    const skillEvent = (msg as any).skillEvent || !!executionId
    // 从 extra_data 重建思考模式信息（历史消息回放）：
    // thinking_steps 由后端 _gateway_meta.extra_data 持久化，驱动 ThinkingExecutionPanel
    const thinkingMode = (msg as any).thinkingMode || !!extra?.thinking_mode
    const thinkingSteps = (msg as any).thinkingSteps
      || (Array.isArray(extra?.thinking_steps) && extra.thinking_steps.length
        ? extra.thinking_steps
        : undefined)
    // 从 extra_data 重建深度研究后台异步任务卡片（历史消息回放）：
    // 离开会话/刷新后 loadMessages 拉回的消息需据此渲染 research-async 卡片并自动轮询进度
    const renderKind = (msg as any).renderKind || extra?.renderKind
    const asyncTask = (msg as any).asyncTask || extra?.asyncTask
    return { ...msg, parsed, sqlbotData, executionId, skillEvent, thinkingMode, thinkingSteps, renderKind, asyncTask }
  })
)

// ── 文件上传/附件 ────────────────────────────────────────────────────────────
const currentFileId = ref<string>('')
const currentFileName = ref<string>('')
const currentSkill = ref<SkillInfo | null>(null)

// 选中的 Agent（智能体模式）
const currentAgent = ref<{ id: number; code: string; name: string; category?: string | null } | null>(null)
const currentAgentId = computed(() => currentAgent.value?.id ?? null)

// 选中的专家团（团队模式）
const currentTeam = ref<{ id: number; code: string; name: string; category?: string | null } | null>(null)
const currentTeamId = computed(() => currentTeam.value?.id ?? null)

const analysisProgress = ref<{
  stage: string; message: string; progress: number
  fileContext?: { attached_files?: any[]; file_count?: number }
} | null>(null)

// 技能执行进度信息
const skillProgress = ref<{ stage: string; message: string } | null>(null)

const chatContainerRef = ref<InstanceType<typeof ChatContainer>>()
const chatInputRef = ref<InstanceType<typeof ChatInput>>()

function handleFileUploaded(file: UploadedFile) {
  currentFileId.value = file.file_id || ''
  currentFileName.value = file.name
}
function handleFileRemoved(file: UploadedFile) {
  if (file.file_id === currentFileId.value) {
    currentFileId.value = ''
    currentFileName.value = ''
  }
}
function handleSkillScriptChange(info: SkillInfo | null) {
  currentSkill.value = info
  // 选中技能时自动切换会话类型为 skill
  if (info) {
    sessionType.value = 'skill'
    // 切换为技能时清理已选 Agent
    currentAgent.value = null
  }
}

function handleAgentChange(info: { id: number; code: string; name: string; category?: string | null } | null) {
  currentAgent.value = info
  // 选择 Agent 时自动切换会话类型为 agent（智能体）
  if (info) {
    sessionType.value = 'agent'
    // 切换为 Agent 时清理已选技能
    currentSkill.value = null
  }
}

function handleTeamChange(info: { id: number; code: string; name: string; category?: string | null } | null) {
  currentTeam.value = info
  // 选择专家团时自动切换会话类型为 team
  if (info) {
    sessionType.value = 'team'
    // 切换为团队时清理已选技能 / 专家
    currentSkill.value = null
    currentAgent.value = null
  }
}

// session_type 切换时，清理与当前类型不匹配的选中项
watch(sessionType, (newType) => {
  // 技能对象与模型选择是两个独立关注点，需拆开判断
  if (newType !== 'skill') {
    currentSkill.value = null
  }
  // 仅当目标类别不支持模型选择时才重置已选模型，避免误清空 agent/team/scheduled/thinking/deep_research
  if (!MODEL_SELECTABLE_TYPES.includes(newType)) {
    selectedModelId.value = null
  }
  if (newType !== 'agent') {
    currentAgent.value = null
  }
  if (newType !== 'team') {
    currentTeam.value = null
  }
  // 切换为数据分析时，清理已选附件
  if (newType === 'data') {
    currentFileId.value = ''
    currentFileName.value = ''
  }
})

function hasAttachments(msg: ChatMessage): boolean {
  if (msg.file?.id) return true
  if (msg.attachments && msg.attachments.length > 0) return true
  if (msg.file_db_ids && msg.file_db_ids.length > 0) return true
  return false
}
function getMessageAttachments(msg: ChatMessage): Array<any> {
  const result: any[] = []
  if (msg.file?.id) result.push({ file_id: `db-${msg.file.id}`, db_id: msg.file.id, name: msg.file.name, size: msg.file.size, url: msg.file.url, type: msg.file.type })
  if (msg.attachments?.length) msg.attachments.forEach((a) => result.push(a))
  return result
}

// ── 工具函数 ─────────────────────────────────────────────────────────────────
const defaultQuestions = [
  '2023年11月8日，原告杭州天堂软件科技公司[组织机构编码:91110108MA01K8XJ2H]与被告杭州茂盛精密技术公司[组织机构编码:91310115MA1K3YD76L]签订《产品销售合同书》（合同编号：JYD202311009）。被告某精密技术公司向原告某科技公司采购27台VTC600C钻攻中心，每台单价为人民币188,000元，合同总金额为人民币5,076,000元。截至起诉之日，被告某精密技术公司仍拖欠原告货款本金人民币3,676,000元。原告多次追索无果，被告某精密技术公司的违约行为给原告造成了重大经济损失。 被告某通信设备公司作为被告某精密技术公司的唯一股东，应对被告某精密技术公司的债务承担连带清偿责任。被告某精密技术公司拖欠原告货款的行为严重损害了原告的合法权益，案涉二十七台机械设备至今仍处于可能被非法转移、处置的高度风险之中，原告某科技公司的合法权益也持续地被被告损害？',
  '张先生在 2023 年 11 月多次向王三支付宝及银行卡转 账共计 16000 元，后多次找王三追要均以下个月给搪塞 且态度恶劣，',
  '被告李某[身份证号:320198709123245]于2013年05月14日向原告处申请办理信用卡，并签署《某银行 信用卡领用合约》，原告经审核向被告发放信用卡，卡号。透支金额：33048.02元 利息、滞纳金/违约金的计算标准： 利息：自原告记账日起按日利率万分之五计收利息至清偿日止； 滞纳金/违约金：按照被告每期账单最低还款额未还部分的5%计收滞纳金/违 约金；逾期时间：2024年01月19日 截至2025年05月13日，被告李某尚欠人民币本金13356.42元、人民币利息 1863.48元、人民币滞纳金/违约金529.38元；美元本金2034.64美元、美元利 息284.33美元、美元滞纳金/违约金80.9美元。',
]

const filteredSessions = computed(() => {
  const kw = sessionSearch.value.trim().toLowerCase()
  return kw ? sessions.value.filter(s => (s.session_title || '').toLowerCase().includes(kw)) : sessions.value
})

function typeLabel(t: string) {
  const item = sessionTypeOptions.value.find(o => (o.item_value || o.item_code) === t)
  return item?.item_name ?? ({ general: '通用', dispute: '纠纷', data: '数据', skill: '技能', agent: '智能体', team: '专家团', thinking: '思考', deep_research: '深度研究', scheduled: '云端调度', react: 'ReAct 计划' } as Record<string, string>)[t] ?? t
}
function sessionTypeColor(t: string) {
  const item = sessionTypeOptions.value.find(o => (o.item_value || o.item_code) === t)
  return item?.color ?? ({ general: 'cyan', dispute: 'purple', data: 'orange', skill: 'green', agent: 'blue', team: 'geekblue', thinking: 'gold', deep_research: 'magenta', scheduled: 'volcano', react: 'lime' } as Record<string, string>)[t] ?? 'default'
}
function formatTime(t: string) { return t ? t.replace('T', ' ').slice(0, 16) : '' }
async function copyText(t: string) { await navigator.clipboard.writeText(t); antMsg.success('已复制') }
function scrollToBottom(smooth = true) { chatContainerRef.value?.scrollToBottom(smooth) }
function toggleThinking(id: number) { thinkingExpanded[id] = !thinkingExpanded[id] }

// ── 会话管理 ─────────────────────────────────────────────────────────────────
async function loadSessions() {
  loadingSessions.value = true
  try { const res = await getMySessions({ page: 1, page_size: 100 }) as any; sessions.value = res?.items ?? [] }
  finally { loadingSessions.value = false }
}
async function loadMessages(prepend = false) {
  if (!currentSession.value) return
  loadingMsg.value = true
  try {
    const res = await getSessionMessages(currentSession.value.session_id, { page: msgPage.value, page_size: msgPageSize }) as any
    const items: ChatMessage[] = res?.items ?? []
    msgTotal.value = res?.total ?? 0
    if (prepend) messages.value = [...items, ...messages.value]
    else { messages.value = items; scrollToBottom(false) }
    // 归一化事件回放：历史消息若含 executionId 但缺 unifiedSteps/Artifacts，异步补全
    void replayUnifiedEvents(items)
  } finally { loadingMsg.value = false }
}

/** 历史消息重连：回拉后端归一化事件，补全时间线与产物画廊 */
async function replayUnifiedEvents(items: ChatMessage[]) {
  const targets = items.filter(
    m => m.role === 'assistant' && m.executionId && !m.unifiedSteps?.length && !m.unifiedArtifacts?.length,
  )
  if (!targets.length) return
  await Promise.all(targets.map(async (m) => {
    try {
      const data = await getUnifiedEvents(m.executionId!) as any
      const msg = messages.value.find(x => x.message_id === m.message_id)
      if (!msg) return
      if (data.steps?.length) msg.unifiedSteps = data.steps
      if (data.artifacts?.length) msg.unifiedArtifacts = data.artifacts
    } catch {
      /* 回放失败不影响主流程 */
    }
  }))
}
async function loadMoreMessages() { msgPage.value++; await loadMessages(true) }

async function switchSession(s: AiChatSession) {
  if (currentSession.value?.session_id === s.session_id) return
  currentSession.value = s; sessionType.value = s.session_type
  difyConvId.value = undefined; messages.value = []; msgPage.value = 1; msgTotal.value = 0
  userTabSelected = false; streamingActiveTab.value = 'case_overview'
  streamingSqlBotData.value = null
  await loadMessages()
}
async function handleNewSession() {
  const userType = sessionType.value
  const s = await createSession({ session_type: userType }) as any
  await loadSessions()
  const found = sessions.value.find(x => x.session_id === s?.session_id)
  if (found) await switchSession(found)
  else if (sessions.value.length > 0) await switchSession(sessions.value[0])
  sessionType.value = userType  // 保持用户选择的类型
}
async function handleDeleteSession(sessionId: number) {
  await apiDeleteSession(sessionId); antMsg.success('删除成功')
  if (currentSession.value?.session_id === sessionId) { currentSession.value = null; messages.value = [] }
  await loadSessions()
}
async function togglePin(s: AiChatSession) { await apiPinSession(s.session_id, !s.is_pinned); await loadSessions() }
function startEditTitle(s: AiChatSession) { editingTitleId.value = s.session_id; editingTitleValue.value = s.session_title || '' }
function cancelEditTitle() { editingTitleId.value = null }
async function submitEditTitle(s: AiChatSession) {
  const title = editingTitleValue.value.trim(); editingTitleId.value = null
  if (!title || title === s.session_title) return
  await apiUpdateSession(s.session_id, title); await loadSessions()
  if (currentSession.value?.session_id === s.session_id) currentSession.value = { ...currentSession.value, session_title: title }
}
async function clearMessages() {
  if (!currentSession.value) return
  await apiClearMessages(currentSession.value.session_id)
  messages.value = []; msgTotal.value = 0; difyConvId.value = undefined
  // 清空消息时同时重置 SQLBot 会话，开始全新对话
  delete sqlbotChatIdMap[currentSession.value.session_id]
  antMsg.success('已清空消息'); await loadSessions()
}

// 打开「我的异步任务」管理界面（通过全局事件通知后台容器 index.vue 打开对应 Tab）
function openAsyncTaskManage() {
  window.dispatchEvent(new CustomEvent('open-async-task-manage'))
}

function sendCurrentInput() {
  const t = inputText.value.trim()
  if (!t || streaming.value) return
  // skill 模式必须选中技能才能提交
  if (sessionType.value === 'skill' && !currentSkill.value) {
    antMsg.warning('请先选择一个技能')
    return
  }
  // agent 模式必须选中专家才能提交
  if (sessionType.value === 'agent' && !currentAgent.value) {
    antMsg.warning('请先选择一个专家')
    return
  }
  // team 模式必须选中专家团才能提交
  if (sessionType.value === 'team' && !currentTeam.value) {
    antMsg.warning('请先选择一个专家团')
    return
  }
  sendMessage(t)
}

function generateSuggestions(q: string, a: string, type: string): string[] {
  // skill 类型不显示追问
  if (type === 'skill') return []

  // data 数据分析类型：针对数据结果、图表、洞察等追问
  if (type === 'data') {
    const text = q + a
    if (text.includes('趋势') || text.includes('变化') || text.includes('增长率'))
      return ['这个趋势的主要原因是什么？', '能否对比去年同期数据？', '预测未来3个月的趋势如何？']
    if (text.includes('占比') || text.includes('比例') || text.includes('分布'))
      return ['各部分的具体数值是多少？', '占比最大的原因是什么？', '能否按时间维度细分？']
    if (text.includes('异常') || text.includes('波动') || text.includes('峰值'))
      return ['这些异常点的根本原因是什么？', '能否排除季节性因素后再分析？', '异常发生的频率如何？']
    return ['能否换个维度重新分析？', '这些数据有哪些值得关注的异常？', '能否生成更详细的统计报表？']
  }

  // general 通用追问
  return ['能否再详细解释一下？', '还有哪些需要注意的点？', '有没有相关的案例可以参考？']
}

// 防重发状态：记录上一次发送的文本和时间戳
let _lastSentText = ''
let _lastSentAt = 0

// ── 深度研究后台异步提交 ──────────────────────────────────────────────────
// 提交后不占用 SSE 连接：立即 push 一张后台任务卡片（DeepResearchTaskCard），
// 由卡片自行轮询任务状态与实时研究进度，完成后展示报告并支持下载。
async function submitDeepResearchAsync(topic: string, sessionId: number) {
  try {
    // 1. 先持久化用户提问消息，保证会话历史完整可回放
    try {
      await addSessionMessage(sessionId, { role: 'user', content: topic, message_type: 'text' })
    } catch { /* 不影响后续提交 */ }

    // 2. 提交后台异步任务
    const resp = await submitDeepResearch(topic, {
      session_id: sessionId,
      model_id: selectedModelId.value ?? null,
      context: { knowledge_bases: ['legal'], max_sub_questions: 8, max_concurrency: 4 },
    })
    const task: AsyncTaskInfo = {
      taskId: resp.task_id,
      taskNo: resp.task_no,
      taskName: `深度研究：${topic.slice(0, 40)}${topic.length > 40 ? '…' : ''}`,
      status: (resp.status as AsyncTaskInfo['status']) || 'queued',
      progress: 0,
      resultData: undefined,
      submittedAt: new Date().toISOString(),
    }
    const msgId = Date.now()
    const msg: ChatMessage = {
      message_id: msgId,
      session_id: sessionId,
      role: 'assistant',
      content: '',
      message_type: 'text',
      created_at: new Date().toISOString(),
      renderKind: 'research-async',
      asyncTask: task,
      suggestedQuestions: [],
    }
    messages.value.push(msg)

    // 3. 持久化助手任务卡片消息（extra_data 携带 asyncTask + renderKind，
    //    离开会话后再返回时由 loadMessages 拉回并重放，解决「无任务显示」问题）
    try {
      await addSessionMessage(sessionId, {
        role: 'assistant',
        content: '',
        message_type: 'async_task',
        extra_data: { renderKind: 'research-async', asyncTask: task },
      })
    } catch { /* 持久化失败不阻断前端实时展示 */ }

    await loadSessions()
    scrollToBottom()
  } catch (e: any) {
    antMsg.error(e?.message || '深度研究提交失败')
  }
}

// ── 发送消息（SSE 流式） ──────────────────────────────────────────────────────
async function sendMessage(text?: string) {
  const msgText = (text ?? inputText.value).trim()
  if (!msgText || streaming.value) return

  // 防重发：同一文本在短时间内（1.5s）已发送过则忽略，
  // 避免快速连点 suggestedQuestions 按钮 / HMR 重挂载导致的重复请求
  const now = Date.now()
  if (_lastSentText === msgText && now - _lastSentAt < 1500) return
  _lastSentText = msgText
  _lastSentAt = now

  // 先捕获用户选择的类型，防止 switchSession 用数据库值覆盖
  const activeSessionType = sessionType.value

  if (!currentSession.value) {
    const s = await createSession({ session_type: activeSessionType }) as any
    await loadSessions()
    const found = sessions.value.find(x => x.session_id === s?.session_id)
    if (found) await switchSession(found); else if (sessions.value.length > 0) await switchSession(sessions.value[0])
    // 恢复用户选择的类型
    sessionType.value = activeSessionType
  }

  inputText.value = ''; streaming.value = true; streamingText.value = ''
  userTabSelected = false; streamingActiveTab.value = 'case_overview'
  analysisProgress.value = null
  streamingSqlBotData.value = null
  skillProgress.value = null
  // 重置执行状态 composable
  agentGroups.value.clear()
  agentOrder.value.splice(0)
  teamState.value = { id: '', name: '', status: 'pending', agentsCount: 0, completedAgents: 0 }
  tasks.value.splice(0)
  progressHistory.value.splice(0)
  executionPhase.value = 'idle'
  streamingThinkingContent.value = ''
  // 思考步骤/激活态一并重置：thinking_start 事件仅在首条思考内容到达时由后端下发，
  // 若本轮无思考内容（协议未遵守且无原生思维链），上轮步骤会残留到面板
  streamingThinkingSteps.value = []
  streamingThinkingActive.value = false
  streamingToolHistory.value = []
  streamingResearchSources.value = []
  currentExecutionId.value = undefined
  resetFlatEvents()
  // ReAct 模式重置
  reactEvents.value = []
  reactGoal.value = ''
  reactPlanStatus.value = 'planning'
  reactRunId.value = null
  reactConfirmVisible.value = false
  reactConfirmQuestion.value = ''
  reactConfirmOptions.value = []
  let _pendingSkillAnswer = ''  // 暂存技能回答，等 _gateway_meta 到达后再保存消息
  let _pendingArtifacts: Array<{ file_id: string; filename: string; size_bytes: number; mime_type: string }> | undefined
  // 统一步骤/产物事件（跨 8 种模式归一化时间线 + 产物画廊）
  // 直接复用外层 ref（此前为局部 ref，值无法回流到 streamingUnifiedStepsRef，
  // 导致 ChatContainer 通过 props 读到的始终是 null，时间线 Tab 无数据）
  const streamingUnifiedSteps = streamingUnifiedStepsRef
  const streamingUnifiedArtifacts = streamingUnifiedArtifactsRef
  // 新一轮对话开始，清空上一轮残留的时间线数据
  streamingUnifiedSteps.value = null
  streamingUnifiedArtifacts.value = null
  // 执行详情面板模式标志：由后端 engine_decision 的 engine_code 可靠判定（后端 resolve_mode 只看 skill 信息，
  // 与 session_type 无关，故不能仅凭 activeSessionType 判断，否则事件不入队、界面卡在“技能执行中”）。
  // thinking 与 skill 共用该路径（两者 SSE 事件契约一致），保证展示与交互完全一致。
  let isSkillExecution = EXECUTION_PANEL_MODES.includes(activeSessionType)
  // team 模式重置：每次新对话开始时重置 team skill 标记，由 engine_decision 重新置位
  isTeamSkillExecution.value = false

  const token = getToken()
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

  const fileList = chatInputRef.value?.getFileList() || []
  messages.value.push({
    message_id: Date.now(),
    session_id: currentSession.value!.session_id,
    role: 'user', content: msgText, message_type: 'text',
    created_at: new Date().toISOString(),
    attachments: fileList.filter(f => f.status === 'done').map(f => ({
      file_id: f.file_id, db_id: f.db_id, name: f.name, size: f.size,
      url: f.url || `${baseUrl}/api/v1/ai/files/${f.file_id}`,
    })),
    file_db_ids: fileList.filter(f => f.status === 'done' && f.db_id).map(f => f.db_id!),
  })
  scrollToBottom()

  // ── 深度研究：后台异步执行 ──────────────────────────────
  // 提交即返回 task_id，由 DeepResearchTaskCard 轮询任务状态 + 实时拉取研究进度，
  // 不再占用前端 SSE 连接，支持事后在历史会话中查看/下载结果。
  if (activeSessionType === 'deep_research') {
    await submitDeepResearchAsync(msgText, currentSession.value!.session_id)
    streaming.value = false
    return
  }

  const fileIds = chatInputRef.value?.getFileIds() || []
  const fileDbIds = fileList.filter(f => f.status === 'done' && f.db_id).map(f => f.db_id!)

  let accAnswer = '', newDifyConvId: string | undefined = difyConvId.value
  let _teamResultReceived = false // 标记 team_result 是否已收到，防止 completed/done 再次追加相同内容
  let _assistantMsgSaved = false // 非技能模式（含 team）消息是否已保存，防止 done/completed 双重 push

  try {
    abortController = new AbortController()
    const res = await fetch(`${baseUrl}/api/v1/ai-agent/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      signal: abortController.signal,
      body: JSON.stringify({
        message: msgText,
        session_id: currentSession.value!.session_id,
        session_type: activeSessionType,
        dify_conversation_id: difyConvId.value,
        sqlbot_chat_id: sqlbotChatIdMap[currentSession.value!.session_id] || null,
        sqlbot_datasource_id: selectedDatasourceId.value || null,
        file_ids: fileIds, file_db_ids: fileDbIds,
        skill: currentSkill.value ? {
          package_id: currentSkill.value.packageId, package_name: currentSkill.value.packageName,
          script_id: currentSkill.value.scriptId, script_name: currentSkill.value.scriptName,
          params: currentSkill.value.params || {},
        } : null,
        // 智能体模式：提交选中的 Agent id 与 code
        agent_id: currentAgent.value ? currentAgent.value.id : null,
        agent_code: currentAgent.value ? currentAgent.value.code : null,
        team_id: currentTeam.value ? currentTeam.value.id : null,
        team_code: currentTeam.value ? currentTeam.value.code : null,
        model_id: selectedModelId.value || null,
        workspace_id: selectedWorkspaceId.value || null,
        // SCHEDULED 模式：提交目标模式与优先级/超时/重试参数
        ...(activeSessionType === 'scheduled' ? {
          context: {
            target_mode: currentScheduledTarget.value || 'agent',
            priority: currentScheduledPriority.value ?? 5,
            timeout_seconds: currentScheduledTimeout.value ?? 1800,
            max_retries: currentScheduledRetries.value ?? 2,
            user_id: currentUserId.value,
          },
        } : {}),
        // DEEP_RESEARCH 模式：联合检索的知识库类型
        ...(activeSessionType === 'deep_research' ? {
          context: { knowledge_bases: ['legal'], max_sub_questions: 8, max_concurrency: 4 },
        } : {}),
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)

    const reader = res.body!.getReader(); const decoder = new TextDecoder(); let buf = ''
    let _skillStreamDone = false  // 技能 done 已收到：进入收尾宽限读取（继续收 step(run_done)/completed）
    let _skillMsgSaved = false   // 技能消息是否已由 completed 事件保存
    while (true) {
      let readResult: { done: boolean; value?: Uint8Array } | null = null
      if (_skillStreamDone) {
        // 收尾宽限读取：done 之后后端还会发出最后 step（run_done「技能执行完成」）
        // 与 completed（携带 execution_id，是消息持久化/回放的关键），
        // 这些事件可能分包到下一个 HTTP chunk，若立即退出会丢弃导致时间线缺最后一步。
        // 流关闭或 1.5s 无新数据均退出。
        let graceTimer: ReturnType<typeof setTimeout> | null = null
        readResult = await Promise.race([
          reader.read(),
          new Promise<null>(resolve => { graceTimer = setTimeout(() => resolve(null), 1500) }),
        ])
        if (graceTimer) clearTimeout(graceTimer)
        if (!readResult) break
      } else {
        readResult = await reader.read()
      }
      if (readResult.done) break
      const value = readResult.value
      buf += decoder.decode(value!, { stream: true })
      const lines = buf.split('\n'); buf = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.startsWith('data:')) continue
        const data = line.slice(5).trim(); if (!data || data === '[DONE]') continue
        try {
          const chunk = JSON.parse(data)
          // 兼容两种事件类型字段：type（旧/agent 模式）和 event_type（team 模式）
          const eventType = chunk.type || chunk.event_type
          if (eventType === '_gateway_meta') {
            // 注意：_gateway_meta 被后端 ai_agent.py 拦截（continue），实际不会到达前端。
            // 保留此分支作为兼容：若未来后端放开此事件，可正确提取 execution_id。
            currentExecutionId.value = chunk.extra_data?.execution_id || currentExecutionId.value
            if (chunk.answer) {
              accAnswer = chunk.answer
              streamingText.value = accAnswer
            }
          } else if (eventType === 'token') {
            accAnswer += chunk.token; streamingText.value = accAnswer
            newDifyConvId = chunk.conversation_id || newDifyConvId
            const sp = streamingParsed.value
            if (sp.isDispute && !userTabSelected) {
              let last = 'case_overview'
              for (const d of DISPUTE_SECTION_DEFS) { if (sp.sections[d.key]) last = d.key }
              // 引用内容出现时自动切到引用 Tab
              if (sp.references?.hasAny) last = 'references'
              streamingActiveTab.value = last
            }
            scrollToBottom(false)
          } else if (eventType === 'team_result') {
            // team 模式最终结果：event_type=team_result，内容在 content 字段
            const teamText = chunk.content || chunk.result || chunk.answer || ''
            if (teamText) {
              accAnswer = teamText
              streamingText.value = accAnswer
              _teamResultReceived = true // 标记已收到完整结果
              // team_result 是 team 模式的最终结果帧，立即保存消息并标记，
              // 防止 done/completed/finally 重复 push
              if (!_assistantMsgSaved) {
                const msgId = Date.now()
                thinkingExpanded[msgId] = false; msgActiveTab[msgId] = 'case_overview'
                const msg: ChatMessage = {
                  message_id: msgId, session_id: currentSession.value!.session_id,
                  role: 'assistant', content: accAnswer, message_type: 'text',
                  created_at: new Date().toISOString(),
                  suggestedQuestions: generateSuggestions(msgText, accAnswer, activeSessionType),
                  sqlbotData: streamingSqlBotData.value || undefined,
                  // 扁平事件（回放时直读）
                  executionEvents: flatEvents.value.length ? [...flatEvents.value] : undefined,
                }
                if (activeSessionType === 'thinking') {
                  msg.renderKind = 'thinking'; msg.thinkingMode = true
                  msg.thinkingSteps = streamingThinkingSteps.value.length ? [...streamingThinkingSteps.value] : undefined
                } else if (activeSessionType === 'deep_research') {
                  msg.renderKind = 'research'; msg.researchReport = streamingResearch.value.report
                  msg.researchPlan = streamingResearch.value.plan.length ? [...streamingResearch.value.plan] : undefined
                  msg.researchStage = streamingResearch.value.stage; msg.researchProgress = streamingResearch.value.progress
                  msg.researchSources = streamingResearchSources.value.length ? [...streamingResearchSources.value] : undefined
                } else if (activeSessionType === 'agent') {
                  msg.renderKind = 'agent'
                  msg.thinkingSteps = streamingThinkingSteps.value.length ? [...streamingThinkingSteps.value] : undefined
                } else if (activeSessionType === 'team') {
                  msg.renderKind = 'team'
                } else if (activeSessionType === 'scheduled') {
                  msg.renderKind = 'scheduled'; msg.asyncTask = streamingAsyncTask.value || undefined
                }
                messages.value.push(msg)
                // team 模式同时被识别为 skill 模式，两个标记都要置位，
                // 否则 completed 的 skill 分支和 finally 兜底会重复 push
                _assistantMsgSaved = true
                _skillMsgSaved = true
                scrollToBottom(); await loadSessions()
              }
            }
            if (chunk.conversation_id) {
              newDifyConvId = chunk.conversation_id
            }
            executionPhase.value = 'completed'
          } else if (eventType === 'done') {
            // 所有执行完成
            skillProgress.value = null
            // team_result 已提供完整答案时，跳过 done 的 answer 覆盖（避免重复）
            if (chunk.answer && !_teamResultReceived) {
              accAnswer = chunk.answer
            }
            const result = accAnswer.trim()
            accAnswer = result
            streamingText.value = result
            newDifyConvId = chunk.conversation_id || newDifyConvId
            executionPhase.value = 'completed'

            // 技能模式：暂存回答作为 finally 兜底。
            // 若 completed 已保存消息（_skillMsgSaved=true）或已 push（_assistantMsgSaved=true），不再重新赋值，
            // 避免 finally 重复保存
            if (isSkillExecution && accAnswer && !_skillMsgSaved && !_assistantMsgSaved) {
              _pendingSkillAnswer = accAnswer
            }
            // 非技能模式（含 team）：标记消息待保存，防止 completed 也 push 一次
            if (!isSkillExecution && accAnswer) {
              _assistantMsgSaved = true
            }
            // 技能执行完成：置位收尾标记进入宽限读取——继续收齐后端紧随其后的
            // 最后 step（run_done）与 completed（携带 execution_id），不再立即退出
            // 读取循环（立即退出会丢弃分包到后续 HTTP chunk 的收尾事件）。
            // 宽限期流关闭或 1.5s 无新数据后退出，finally 保存消息的时序基本不受影响
            if (isSkillExecution) {
              _skillStreamDone = true
            }
          } else if (eventType === 'error') {
            // 错误情况
            skillProgress.value = null
            if (isSkillExecution) {
              enqueueEvent(chunk)
            }
            const errorMsg = `[执行错误] ${chunk.message || '未知错误'}`
            accAnswer += errorMsg
            streamingText.value = accAnswer
            // 数据分析结果：提取 records/sql/total/chart_config/sqlbot_chat_id
            if (chunk.records || chunk.sql || chunk.sqlbot_chat_id) {
              if (!streamingSqlBotData.value) streamingSqlBotData.value = {}
              streamingSqlBotData.value = {
                ...streamingSqlBotData.value,
                stage: 'done',
                sql: chunk.sql || streamingSqlBotData.value.sql,
                records: chunk.records || [],
                total: chunk.total ?? (chunk.records?.length || 0),
                chartConfig: chunk.chart_config || streamingSqlBotData.value.chartConfig,
                chatId: chunk.sqlbot_chat_id || streamingSqlBotData.value.chatId,
              }
              // 保存 sqlbot_chat_id 到当前会话，实现多轮对话上下文
              if (chunk.sqlbot_chat_id && currentSession.value) {
                sqlbotChatIdMap[currentSession.value.session_id] = chunk.sqlbot_chat_id
              }
            }
          } else if (eventType === 'progress') {
            if (chunk.stage === 'analyzing_files') {
              analysisProgress.value = { stage: chunk.stage, message: chunk.message || '正在分析文件...', progress: chunk.progress || 0, fileContext: chunk.file_context }
            } else if (chunk.stage?.startsWith('nl2sql')) {
              // 数据分析进度事件
              if (!streamingSqlBotData.value) streamingSqlBotData.value = {}
              streamingSqlBotData.value = {
                ...streamingSqlBotData.value,
                stage: chunk.stage,
                progressMessage: chunk.message || '',
                sql: chunk.sql || streamingSqlBotData.value.sql,
              }
            } else if (chunk.stage?.startsWith('thinking')) {
              // 思考模式进度事件（thinking_start / thinking_progress）
              // 入队驱动「执行事件」Tab；不使用技能进度卡片（思考模式在面板内展示进度）
              if (isSkillExecution) {
                enqueueEvent(chunk)
                executionPhase.value = 'streaming'
              }
            }
          } else if (eventType === 'thinking') {
            // 思考阶段 —— 技能/思考模式均记录到 composable（驱动「思考过程」Tab）
            if (isSkillExecution) {
              enqueueEvent(chunk)
              executionPhase.value = 'streaming'
            }
            streamingThinkingContent.value = chunk.content || ''
            // THINKING 模式：构建思考步骤。
            // chunk.append=true 表示增量分片（同一 step 的内容追加）；
            // 无 append 标记表示整步内容（幂等覆盖）。
            // 注：原下方 `eventType === 'thinking' && activeSessionType === 'thinking'` 分支
            // 因本分支先命中而永不可达（dead code），故在此统一维护 streamingThinkingSteps。
            if (activeSessionType === 'thinking') {
              const stepNo = chunk.step ?? (streamingThinkingSteps.value.length + 1)
              const idx = streamingThinkingSteps.value.findIndex(s => s.step === stepNo)
              if (idx >= 0) {
                const existing = streamingThinkingSteps.value[idx]
                if (chunk.append) {
                  existing.content += chunk.content || ''
                  if (chunk.title) existing.title = chunk.title
                  if (chunk.confidence != null) existing.confidence = chunk.confidence
                } else {
                  streamingThinkingSteps.value[idx] = {
                    step: stepNo,
                    title: chunk.title || existing.title,
                    content: chunk.content || '',
                    confidence: chunk.confidence,
                  }
                }
              } else {
                streamingThinkingSteps.value.push({
                  step: stepNo,
                  title: chunk.title || `步骤 ${stepNo}`,
                  content: chunk.content || '',
                  confidence: chunk.confidence,
                })
              }
            }

          } else if (eventType === 'tool_call') {
            // 工具调用 - 仅技能会话时记录到 composable
            if (isSkillExecution) {
              enqueueEvent(chunk)
              executionPhase.value = 'streaming'
              // 添加到工具历史
              streamingToolHistory.value.push({
                name: chunk.tool_name,
                input: chunk.input || {},
              })
            }

          } else if (eventType === 'tool_result') {
            // 工具结果 - 仅技能会话时记录到 composable
            if (isSkillExecution) {
              enqueueEvent(chunk)
              executionPhase.value = 'streaming'
              // 更新工具历史
              const toolHistoryItem = streamingToolHistory.value.find(
                t => t.name === chunk.tool_name
              )
              if (toolHistoryItem) {
                toolHistoryItem.result = chunk.result || chunk.delta || ''
              }
            }

          } else if (eventType === 'engine_decision') {
            // 引擎决策事件（SSE 首个事件）：engine_code 含 skill 即确认为技能执行，
            // 以此作为后续事件入队的可靠依据，避免依赖可能被覆盖的 activeSessionType
            if (typeof chunk.engine_code === 'string' && chunk.engine_code.includes('skill')) {
              isSkillExecution = true
              // team 模式（engine_code 形如 'skill:team'）也要渲染 SkillExecutionPanel
              if (chunk.engine_code.includes('team')) {
                isTeamSkillExecution.value = true
              }
            }
            if (isSkillExecution) {
              enqueueEvent(chunk)
            }

          } else if (eventType === 'completed') {
            // 执行完成事件 - 仅技能会话时记录到 composable
            skillProgress.value = null
            // completed 事件携带执行 ID，提取保存（Router 层拦截了 _gateway_meta，
            // 这是前端获取 execution_id 的唯一途径，用于消息持久化后的历史回放）
            if (chunk.execution_id) {
              currentExecutionId.value = chunk.execution_id
            }
            if (isSkillExecution) {
              enqueueEvent(chunk)
            }
            // 如果有输出内容，添加到答案中（team_result 已提供完整答案时跳过，避免重复追加）
            if (chunk.output && chunk.output.trim() && !_teamResultReceived) {
              accAnswer += chunk.output
              streamingText.value = accAnswer
            }
            const result = accAnswer.trim()
            accAnswer = result
            streamingText.value = result
            // 技能消息保存：completed 事件是唯一能获取 execution_id 的时机
            // （_gateway_meta 被后端拦截，execution_id 仅在此事件中可用）
            if (isSkillExecution && result && currentExecutionId.value && !_skillMsgSaved && !_assistantMsgSaved) {
              const msgId = Date.now()
              thinkingExpanded[msgId] = false
              msgActiveTab[msgId] = 'case_overview'
              messages.value.push({
                message_id: msgId,
                session_id: currentSession.value!.session_id,
                role: 'assistant',
                content: result,
                message_type: 'text',
                created_at: new Date().toISOString(),
                suggestedQuestions: generateSuggestions(msgText, result, activeSessionType),
                skillEvent: true,
                executionId: currentExecutionId.value,
                executionSteps: [],
                thinkingContent: streamingThinkingContent.value,
                toolHistory: streamingToolHistory.value,
                artifacts: _pendingArtifacts || [],
                unifiedSteps: streamingUnifiedSteps.value || undefined,
                unifiedArtifacts: streamingUnifiedArtifacts.value || undefined,
                // 扁平事件（回放时直读，用于各模式专属面板）
                executionEvents: flatEvents.value.length ? [...flatEvents.value] : undefined,
                // 思考模式专属字段：驱动 ThinkingExecutionPanel 渲染（Tab 在上、正文在下）
                ...(activeSessionType === 'thinking'
                  ? {
                      renderKind: 'thinking' as const,
                      thinkingMode: true,
                      thinkingSteps: streamingThinkingSteps.value.length
                        ? [...streamingThinkingSteps.value]
                        : undefined,
                    }
                  : {}),
                // 智能体模式专属字段：驱动 AgentExecutionPanel 渲染（Tab 在上、正文在下）
                ...(activeSessionType === 'agent'
                  ? {
                      renderKind: 'agent' as const,
                      thinkingSteps: streamingThinkingSteps.value.length
                        ? [...streamingThinkingSteps.value]
                        : undefined,
                    }
                  : {}),
                // 智能体团队模式专属字段：驱动 TeamExecutionPanel 渲染（Tab 在上、正文在下）
                ...(activeSessionType === 'team'
                  ? {
                      renderKind: 'team' as const,
                    }
                  : {}),
                // 深度研究模式专属字段：驱动 DeepResearchExecutionPanel 渲染（Tab 在上、正文在下）
                ...(activeSessionType === 'deep_research'
                  ? {
                      renderKind: 'research' as const,
                      thinkingSteps: streamingThinkingSteps.value.length
                        ? [...streamingThinkingSteps.value]
                        : undefined,
                      researchSources: streamingResearchSources.value.length
                        ? [...streamingResearchSources.value]
                        : undefined,
                    }
                  : {}),
                result,
              })
              _pendingSkillAnswer = ''  // 已保存，清除暂存
              _skillMsgSaved = true     // 标记已保存，防止 done/finally 重复保存
              _assistantMsgSaved = true // team 模式也按 skill 识别，需同步置位
              scrollToBottom()
              await loadSessions()
            }
            // 非技能模式（含 team / harness / agent）：completed 已携带完整 output，
            // 必须在此处直接 push 消息，否则仅置位 _assistantMsgSaved 会导致 finally
            // 兜底（依赖 !_assistantMsgSaved）被跳过，最终前端无任何 assistant 气泡（空白）。
            if (!isSkillExecution && result && !_assistantMsgSaved) {
              const msgId = Date.now()
              thinkingExpanded[msgId] = false
              msgActiveTab[msgId] = 'case_overview'
              messages.value.push({
                message_id: msgId,
                session_id: currentSession.value!.session_id,
                role: 'assistant',
                content: result,
                message_type: 'text',
                created_at: new Date().toISOString(),
                suggestedQuestions: generateSuggestions(msgText, result, activeSessionType),
                executionId: currentExecutionId.value || undefined,
                unifiedSteps: streamingUnifiedSteps.value || undefined,
                unifiedArtifacts: streamingUnifiedArtifacts.value || undefined,
                // ReAct 模式：保存事件列表与运行 ID 供历史回放
                ...(activeSessionType === 'react' ? {
                  renderKind: 'react' as const,
                  reactEvents: reactEvents.value.length ? [...reactEvents.value] : undefined,
                  reactRunId: reactRunId.value || undefined,
                } : {}),
              })
              _assistantMsgSaved = true
              scrollToBottom()
              await loadSessions()
            }

          } else if (eventType === 'text_chunk') {
            // 文本流式输出 - 仅技能会话时记录到 composable
            // 注意：空白 chunk 用 continue 跳过当前行，绝不能用 return（会中断整个 SSE 处理循环）
            if (!chunk.content.trim()) continue
            if (isSkillExecution) {
              enqueueEvent(chunk)
              executionPhase.value = 'streaming'
            }
            accAnswer += chunk.content
            streamingText.value = accAnswer
            scrollToBottom(false)
          } else if (eventType === 'text_done') {
            // 文本完成
            if (isSkillExecution) {
              enqueueEvent(chunk)
            }
            skillProgress.value = null
            const result = accAnswer.trim()
            accAnswer = result
            streamingText.value = result
            newDifyConvId = chunk.conversation_id || newDifyConvId
          } else if (eventType === 'text') {
            // 后端 SkillEvent type="text" —— 累加到流式文本
            accAnswer += chunk.content || chunk.data?.content || ''
            streamingText.value = accAnswer
            scrollToBottom(false)
          } else if (eventType === 'artifact') {
            // 产物文件事件：累积到当前消息的 artifacts 列表（旧扁平格式）
            if (!_pendingArtifacts) _pendingArtifacts = []
            _pendingArtifacts.push({
              file_id: chunk.file_id || chunk.data?.file_id,
              filename: chunk.filename || chunk.data?.filename,
              size_bytes: chunk.size_bytes || chunk.data?.size_bytes || 0,
              mime_type: chunk.mime_type || chunk.data?.mime_type || 'application/octet-stream',
            })
            // 统一产物事件（StepEvent/ArtifactItem 归一化形状）：同时存在两种格式，
            // 直接累积到 unifiedArtifacts，供 UnifiedTimeline 产物画廊渲染
            if (chunk.artifact_id !== undefined || chunk.kind !== undefined) {
              if (!streamingUnifiedArtifacts.value) streamingUnifiedArtifacts.value = []
              streamingUnifiedArtifacts.value.push({
                artifact_id: chunk.artifact_id,
                kind: chunk.kind,
                title: chunk.title,
                seq: chunk.seq ?? 0,
                mime_type: chunk.mime_type ?? null,
                file_id: chunk.file_id ?? null,
                chart_config: chunk.chart_config ?? null,
                media_data: chunk.media_data ?? null,
                size_bytes: chunk.size_bytes ?? null,
                status: chunk.status ?? 'ready',
                error: chunk.error ?? null,
                suggestion: chunk.suggestion ?? null,
              })
            }

          } else if (eventType === 'step') {
            // 统一步骤事件（StepEvent 归一化形状）：累加到 unifiedSteps，供统一时间线渲染
            if (!streamingUnifiedSteps.value) streamingUnifiedSteps.value = []
            streamingUnifiedSteps.value.push({
              phase: chunk.phase,
              event_type: chunk.event_type,
              title: chunk.title,
              seq: chunk.seq ?? streamingUnifiedSteps.value.length + 1,
              status: chunk.status ?? 'done',
              detail: chunk.detail ?? null,
              elapsed_ms: chunk.elapsed_ms ?? null,
              artifact_id: chunk.artifact_id ?? null,
              // 工作流执行形式（并行分支/判断节点），供横向流程图渲染
              exec_mode: chunk.exec_mode ?? 'serial',
              group_id: chunk.group_id ?? null,
              branch_label: chunk.branch_label ?? null,
              branch_note: chunk.branch_note ?? null,
            })
          } else if (eventType === 'progress' || eventType === 'engine_decision') {
            // 进度/引擎决策等执行事件：归一化为统一步骤，在执行详情时间线中展示
            // （text_chunk 已在正文显示、thinking 已在思考过程显示，故排除）
            if (!streamingUnifiedSteps.value) streamingUnifiedSteps.value = []
            if (eventType === 'progress') {
              streamingUnifiedSteps.value.push({
                phase: chunk.stage ?? '进度',
                event_type: 'progress',
                title: chunk.message ?? '处理中',
                seq: chunk.seq ?? streamingUnifiedSteps.value.length + 1,
                status: 'done',
                detail: null,
                elapsed_ms: null,
                artifact_id: null,
              })
            } else {
              streamingUnifiedSteps.value.push({
                phase: '引擎决策',
                event_type: 'engine_decision',
                title: `引擎: ${chunk.engine_code ?? 'unknown'}`,
                seq: chunk.seq ?? streamingUnifiedSteps.value.length + 1,
                status: 'done',
                detail: chunk.reason ?? null,
                elapsed_ms: null,
                artifact_id: null,
              })
            }

          // ── THINKING 思考模式 ──────────────────────────────────────────────
          } else if (eventType === 'thinking_start') {
            // 思考开始：仅 THINKING 模式接管（技能模式的 thinking 事件已在上面分支处理）
            if (activeSessionType === 'thinking') {
              streamingThinkingSteps.value = []
              streamingThinkingActive.value = true
              accAnswer = ''  // 结论区稍后由 token 流式填充
              streamingText.value = ''
            }
          } else if (eventType === 'thinking' && activeSessionType === 'thinking') {
            // THINKING 模式：按 step 幂等覆盖，构建思考步骤
            const st = {
              step: chunk.step ?? (streamingThinkingSteps.value.length + 1),
              title: chunk.title || `步骤 ${chunk.step ?? streamingThinkingSteps.value.length + 1}`,
              content: chunk.content || '',
              confidence: chunk.confidence,
            }
            const idx = streamingThinkingSteps.value.findIndex(s => s.step === st.step)
            if (idx >= 0) streamingThinkingSteps.value[idx] = st
            else streamingThinkingSteps.value.push(st)
          } else if (eventType === 'thinking_end' && activeSessionType === 'thinking') {
            streamingThinkingActive.value = false

          // ── DEEP_RESEARCH 深度研究模式 ─────────────────────────────────────
          } else if (eventType === 'research_start') {
            streamingResearch.value = { topic: chunk.topic, stage: 'decompose', progress: 5, plan: [] }
          } else if (eventType === 'research_plan') {
            streamingResearch.value.plan = (chunk.sub_questions || []).map((q: any) => ({
              id: q.id, question: q.question, status: q.status || 'queued', sources: [],
            }))
          } else if (eventType === 'research_progress') {
            streamingResearch.value.stage = chunk.stage || streamingResearch.value.stage
            if (typeof chunk.progress === 'number') streamingResearch.value.progress = chunk.progress
            if (chunk.sub_question_id && chunk.status) {
              const sq = streamingResearch.value.plan.find(p => p.id === chunk.sub_question_id)
              if (sq) sq.status = chunk.status
            }
            if (chunk.sub_questions) streamingResearch.value.plan = chunk.sub_questions
          } else if (eventType === 'research_source') {
            const sq = streamingResearch.value.plan.find(p => p.id === chunk.sub_question_id)
            if (sq) sq.sources.push({ title: chunk.title, url: chunk.url, credibility: chunk.credibility ?? 0 })
            // 同步到独立的 researchSources 列表（供 DeepResearchExecutionPanel 渲染）
            streamingResearchSources.value.push({
              title: chunk.title || '未知来源',
              url: chunk.url,
              snippet: chunk.snippet || chunk.credibility ? `可信度: ${chunk.credibility ?? 'N/A'}` : undefined,
            })
          } else if (eventType === 'research_report') {
            streamingResearch.value.report = {
              summary: chunk.summary || '',
              keyFindings: chunk.key_findings || [],
              analysis: chunk.analysis || '',
              sources: chunk.sources || [],
            }
            streamingResearch.value.progress = 100

          // ── SCHEDULED 云端调度模式 ────────────────────────────────────────
          } else if (eventType === 'task_submitted') {
            streamingAsyncTask.value = {
              taskId: chunk.task_id,
              taskNo: chunk.task_no,
              status: chunk.status || 'queued',
              progress: 0,
            }

          // ── REACT 计划执行模式 ──────────────────────────────────────────
          } else if (eventType?.startsWith('react_')) {
            reactEvents.value.push({ type: eventType, ...chunk })
            if (eventType === 'react_start') {
              reactGoal.value = chunk.goal || msgText
              reactRunId.value = chunk.run_id || null
              reactPlanStatus.value = 'planning'
            } else if (eventType === 'react_plan') {
              reactPlanStatus.value = 'planning'
              reactGoal.value = chunk.goal || reactGoal.value
            } else if (eventType === 'react_executing') {
              reactPlanStatus.value = 'executing'
            } else if (eventType === 'react_reflect') {
              reactPlanStatus.value = 'reflecting'
            } else if (eventType === 'react_confirm') {
              reactConfirmVisible.value = true
              reactConfirmQuestion.value = chunk.question || '请确认以下操作'
              reactConfirmOptions.value = chunk.options || []
            } else if (eventType === 'react_done') {
              reactPlanStatus.value = 'done'
              reactConfirmVisible.value = false
              if (chunk.result) {
                accAnswer += chunk.result
                streamingText.value = accAnswer
              }
            } else if (eventType === 'react_report') {
              if (chunk.content) {
                accAnswer += chunk.content
                streamingText.value = accAnswer
              }
            }
          }
        } catch { /* ignore */ }
      }
    }
  } catch (e: any) {
    if (e?.name === 'AbortError') {
      // 用户主动中断，不清空已产出内容
    } else {
      antMsg.error(`发送失败：${e.message || '网络错误'}`); accAnswer = ''
    }
  } finally {
    // 先缓存统一时间线数据：下方兜底保存消息仍需使用，
    // 若等清空后再读取将恒为 undefined（会话模式时间线丢失的直接原因）
    const finalUnifiedSteps = streamingUnifiedSteps.value || undefined
    const finalUnifiedArtifacts = streamingUnifiedArtifacts.value || undefined
    streaming.value = false; streamingText.value = ''; difyConvId.value = newDifyConvId; _pendingArtifacts = undefined; streamingUnifiedSteps.value = null; streamingUnifiedArtifacts.value = null; abortController = null
    setTimeout(() => { analysisProgress.value = null }, 1000)
    // 兜底：若 completed 事件未保存消息（如缺少 execution_id）且未手动 push，在此保存
    if (_pendingSkillAnswer && (accAnswer || isSkillExecution) && !_assistantMsgSaved) {
      const msgId = Date.now() + 1
      thinkingExpanded[msgId] = false; msgActiveTab[msgId] = 'case_overview'
      messages.value.push({
        message_id: msgId, session_id: currentSession.value!.session_id,
        role: 'assistant', content: _pendingSkillAnswer, message_type: 'text',
        created_at: new Date().toISOString(),
        suggestedQuestions: generateSuggestions(msgText, _pendingSkillAnswer, activeSessionType),
        skillEvent: true, executionId: currentExecutionId.value,
        executionSteps: [], thinkingContent: streamingThinkingContent.value,
        toolHistory: streamingToolHistory.value, result: _pendingSkillAnswer,
        unifiedSteps: finalUnifiedSteps,
        unifiedArtifacts: finalUnifiedArtifacts,
      })
      _pendingSkillAnswer = ''
      scrollToBottom(); await loadSessions()
    } else if (accAnswer && !_assistantMsgSaved) {
      const msgId = Date.now() + 1
      thinkingExpanded[msgId] = false; msgActiveTab[msgId] = 'case_overview'
      const msg: ChatMessage = {
        message_id: msgId, session_id: currentSession.value!.session_id,
        role: 'assistant', content: accAnswer, message_type: 'text',
        created_at: new Date().toISOString(),
        suggestedQuestions: generateSuggestions(msgText, accAnswer, activeSessionType),
        sqlbotData: streamingSqlBotData.value || undefined,
        unifiedSteps: finalUnifiedSteps,
        unifiedArtifacts: finalUnifiedArtifacts,
      }
      // 新模式专属字段持久化（历史回放直读）
      if (activeSessionType === 'thinking') {
        msg.renderKind = 'thinking'
        msg.thinkingMode = true
        msg.thinkingSteps = streamingThinkingSteps.value.length ? [...streamingThinkingSteps.value] : undefined
      } else if (activeSessionType === 'deep_research') {
        msg.renderKind = 'research'
        msg.researchReport = streamingResearch.value.report
        msg.researchPlan = streamingResearch.value.plan.length ? [...streamingResearch.value.plan] : undefined
        msg.researchStage = streamingResearch.value.stage
        msg.researchProgress = streamingResearch.value.progress
        msg.researchSources = streamingResearchSources.value.length ? [...streamingResearchSources.value] : undefined
      } else if (activeSessionType === 'agent') {
        msg.renderKind = 'agent'
        msg.thinkingSteps = streamingThinkingSteps.value.length ? [...streamingThinkingSteps.value] : undefined
      } else if (activeSessionType === 'team') {
        msg.renderKind = 'team'
      } else if (activeSessionType === 'scheduled') {
        msg.renderKind = 'scheduled'
        msg.asyncTask = streamingAsyncTask.value || undefined
      }
      messages.value.push(msg)
      scrollToBottom(); await loadSessions()
    }
  }
}

async function loadSessionTypes() {
  try {
    const res = await getDictionaryItems('session_type')
    sessionTypeOptions.value = (res || []).filter(i => i.is_active)
  } catch (e) { console.error('加载会话类型字典失败:', e); sessionTypeOptions.value = [] }
}

async function loadDatasourceOptions() {
  datasourceLoading.value = true
  try {
    const res = await getSqlbotDatasources() as any
    const list: SqlbotDatasource[] = res?.datasources || []
    datasourceOptions.value = list
    // 如果只有一个数据源，自动选中
    if (list.length === 1 && !selectedDatasourceId.value) {
      selectedDatasourceId.value = list[0].id
    }
  } catch (e) {
    console.error('加载数据源列表失败:', e)
    datasourceOptions.value = []
  } finally {
    datasourceLoading.value = false
  }
}

function getMessageAnalysis(msg: ChatMessage): any {
  if (msg.role !== 'assistant') return null
  const extra = msg.extra_data
  if (extra && typeof extra === 'object' && (extra as any).analysis) return (extra as any).analysis
  return null
}

async function loadAvailableModels() {
  try {
    const res = await getAvailableModels() as any
    const all = Array.isArray(res) ? res : []
    // 只保留 type=1(文本模型)、2(图片生成)、3(视频生成)
    availableModels.value = all.filter((m: AvailableModel) => m.type && [1, 2, 3].includes(m.type))
    // 默认选中第一个模型
    if (availableModels.value.length > 0 && !selectedModelId.value) {
      selectedModelId.value = availableModels.value[0].id
    }
  } catch (e) {
    console.error('加载可用模型列表失败:', e)
    availableModels.value = []
  }
}

// ── Skill Timeline View Events ───────────────────────────────────────────────

async function loadWorkspaces() {
  try {
    workspaceOptions.value = (await getWorkspacesSimple()) as any || []
    // 默认选中公共空间（后端 is_default 可能为 true / 't'）
    const def = workspaceOptions.value.find(
      (w: any) => w.isDefault === true || w.is_default === true || w.is_default === 't'
    )
    selectedWorkspaceId.value = def ? def.id : (workspaceOptions.value[0]?.id ?? null)
  } catch (e) {
    console.error('加载工作空间列表失败:', e)
    workspaceOptions.value = []
  }
}

onMounted(() => { loadSessions(); loadSessionTypes(); loadDatasourceOptions(); loadAvailableModels(); loadWorkspaces() })
</script>

<style scoped lang="less">
.ai-dispute-panel {
  display: flex; flex: 1; min-width: 0; width: 100%; height: 100%; min-height: 0;
  background: var(--bg-input); border-radius: 8px; overflow: hidden; border: 1px solid var(--border);
}
.chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; min-height: 0; overflow: hidden; }

.chat-main-header {
  flex: 0 0 auto;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
}
.chat-main-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.async-task-btn { margin-left: auto; }

.session-artifact-fab {
  position: absolute; right: 16px; bottom: 16px; z-index: 20;
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.3);
}
.drawer-artifact { margin-bottom: 12px; }
</style>
