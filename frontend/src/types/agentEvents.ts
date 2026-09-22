/** 统一事件信封前端类型（与后端 app/schemas/agent/event_types.py 对齐） */

export type EventLevel = 0 | 1 | 2 | 3

export interface EventEnvelope {
  sequence?: number
  execution_id: string
  trace_id?: string | null
  event_type: string
  category: string
  levels: EventLevel[]
  content: Record<string, any>
  source?: string | null
  source_id?: string | null
  reply_id?: string | null
  block_id?: string | null
  tool_call_id?: string | null
  interrupt_reason?: string | null
  ui_hint?: string | null
  event_version?: number
  metadata?: Record<string, any>
}

export interface HitlToolCall {
  id: string
  name: string
  input: any
  suggested_rules?: string[]
}

export interface HitlPausePayload {
  reply_id?: string | null
  tool_calls?: HitlToolCall[]
  timeout_minutes?: number
}

export type HitlAction = 'approve' | 'reject' | 'interrupt'

export const HITL_UI_HINT = 'confirm'
