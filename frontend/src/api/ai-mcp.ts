/**
 * MCP 服务管理 API
 *
 * 命名约定：本文件所有接口字段与服务端保持一致（snake_case），
 * 后端 Pydantic schema 不做驼峰转换，axios 拦截器也不做字段重命名。
 * 如需驼峰字段，请在调用侧手动映射。
 */
import request from '@/utils/request'

// ========== Types ==========

export interface McpApiKey {
  id: number
  name: string
  service_type: string
  platform?: string | null
  protocol_type?: string | null
  version?: string | null
  description?: string | null
  service_url?: string | null
  service_name?: string | null
  api_key?: string | null
  namespace?: string | null
  group_key?: string | null
  access_path?: string | null
  properties?: Record<string, any> | null
  capabilities?: string[] | null
  remark?: string | null
  status: number
  sort: number
  template_id: number
  health_status: string
  last_check_at?: string | null
  creator?: string | null
  updater?: string | null
  created_at?: string
  updated_at?: string
}

export interface McpClient {
  id: number
  name: string
  api_key_id: number
  client_type: string
  mcp_type: string
  version?: string | null
  description?: string | null
  tools_config?: Record<string, any> | null
  remark?: string | null
  status: number
  creator?: string | null
  created_at?: string
}

export interface McpSquareTemplate {
  id: number
  name: string
  icon?: string | null
  category?: string | null
  platform?: string | null
  description?: string | null
  service_type: string
  service_url?: string | null
  access_path?: string | null
  version?: string | null
  capabilities?: string[] | null
  default_client_config?: Record<string, any> | null
  sort: number
  status?: number
  is_installed: boolean
  created_at?: string
  updated_at?: string
}

export interface PageResp<T> {
  data: T[]
  total: number
  page: number
  pageSize: number
}

// ========== API Key ==========

export function getMcpApiKeyPage(params: {
  name?: string
  service_type?: string
  status?: number
  page?: number
  pageSize?: number
}) {
  return request.get<PageResp<McpApiKey>>('/api/v1/admin/ai/mcp-api-key/page', { params })
}

export function getMcpApiKeyDetail(id: number) {
  return request.get<McpApiKey>('/api/v1/admin/ai/mcp-api-key/get', { params: { id } })
}

export function createMcpApiKey(data: Partial<McpApiKey>) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/mcp-api-key/create', data)
}

export function updateMcpApiKey(data: Partial<McpApiKey> & { id: number }) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/mcp-api-key/update', data)
}

export function deleteMcpApiKey(id: number) {
  return request.delete<{ message: string }>('/api/v1/admin/ai/mcp-api-key/delete', { params: { id } })
}

export function getMcpApiKeySimpleList() {
  return request.get<{ id: number; name: string; service_type: string }[]>(
    '/api/v1/admin/ai/mcp-api-key/simple-list'
  )
}

export interface McpServerSelectOption {
  value: number | string
  label: string
  service_type: string
  source: 'installed' | 'builtin'
  template_id: number
  /** 兼容回填逻辑补充的字段（实际列表中会以 label 填充） */
  name?: string
  description?: string
}

export function getMcpServerSelect() {
  return request.get<McpServerSelectOption[]>(
    '/api/v1/admin/ai/mcp-api-key/simple-select'
  )
}

// ========== Client ==========

export function getMcpClientPage(params: {
  api_key_id: number
  page?: number
  pageSize?: number
}) {
  return request.get<PageResp<McpClient>>('/api/v1/admin/ai/mcp-client/page', { params })
}

export function getMcpClientDetail(id: number) {
  return request.get<McpClient>('/api/v1/admin/ai/mcp-client/get', { params: { id } })
}

export function createMcpClient(data: Partial<McpClient>) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/mcp-client/create', data)
}

export function updateMcpClient(data: Partial<McpClient> & { id: number }) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/mcp-client/update', data)
}

export function deleteMcpClient(id: number) {
  return request.delete<{ message: string }>('/api/v1/admin/ai/mcp-client/delete', { params: { id } })
}

// ========== Square ==========

export function getMcpSquarePage(params: {
  name?: string
  category?: string
  status?: number
  page?: number
  pageSize?: number
}) {
  return request.get<PageResp<McpSquareTemplate>>('/api/v1/admin/ai/mcp-square/page', { params })
}

export function getMcpSquareDetail(id: number) {
  return request.get<McpSquareTemplate>('/api/v1/admin/ai/mcp-square/get', { params: { id } })
}

export function createMcpSquare(data: Partial<McpSquareTemplate>) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/mcp-square/create', data)
}

export function updateMcpSquare(data: Partial<McpSquareTemplate> & { id: number }) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/mcp-square/update', data)
}

export function deleteMcpSquare(id: number, force = false) {
  return request.delete<{ message: string }>('/api/v1/admin/ai/mcp-square/delete', {
    params: { id, force },
  })
}

export interface McpSquareInstallData {
  template_id: number
  name?: string
  service_url?: string
  api_key?: string
  access_path?: string
  service_name?: string
  namespace?: string
  group_key?: string
}

export function installMcpSquare(data: McpSquareInstallData) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/mcp-square/install', data)
}

export function testMcpConnection(id: number) {
  return request.post<{ id: number; health_status: string; detail: string; checked_at: string }>(
    `/api/v1/admin/ai/mcp-square/test/${id}`
  )
}

export function uninstallMcpSquare(apiKeyId: number) {
  return request.delete<{ message: string }>('/api/v1/admin/ai/mcp-square/uninstall', {
    params: { apiKeyId },
  })
}

// ========== MCP 已注册工具 ==========

export interface McpRegisteredTool {
  name: string
  description: string
  category: string
  input_schema: Record<string, any>
}

export function getMcpToolsList(params: {
  name?: string
  category?: string
  page?: number
  pageSize?: number
}) {
  return request.get<PageResp<McpRegisteredTool>>('/api/v1/admin/ai/mcp-tools/list', { params })
}
