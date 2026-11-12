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

/** HITL 暂停类型（spec B4：tool_confirm 工具授权 / plan_approval 计划审批 / ask_user 对话追问） */
export type HitlPauseType = 'tool_confirm' | 'plan_approval' | 'ask_user'

export interface HitlPausePayload {
  reply_id?: string | null
  tool_calls?: HitlToolCall[]
  timeout_minutes?: number
  pause_type?: HitlPauseType | string
}

/** AskUser 问题（tool_calls[0].input.questions 元素，spec F6/B3） */
export interface HitlAskUserQuestion {
  question: string
  options?: string[]
}

/** 已完成 HITL 轮次（多轮队列语义，spec F3） */
export interface HitlPauseHistoryItem {
  pause_type: HitlPauseType | string
  action: HitlAction | string
  time: string
  tools: string[]
}

export type HitlAction = 'approve' | 'reject' | 'interrupt'

export const HITL_UI_HINT = 'confirm'
