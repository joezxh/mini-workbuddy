/**
 * SSE Event Types Module
 * 
 * Type definitions for SSE events matching backend schema
 */

export interface SSEEvent {
  type: string
  timestamp: string
  agent_id?: string | null
  team_id?: string
}

// Team Events
export interface TeamStartEvent extends SSEEvent {
  type: 'team_start'
  team_name: string
  agents_count: number
}

export interface TeamDoneEvent extends SSEEvent {
  type: 'team_done'
  success: boolean
  completed_agents: number
  total_agents: number
  final_output?: Record<string, unknown>
  summary?: string
}

// Agent Events
export interface AgentStartEvent extends SSEEvent {
  type: 'agent_start'
  agent_name: string
  role: string
}

export interface AgentDoneEvent extends SSEEvent {
  type: 'agent_done'
  output: string
  execution_time_ms?: number
  skills_used?: string[]
  tools_used?: string[]
}

export interface AgentErrorEvent extends SSEEvent {
  type: 'agent_error'
  error: string
  traceback?: string
  recovered?: boolean
}

// Execution Events
export interface ThinkingEvent extends SSEEvent {
  type: 'thinking'
  content: string
  confidence?: number
  step?: number
}

export interface ToolCallEvent extends SSEEvent {
  type: 'tool_call'
  tool_name: string
  parameters: Record<string, unknown>
  tool_description?: string
  timeout_seconds?: number
}

export interface ToolResultEvent extends SSEEvent {
  type: 'tool_result'
  tool_name: string
  success: boolean
  result?: Record<string, unknown>
  error_message?: string
  duration_ms?: number
}

export interface TextChunkEvent extends SSEEvent {
  type: 'text_chunk' | 'text_final'
  content: string
}

// Progress/Error Events
export interface ProgressEvent extends SSEEvent {
  type: 'progress'
  stage: string
  progress: number
  message: string
}

export interface ErrorEvent extends SSEEvent {
  type: 'error'
  message: string
  context?: Record<string, unknown>
}

// Union type of all event types
export type SSEReasoningEvent = ThinkingEvent
export type SSToolEvent = ToolCallEvent | ToolResultEvent
export type SSSkillEvent = SkillResultEvent

export interface SkillResultEvent extends SSEEvent {
  type: 'skill_result'
  skill_name: string
  result: string
}

// Export all event interfaces as named exports for consistency with backend
export const SSEEventTypes = {
  TEAM_START: 'team_start',
  TEAM_DONE: 'team_done',
  AGENT_START: 'agent_start',
  AGENT_DONE: 'agent_done',
  AGENT_ERROR: 'agent_error',
  THINKING: 'thinking',
  TOOL_CALL: 'tool_call',
  TOOL_RESULT: 'tool_result',
  TEXT_CHUNK: 'text_chunk',
  TEXT_FINAL: 'text_final',
  PROGRESS: 'progress',
  ERROR: 'error',
  SKILL_RESULT: 'skill_result',
} as const

export default {
  SSEEventTypes,
}
