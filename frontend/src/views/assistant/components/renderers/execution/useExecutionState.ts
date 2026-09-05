import { ref, computed, onUnmounted } from 'vue'
import { getToken } from '@/utils/auth'
import type {
  AgentState, TeamState, ToolCallPair, TaskItem,
  TimelineEvent, ExecutionPanelProps, ExecutionPhase, ExecutionStats,
  DispatchPlanState,
} from '../types/timeline'
import { EventType } from '../types/timeline'
import type { ExecutionEvent } from '@/types/shared'

export function useExecutionState(props: ExecutionPanelProps) {
  // ── 响应式状态 ──
  const teamState = ref<TeamState>({
    id: '', name: '', status: 'pending', agentsCount: 0, completedAgents: 0,
  })
  const agentGroups = ref<Map<string, AgentState>>(new Map())
  const agentOrder = ref<string[]>([])
  const tasks = ref<TaskItem[]>([])
  // 进度事件历史（累积显示，而非仅最新一条覆盖）
  const progressHistory = ref<Array<{ stage: string; progress: number; message: string }>>([])
  const phase = ref<ExecutionPhase>('idle')
  // v2.1 调度计划状态（dispatch_plan 事件驱动，spec §9.2）
  const planState = ref<DispatchPlanState | null>(null)
  const hasError = ref(false)
  const errorMessage = ref('')
  const selectedAgentId = ref<string | null>(null)

  // ── 扁平事件收集（供 SkillExecutionPanel 使用，与 MediatorPanel ExecutionEvent 对齐） ──
  const flatEvents = ref<ExecutionEvent[]>([])

  // ── 内部状态 ──
  let eventQueue: TimelineEvent[] = []
  let rafId: number | null = null
  let startTime = 0
  let abortController: AbortController | null = null
  const sequenceCounter = { value: 0 }

  // ── 计算属性 ──
  const elapsed = computed(() => {
    if (!startTime) return 0
    return Date.now() - startTime
  })

  const stats = computed<ExecutionStats>(() => {
    let totalTools = 0
    let totalErrors = 0
    for (const agent of agentGroups.value.values()) {
      totalTools += agent.toolPairs.length
      if (agent.status === 'error') totalErrors++
    }
    return {
      totalAgents: agentOrder.value.length,
      completedAgents: teamState.value.completedAgents,
      totalTools,
      totalErrors,
      totalDurationMs: startTime ? Date.now() - startTime : undefined,
    }
  })

  // ── rAF 批量更新（参考 AgentScope scheduleUpdate） ──
  function scheduleUpdate() {
    if (rafId != null) return
    rafId = requestAnimationFrame(() => {
      rafId = null
      flushEvents()
    })
  }

  function flushEvents() {
    const batch = eventQueue.splice(0)
    for (const evt of batch) {
      processEvent(evt)
    }
  }

  // ── 事件处理 ──
  function enqueueEvent(raw: Record<string, any>) {
    const evt = parseEvent(raw)
    if (!evt) return
    eventQueue.push(evt)
    scheduleUpdate()
  }

  function parseEvent(raw: Record<string, any>): TimelineEvent | null {
    // 兼容 SSE chunk 的两种字段：type（旧/agent 模式）和 event_type（team 模式）
    // （与 AssistantPanel SSE 解析逻辑 629 行 `chunk.type || chunk.event_type` 一致）
    const type = (raw.type || raw.event_type) as EventType
    if (!type) return null
    return {
      id: raw.event_id || `evt_${Date.now()}_${sequenceCounter.value++}`,
      type,
      timestamp: raw.timestamp ? new Date(raw.timestamp).getTime() : Date.now(),
      sequence: raw.sequence ?? sequenceCounter.value,
      agentId: raw.agent_id,
      teamId: raw.team_id,
      raw,
    }
  }

  function processEvent(evt: TimelineEvent) {
    const { type, raw, agentId } = evt

    // Team 级别事件
    if (type === EventType.TEAM_START) {
      teamState.value = {
        ...teamState.value,
        id: raw.team_id || '', name: raw.team_name || '',
        status: 'running', agentsCount: raw.agents_count || 0,
      }
      if (!startTime) startTime = Date.now()
      phase.value = 'streaming'
      // 同步到 flatEvents，让 SkillExecutionPanel「执行事件」Tab 可见
      flatEvents.value.push({
        type: 'progress',
        time: new Date(evt.timestamp).toISOString(),
        message: `▶ 团队 ${raw.team_code || raw.team_name || ''} 启动`,
      })
      return
    }
    if (type === EventType.TEAM_DONE) {
      teamState.value = {
        ...teamState.value,
        status: raw.success ? 'done' : 'failed',
        completedAgents: raw.completed_agents ?? teamState.value.agentsCount,
        finalOutput: raw.final_output,
      }
      phase.value = raw.success ? 'completed' : 'failed'
      // 同步到 flatEvents，让 SkillExecutionPanel「执行事件」Tab 可见
      flatEvents.value.push({
        type: 'progress',
        time: new Date(evt.timestamp).toISOString(),
        message: raw.success ? '✓ 团队编排完成' : '✗ 团队编排失败',
      })
      return
    }

    // v2.1 调度计划事件（Plan & Execute，spec §9.2）
    if (type === EventType.DISPATCH_PLAN) {
      const plan = (raw.plan || raw) as Record<string, any>
      planState.value = {
        planId: plan.plan_id,
        planReason: plan.plan_reason || '',
        batches: (plan.batches || []).map((b: any) => ({
          batch_no: b.batch_no,
          members: b.members || [],
          status: 'pending' as const,
        })),
      }
      // 同步到 flatEvents，让 SkillExecutionPanel「执行事件」Tab 可见
      const batchCount = planState.value.batches.length
      flatEvents.value.push({
        type: 'progress',
        time: new Date(evt.timestamp).toISOString(),
        message: `📋 计划生成（${batchCount} 批）${plan.plan_reason ? '：' + plan.plan_reason : ''}`,
      })
      return
    }
    if (type === EventType.PLAN_REVISED) {
      const plan = planState.value
      const payload = (raw.plan || raw) as Record<string, any>
      if (plan && payload.remaining_batches) {
        const kept = new Set(payload.remaining_batches.map((b: any) => b.batch_no))
        plan.batches = plan.batches.filter((b) => kept.has(b.batch_no))
        for (const rb of payload.remaining_batches) {
          if (!plan.batches.find((b) => b.batch_no === rb.batch_no)) {
            plan.batches.push({
              batch_no: rb.batch_no,
              members: (rb.members || []).map((m: any) => ({ role_name: m })),
              status: 'pending' as const,
            })
          }
        }
        plan.batches.sort((a, b) => a.batch_no - b.batch_no)
      }
      return
    }
    if (type === EventType.TEAM_LAYER_START || type === EventType.TEAM_LAYER_DONE) {
      const no = raw.batch_no
      const batch = planState.value?.batches.find((b) => b.batch_no === no)
      if (batch) batch.status = type === EventType.TEAM_LAYER_START ? 'running' : 'done'
      // 同步到 flatEvents，让 SkillExecutionPanel「执行事件」Tab 可见
      const members = batch?.members?.map((m: any) => m.role_name).join('、') || raw.members?.join('、') || ''
      const membersLabel = members ? `（成员: ${members}）` : ''
      flatEvents.value.push({
        type: 'progress',
        time: new Date(evt.timestamp).toISOString(),
        message: type === EventType.TEAM_LAYER_START
          ? `▶ 批次 ${no} 开始${membersLabel}`
          : `✓ 批次 ${no} 完成${membersLabel}`,
      })
      return
    }

    // Agent 级别事件
    if (type === EventType.AGENT_START && agentId) {
      ensureAgent(agentId, raw)
      const agent = agentGroups.value.get(agentId)!
      agent.status = 'running'
      agent.startTime = Date.now()
      agent.name = raw.agent_name || raw.role_name || agentId
      agent.role = raw.role || raw.role_name
      // 运行态可视化（§13.6）：捕获通道与节点标识
      if (raw.channel) agent.channel = raw.channel
      if (raw.agent_code) agent.nodeKey = raw.agent_code
      // 同步到 flatEvents，让 SkillExecutionPanel「执行事件」Tab 可见
      const roleLabel = raw.role_name || raw.agent_name || agentId
      flatEvents.value.push({
        type: 'progress',
        time: new Date(evt.timestamp).toISOString(),
        message: `▸ 专家 [${roleLabel}] 开始执行`,
      })
      return
    }
    if (type === EventType.AGENT_DONE && agentId) {
      const agent = agentGroups.value.get(agentId)
      if (agent) {
        agent.status = 'done'
        agent.endTime = Date.now()
        agent.textOutput = raw.output || agent.textOutput
        agent.skillsUsed = raw.skills_used || []
        agent.toolsUsed = raw.tools_used || []
        teamState.value.completedAgents++
      }
      // 同步到 flatEvents，让 SkillExecutionPanel「执行事件」Tab 可见
      const roleLabel = raw.role_name || raw.agent_name || agentId
      const outputLen = raw.output?.length || (typeof raw.output === 'string' ? raw.output.length : 0)
      const outputLabel = outputLen ? `（输出 ${outputLen} 字）` : ''
      flatEvents.value.push({
        type: 'progress',
        time: new Date(evt.timestamp).toISOString(),
        message: `✓ 专家 [${roleLabel}] 执行完成${outputLabel}`,
      })
      return
    }
    if (type === EventType.AGENT_ERROR && agentId) {
      const agent = agentGroups.value.get(agentId)
      if (agent) {
        agent.status = 'error'
        agent.endTime = Date.now()
        agent.error = { message: raw.error || '', traceback: raw.traceback, recovered: raw.recovered ?? false }
      }
      return
    }

    // 确保 agent 存在
    if (agentId) ensureAgent(agentId, raw)

    // Legacy 事件处理
    if (type === EventType.THINKING && agentId) {
      const agent = agentGroups.value.get(agentId)!
      agent.thinkingContent += raw.content || ''
      pushAgentEvent(agentId, evt)
      // 收集扁平事件。
      // step/title 为思考模式专用：思考模式每个 thinking 事件是一个独立推理步骤，
      // 需保留序号与标题以便面板分步展示；技能模式为增量块，无此字段（走合并逻辑）。
      // data.agent_id / data.role_name 为团队模式专用：多名专家并行产出思考，
      // 团队面板需按专家分组聚合（扁平事件丢失 agent_id 会导致无法区分专家）。
      flatEvents.value.push({
        type: 'thinking',
        time: new Date(evt.timestamp).toISOString(),
        message: raw.content || '',
        step: raw.step,
        title: raw.title,
        data: { agent_id: raw.agent_id, role_name: raw.role_name },
      })
      return
    }
    if (type === EventType.TEXT_CHUNK && agentId) {
      const agent = agentGroups.value.get(agentId)!
      agent.textOutput += raw.content || ''
      return
    }
    if (type === EventType.TOOL_CALL && agentId) {
      const agent = agentGroups.value.get(agentId)!
      const pair: ToolCallPair = {
        id: raw.tool_call_id || `tc_${Date.now()}`,
        toolName: raw.tool_name || 'unknown',
        toolDescription: raw.tool_description,
        parameters: raw.parameters || raw.input || {},
        status: 'calling',
        agentId,
      }
      agent.toolPairs.push(pair)
      pushAgentEvent(agentId, evt)
      // 收集扁平事件
      flatEvents.value.push({
        type: 'tool_call',
        time: new Date(evt.timestamp).toISOString(),
        message: raw.tool_name || 'unknown',
        data: { tool_name: raw.tool_name || 'unknown', parameters: raw.parameters || raw.input || {} },
      })
      return
    }
    if ((type === EventType.TOOL_RESULT || type === EventType.TOOL_ERROR) && agentId) {
      const agent = agentGroups.value.get(agentId)!
      const pair = agent.toolPairs.find(p =>
        p.toolName === raw.tool_name || p.id === raw.tool_call_id
      )
      if (pair) {
        pair.status = type === EventType.TOOL_ERROR ? 'error' : (raw.success ? 'success' : 'error')
        pair.result = raw.result
        pair.errorMessage = raw.error_message
        pair.durationMs = raw.duration_ms
      }
      pushAgentEvent(agentId, evt)
      // 收集扁平事件
      flatEvents.value.push({
        type: 'tool_result',
        time: new Date(evt.timestamp).toISOString(),
        message: raw.tool_name || 'unknown',
        data: {
          tool_name: raw.tool_name || 'unknown',
          result: type === EventType.TOOL_ERROR ? (raw.error_message || 'Error') : (typeof raw.result === 'string' ? raw.result : JSON.stringify(raw.result)),
        },
      })
      return
    }

    // Progress 事件 —— 累积到 history，同时更新 task 状态
    if (type === EventType.PROGRESS) {
      progressHistory.value.push({ stage: raw.stage, progress: raw.progress, message: raw.message })
      // 收集扁平事件
      flatEvents.value.push({
        type: 'progress',
        time: new Date(evt.timestamp).toISOString(),
        message: raw.message || raw.stage || '',
      })
      // 更新或创建任务
      const existing = tasks.value.find(t => t.stage === raw.stage)
      if (existing) {
        existing.progress = raw.progress
        existing.message = raw.message
      } else {
        tasks.value.push({
          id: raw.stage, name: raw.stage, status: raw.progress >= 100 ? 'done' : 'running',
          progress: raw.progress, message: raw.message, stage: raw.stage,
        })
      }
      return
    }

    // Step 事件（时间线步骤：run_start / reply_start / model_call / llm_think /
    // text_gen / run_done 等，来自 SSE `type=step` 归一化）。
    // 此前该分支缺失，导致「执行事件」Tab 不显示时间线步骤（仅「时间线」Tab 有）。
    // 新增收集到 flatEvents，使执行事件 Tab 也能看到完整步骤流。
    if (type === 'step') {
      flatEvents.value.push({
        type: 'step',
        time: new Date(evt.timestamp).toISOString(),
        message: raw.title || raw.event_type || '',
        phase: raw.phase,
        eventType: raw.event_type,
        seq: raw.seq,
        status: raw.status,
        detail: raw.detail,
        elapsedMs: raw.elapsed_ms,
      })
      return
    }

    // Error 事件
    if (type === EventType.ERROR) {
      hasError.value = true
      errorMessage.value = raw.message || 'Unknown error'
    }

    // 其他事件直接推入 agent
    if (agentId) pushAgentEvent(agentId, evt)
  }

  function ensureAgent(agentId: string, raw: Record<string, any>) {
    if (!agentGroups.value.has(agentId)) {
      agentGroups.value.set(agentId, {
        id: agentId, name: raw.agent_name || agentId,
        status: 'pending', events: [], toolPairs: [],
        textOutput: '', thinkingContent: '',
        skillsUsed: [], toolsUsed: [],
        channel: raw.channel, nodeKey: raw.agent_code, paused: false,
      })
      agentOrder.value.push(agentId)
    }
  }

  function pushAgentEvent(agentId: string, evt: TimelineEvent) {
    const agent = agentGroups.value.get(agentId)
    if (agent) agent.events.push(evt)
  }

  // ── SSE 连接 ──
  async function startStream(url: string) {
    abortController = new AbortController()
    phase.value = 'streaming'
    hasError.value = false

    try {
      const token = getToken()
      const response = await fetch(url, {
        signal: abortController.signal,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!response.body) throw new Error('No response body')
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.trim().startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              enqueueEvent(data)
            } catch { /* skip parse errors */ }
          }
        }
      }
      if (phase.value === 'streaming') phase.value = 'completed'
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        hasError.value = true
        errorMessage.value = err.message || 'SSE connection failed'
        phase.value = 'failed'
      }
    }
  }

  function stopStream() {
    abortController?.abort()
    abortController = null
    if (rafId != null) { cancelAnimationFrame(rafId); rafId = null }
  }

  // ── 初始化 ──
  function init(): Promise<void> | void {
    // 模式 1：直接传入事件数组
    if (props.events?.length) {
      for (const evt of props.events) {
        if ('raw' in evt) processEvent(evt as TimelineEvent)
        else processEvent(parseEvent(evt as any)!)
      }
      phase.value = 'completed'
      return
    }
    // 模式 2：SSE URL
    if (props.streamUrl) { return startStream(props.streamUrl) }
    // 模式 3：executionId（使用 fetch JSON 加载历史事件）
    if (props.executionId) {
      return loadHistoricalEvents(props.executionId)
    }
  }

  // ── 历史事件加载（fetch JSON） ──
  async function loadHistoricalEvents(executionId: string) {
    // 如果 status 已经是终态（如历史消息 skillEvent 返回 'completed'），
    // 直接设为对应状态，不经过 'streaming'，避免面板闪烁折叠
    const isAlreadyDone = props.status === 'completed' || props.status === 'failed'
    phase.value = isAlreadyDone ? props.status as ExecutionPhase : 'streaming'
    hasError.value = false
    try {
      const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
      const token = getToken()
      const response = await fetch(`${baseUrl}/api/v1/ai-agent/skill-execution/${executionId}/events`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const data = await response.json()
      const events = data.events || []
      for (const raw of events) {
        const evt = parseEvent(raw)
        if (evt) processEvent(evt)
      }
      // 确保终态不被回退（processEvent 中的 TEAM_DONE 可能已设置过）
      if (phase.value !== 'completed' && phase.value !== 'failed') {
        phase.value = 'completed'
      }
    } catch (err: any) {
      hasError.value = true
      errorMessage.value = err.message || 'Failed to load historical events'
      // 如果已经是 completed 状态，不因 API 失败而回退
      if (phase.value !== 'completed') {
        phase.value = 'failed'
      }
    }
  }

  // ── 清理 ──
  onUnmounted(() => {
    stopStream()
  })

  function retry() {
    stopStream()
    hasError.value = false
    errorMessage.value = ''
    if (props.streamUrl) startStream(props.streamUrl)
    else if (props.executionId) loadHistoricalEvents(props.executionId)
  }

  function resetFlatEvents() {
    flatEvents.value = []
  }

  function exportTimeline() {
    const data = {
      team: teamState.value,
      agents: Object.fromEntries(agentGroups.value),
      tasks: tasks.value,
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `execution-${Date.now()}.json`; a.click()
    URL.revokeObjectURL(url)
  }

  return {
    teamState, agentGroups, agentOrder, tasks, progressHistory,
    phase, hasError, errorMessage, selectedAgentId,
    planState,
    stats, elapsed,
    retry, exportTimeline, init, enqueueEvent,
    flatEvents, resetFlatEvents,
  }
}
