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

// ── 实体批量查询（AI 输出后处理 Hover 弹窗） ────────────────────────────────

export interface EntityLookupResult {
  entities: Array<{
    entity_id: number
    entity_name: string
    entity_type: string
    legal_person: string
    registered_capital: number | null
    industry: string
    risk_level: string
    risk_score: number
    registered_address: string
    business_scope: string
    unified_social_credit_code?: string
  }>
  persons: Array<{
    person_id: number
    real_name: string
    gender: string
    age: number | null
    person_type: string
    risk_level: string
    risk_score: number
    current_region_name: string
    occupation: string
    tags: string
    is_key_person: boolean
    id_card?: string
  }>
  locations: Array<{
    location_id: number
    location_name: string
    location_type: string
    region_name: string
    address: string
    risk_level: string
    risk_score: number
    description: string
  }>
}

/** 批量查询企业/人员/地点实体详情 */
export function lookupEntities(names: string[]) {
  return request.post<EntityLookupResult>(`${BASE}/ai-assistant/entities/lookup`, { names })
}

/** 通过身份证号查找风险人员 */
export function getPersonByIdCard(idCard: string) {
  return request.get<EntityLookupResult['persons'][0] | null>(`${BASE}/ai-assistant/person-by-id-card`, { params: { id_card: idCard } })
}

/** 通过姓名查找风险人员 */
export function getPersonByName(name: string) {
  return request.get<EntityLookupResult['persons'][0] | null>(`${BASE}/ai-assistant/person-by-name`, { params: { name } })
}

/** 通过统一社会信用代码查找风险企业 */
export function getEntityByCreditCode(creditCode: string) {
  return request.get<EntityLookupResult['entities'][0] | null>(`${BASE}/ai-assistant/entity-by-credit-code`, { params: { credit_code: creditCode } })
}

/** 通过企业名称查找风险企业 */
export function getEntityByName(name: string) {
  return request.get<EntityLookupResult['entities'][0] | null>(`${BASE}/ai-assistant/entity-by-name`, { params: { name } })
}

/** 通过法律名称查找法律基本信息 */
export function getLegalByTitle(title: string) {
  return request.get<{
    id: number
    law_title: string
    release_org?: string
    release_date?: string
    implement_date?: string
    disable_date?: string
    keywords?: string
    legal_level?: number
    timelines?: number
  } | null>(`${BASE}/ai-assistant/legal-by-title`, { params: { title } })
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
