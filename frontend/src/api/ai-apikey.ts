/**
 * AI API Key Management API
 */
import request from '@/utils/request'

// 平台类型
export const AI_PLATFORMS = [
  'OpenAI',
  '通义千问',
  '智谱',
  '讯飞',
  '百度',
  'Claude',
  'Gemini',
  'Dify',
  'Coze',
  '其他'
] as const
export type AiPlatform = typeof AI_PLATFORMS[number]

export interface AiApiKey {
  id: number
  name: string
  api_key: string
  platform: string
  url?: string
  app_id?: string
  property?: Record<string, any>
  status: number
  sort: number
  created_at?: string
  updated_at?: string
  creator?: string
  updater?: string
}

export interface AiChatModel {
  id: number
  code?: string
  key_id: number
  name: string
  model: string
  platform?: string
  sort: number
  status: number
  type?: number
  temperature?: number
  max_tokens?: number
  top_k?: number
  top_p?: number
  seed?: number
  max_contexts?: number
  max_turns?: number
  dimensions?: number
  retry?: number
  timeout?: number
  stream_timeout?: number
  enable_thinking?: boolean
  enable_search?: boolean
  is_default?: boolean
  created_at?: string
  updated_at?: string
}

export interface ApiKeyPageResp {
  data: AiApiKey[]
  total: number
  page: number
  pageSize: number
}

export interface ChatModelPageResp {
  data: AiChatModel[]
  total: number
  page: number
  pageSize: number
}

// ========== API Key CRUD ==========

/**
 * 分页获取 API Key 列表
 */
export function getApiKeyPage(params: {
  name?: string
  platform?: string
  status?: number
  page?: number
  pageSize?: number
}) {
  return request.get<ApiKeyPageResp>('/api/v1/admin/ai/api-key/page', { params })
}

/**
 * 获取 API Key 简易列表（用于下拉选择）
 */
export function getApiKeySimpleList(params?: { platform?: string }) {
  return request.get<Array<{ id: number; name: string; platform: string }>>('/api/v1/admin/ai/api-key/simple-list', { params })
}

/**
 * 获取 API Key 详情
 */
export function getApiKeyDetail(id: number) {
  return request.get<AiApiKey>(`/api/v1/admin/ai/api-key/${id}`)
}

/**
 * 创建 API Key
 */
export function createApiKey(data: Partial<AiApiKey>) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/api-key/create', data)
}

/**
 * 更新 API Key
 */
export function updateApiKey(data: Partial<AiApiKey> & { id: number }) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/api-key/update', data)
}

/**
 * 删除 API Key
 */
export function deleteApiKey(id: number) {
  return request.delete<{ message: string }>('/api/v1/admin/ai/api-key/delete', { params: { id } })
}

// ========== ChatModel CRUD ==========

/**
 * 分页获取关联的 ChatModel 列表
 */
export function getChatModelPage(params: {
  keyId: number
  name?: string
  page?: number
  pageSize?: number
}) {
  return request.get<ChatModelPageResp>('/api/v1/admin/ai/api-key/chat-model/page', { params })
}

/**
 * 获取 ChatModel 详情
 */
export function getChatModelDetail(id: number) {
  return request.get<AiChatModel>(`/api/v1/admin/ai/api-key/chat-model/${id}`)
}

/**
 * 创建 ChatModel
 */
export function createChatModel(data: Partial<AiChatModel>) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/api-key/chat-model/create', data)
}

/**
 * 更新 ChatModel
 */
export function updateChatModel(data: Partial<AiChatModel> & { id: number }) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/api-key/chat-model/update', data)
}

/**
 * 删除 ChatModel
 */
export function deleteChatModel(id: number) {
  return request.delete<{ message: string }>('/api/v1/admin/ai/api-key/chat-model/delete', { params: { id } })
}

/**
 * 设置 ChatModel 为默认模型（含连通性检测）
 */
export function setChatModelDefault(modelId: number) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/api-key/chat-model/set-default', { model_id: modelId })
}

/**
 * 获取所有可用的聊天模型（用于前端下拉选择）
 */
export interface AvailableModel {
  id: number
  name: string
  model: string
  platform: string
  key_name: string
  type?: number | null
}

export function getAvailableModels() {
  return request.get<AvailableModel[]>('/api/v1/admin/ai/api-key/chat-model/available')
}

// ========== 模型测试 ==========

export interface ModelTestPayload {
  model_id: number
  prompt: string
  system_prompt?: string
  stream?: boolean
}

/**
 * 使用 fetch 发起流式测试请求，返回 Response（调用方自行处理 SSE）
 */
export async function fetchModelTestStream(
  payload: ModelTestPayload,
  signal?: AbortSignal
): Promise<Response> {
  const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const token = localStorage.getItem('token') || ''
  const res = await fetch(`${base}/api/v1/admin/ai/api-key/chat-model/test`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ ...payload, stream: true }),
    signal,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res
}
