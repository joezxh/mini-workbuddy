<template>
  <div class="hitl-confirm-panel">
    <div class="hcp-header">
      <span class="hcp-badge">
        <SafetyCertificateOutlined />
        {{ titleByType }}
        <a-tag color="blue" class="hcp-round-tag">{{ t('assistantChat.hitl.round', { n: round ?? 1 }) }}</a-tag>
      </span>
      <span v-if="countdownText" class="hcp-timeout">
        <ClockCircleOutlined /> {{ countdownText }}
      </span>
    </div>

    <!-- 形态一：工具授权（tool_confirm） -->
    <template v-if="pauseType !== 'ask_user'">
      <div class="hcp-tools">
        <div v-for="tc in toolCalls" :key="tc.id" class="hcp-tool">
          <div class="hcp-tool-name">
            <code>{{ tc.name }}</code>
            <span v-if="tc.id" class="hcp-tool-id">#{{ tc.id }}</span>
          </div>
          <pre class="hcp-tool-input">{{ formatInput(tc.input) }}</pre>
          <div v-if="tc.suggested_rules?.length" class="hcp-rules">
            <a-tag v-for="r in tc.suggested_rules" :key="r" color="gold">{{ r }}</a-tag>
          </div>
        </div>
      </div>
      <a-checkbox v-if="pauseType === 'tool_confirm'" v-model:checked="acceptRules" class="hcp-accept">
        {{ t('assistantChat.hitl.acceptRules') }}
      </a-checkbox>
    </template>

    <!-- 形态三：对话追问（ask_user）——渲染 questions 与 options，文本输入回答 -->
    <template v-else>
      <div class="hcp-questions">
        <div v-for="(q, qi) in askQuestions" :key="qi" class="hcp-question">
          <div class="hcp-question-text"><QuestionCircleOutlined /> {{ q.question }}</div>
          <div v-if="q.options?.length" class="hcp-question-options">
            <a-button
              v-for="opt in q.options"
              :key="opt"
              size="small"
              :type="answerText === opt ? 'primary' : 'default'"
              class="hcp-option-btn"
              :disabled="resolved"
              @click="answerText = opt"
            >{{ opt }}</a-button>
          </div>
        </div>
      </div>
      <a-textarea
        v-model:value="answerText"
        class="hcp-answer-input"
        :placeholder="t('assistantChat.hitl.answerPlaceholder')"
        :auto-size="{ minRows: 2, maxRows: 5 }"
        :disabled="resolved"
      />
    </template>

    <!-- 形态二：计划审批驳回原因（plan_approval reject 时随 message 提交） -->
    <a-textarea
      v-if="pauseType === 'plan_approval'"
      v-model:value="rejectReason"
      class="hcp-answer-input"
      :placeholder="t('assistantChat.hitl.rejectReason')"
      :auto-size="{ minRows: 1, maxRows: 4 }"
      :disabled="resolved"
    />

    <div class="hcp-actions">
      <a-button
        type="primary"
        size="small"
        :loading="loading"
        :disabled="resolved"
        @click="handle('approve')"
      >
        <CheckOutlined /> {{ approveLabel }}
      </a-button>
      <a-button
        size="small"
        danger
        :loading="loading"
        :disabled="resolved"
        @click="handle('reject')"
      >
        <CloseOutlined /> {{ rejectLabel }}
      </a-button>
      <a-button size="small" :loading="loading" :disabled="resolved" @click="handle('interrupt')">
        <StopOutlined /> {{ t('assistantChat.hitl.interrupt') }}
      </a-button>
    </div>

    <!-- 已提交：多轮队列语义下面板保持可见，等待下一轮 hitl_pause -->
    <div v-if="resolved" class="hcp-resolved-tip">
      <LoadingOutlined spin /> {{ t('assistantChat.hitl.resolvedWaiting') }}
    </div>

    <!-- 已完成轮次折叠展示 -->
    <div v-if="history.length" class="hcp-history">
      <div class="hcp-history-toggle" @click="historyOpen = !historyOpen">
        <CaretRightOutlined :class="{ expanded: historyOpen }" />
        <span>{{ t('assistantChat.hitl.historyTitle') }}（{{ history.length }}）</span>
      </div>
      <div v-show="historyOpen" class="hcp-history-list">
        <div v-for="(h, hi) in history" :key="hi" class="hcp-history-item">
          <span class="hcp-history-round">#{{ hi + 1 }}</span>
          <a-tag :color="typeColor(h.pause_type)" class="hcp-history-type">{{ typeLabel(h.pause_type) }}</a-tag>
          <span class="hcp-history-action" :class="h.action">{{ actionLabel(h.action) }}</span>
          <span v-if="h.tools?.length" class="hcp-history-tools">{{ h.tools.join(', ') }}</span>
          <span class="hcp-history-time">{{ formatTime(h.time) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  CheckOutlined, CloseOutlined, StopOutlined, SafetyCertificateOutlined,
  ClockCircleOutlined, QuestionCircleOutlined, CaretRightOutlined,
} from '@ant-design/icons-vue'
import type {
  EventEnvelope, HitlToolCall, HitlAskUserQuestion, HitlPauseHistoryItem,
} from '@/types/agentEvents'
import { confirmExecution } from '@/api/agentExecution'

const props = withDefaults(
  defineProps<{
    executionId: string
    pause: EventEnvelope
    /** 当前轮次号（已完成轮次数 + 1，本地计数） */
    round?: number
    /** 已完成轮次历史 */
    history?: HitlPauseHistoryItem[]
    /** 当前轮是否已提交（提交后面板保持可见等待下一轮） */
    resolved?: boolean
  }>(),
  { round: 1, history: () => [], resolved: false },
)

const emit = defineEmits<{
  (e: 'resolved', action: string): void
}>()

const { t } = useI18n()

const loading = ref(false)
const acceptRules = ref(false)
const answerText = ref('')
const rejectReason = ref('')
const historyOpen = ref(false)

const toolCalls = computed<HitlToolCall[]>(() => props.pause.content?.tool_calls || [])
const pauseType = computed<string>(() => props.pause.content?.pause_type || 'tool_confirm')
const timeoutMinutes = computed<number | undefined>(() => props.pause.content?.timeout_minutes)

// ── 超时倒计时（timeout_minutes，收到 pause 时起算） ─────────────────────────
const remainSeconds = ref(0)
let countdownTimer: ReturnType<typeof setInterval> | null = null

function startCountdown() {
  stopCountdown()
  if (!timeoutMinutes.value) return
  const deadline = Date.now() + timeoutMinutes.value * 60 * 1000
  const tick = () => {
    const left = Math.max(0, Math.floor((deadline - Date.now()) / 1000))
    remainSeconds.value = left
    if (left <= 0) stopCountdown()
  }
  tick()
  countdownTimer = setInterval(tick, 1000)
}
function stopCountdown() {
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
}

const countdownText = computed(() => {
  if (!timeoutMinutes.value || remainSeconds.value <= 0) return ''
  const m = Math.floor(remainSeconds.value / 60)
  const s = remainSeconds.value % 60
  return t('assistantChat.hitl.timeoutLeft', { time: `${m}:${String(s).padStart(2, '0')}` })
})

watch(
  () => [props.pause, props.pause.content?.reply_id],
  () => {
    // 新一轮 pause 到达：重置输入与倒计时
    answerText.value = ''
    rejectReason.value = ''
    acceptRules.value = false
    startCountdown()
  },
  { immediate: true, deep: true },
)
onBeforeUnmount(stopCountdown)

// ── 形态标题 / 按钮文案 ─────────────────────────────────────────────────────
const titleByType = computed(() => {
  if (pauseType.value === 'plan_approval') return t('assistantChat.hitl.planApproval')
  if (pauseType.value === 'ask_user') return t('assistantChat.hitl.askUser')
  return t('assistantChat.hitl.title')
})
const approveLabel = computed(() =>
  pauseType.value === 'plan_approval' ? t('assistantChat.hitl.planApprove') : t('assistantChat.hitl.approve'),
)
const rejectLabel = computed(() =>
  pauseType.value === 'plan_approval' ? t('assistantChat.hitl.planReject') : t('assistantChat.hitl.reject'),
)

// ── AskUser 问题列表（tool_calls[0].input.questions，input 可能为 JSON 字符串） ──
const askQuestions = computed<HitlAskUserQuestion[]>(() => {
  const first = toolCalls.value[0]
  if (!first) return []
  let input = first.input
  if (typeof input === 'string') {
    try { input = JSON.parse(input) } catch { return [] }
  }
  const qs = input?.questions
  return Array.isArray(qs) ? qs : []
})

function formatInput(input: unknown): string {
  try {
    return typeof input === 'string' ? input : JSON.stringify(input, null, 2)
  } catch {
    return String(input)
  }
}

// ── 轮次历史展示辅助 ────────────────────────────────────────────────────────
function typeLabel(pt: string): string {
  if (pt === 'plan_approval') return t('assistantChat.hitl.planApproval')
  if (pt === 'ask_user') return t('assistantChat.hitl.askUser')
  return t('assistantChat.hitl.toolConfirm')
}
function typeColor(pt: string): string {
  if (pt === 'plan_approval') return 'purple'
  if (pt === 'ask_user') return 'cyan'
  return 'orange'
}
function actionLabel(a: string): string {
  if (a === 'approve') return t('assistantChat.hitl.actionApprove')
  if (a === 'reject') return t('assistantChat.hitl.actionReject')
  return t('assistantChat.hitl.actionInterrupt')
}
function formatTime(ts?: string): string {
  if (!ts) return ''
  return ts.includes('T') ? ts.slice(11, 19) : ts
}

async function handle(action: 'approve' | 'reject' | 'interrupt') {
  loading.value = true
  try {
    // ask_user：回答随 message 提交（后端 build_ask_user_resume_event 消费）；
    // plan_approval reject：驳回原因随 message 提交（重规划参考）。
    let msg = ''
    if (pauseType.value === 'ask_user' && action === 'approve') {
      msg = answerText.value.trim()
      if (!msg) {
        message.warning(t('assistantChat.hitl.answerRequired'))
        loading.value = false
        return
      }
    } else if (pauseType.value === 'plan_approval' && action === 'reject') {
      msg = rejectReason.value.trim()
    }
    await confirmExecution(props.executionId, {
      action,
      accept_rules: acceptRules.value,
      tool_calls: toolCalls.value,
      ...(msg ? { message: msg } : {}),
    })
    message.success(
      action === 'approve'
        ? t('assistantChat.hitl.approvedToast')
        : action === 'reject' ? t('assistantChat.hitl.rejectedToast') : t('assistantChat.hitl.interruptedToast'),
    )
    emit('resolved', action)
  } catch (e: any) {
    message.error(`${t('assistantChat.hitl.actionFailed')}：${e?.message || e}`)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="less">
.hitl-confirm-panel {
  border: 1px solid var(--accent-soft);
  border-radius: 12px;
  background: var(--bg-surface);
  padding: 14px 16px;
  margin: 6px 0;
}
.hcp-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px;
}
.hcp-badge { font-weight: 600; color: var(--fg); display: inline-flex; align-items: center; gap: 6px; }
.hcp-round-tag { margin-left: 2px; }
.hcp-timeout { font-size: 12px; color: var(--fg-secondary); display: inline-flex; align-items: center; gap: 4px; }
.hcp-tools { display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px; }
.hcp-tool { border: 1px solid var(--border-soft); border-radius: 8px; padding: 8px 10px; background: var(--bg-subtle); }
.hcp-tool-name { font-size: 13px; color: var(--fg); margin-bottom: 4px; }
.hcp-tool-id { margin-left: 6px; color: var(--fg-secondary); font-size: 12px; }
.hcp-tool-input {
  margin: 0; font-size: 12px; white-space: pre-wrap; word-break: break-all;
  max-height: 160px; overflow: auto; color: var(--fg-secondary);
}
.hcp-rules { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 4px; }
.hcp-accept { margin-bottom: 10px; }
.hcp-questions { display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px; }
.hcp-question-text { font-size: 13px; color: var(--fg); display: flex; align-items: baseline; gap: 6px; }
.hcp-question-options { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.hcp-option-btn { margin: 0; }
.hcp-answer-input { margin-bottom: 10px; }
.hcp-actions { display: flex; gap: 8px; }
.hcp-resolved-tip {
  margin-top: 10px; font-size: 12px; color: var(--accent);
  display: flex; align-items: center; gap: 6px;
}
.hcp-history { margin-top: 10px; border-top: 1px dashed var(--border-soft); padding-top: 8px; }
.hcp-history-toggle {
  display: inline-flex; align-items: center; gap: 4px; cursor: pointer; user-select: none;
  font-size: 12px; color: var(--fg-secondary);
  &:hover { color: var(--accent); }
  .anticon { font-size: 9px; transition: transform 0.2s; }
  .expanded { transform: rotate(90deg); }
}
.hcp-history-list { margin-top: 6px; display: flex; flex-direction: column; gap: 4px; }
.hcp-history-item {
  display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--fg-secondary);
  .hcp-history-round { color: var(--fg-muted); font-family: monospace; }
  .hcp-history-type { margin: 0; font-size: 10px; line-height: 16px; }
  .hcp-history-action {
    &.approve { color: var(--ok); }
    &.reject { color: var(--err, #f5222d); }
    &.interrupt { color: var(--warn, #faad14); }
  }
  .hcp-history-tools { color: var(--fg-muted); word-break: break-all; }
  .hcp-history-time { margin-left: auto; color: var(--fg-muted); font-family: monospace; }
}
</style>
