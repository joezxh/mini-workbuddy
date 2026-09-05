/**
 * AI Agent 配置 / 链路追踪 API
 */
import request from '@/utils/request'

const BASE_URL = '/api/v1'

// ── 链路追踪（Trace）──────────────────────────────────────────────────────────

/** 单条 trace 概览 */
export interface TraceTimeline {
  trace_id: string
  agent_id?: string
  status?: string
  duration_ms?: number
  start_time?: string
  spans?: any[]
  [key: string]: any
}

/** trace span 列表响应 */
export interface TraceSpansResponse {
  trace_id: string
  spans: any[]
}

/** trace 列表项 */
export interface TraceItem {
  trace_id: string
  agent_id?: string
  agent_code?: string
  status?: string
  duration_ms?: number
  start_time?: string
  [key: string]: any
}

/** trace 列表响应 */
export interface TraceListResponse {
  traces: TraceItem[]
  total?: number
}

/** 获取单条 trace 的时间线概览 */
export function getTraceTimeline(traceId: string): Promise<TraceTimeline> {
  return request.get(`${BASE_URL}/agent/trace/timeline`, { params: { trace_id: traceId } })
}

/** 获取单条 trace 的 spans 明细 */
export function getTraceSpans(traceId: string): Promise<TraceSpansResponse> {
  return request.get(`${BASE_URL}/agent/trace/spans`, { params: { trace_id: traceId } })
}

/** 查询 Agent 的 trace 列表 */
export function getTraceList(params: {
  agent_id?: string
  limit?: number
}): Promise<TraceListResponse> {
  return request.get(`${BASE_URL}/agent/trace/list`, { params })
}

// ── Agent 配置 ─────────────────────────────────────────────────────────────────

/** Agent 配置项（来自 AgentConfigResponse 的精简前端视图） */
export interface AgentItem {
  id: number
  agent_code: string
  name: string
  agent_type: string // CHAT / WORKFLOW / SKILL
  category?: string | null
  description?: string | null
  is_active: boolean
  execution_mode?: string
  sort_order?: number
}

/** AgentTeam 能力状态 */
export interface AgentTeamStatus {
  available: boolean
  message?: string
}

/** Agent 注册表响应（按 category 分组） */
export interface AgentRegistryResponse {
  total: number
  agents: AgentItem[]
  grouped: Record<string, AgentItem[]>
  categories: string[]
  agent_team: AgentTeamStatus
}

/** 前端选中的 Agent 信息（提交时透传） */
export interface AgentInfo {
  id: number
  code: string
  name: string
  category?: string | null
}

/** 获取 Agent 注册表（按 category 分组，参考技能获取接口） */
export function getAgentRegistry(params?: { category?: string }): Promise<AgentRegistryResponse> {
  return request.get(`${BASE_URL}/agent-config/registry`, { params })
}
