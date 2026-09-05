/**
 * 事件可视化类型定义 — v2 AgentScope 对齐版
 * 41 种事件类型，覆盖 AgentScope 全部 28 种 + 13 种领域特有
 */

// ── EventType 枚举（41 种） ──────────────────────────────────
export enum EventType {
  // Reply Lifecycle
  REPLY_START = 'reply_start',
  REPLY_END = 'reply_end',
  // Model Call
  MODEL_CALL_START = 'model_call_start',
  MODEL_CALL_END = 'model_call_end',
  // Team Level（领域特有）
  TEAM_START = 'team_start',
  TEAM_DONE = 'team_done',
  // Team Dispatch v2.1（Plan & Execute 调度计划，spec §9.2）
  DISPATCH_PLAN = 'dispatch_plan',
  PLAN_REVISED = 'plan_revised',
  TEAM_LAYER_START = 'team_layer_start',
  TEAM_LAYER_DONE = 'team_layer_done',
  // Agent Level（领域特有）
  AGENT_START = 'agent_start',
  AGENT_DONE = 'agent_done',
  AGENT_ERROR = 'agent_error',
  // Text Block Streaming
  TEXT_BLOCK_START = 'text_block_start',
  TEXT_BLOCK_DELTA = 'text_block_delta',
  TEXT_BLOCK_END = 'text_block_end',
  // Thinking Block Streaming
  THINKING_BLOCK_START = 'thinking_block_start',
  THINKING_BLOCK_DELTA = 'thinking_block_delta',
  THINKING_BLOCK_END = 'thinking_block_end',
  // Data Block Streaming
  DATA_BLOCK_START = 'data_block_start',
  DATA_BLOCK_DELTA = 'data_block_delta',
  DATA_BLOCK_END = 'data_block_end',
  // Hint Block
  HINT_BLOCK = 'hint_block',
  // Tool Call Streaming
  TOOL_CALL_START = 'tool_call_start',
  TOOL_CALL_DELTA = 'tool_call_delta',
  TOOL_CALL_END = 'tool_call_end',
  // Tool Result Streaming
  TOOL_RESULT_START = 'tool_result_start',
  TOOL_RESULT_TEXT_DELTA = 'tool_result_text_delta',
  TOOL_RESULT_DATA_DELTA = 'tool_result_data_delta',
  TOOL_RESULT_END = 'tool_result_end',
  // Legacy Execution（向后兼容）
  THINKING = 'thinking',
  TOOL_CALL = 'tool_call',
  TOOL_RESULT = 'tool_result',
  TOOL_ERROR = 'tool_error',
  TEXT_CHUNK = 'text_chunk',
  TEXT_DONE = 'text_done',
  // Human-in-the-Loop
  REQUIRE_USER_CONFIRM = 'require_user_confirm',
  REQUIRE_EXTERNAL_EXECUTION = 'require_external_execution',
  USER_CONFIRM_RESULT = 'user_confirm_result',
  USER_INTERRUPT = 'user_interrupt',
  EXTERNAL_EXECUTION_RESULT = 'external_execution_result',
  // Status & Progress
  PROGRESS = 'progress',
  ERROR = 'error',
  // Safety
  EXCEED_MAX_ITERS = 'exceed_max_iters',
  // Extensibility
  CUSTOM = 'custom',
}

/**
 * SSE 流式事件类型常量 —— 后端 SkillEvent.type 的前端镜像。
 * 用于 AssistantPanel.vue 的 chunk.type 匹配，避免硬编码字符串。
 */
export const SSE_EVENT_TYPE = {
  GATEWAY_META: '_gateway_meta',
  TOKEN: 'token',
  TEXT: 'text',
  TEXT_CHUNK: 'text_chunk',
  TEXT_DONE: 'text_done',
  THINKING: 'thinking',
  TOOL_CALL: 'tool_call',
  TOOL_RESULT: 'tool_result',
  PROGRESS: 'progress',
  ENGINE_DECISION: 'engine_decision',
  COMPLETED: 'completed',
  DONE: 'done',
  ERROR: 'error',
  ARTIFACT: 'artifact',
} as const

export type SSEEventType = typeof SSE_EVENT_TYPE[keyof typeof SSE_EVENT_TYPE]

// ── 执行面板专用类型 ──────────────────────────────────────────

/** Agent 执行状态 */
export interface AgentState {
  id: string
  name: string
  role?: string
  status: 'pending' | 'running' | 'done' | 'error'
  startTime?: number
  endTime?: number
  events: TimelineEvent[]
  toolPairs: ToolCallPair[]
  textOutput: string
  thinkingContent: string
  error?: { message: string; traceback?: string; recovered: boolean }
  skillsUsed: string[]
  toolsUsed: string[]
  /** 运行态可视化（§13.6）：来源通道 teamsay=@提及单点追问 / leader=完整编排 */
  channel?: 'leader' | 'teamsay'
  /** 节点 role 名称（与团队拓扑对齐） */
  nodeKey?: string
  /** 是否被操作员暂停（运行态干预） */
  paused?: boolean
}

/** Team 执行状态 */
export interface TeamState {
  id: string
  name: string
  status: 'pending' | 'running' | 'done' | 'failed'
  agentsCount: number
  completedAgents: number
  description?: string
  finalOutput?: Record<string, any>
}

/** 工具调用配对（类比 AgentScope ToolCallWithResult） */
export interface ToolCallPair {
  id: string
  toolName: string
  toolDescription?: string
  parameters: Record<string, any>
  status: 'calling' | 'success' | 'error'
  result?: Record<string, any>
  errorMessage?: string
  durationMs?: number
  agentId: string
}

/** 任务项 */
export interface TaskItem {
  id: string
  name: string
  agentId?: string
  status: 'pending' | 'running' | 'done' | 'error'
  progress: number
  message: string
  stage: string
}

/** 时间线事件（统一格式） */
export interface TimelineEvent {
  id: string
  type: EventType
  timestamp: number
  sequence: number
  agentId?: string
  teamId?: string
  raw: Record<string, any>
}

/** 执行面板 Props */
export interface ExecutionPanelProps {
  executionId?: string
  streamUrl?: string
  events?: TimelineEvent[]
  status?: 'pending' | 'running' | 'completed' | 'failed'
  streaming?: boolean
  // 新增：直接传入 composable 状态（实时流模式，由父组件的 useExecutionState 提供）
  agentGroups?: Map<string, AgentState>
  agentOrder?: string[]
  teamState?: TeamState
  tasks?: TaskItem[]
  /** 进度事件历史（累积显示，而非仅最新一条） */
  progressHistory?: Array<{ stage: string; progress: number; message: string }>
  phase?: ExecutionPhase
  /** v2.1 调度计划状态（外部传入模式） */
  plan?: DispatchPlanState | null
}

/** 执行阶段 */
export type ExecutionPhase = 'idle' | 'streaming' | 'completed' | 'failed'

/** 执行统计 */
export interface ExecutionStats {
  totalAgents: number
  completedAgents: number
  totalTools: number
  totalErrors: number
  totalDurationMs?: number
}

// ── 保留旧类型（向后兼容，其他组件仍在使用） ──────────────────

/** @deprecated 使用新的 TimelineEvent */
export interface LegacyTimelineEvent {
  id: string
  timestamp: number
  eventType: EventType
  payload: Record<string, any>
  summary: string
  details?: EventDetails
  isCompleted?: boolean
}

export interface EventDetails {
  toolInfo?: { name: string; input: Record<string, any>; output: string | object; duration?: number }
  chartConfig?: ChartConfig
  fileMeta?: FileMetadata
  markdownContent?: string
  jsonData?: any
  errorStack?: string
}

export interface ChartConfig {
  type: 'bar' | 'line' | 'pie' | 'scatter' | 'gauge' | 'table' | 'column' | 'area' | 'radar'
  title?: string
  data: Array<{ [key: string]: string | number }>
  axis?: {
    x?: { name: string; unit?: string; type?: 'category' | 'value' }
    y?: { name: string; unit?: string; type?: 'value' }
    series?: { name: string; type: string }
  }
  tooltip?: any
  legend?: any
  grid?: any
  options?: any
}

export interface FileMetadata {
  name: string
  url: string
  size?: number
  type?: string
  mimeType?: string
  pageCount?: number
  sheetCount?: number
}

/** @deprecated 使用 ExecutionPhase */
export enum ExecutionStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

/** @deprecated 使用 ExecutionStats */
export interface TimelineStats {
  total: number
  thinking: number
  toolCalls: number
  errors: number
  completed: number
  avgDurationMs?: number
}

/** v2.1 调度计划批次成员（spec §9.2） */
export interface PlanBatchMember {
  role_name: string
  instruction?: string
  depends_on?: string[]
}

/** v2.1 调度计划批次泳道 */
export interface PlanBatch {
  batch_no: number
  members: PlanBatchMember[]
  status: 'pending' | 'running' | 'done'
}

/** v2.1 调度计划状态（dispatch_plan 事件驱动） */
export interface DispatchPlanState {
  planId?: string
  planReason?: string
  batches: PlanBatch[]
}

export interface SSERawEvent {
  type: string
  event_id?: string
  agent_id?: string
  [key: string]: any
}
