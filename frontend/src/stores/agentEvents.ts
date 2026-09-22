/** AgentEvents Store（P1.3）：统一事件流状态。
 *
 * 负责：按 execution_id 汇总 /stream 推送的统一信封、按 seq 去重、
 * 按 ui_hint 路由（confirm → HITL 面板）、维护最新一次 hitl_pause。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { EventEnvelope } from '@/types/agentEvents'
import { connectEventStream, type SSEClient } from '@/utils/sseClient'

export const useAgentEventsStore = defineStore('agentEvents', () => {
  // 每个 execution 的事件列表（按 seq 去重）
  const byExecution = ref<Record<string, EventEnvelope[]>>({})
  const lastSeq = ref<Record<string, number>>({})
  const hitlPause = ref<EventEnvelope | null>(null)
  const connected = ref(false)
  const error = ref<string | null>(null)

  let client: SSEClient | null = null

  const getEvents = (executionId: string): EventEnvelope[] =>
    byExecution.value[executionId] || []

  const pendingHitl = computed(() => hitlPause.value)

  function addEvent(env: EventEnvelope) {
    const eid = env.execution_id
    if (!byExecution.value[eid]) byExecution.value[eid] = []
    const seq = env.sequence ?? 0
    if (byExecution.value[eid].some((e) => (e.sequence ?? -1) === seq)) return
    byExecution.value[eid].push(env)
    if (seq) lastSeq.value[eid] = Math.max(lastSeq.value[eid] || 0, seq)

    if (env.event_type === 'hitl_pause') hitlPause.value = env
    else if (env.event_type === 'hitl_resume' || env.event_type === 'interrupted')
      hitlPause.value = null
  }

  function connect(executionId: string) {
    disconnect()
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

  function clearHitl() {
    hitlPause.value = null
  }

  function reset() {
    disconnect()
    byExecution.value = {}
    lastSeq.value = {}
    hitlPause.value = null
    error.value = null
  }

  return {
    byExecution,
    lastSeq,
    hitlPause,
    connected,
    error,
    pendingHitl,
    getEvents,
    addEvent,
    connect,
    disconnect,
    clearHitl,
    reset,
  }
})
