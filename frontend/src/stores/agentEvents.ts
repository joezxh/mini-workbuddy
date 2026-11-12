/** AgentEvents Store（P1.3）：统一事件流状态。
 *
 * 负责：按 execution_id 汇总 /stream 推送的统一信封、按 seq 去重、
 * 按 ui_hint 路由（confirm → HITL 面板）、维护最新一次 hitl_pause。
 *
 * HITL 多轮队列语义（spec F3）：resolve 后不 clearHitl、不断开订阅，
 * 面板保持可见等待下一轮 hitl_pause；已完成轮次记入 pauseHistory，
 * 轮次号 = pauseHistory.length + 1（本地计数，pause 事件无轮次字段）。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { EventEnvelope, HitlPauseHistoryItem } from '@/types/agentEvents'
import { connectEventStream, type SSEClient } from '@/utils/sseClient'

export const useAgentEventsStore = defineStore('agentEvents', () => {
  // 每个 execution 的事件列表（按 seq 去重）
  const byExecution = ref<Record<string, EventEnvelope[]>>({})
  const lastSeq = ref<Record<string, number>>({})
  const hitlPause = ref<EventEnvelope | null>(null)
  // 多轮 HITL：已完成轮次历史 + 当前轮是否已提交（面板保持可见等待下一轮）
  const pauseHistory = ref<HitlPauseHistoryItem[]>([])
  const hitlResolved = ref(false)
  const connected = ref(false)
  const error = ref<string | null>(null)

  let client: SSEClient | null = null
  let activeExecutionId = ''

  const getEvents = (executionId: string): EventEnvelope[] =>
    byExecution.value[executionId] || []

  const pendingHitl = computed(() => hitlPause.value)

  /** 当前轮次号：已完成轮次数 + 1 */
  const hitlRound = computed(() => pauseHistory.value.length + 1)

  function addEvent(env: EventEnvelope) {
    const eid = env.execution_id
    if (!byExecution.value[eid]) byExecution.value[eid] = []
    const seq = env.sequence ?? 0
    if (byExecution.value[eid].some((e) => (e.sequence ?? -1) === seq)) return
    byExecution.value[eid].push(env)
    if (seq) lastSeq.value[eid] = Math.max(lastSeq.value[eid] || 0, seq)

    if (env.event_type === 'hitl_pause') {
      // 同一 reply_id 的重复 pause（主流 SSE + /stream 信封双通道）不重复计数
      const dup = hitlPause.value && env.reply_id && hitlPause.value.reply_id === env.reply_id
      hitlPause.value = env
      if (!dup) hitlResolved.value = false
    } else if (env.event_type === 'hitl_resume') {
      // 恢复信封：标记当前轮已处理；面板保持可见等待下一轮（多轮队列语义）
      hitlResolved.value = true
    } else if (env.event_type === 'interrupted' || env.event_type === 'reply_end' || env.event_type === 'error') {
      // 执行终态：收起面板
      hitlPause.value = null
    }
  }

  /** 面板 resolve 回调：记录已完成轮次（动作 + 时间），不 clearHitl / 不断开 */
  function resolveCurrentPause(action: string) {
    const p = hitlPause.value
    if (p) {
      const tools = ((p.content?.tool_calls || []) as Array<{ name?: string }>)
        .map((tc) => tc?.name)
        .filter((n): n is string => !!n)
      pauseHistory.value.push({
        pause_type: p.content?.pause_type || 'tool_confirm',
        action,
        time: new Date().toISOString(),
        tools,
      })
    }
    hitlResolved.value = true
  }

  /** 切换执行时清空多轮会话状态（历史轮次按 execution 归零） */
  function resetHitlSession() {
    hitlPause.value = null
    pauseHistory.value = []
    hitlResolved.value = false
  }

  function connect(executionId: string) {
    disconnect()
    if (activeExecutionId !== executionId) resetHitlSession()
    activeExecutionId = executionId
    client = connectEventStream(`/api/v1/agents/executions/${executionId}/stream`, {
      afterSeq: lastSeq.value[executionId] ?? null,
      onOpen: () => {
        connected.value = true
      },
      onEvent: (env: any) => {
        if (env && env.execution_id) addEvent(env as EventEnvelope)
      },
      onError: (e) => {
        error.value = String(e)
      },
    })
  }

  function disconnect() {
    client?.close()
    client = null
    connected.value = false
  }

  /** 兼容保留：仅清除当前暂停（多轮队列语义下不再用于 resolve） */
  function clearHitl() {
    hitlPause.value = null
  }

  function reset() {
    disconnect()
    byExecution.value = {}
    lastSeq.value = {}
    activeExecutionId = ''
    resetHitlSession()
    error.value = null
  }

  return {
    byExecution,
    lastSeq,
    hitlPause,
    pauseHistory,
    hitlResolved,
    hitlRound,
    connected,
    error,
    pendingHitl,
    getEvents,
    addEvent,
    resolveCurrentPause,
    resetHitlSession,
    connect,
    disconnect,
    clearHitl,
    reset,
  }
})
