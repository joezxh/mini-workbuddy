/**
 * AI Team 多智能体团队 API（P3 管理 + P4 运行 + P7 干预/提及 + P8 回放）
 *
 * 后端前缀：GET/POST /api/v1/ai-team/...
 * 回放前缀：  GET/POST /api/v1/ai-team/replay/...
 */
import request from '@/utils/request'

const BASE = '/api/v1/ai-team'

// ── 团队 ──────────────────────────────────────────────
export interface TeamMember {
  node_key: string
  role_name: string
  agent_code?: string
  agent_id?: number
  model?: string
  system_prompt?: string
  is_leader?: boolean
  order_index?: number
  [key: string]: any
}

export interface TeamEdge {
  id: number
  source: string
  target: string
  edge_type?: string
  condition?: string
  [key: string]: any
}

export interface TeamOut {
  id: number
  team_code: string
  name?: string
  team_name?: string
  category?: string
  description?: string
  is_active?: boolean
  member_count?: number
  created_at?: string
  [key: string]: any
}

export interface TeamDetail extends TeamOut {
  members?: TeamMember[]
  edges?: TeamEdge[]
}

export interface TeamCreate {
  team_code?: string
  name: string
  category?: string
  description?: string
  is_active?: boolean
}

// ── 运行 ──────────────────────────────────────────────
export interface TeamRunOut {
  id: number
  run_id: string
  team_id: number
  conversation_id?: string
  input_text?: string
  final_output?: string
  status: string
  current_round?: number
  current_nodes?: string[]
  error_message?: string
  total_tokens?: number
  total_steps?: number
  duration_ms?: number
  trigger_type?: string
  parent_run_id?: string
  branch_from_node?: string
  created_by?: number
  started_at?: string
  finished_at?: string
  created_at?: string
  team_name?: string
}

export interface TeamRunCreate {
  input_text: string
  input_context?: Record<string, any>
  conversation_id?: string
  trigger_type?: string
}

// ── 回放 / 时间线 ─────────────────────────────────────
export interface TeamRunEvent {
  sequence: number
  event_type: string
  node_key?: string | null
  content?: Record<string, any> | null
  event_metadata?: Record<string, any> | null
  created_at?: string
}

export interface TeamRunReplay {
  run: TeamRunOut
  events: TeamRunEvent[]
}

export interface TimelineItem {
  sequence: number
  event_type: string
  node_key?: string | null
  title: string
  detail?: string | null
  created_at?: string
}

export interface TeamTimeline {
  run: TeamRunOut
  timeline: TimelineItem[]
}

export interface TeamRerunCreate {
  branch_from_node?: string
  input_text?: string
  input_context?: Record<string, any>
  trigger_type?: string
}

// ── 实时干预（v2）─────────────────────────────────────────
export interface InterventionV2Create {
  intervention_type: string
  node_key?: string | null
  round_no?: number | null
  payload?: Record<string, any> | null
  operator_name?: string | null
}

export interface InterventionV2Out {
  id: number
  run_id: string
  intervention_type: string
  node_key: string | null
  round_no: number | null
  payload: Record<string, any> | null
  status: string
  applied_at_round: number | null
  operator_id: number | null
  operator_name: string | null
  created_at: string | null
  resolved_by: string | null
  result_note: string | null
  total_events: number
}

// ──────────────────────────────────────────────────────
// 团队 CRUD
// ──────────────────────────────────────────────────────
export function listTeams(params?: {
  workspace_id?: number
  category?: string
  is_active?: boolean
  keyword?: string
  skip?: number
  limit?: number
}) {
  return request.get<TeamOut[]>(`${BASE}`, { params })
}

export function createTeam(payload: TeamCreate) {
  return request.post<TeamDetail>(`${BASE}`, payload)
}

export function getTeam(teamId: number) {
  return request.get<TeamDetail>(`${BASE}/${teamId}`)
}

export function updateTeam(teamId: number, payload: Partial<TeamCreate>) {
  return request.put<TeamDetail>(`${BASE}/${teamId}`, payload)
}

export function deleteTeam(teamId: number) {
  return request.delete(`${BASE}/${teamId}`)
}

export function listMembers(teamId: number) {
  return request.get<TeamMember[]>(`${BASE}/${teamId}/members`)
}

export function listEdges(teamId: number) {
  return request.get<TeamEdge[]>(`${BASE}/${teamId}/edges`)
}

export function validateTeam(teamId: number) {
  return request.post(`${BASE}/${teamId}/validate`)
}

/**
 * §6.2 拓扑保存：提交成员 + 边 + 画布布局，闭环 PUT /{team_id}/graph。
 *
 * 后端 TeamGraphSaveRequest 的成员使用 agent_config_id（agent_config 主键），
 * 与前端 TeamMember.agent_id 对应；边使用 from_node_key / to_node_key，
 * 与前端 TeamEdge.source / target 对应。layout 即画布快照（graph 字段）。
 */
export interface TeamGraphSavePayload {
  members: Array<{
    node_key: string
    agent_config_id: number
    role_name?: string
    model?: string
    system_prompt?: string
    agent_overrides?: Record<string, any>
  }>
  edges: Array<{
    from_node_key: string
    to_node_key: string
    edge_config?: Record<string, any>
  }>
  layout?: Record<string, any>
}

export function saveGraph(teamId: number, payload: TeamGraphSavePayload) {
  return request.put<TeamDetail>(`${BASE}/${teamId}/graph`, payload)
}

// ── 运行 ──────────────────────────────────────────────
export function runTeam(teamId: number, payload: TeamRunCreate) {
  return request.post<TeamRunOut>(`${BASE}/${teamId}/run`, payload)
}

export function chatTeam(teamId: number) {
  // SSE 流式，返回 EventSource 连接地址（由调用方消费）
  return `${BASE}/${teamId}/chat`
}

// ── 回放（P8）─────────────────────────────────────────
export function replayRun(runId: string) {
  return request.get<TeamRunReplay>(`${BASE}/replay/${runId}`)
}

export function replayTimeline(runId: string) {
  return request.get<TeamTimeline>(`${BASE}/replay/${runId}/timeline`)
}

export function rerunBranch(runId: string, payload: TeamRerunCreate) {
  return request.post<TeamRunOut>(`${BASE}/replay/${runId}/rerun`, payload)
}

// ── 实时干预（v2）─────────────────────────────────────────
export function listInterventions(teamId: number, runId: string) {
  return request.get<InterventionV2Out[]>(`${BASE}/${teamId}/runs/${runId}/interventions`)
}

// ── 历史对话恢复 ─────────────────────────────────────
export interface RunMessage {
  role: string          // user / team / worker / system
  author: string
  node_key?: string | null
  content: string
}

export function getRunMessages(teamId: number, runId: string) {
  return request.get<RunMessage[]>(`${BASE}/${teamId}/runs/${runId}/messages`)
}

export function createIntervention(teamId: number, runId: string, payload: InterventionV2Create) {
  return request.post<InterventionV2Out>(`${BASE}/${teamId}/runs/${runId}/interventions`, payload)
}
