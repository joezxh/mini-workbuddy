/**
 * SuperAgent API 客户端（Task 4.1 / 4.6）
 *
 * REST 走 @/utils/request（自动带 Bearer token）；
 * SSE 用原生 EventSource / fetch 流（request 封装不支持流式响应）。
 */
import request from '@/utils/request'
import { getApiBase } from '@/utils/apiBase'

const BASE = '/api/v1/super-agent'

// ============ 类型 ============

export interface TicketBrief {
  id: string
  status: string
  title: string
  source: string
  created_at: string
}

export interface TicketDetail extends TicketBrief {
  intent_evidence?: string | null
  mandate?: { strength: string; policy_version: string; matched_rules: any[] } | null
  assignment?: { status: string; executor_session: string; started_at: string | null } | null
}

export interface FeedPost {
  id: number
  workspace_id: number
  kind: string
  title: string
  body?: string | null
  prompt?: string | null
  goal_id?: string | null
  quiet?: boolean
  read?: boolean
  created_at?: string
}

export interface Idea {
  id: number
  emo: string
  pitch: string
  detail?: string | null
  kind: string
  prompt?: string | null
  src?: string | null
  pinned: boolean
  created_at?: string
}

export interface GoalStep {
  idx: number
  text: string
  status: string // done/pending/in_progress/blocked/skipped
}

export interface GoalProposal {
  idx: number
  kind: string
  message: string
  payload?: Record<string, any>
  status: string // pending/accepted/dismissed
  created_at?: string
}

export interface Goal {
  id: string
  workspace_id: number
  title: string
  context?: string | null
  status: string // active/paused/done/cancelled
  progress: number
  cron?: string | null
  due?: string | null
  source?: string | null
  version: number
  steps: GoalStep[]
  proposals: GoalProposal[]
  notes: { ts: string; text: string }[]
  created_at?: string
  updated_at?: string
}

export interface ChatSession {
  id: string
  title: string
  created_at: string
  message_count?: number
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  ts: string
}

// ============ REST ============

export const listTickets = (workspaceId: number, status?: string) =>
  request.get<TicketBrief[]>(`${BASE}/tickets`, { params: { workspace_id: workspaceId, status } })

export const getTicket = (ticketId: string) =>
  request.get<TicketDetail>(`${BASE}/tickets/${ticketId}`)

export const createTicket = (data: { workspace_id: number; title: string; prompt?: string; source?: string }) =>
  request.post<TicketBrief>(`${BASE}/tickets`, data)

export const listSources = () => request.get<any[]>(`${BASE}/sources`)

export const getSourceConfig = (kind: string) =>
  request.get<any>(`${BASE}/sources/${kind}/config`)

export const updateSourceConfig = (kind: string, value: any) =>
  request.put<any>(`${BASE}/sources/${kind}/config`, value)

export const listThreads = (workspaceId: number, source?: string) =>
  request.get<any[]>(`${BASE}/threads`, { params: { workspace_id: workspaceId, source } })

export const listTicketSubscriptions = (ticketId: string) =>
  request.get<any[]>(`${BASE}/tickets/${ticketId}/subscriptions`)

// --- Workbench：Feed ---

export const listFeed = (workspaceId: number, kind?: string) =>
  request.get<FeedPost[]>(`${BASE}/feed`, { params: { workspace_id: workspaceId, kind } })

export const markFeedRead = (postId: number, workspaceId: number) =>
  request.post<{ ok: boolean }>(`${BASE}/feed/${postId}/read`, null, { params: { workspace_id: workspaceId } })

// --- Workbench：Ideas ---

export const listIdeas = (workspaceId: number) =>
  request.get<Idea[]>(`${BASE}/ideas`, { params: { workspace_id: workspaceId } })

export const createIdea = (data: { workspace_id: number; emo?: string; pitch: string; detail?: string; kind?: string; prompt?: string }) =>
  request.post<Idea>(`${BASE}/ideas`, data)

export const pinIdea = (ideaId: number, workspaceId: number) =>
  request.post<{ ok: boolean }>(`${BASE}/ideas/${ideaId}/pin`, null, { params: { workspace_id: workspaceId } })

export const refreshIdeas = (workspaceId: number, count = 3) =>
  request.post<{ created: Idea[]; count: number }>(`${BASE}/ideas/refresh`, { workspace_id: workspaceId, count })

// --- Workbench：Goals ---

export const listGoals = (workspaceId: number) =>
  request.get<Goal[]>(`${BASE}/goals`, { params: { workspace_id: workspaceId } })

export const getGoal = (goalId: string, workspaceId: number) =>
  request.get<Goal>(`${BASE}/goals/${goalId}`, { params: { workspace_id: workspaceId } })

export const createGoal = (data: { workspace_id: number; title: string; context?: string; steps?: string[]; cron?: string; due?: string }) =>
  request.post<Goal>(`${BASE}/goals`, data)

export const patchGoal = (goalId: string, status: string, workspaceId: number) =>
  request.patch<Goal>(`${BASE}/goals/${goalId}`, { status }, { params: { workspace_id: workspaceId } })

export const toggleGoalStep = (goalId: string, stepIdx: number, workspaceId: number) =>
  request.post<Goal>(`${BASE}/goals/${goalId}/steps/${stepIdx}/toggle`, null, { params: { workspace_id: workspaceId } })

export const skipGoalStep = (goalId: string, stepIdx: number, workspaceId: number) =>
  request.post<Goal>(`${BASE}/goals/${goalId}/steps/${stepIdx}/skip`, null, { params: { workspace_id: workspaceId } })

export const proposeGoal = (goalId: string, workspaceId: number) =>
  request.post<Goal>(`${BASE}/goals/${goalId}/proposals`, null, { params: { workspace_id: workspaceId } })

export const acceptProposal = (goalId: string, proposalIdx: number, workspaceId: number) =>
  request.post<Goal>(`${BASE}/goals/${goalId}/proposals/${proposalIdx}/accept`, null, { params: { workspace_id: workspaceId } })

export const dismissProposal = (goalId: string, proposalIdx: number, workspaceId: number) =>
  request.post<Goal>(`${BASE}/goals/${goalId}/proposals/${proposalIdx}/dismiss`, null, { params: { workspace_id: workspaceId } })

export const addGoalNote = (goalId: string, text: string, workspaceId: number) =>
  request.post<Goal>(`${BASE}/goals/${goalId}/notes`, { text }, { params: { workspace_id: workspaceId } })

// --- Workbench：Chat ---

export const listChatSessions = (workspaceId: number) =>
  request.get<ChatSession[]>(`${BASE}/chat/sessions`, { params: { workspace_id: workspaceId } })

export const createChatSession = (workspaceId: number, title = '新对话') =>
  request.post<ChatSession>(`${BASE}/chat/sessions`, { workspace_id: workspaceId, title })

export const getChatSession = (sessionId: string, workspaceId: number) =>
  request.get<ChatSession & { messages: ChatMessage[] }>(`${BASE}/chat/sessions/${sessionId}`, { params: { workspace_id: workspaceId } })

/**
 * 发送消息并消费 SSE 流（POST 不支持 EventSource，用 fetch + ReadableStream 解析）。
 * 回调 onEvent(event, data)，事件：text_delta / done / interrupted / error。
 */
export async function streamChatSend(
  sessionId: string,
  message: string,
  runId: string,
  onEvent: (event: string, data: any) => void,
  signal?: AbortSignal
): Promise<void> {
  const base = getApiBase()
  const token = (await import('@/utils/auth')).getToken()
  const resp = await fetch(`${base}${BASE}/chat/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token || ''}` },
    body: JSON.stringify({ session_id: sessionId, message, run_id: runId }),
    signal
  })
  if (!resp.ok || !resp.body) {
    onEvent('error', { message: `HTTP ${resp.status}` })
    return
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    // SSE 解析：按空行分帧，event: <name>\ndata: <json>
    const frames = buf.split('\n\n')
    buf = frames.pop() || ''
    for (const frame of frames) {
      let event = 'message'
      let data = ''
      for (const line of frame.split('\n')) {
        if (line.startsWith('event: ')) event = line.slice(7).trim()
        else if (line.startsWith('data: ')) data += line.slice(6)
      }
      if (data) {
        try {
          onEvent(event, JSON.parse(data))
        } catch {
          onEvent(event, { raw: data })
        }
      }
    }
  }
}

export const abortChat = (runId: string) =>
  request.post<{ ok: boolean }>(`${BASE}/chat/abort`, { run_id: runId })

// --- HITL 审批（只读列表，spec 步骤三 4.4） ---

export interface HitlPause {
  id: number
  execution_id: string
  reply_id?: string | null
  tool_calls?: any[] | null
  suggested_rules?: any[] | null
  status: string // waiting/approved/rejected/interrupted
  accept_rules?: number
  timeout_at?: string | null
  answered_at?: string | null
  created_at?: string | null
  tenant_id?: number | null
}

export const listHitlPauses = (params: {
  status?: string
  execution_id?: string
  tenant_id?: number
  page?: number
  pageSize?: number
}) =>
  request.get<{ data: HitlPause[]; total: number; page: number; pageSize: number }>(
    '/api/v1/agent-hitl/pauses',
    { params }
  )


// ============ SSE 订阅（EventSource） ============

/**
 * 订阅引擎事件流 /super-agent/events（ticket_created / effect_* / ticket_completed）。
 * 返回 EventSource 实例（调用方 onUnmounted 时 close）。
 */
export function openEventsSSE(workspaceId: number, handlers: Record<string, (data: any) => void>): EventSource {
  const es = new EventSource(`${getApiBase()}${BASE}/events?workspace_id=${workspaceId}`)
  for (const [event, handler] of Object.entries(handlers)) {
    es.addEventListener(event, (e: MessageEvent) => {
      try {
        handler(JSON.parse(e.data))
      } catch {
        /* 忽略非 JSON 心跳帧 */
      }
    })
  }
  return es
}

/**
 * 订阅工作台 Feed 流 /super-agent/feed/stream（feed_post / proposal_created / goal_updated）。
 * 注：EventSource 仅支持 GET，历史由 REST listFeed 补齐。
 */
export function openFeedSSE(workspaceId: number, handlers: Record<string, (data: any) => void>): EventSource {
  const es = new EventSource(`${getApiBase()}${BASE}/feed/stream?workspace_id=${workspaceId}`)
  for (const [event, handler] of Object.entries(handlers)) {
    es.addEventListener(event, (e: MessageEvent) => {
      try {
        handler(JSON.parse(e.data))
      } catch {
        /* 忽略非 JSON 心跳帧 */
      }
    })
  }
  return es
}
