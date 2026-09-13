/**
 * AI会话管理 API（管理端 + 用户端）
 */
import request from '@/utils/request'

const BASE = '/api/v1'

// ── 类型定义 ─────────────────────────────────────────────────────────────────

export interface AiChatSession {
  session_id: number
  user_id: number
  session_title: string
  session_type: string
  status: string
  message_count: number
  is_pinned: boolean
  created_at: string
  updated_at: string
}

export interface AiChatMessage {
  message_id: number
  session_id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  message_type: string
  extra_data?: Record<string, any>
  created_at: string
}

export interface PageResult<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}

// ── 用户端接口 ───────────────────────────────────────────────────────────────

/** 我的会话列表 */
export function getMySessions(params?: { page?: number; page_size?: number; status?: string }) {
  return request.get<PageResult<AiChatSession>>(`${BASE}/ai-assistant/sessions`, { params })
}

/** 新建会话 */
export function createSession(data?: { session_title?: string; session_type?: string }) {
  return request.post<AiChatSession>(`${BASE}/ai-assistant/sessions`, data)
}

/** 获取会话详情 */
export function getSession(sessionId: number) {
  return request.get<AiChatSession>(`${BASE}/ai-assistant/sessions/${sessionId}`)
}

/** 修改会话标题 */
export function updateSession(sessionId: number, session_title: string) {
  return request.put<AiChatSession>(`${BASE}/ai-assistant/sessions/${sessionId}`, { session_title })
}

/** 删除会话 */
export function deleteSession(sessionId: number) {
  return request.delete(`${BASE}/ai-assistant/sessions/${sessionId}`)
}

/** 置顶 / 取消置顶 */
export function pinSession(sessionId: number, is_pinned: boolean) {
  return request.post(`${BASE}/ai-assistant/sessions/${sessionId}/pin`, { is_pinned })
}

/** 批量删除我的会话 */
export function batchDeleteMySessions(ids: number[]) {
  return request.post(`${BASE}/ai-assistant/sessions/batch-delete`, { ids })
}

/** 获取会话消息列表 */
export function getSessionMessages(sessionId: number, params?: { page?: number; page_size?: number }) {
  return request.get<PageResult<AiChatMessage>>(
    `${BASE}/ai-assistant/sessions/${sessionId}/messages`,
    { params }
  )
}

/** 清空会话消息 */
export function clearSessionMessages(sessionId: number) {
  return request.delete(`${BASE}/ai-assistant/sessions/${sessionId}/messages`)
}

/** 保存一条消息（深度研究后台异步任务卡片等场景） */
export function addSessionMessage(
  sessionId: number,
  data: {
    role: 'user' | 'assistant' | 'system'
    content: string
    message_type?: string
    extra_data?: Record<string, unknown>
  }
) {
  return request.post<AiChatMessage>(`${BASE}/admin/ai-sessions/${sessionId}/messages`, data)
}

// ── 管理端接口 ───────────────────────────────────────────────────────────────

/** 管理端：所有用户会话列表 */
export function adminGetAllSessions(params?: {
  page?: number
  page_size?: number
  user_id?: number
  status?: string
}) {
  return request.get<PageResult<AiChatSession>>(`${BASE}/admin/ai-sessions`, { params })
}

/** 管理端：获取会话详情 */
export function adminGetSession(sessionId: number) {
  return request.get<AiChatSession>(`${BASE}/admin/ai-sessions/${sessionId}`)
}

/** 管理端：删除会话 */
export function adminDeleteSession(sessionId: number) {
  return request.delete(`${BASE}/admin/ai-sessions/${sessionId}`)
}

/** 管理端：批量删除会话 */
export function adminBatchDeleteSessions(ids: number[]) {
  return request.post(`${BASE}/admin/ai-sessions/batch-delete`, { ids })
}

/** 管理端：获取会话消息列表 */
export function adminGetSessionMessages(sessionId: number, params?: { page?: number; page_size?: number }) {
  return request.get<PageResult<AiChatMessage>>(
    `${BASE}/admin/ai-sessions/${sessionId}/messages`,
    { params }
  )
}

/** 管理端：清空会话消息 */
export function adminClearSessionMessages(sessionId: number) {
  return request.delete(`${BASE}/admin/ai-sessions/${sessionId}/messages`)
}

/** 管理端：批量删除消息 */
export function adminBatchDeleteMessages(ids: number[]) {
  return request.post(`${BASE}/admin/ai-messages/batch-delete`, { ids })
}

// ── SQLBot 数据源 ────────────────────────────────────────────────────────────

export interface SqlbotDatasource {
  id: number
  name: string
  db_type: string
}

/** 获取 SQLBot 可用数据源列表（后端缓存 10 分钟） */
export function getSqlbotDatasources(refresh = false) {
  return request.get<{ datasources: SqlbotDatasource[] }>(
    `${BASE}/ai-assistant/chat/sqlbot/datasources`,
    { params: { refresh } }
  )
}

// ── 示例提问推荐（自动请求 + 关键词匹配检索）──────────────────────────────────

export interface ExampleQuestionRecommendResult {
  questions: string[]
  matched: boolean
  source_keywords: string[]
}

/**
 * 根据会话关键词向服务端发起匹配检索，返回最相关的示例提问。
 * 关键词来源于「当前已打开会话」的内容，由前端提取后传入。
 */
export function recommendExampleQuestions(params: {
  keywords: string[]
  session_type?: string
  limit?: number
}) {
  return request.post<ExampleQuestionRecommendResult>(
    `${BASE}/ai-assistant/example-questions/recommend`,
    params
  )
}
