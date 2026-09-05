/**
 * AI 工具管理 API
 */
import request from '@/utils/request'

// 工具类型
export const TOOL_TYPES = [
  { value: 'custom', label: '自定义' },
  { value: 'skill', label: '技能' },
  { value: 'mcp', label: 'MCP' },
  { value: 'group', label: '分组' },
  { value: 'sqlbot', label: 'SQLBot' },
  { value: 'agentscope_builtin', label: 'AgentScope内置' },
  { value: 'custom_dev', label: '自定义开发' }
] as const

// 默认分类（与后端 /categories 兜底一致）
export const DEFAULT_CATEGORIES = [
  '信息查询', '数据处理', 'AI增强',
  // AgentScope 内置工具分类
  '文件系统', '任务管理', 'Shell执行',
  // 项目自定义开发工具分类
  '文档处理', '自动化', '消息通知', '数据分析',
] as const

export interface AiTool {
  id: number
  toolKey: string
  displayName: string
  category?: string | null
  type: string
  className?: string | null
  methodName?: string | null
  description?: string | null
  configSchema?: Record<string, any> | null
  configValue?: Record<string, any> | null
  inputSchema?: Record<string, any> | null
  outputSchema?: Record<string, any> | null
  status: string
  isSystem: boolean
  sort: number
  creator?: string | null
  updater?: string | null
  createdAt?: string
  updatedAt?: string
}

export interface ToolPageResp {
  data: AiTool[]
  total: number
  page: number
  pageSize: number
}

export interface ToolSimpleItem {
  id: number
  toolKey: string
  displayName: string
  category?: string | null
}

export interface ToolGroup {
  id: number
  name: string
  displayName?: string | null
  description?: string | null
  instructions?: string | null
  isActive: boolean
  sort: number
  toolCount: number
  createdAt?: string
  updatedAt?: string
}

export interface ToolGroupPageResp {
  data: ToolGroup[]
  total: number
  page: number
  pageSize: number
}

// ========== 工具 CRUD ==========

export function getToolPage(params: {
  toolKey?: string
  displayName?: string
  category?: string
  type?: string
  status?: string
  isSystem?: boolean
  page?: number
  pageSize?: number
}) {
  return request.get<ToolPageResp>('/api/v1/admin/ai/tool/page', { params })
}

export function getToolDetail(id: number) {
  return request.get<AiTool>(`/api/v1/admin/ai/tool/get`, { params: { id } })
}

export function createTool(data: Partial<AiTool>) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/tool/create', data)
}

export function updateTool(data: Partial<AiTool> & { id: number }) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/tool/update', data)
}

export function deleteTool(id: number) {
  return request.delete<{ message: string }>('/api/v1/admin/ai/tool/delete', { params: { id } })
}

export function deleteToolList(ids: number[]) {
  return request.delete<{ message: string }>('/api/v1/admin/ai/tool/delete-list', {
    params: { ids: ids.join(',') }
  })
}

export function getToolSimpleList(params?: { category?: string }) {
  return request.get<ToolSimpleItem[]>('/api/v1/admin/ai/tool/simple-list', { params })
}

export function testTool(payload: {
  toolKey?: string
  id?: number
  inputs?: Record<string, any>
  className?: string
  methodName?: string
}) {
  return request.post<{
    success: boolean
    output: any
    error: string | null
    target: string
  }>('/api/v1/admin/ai/tool/test', payload)
}

export function refreshToolCache() {
  return request.post<{ message: string; count: number }>('/api/v1/admin/ai/tool/refresh-cache')
}

export function getToolCategories() {
  return request.get<string[]>('/api/v1/admin/ai/tool/categories')
}

// ========== 工具分组 ==========

export function getToolGroupPage(params: { name?: string; page?: number; pageSize?: number }) {
  return request.get<ToolGroupPageResp>('/api/v1/admin/ai/tool/group/page', { params })
}

export function createToolGroup(data: {
  name: string
  displayName?: string
  description?: string
  instructions?: string
  isActive?: boolean
  sort?: number
}) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/tool/group/create', data)
}

export function updateToolGroup(data: {
  id: number
  name: string
  displayName?: string
  description?: string
  instructions?: string
  isActive?: boolean
  sort?: number
}) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/tool/group/update', data)
}

export function deleteToolGroup(id: number) {
  return request.delete<{ message: string }>('/api/v1/admin/ai/tool/group/delete', { params: { id } })
}

export function addGroupMembers(groupId: number, toolKeys: string[]) {
  return request.post<{ message: string }>('/api/v1/admin/ai/tool/group/members/add', {
    toolKeys
  }, { params: { group_id: groupId } })
}

export function removeGroupMember(groupId: number, toolKey: string) {
  return request.post<{ message: string }>('/api/v1/admin/ai/tool/group/members/remove', null, {
    params: { group_id: groupId, toolKey }
  })
}

export function getGroupMembers(groupId: number) {
  return request.get<AiTool[]>('/api/v1/admin/ai/tool/group/members', { params: { group_id: groupId } })
}

// ========== 工具启用/禁用 ==========

export function enableTool(id: number) {
  return request.post<{ id: number; status: string; message: string }>(
    '/api/v1/admin/ai/tool/enable',
    null,
    { params: { id } }
  )
}

export function disableTool(id: number) {
  return request.post<{ id: number; status: string; message: string }>(
    '/api/v1/admin/ai/tool/disable',
    null,
    { params: { id } }
  )
}

// ========== SQLBot 数据源管理 ==========

export const SQLBOT_TOOL_TYPE = 'sqlbot'

export interface SqlBotDatasource {
  id: number
  name: string
  dbType: string
  database: string
  description: string
  tableCount: number
}

export interface SqlBotTableColumn {
  name: string
  type: string
  comment?: string
  nullable?: boolean
  isSensitive?: boolean
  suggestedMask?: string
}

export interface SqlBotTableInfo {
  id?: number
  datasourceId: number
  datasourceName?: string | null
  tableName: string
  tableComment?: string | null
  businessLine?: string | null
  columns?: SqlBotTableColumn[]
  source: string
  confirmed: boolean
  status: string
  syncedAt?: string | null
}

export interface DdlImportDetail {
  tableName: string
  columnCount: number
  sensitiveColumns: string[]
  created: number
  updated: number
}

export interface DdlImportResult {
  datasourceId: number
  imported: number
  skipped: number
  errors: string[]
  details: DdlImportDetail[]
}

export function getSqlBotDatasources() {
  return request.get<{ datasources: SqlBotDatasource[]; total: number }>(
    '/api/v1/admin/ai/sqlbot-tool/datasource/list'
  )
}

export function getSqlBotTables(datasourceId: number) {
  return request.get<SqlBotTableInfo[]>(`/api/v1/admin/ai/sqlbot-tool/tables`, {
    params: { datasourceId }
  })
}

export function importSqlBotDdl(payload: { datasourceId: number; datasourceName?: string; ddlText: string }) {
  return request.post<DdlImportResult>('/api/v1/admin/ai/sqlbot-tool/tables/import-ddl', payload)
}

export function updateSqlBotTableColumns(
  id: number,
  payload: {
    tableComment?: string
    businessLine?: string
    columns?: SqlBotTableColumn[]
    confirmed?: boolean
    status?: string
    sort?: number
  }
) {
  return request.post<SqlBotTableInfo>(
    `/api/v1/admin/ai/sqlbot-tool/tables/${id}/columns-update`,
    payload
  )
}

export function deleteSqlBotTable(id: number) {
  return request.delete<{ message: string }>(`/api/v1/admin/ai/sqlbot-tool/tables`, {
    params: { id }
  })
}

// ========== SQLBot 工具配置校验/试跑/发布 ==========

export interface ConfigValidateResp {
  valid: boolean
  errors: string[]
  warnings: string[]
  inputSchema?: Record<string, any>
  renderedQuestionPreview?: string
}

export function validateSqlBotConfig(configValue: Record<string, any>) {
  return request.post<ConfigValidateResp>('/api/v1/admin/ai/sqlbot-tool/config/validate', {
    configValue
  })
}

export function testSqlBotTool(payload: {
  toolKey?: string
  configValue?: Record<string, any>
  inputs?: Record<string, any>
}) {
  return request.post<{ success: boolean; output: any; warnings: string[]; target: string }>(
    '/api/v1/admin/ai/sqlbot-tool/test',
    payload
  )
}

export function publishSqlBotTool(data: {
  toolKey: string
  displayName: string
  category?: string
  description?: string
  configValue: Record<string, any>
  status?: string
  sort?: number
  groupName?: string
}) {
  return request.post<{ id: number; message: string }>('/api/v1/admin/ai/sqlbot-tool/publish', data)
}

export function getSqlBotConfigSchema() {
  return request.get<{
    configVersion: string
    classPath: string
    schema: Record<string, any>
  }>('/api/v1/admin/ai/sqlbot-tool/config-schema')
}

