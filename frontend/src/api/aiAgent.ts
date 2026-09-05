/**
 * AI Agent 统一聊天 API
 *
 * 替代原 /ai-assistant/chat，统一走 Gateway 体系。
 * 会话管理（CRUD）仍复用 aiSession.ts 中的 /ai-assistant/sessions 接口。
 */
import { getToken } from '@/utils/auth'

const BASE_URL = '/api/v1'

export interface UnifiedChatRequest {
  message: string
  session_id?: number | null
  session_type?: string
  dify_conversation_id?: string | null
  file_ids?: string[]
  file_db_ids?: number[]
  skill?: {
    package_id: string
    package_name?: string
    script_id: string
    script_name?: string
    params?: Record<string, any>
  } | null
  sqlbot_chat_id?: number | null
  sqlbot_datasource_id?: number | null
  model_id?: number | null
  workspace_id?: number | null
}

/** 异步任务信息（SCHEDULED 模式） */
export interface AsyncTaskInfoDTO {
  id: number
  taskNo?: string
  taskName?: string
  targetMode?: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  priority?: number
  errorMessage?: string
  /** 网关执行 ID（后端启动即写入，运行中即可实时回放执行事件） */
  executionId?: string | null
  resultData?: any
  submittedAt?: string
  startedAt?: string
  finishedAt?: string
}

/** 查询单个异步任务状态 */
export async function getAsyncTask(taskId: number, token?: string): Promise<AsyncTaskInfoDTO> {
  const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const authToken = token || getToken() || ''
  const res = await fetch(`${baseURL}${BASE_URL}/ai-agent/async-tasks/${taskId}`, {
    headers: { Authorization: authToken ? `Bearer ${authToken}` : '' },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

/** 异步任务列表 */
export async function listAsyncTasks(params: { status?: string; targetMode?: string; page?: number; size?: number }, token?: string): Promise<{ total: number; items: AsyncTaskInfoDTO[] }> {
  const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const authToken = token || getToken() || ''
  const qs = new URLSearchParams()
  if (params.status) qs.set('status', params.status)
  if (params.targetMode) qs.set('target_mode', params.targetMode)
  if (params.page) qs.set('page', String(params.page))
  if (params.size) qs.set('size', String(params.size))
  const res = await fetch(`${baseURL}${BASE_URL}/ai-agent/async-tasks?${qs.toString()}`, {
    headers: { Authorization: authToken ? `Bearer ${authToken}` : '' },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

/** 手动重试失败/已取消的异步任务（复用原参数重新投递执行） */
export async function retryAsyncTask(taskId: number, token?: string): Promise<AsyncTaskInfoDTO> {
  const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const authToken = token || getToken() || ''
  const res = await fetch(`${baseURL}${BASE_URL}/ai-agent/async-tasks/${taskId}/retry`, {
    method: 'POST',
    headers: { Authorization: authToken ? `Bearer ${authToken}` : '' },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

/** 取消异步任务 */
export async function cancelAsyncTask(taskId: number, token?: string): Promise<any> {
  const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const authToken = token || getToken() || ''
  const res = await fetch(`${baseURL}${BASE_URL}/ai-agent/async-tasks/${taskId}/cancel`, {
    method: 'POST',
    headers: { Authorization: authToken ? `Bearer ${authToken}` : '' },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

/**
 * 统一聊天流式请求（SSE）
 *
 * 返回原始 fetch Response，调用方通过 reader 逐行解析 SSE 事件。
 */
export async function chatStream(
  data: UnifiedChatRequest,
  token?: string,
): Promise<Response> {
  const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const authToken = token || getToken() || ''

  return fetch(`${baseURL}${BASE_URL}/ai-agent/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': authToken ? `Bearer ${authToken}` : '',
    },
    body: JSON.stringify(data),
  })
}

// ── AI 任务定时调度（深度研究 / Agent / AgentTeam 周期自动执行） ──────────

/** skill 模式技能信息（与后端 skill_info JSON 约定一致） */
export interface ScheduledSkillInfo {
  package_id: string
  package_name?: string
  script_id?: string
  script_name?: string
  params?: Record<string, any>
}

export interface AgentScheduledTaskDTO {
  id: number
  taskName: string
  description?: string
  targetMode: 'deep_research' | 'agent' | 'team' | 'skill'
  agentId?: number | null
  teamId?: number | null
  skillInfo?: ScheduledSkillInfo | null
  prompt: string
  sessionId?: string | null
  modelId?: number | null
  scheduleType: 'cron' | 'interval' | 'once'
  cronExpression?: string | null
  intervalSeconds?: number | null
  runAt?: string | null
  timezone?: string
  status: 'enabled' | 'paused' | 'deleted'
  lastRunAt?: string | null
  nextRunAt?: string | null
  lastTaskId?: number | null
  runCount: number
  failCount: number
  createdAt?: string
  updatedAt?: string
}

/** 调度任务保存 payload（字段与后端 pydantic snake_case 一致） */
export interface ScheduledTaskSavePayload {
  task_name: string
  description?: string | null
  target_mode: string
  agent_id?: number | null
  team_id?: number | null
  skill_info?: ScheduledSkillInfo | null
  prompt: string
  session_id?: string | null
  model_id?: number | null
  schedule_type: string
  cron_expression?: string | null
  interval_seconds?: number | null
  run_at?: string | null
}

async function _schedRequest(path: string, init?: RequestInit, token?: string): Promise<any> {
  const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const authToken = token || getToken() || ''
  const res = await fetch(`${baseURL}${BASE_URL}/ai-agent/agent-scheduled-tasks${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
      Authorization: authToken ? `Bearer ${authToken}` : '',
    },
  })
  if (!res.ok) {
    // 后端 400 detail 优先透出（如 cron 表达式非法）
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      if (body?.detail) detail = String(body.detail)
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json()
}

/** 调度任务列表 */
export function listScheduledTasks(params: { status?: string; page?: number; size?: number }, token?: string): Promise<{ total: number; items: AgentScheduledTaskDTO[] }> {
  const qs = new URLSearchParams()
  if (params.status) qs.set('status', params.status)
  if (params.page) qs.set('page', String(params.page))
  if (params.size) qs.set('size', String(params.size))
  const q = qs.toString()
  return _schedRequest(q ? `?${q}` : '', undefined, token)
}

/** 调度任务详情 */
export function getScheduledTask(id: number, token?: string): Promise<AgentScheduledTaskDTO> {
  return _schedRequest(`/${id}`, undefined, token)
}

/** 创建调度任务 */
export function createScheduledTask(data: ScheduledTaskSavePayload, token?: string): Promise<AgentScheduledTaskDTO> {
  return _schedRequest('', { method: 'POST', body: JSON.stringify(data) }, token)
}

/** 更新调度任务（重注册） */
export function updateScheduledTask(id: number, data: Partial<ScheduledTaskSavePayload>, token?: string): Promise<AgentScheduledTaskDTO> {
  return _schedRequest(`/${id}`, { method: 'PUT', body: JSON.stringify(data) }, token)
}

/** 暂停调度 */
export function pauseScheduledTask(id: number, token?: string): Promise<AgentScheduledTaskDTO> {
  return _schedRequest(`/${id}/pause`, { method: 'POST' }, token)
}

/** 恢复调度 */
export function resumeScheduledTask(id: number, token?: string): Promise<AgentScheduledTaskDTO> {
  return _schedRequest(`/${id}/resume`, { method: 'POST' }, token)
}

/** 立即执行一次（不改变调度计划） */
export function runScheduledTaskNow(id: number, token?: string): Promise<{ scheduledId: number; asyncTaskId: number; message: string }> {
  return _schedRequest(`/${id}/run-now`, { method: 'POST' }, token)
}

/** 删除调度任务（软删） */
export function deleteScheduledTask(id: number, token?: string): Promise<{ id: number; status: string; message: string }> {
  return _schedRequest(`/${id}`, { method: 'DELETE' }, token)
}
