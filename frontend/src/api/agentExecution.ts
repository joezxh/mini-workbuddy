import { getToken } from '@/utils/auth'

const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export type ExecutionMode = 'dify' | 'skill' | 'agent' | 'agent_team' | 'sqlbot'
export type ExecutionStatus = 'running' | 'completed' | 'failed'

export interface AgentExecutionItem {
  execution_id: string
  session_id: number
  session_title?: string
  user_id?: number
  execution_mode: ExecutionMode
  target_id?: string
  status: ExecutionStatus
  user_input?: string
  output?: string
  error?: string
  latency_ms?: number
  started_at?: string
  completed_at?: string
}

export interface AgentExecutionEvent {
  id: number
  execution_id: string
  event_type?: string
  sequence?: number
  content?: string
  source?: string
  source_id?: string
  // 拓扑便捷字段（来自 metadata_json）
  node_key?: string
  agent_code?: string
  role_name?: string
  node_status?: string
  node_type?: string
  channel?: string
  layer?: number
  parent_keys?: string[]
  created_at?: string
  metadata_json?: Record<string, any>
}

export interface AgentHitlPause {
  id: number
  execution_id: string
  pause_type?: string
  status?: string
  payload?: Record<string, any>
  response_data?: Record<string, any>
  user_id?: number
  approver_id?: number
  comment?: string
  created_at?: string
  resolved_at?: string
}

export interface AgentExecutionDetail extends AgentExecutionItem {
  metadata_json?: Record<string, any>
  trace?: Record<string, any>
  events?: AgentExecutionEvent[]
  hitl_pauses?: AgentHitlPause[]
}

export interface AgentExecutionEventListResp {
  items: AgentExecutionEvent[]
  total: number
}

export interface AgentExecutionListResp {
  items: AgentExecutionItem[]
  total: number
  page: number
  page_size: number
}

export interface AgentExecutionStats {
  by_execution_mode: Record<string, number>
  by_status: Record<string, number>
  avg_latency_ms?: number
  total_latency_ms?: number
  total?: number
  [key: string]: unknown
}

export interface ListAgentExecutionsParams {
  session_id?: number
  execution_mode?: ExecutionMode
  status?: ExecutionStatus
  target_id?: string
  keyword?: string
  start_time?: string
  end_time?: string
  page?: number
  page_size?: number
}

async function authHeader(): Promise<Record<string, string>> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function buildQuery(params: ListAgentExecutionsParams): string {
  const query = new URLSearchParams()
  if (params.page) query.set('page', String(params.page))
  if (params.page_size) query.set('page_size', String(params.page_size))
  if (params.session_id) query.set('session_id', String(params.session_id))
  if (params.execution_mode) query.set('execution_mode', params.execution_mode)
  if (params.status) query.set('status', params.status)
  if (params.target_id) query.set('target_id', params.target_id)
  if (params.keyword) query.set('keyword', params.keyword)
  if (params.start_time) query.set('start_time', params.start_time)
  if (params.end_time) query.set('end_time', params.end_time)
  return query.toString()
}

export async function listAgentExecutions(
  params: ListAgentExecutionsParams = {},
): Promise<AgentExecutionListResp> {
  const qs = buildQuery(params)
  const res = await fetch(`${baseUrl}/api/v1/agent-execution/?${qs}`, {
    headers: { ...(await authHeader()) },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getAgentExecutionDetail(
  executionId: string,
): Promise<AgentExecutionDetail> {
  const res = await fetch(`${baseUrl}/api/v1/agent-execution/${executionId}`, {
    headers: { ...(await authHeader()) },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function listAgentExecutionsBySession(
  sessionId: number | string,
): Promise<AgentExecutionListResp> {
  const res = await fetch(`${baseUrl}/api/v1/agent-execution/session/${sessionId}`, {
    headers: { ...(await authHeader()) },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getAgentExecutionStats(): Promise<AgentExecutionStats> {
  const res = await fetch(`${baseUrl}/api/v1/agent-execution/stats`, {
    headers: { ...(await authHeader()) },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getAgentExecutionEvents(
  executionId: string,
): Promise<AgentExecutionEventListResp> {
  const res = await fetch(`${baseUrl}/api/v1/agent-execution/${executionId}/events`, {
    headers: { ...(await authHeader()) },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

/** 归一化事件回放：仅返回 step / artifact 两类统一事件（结构化 dict） */
export async function getUnifiedEvents(
  executionId: string,
): Promise<{ execution_id: string; steps: any[]; artifacts: any[]; total: number }> {
  const res = await fetch(`${baseUrl}/api/v1/agent-execution/${executionId}/unified-events`, {
    headers: { ...(await authHeader()) },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
