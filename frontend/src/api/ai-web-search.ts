/**
 * AI 联网搜索供应商 API
 */
import request from '@/utils/request'

// 搜索平台列表
export const WEB_SEARCH_PLATFORMS = ['bocha', 'anspire', 'google', 'bing', 'custom'] as const
export type WebSearchPlatform = typeof WEB_SEARCH_PLATFORMS[number]

// 平台显示名映射
export const PLATFORM_LABELS: Record<string, string> = {
  bocha: '博查',
  anspire: 'Anspire',
  google: 'Google',
  bing: 'Bing',
  custom: '自定义',
}

// ========== 类型定义 ==========

export interface AiWebSearch {
  id: number
  name: string
  api_key: string
  platform: string
  url: string
  app_id: string
  property: Record<string, any>
  // 扩展配置字段
  timeout: number
  max_results: number
  daily_quota: number
  used_count: number
  priority: number
  status: number
  sort: number
  created_at: string
  updated_at: string | null
  creator: string | null
  updater: string | null
}

export interface WebSearchQuotaItem {
  id: number
  name: string
  platform: string
  daily_quota: number
  used_count: number
  remaining: number
  usage_percent: number
}

export interface WebSearchHealthItem {
  id: number
  name: string
  platform: string
  status: 'normal' | 'warning' | 'error'
  message: string
  response_time: number
}

export interface WebSearchLogItem {
  id: number
  web_search_id: number
  service_name: string
  platform: string
  query: string
  response_time: number
  results_count: number
  success: boolean
  error: string
  created_at: string | null
}

export interface WebSearchPageResp {
  data: AiWebSearch[]
  total: number
  page: number
  pageSize: number
}

export interface SearchTestResult {
  results: Array<{
    title: string
    url: string
    snippet: string
    score: number
  }>
  total: number
  raw: Record<string, any>
}

// ========== 接口 ==========

/**
 * 分页获取搜索供应商列表
 */
export function getWebSearchPage(params: {
  name?: string
  platform?: string
  status?: number
  page?: number
  pageSize?: number
}) {
  return request.get<WebSearchPageResp>('/api/v1/admin/ai/web-search/page', { params })
}

/**
 * 简易列表（下拉选择用）
 */
export function getWebSearchSimpleList() {
  return request.get<Array<{ id: number; name: string; platform: string }>>(
    '/api/v1/admin/ai/web-search/simple-list'
  )
}

/**
 * 获取搜索供应商详情
 */
export function getWebSearch(id: number) {
  return request.get<AiWebSearch>(`/api/v1/admin/ai/web-search/${id}`)
}

/**
 * 创建搜索供应商
 */
export function createWebSearch(data: Partial<AiWebSearch>) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/web-search/create', data)
}

/**
 * 更新搜索供应商
 */
export function updateWebSearch(data: Partial<AiWebSearch> & { id: number }) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/web-search/update', data)
}

/**
 * 删除搜索供应商
 */
export function deleteWebSearch(id: number) {
  return request.delete<{ message: string }>('/api/v1/admin/ai/web-search/delete', { params: { id } })
}

/**
 * 测试搜索
 */
export function testWebSearch(data: { id: number; query: string }) {
  return request.post<SearchTestResult>('/api/v1/admin/ai/web-search/test', data)
}

/**
 * 配额与用量统计
 */
export function getWebSearchQuota() {
  return request.get<WebSearchQuotaItem[]>('/api/v1/admin/ai/web-search/quota')
}

/**
 * 健康检查
 */
export function getWebSearchHealth() {
  return request.get<WebSearchHealthItem[]>('/api/v1/admin/ai/web-search/health')
}

/**
 * 搜索调用日志
 */
export function getWebSearchLogs(params: { web_search_id?: number; page?: number; pageSize?: number }) {
  return request.get<{ data: WebSearchLogItem[]; total: number }>('/api/v1/admin/ai/web-search/logs', { params })
}
