/**
 * 统一 Agent 工作台 API 调用
 */
import { getToken } from '@/utils/auth'

const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const BASE_URL = `${baseUrl}/api/v1/ai-agent`

// ── 类型定义 ──────────────────────────────────────

export type AgentMode = 'dify_chatflow' | 'skill' | 'agent' | 'team' | 'thinking' | 'deep_research' | 'scheduled'

export interface ExecuteRequest {
  mode: AgentMode
  user_input: string
  session_id?: number
  conversation_id?: string
  agent_ids?: string[]
  skill_code?: string
  flow_code?: string
  workspace_id?: number
  context?: Record<string, any>
  config?: Record<string, any>
  model_id?: number  // 用户指定的 AI 模型 ID
}

export interface AgentResponse {
  execution_id: string
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed'
  mode: AgentMode
  output: string
  error?: string
  latency_ms: number
  metadata: Record<string, any>
}

export interface SessionInfo {
  session_id: number
  title: string
  type: string
  message_count: number
}

export interface MessageInfo {
  id: number
  role: string
  content: string
  created_at?: string
}

export interface ExecutionInfo {
  execution_id: string
  session_id?: number
  mode: string
  engine_code?: string
  status: string
  output?: string
  error?: string
  latency_ms?: number
  started_at?: string
  completed_at?: string
}

// ── 执行 API ──────────────────────────────────────

export async function executeAgent(data: ExecuteRequest): Promise<AgentResponse> {
  const token = getToken()
  const res = await fetch(`${BASE_URL}/execute`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  return res.json()
}

/**
 * SSE 流式执行（推荐方式，使用 fetch + reader）
 */
export async function executeAgentSSE(
  data: ExecuteRequest,
  onEvent: (event: { type: string; [key: string]: any }) => void,
  onError?: (error: Error) => void,
): Promise<void> {
  const token = getToken()

  try {
    const response = await fetch(`${BASE_URL}/execute/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('No response body')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6))
            onEvent(event)
          } catch {
            // 忽略解析失败
          }
        }
      }
    }
  } catch (err) {
    onError?.(err as Error)
  }
}

// ── 执行状态 API ──────────────────────────────────

export async function getExecution(executionId: string): Promise<ExecutionInfo> {
  const token = getToken()
  const res = await fetch(`${BASE_URL}/executions/${executionId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getExecutionTrace(executionId: string): Promise<any> {
  const token = getToken()
  const res = await fetch(`${BASE_URL}/executions/${executionId}/trace`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ── 会话 API ──────────────────────────────────────

export async function listSessions(userId: number, sessionType?: string): Promise<{ sessions: SessionInfo[] }> {
  const token = getToken()
  const query = sessionType ? `?user_id=${userId}&session_type=${sessionType}` : `?user_id=${userId}`
  const res = await fetch(`${BASE_URL}/sessions${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function createSession(userId: number, title?: string, sessionType = 'agent'): Promise<{ session_id: number }> {
  const token = getToken()
  const res = await fetch(`${BASE_URL}/sessions?user_id=${userId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ title, session_type: sessionType }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getMessages(sessionId: number, limit = 50): Promise<{ messages: MessageInfo[] }> {
  const token = getToken()
  const res = await fetch(`${BASE_URL}/sessions/${sessionId}/messages?limit=${limit}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ── 深度研究后台异步提交 ───────────────────────────
export interface DeepResearchSubmitResp {
  task_id: number
  task_no?: string
  status: string
  target_mode: string
  poll_url: string
  message: string
}

/**
 * 提交深度研究后台任务。立即返回 task_id，前端轮询任务状态并实时查看研究进度。
 */
export async function submitDeepResearch(
  topic: string,
  opts?: { session_id?: number; context?: Record<string, any>; config?: Record<string, any>; model_id?: number | null },
): Promise<DeepResearchSubmitResp> {
  const token = getToken()
  const res = await fetch(`${BASE_URL}/deep-research/submit`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      topic,
      session_id: opts?.session_id,
      context: opts?.context || {},
      config: opts?.config || {},
      model_id: opts?.model_id ?? null,
    }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  return res.json()
}

export async function deleteSession(sessionId: number): Promise<void> {
  const token = getToken()
  const res = await fetch(`${BASE_URL}/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}
