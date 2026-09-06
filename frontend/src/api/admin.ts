/**
 * 管理员相关API
 */

import request from '@/utils/request'
import type { ApiResponse, PageParams, PageData } from '@/types/api'
import type { UserListItem } from '@/types/user'

// ============================================================
// 通用类型
// ============================================================
export interface BasePageParams {
  page?: number
  page_size?: number
  keyword?: string
  sort_field?: string
  sort_order?: string
}

export interface SystemConfig {
  configKey: string
  configValue: string
  description: string
  updateTime: string
}

export interface OperationLog {
  logId: string
  userId: string
  userName: string
  operation: string
  module: string
  detail: string
  ip: string
  createTime: string
}

// ============================================================
// 用户管理
// ============================================================
export function getUserList(params: PageParams) {
  return request.get<ApiResponse<PageData<UserListItem>>>('/api/v1/admin/users', { params })
}
export function createUser(data: any) {
  return request.post<ApiResponse<UserListItem>>('/api/v1/admin/users', data)
}
export function updateUser(userId: string, data: any) {
  return request.put<ApiResponse<UserListItem>>(`/api/v1/admin/users/${userId}`, data)
}
export function deleteUser(userId: string) {
  return request.delete<ApiResponse<void>>(`/api/v1/admin/users/${userId}`)
}
export function resetPassword(userId: string, newPassword: string) {
  return request.post<ApiResponse<void>>(`/api/v1/admin/users/${userId}/reset-password`, { newPassword })
}
export function updateUserStatus(userId: number | string, status: string) {
  return request.put(`/api/v1/admin/users/${userId}/status`, { status })
}
export function changePassword(userId: number | string, oldPassword: string, newPassword: string) {
  return request.post(`/api/v1/admin/users/${userId}/reset-password`, { oldPassword, newPassword })
}
export function assignUserRole(userId: number | string, roleIds: number[]) {
  return request.put(`/api/v1/admin/users/${userId}/role`, { roleIds })
}
export function getSystemConfig() {
  return request.get<ApiResponse<SystemConfig[]>>('/api/v1/admin/config')
}
export function updateSystemConfig(configKey: string, configValue: string) {
  return request.put<ApiResponse<void>>('/api/v1/admin/config', { configKey, configValue })
}
export function getOperationLogs(params: PageParams) {
  return request.get<ApiResponse<PageData<OperationLog>>>('/api/v1/admin/logs', { params })
}

// ============================================================
// 数据迁移
// ============================================================
export function getMigrationStats() {
  return request.get('/api/v1/admin/migration/stats')
}
export function migrateEvent() {
  return request.post('/api/v1/admin/migration/event')
}
export function migratePerson() {
  return request.post('/api/v1/admin/migration/person')
}
export function migrateDispute() {
  return request.post('/api/v1/admin/migration/dispute')
}

// ============================================================
// 源数据浏览（只读）- 指向 /api/v1/dws/* 路由
// ============================================================
export function getDwsEvents(params: BasePageParams) {
  return request.get('/api/v1/dws/events', { params })
}
export function getDwsEventDetail(eventId: string) {
  return request.get(`/api/v1/dws/events/${eventId}`)
}
export function getDwsPersons(params: BasePageParams) {
  return request.get('/api/v1/dws/persons', { params })
}
export function getDwsPersonDetail(personId: string) {
  return request.get(`/api/v1/dws/persons/${personId}`)
}
export function getDwsDisputes(params: BasePageParams) {
  return request.get('/api/v1/dws/disputes', { params })
}
export function getDwsDisputeDetail(pkId: string) {
  return request.get(`/api/v1/dws/disputes/${pkId}`)
}
export function getDwsEnterprises(params: BasePageParams) {
  return request.get('/api/v1/dws/enterprises', { params })
}
export function getDwsEnterpriseDetail(uniscid: string) {
  return request.get(`/api/v1/dws/enterprises/${uniscid}`)
}

// ============================================================
// AI 分析
// ============================================================
export function aiAnalyzeEvent(eventId: number) {
  return request.post(`/api/v1/admin/risk-events/${eventId}/ai-analyze`)
}
export function aiAnalyzePerson(personId: number) {
  return request.post(`/api/v1/admin/risk-persons/${personId}/ai-analyze`)
}
export function aiAnalyzeEntity(entityId: number) {
  return request.post(`/api/v1/admin/risk-entities/${entityId}/ai-analyze`)
}
export function aiAnalyzeLocation(locationId: number) {
  return request.post(`/api/v1/admin/risk-locations/${locationId}/ai-analyze`)
}

// ============================================================
// 风险事件管理
// ============================================================
export interface RiskEventForm {
  event_title: string
  event_content?: string
  event_type?: string
  risk_level?: string
  region_code?: string
  region_name?: string
  event_date?: string
  disposal_status?: string
  tags?: string
  is_key_event?: boolean
}

export function listRiskEvents(params: BasePageParams & { risk_level?: string; disposal_status?: string, sort_field?: string; sort_order?: string }) {
  return request.get('/api/v1/admin/risk-events', { params })
}
export function getRiskEventDetail(eventId: number) {
  return request.get(`/api/v1/admin/risk-events/${eventId}`)
}
export function createRiskEvent(data: RiskEventForm) {
  return request.post('/api/v1/admin/risk-events', data)
}
export function updateRiskEvent(eventId: number, data: RiskEventForm) {
  return request.put(`/api/v1/admin/risk-events/${eventId}`, data)
}
export function deleteRiskEvent(eventId: number) {
  return request.delete(`/api/v1/admin/risk-events/${eventId}`)
}
export function batchDeleteRiskEvents(ids: number[]) {
  return request.post('/api/v1/admin/risk-events/batch-delete', { ids })
}
export function batchAiAnalyzeEvents(ids: number[]) {
  return request.post('/api/v1/admin/risk-events/batch-ai-analyze', { ids })
}

// ============================================================
// 风险人员管理
// ============================================================
export interface RiskPersonForm {
  real_name: string
  gender?: string
  age?: number
  phone?: string
  person_type?: string
  risk_level?: string
  current_region_code?: string
  current_region_name?: string
  residence_address?: string
  occupation?: string
  tags?: string
  is_key_person?: boolean
  /** 疑似三失一偏 */
  three_losses_one_deviation?: boolean
  /** 疑似严重精神障碍 */
  severe_mental_illness?: boolean
}

export function listRiskPersons(params: BasePageParams & { risk_level?: string; person_type?: string; event_id?: string }) {
  return request.get('/api/v1/admin/risk-persons', { params })
}
export function getRiskPersonDetail(personId: number) {
  return request.get(`/api/v1/admin/risk-persons/${personId}`)
}
export function createRiskPerson(data: RiskPersonForm) {
  return request.post('/api/v1/admin/risk-persons', data)
}
export function updateRiskPerson(personId: number, data: RiskPersonForm) {
  return request.put(`/api/v1/admin/risk-persons/${personId}`, data)
}
export function deleteRiskPerson(personId: number) {
  return request.delete(`/api/v1/admin/risk-persons/${personId}`)
}
export function batchDeleteRiskPersons(ids: number[]) {
  return request.post('/api/v1/admin/risk-persons/batch-delete', { ids })
}
export function batchAiAnalyzePersons(ids: number[]) {
  return request.post('/api/v1/admin/risk-persons/batch-ai-analyze', { ids })
}

// ============================================================
// 风险企业管理
// ============================================================
export interface RiskEntityForm {
  entity_name: string
  entity_type?: string
  unified_social_credit_code?: string
  legal_person?: string
  registered_capital?: number
  establishment_date?: string
  region_code?: string
  registered_address?: string
  industry?: string
  business_scope?: string
  risk_level?: string
}

export function listRiskEntities(params: BasePageParams & { risk_level?: string; entity_type?: string }) {
  return request.get('/api/v1/admin/risk-entities', { params })
}
export function getRiskEntityDetail(entityId: number) {
  return request.get(`/api/v1/admin/risk-entities/${entityId}`)
}
export function createRiskEntity(data: RiskEntityForm) {
  return request.post('/api/v1/admin/risk-entities', data)
}
export function updateRiskEntity(entityId: number, data: RiskEntityForm) {
  return request.put(`/api/v1/admin/risk-entities/${entityId}`, data)
}
export function deleteRiskEntity(entityId: number) {
  return request.delete(`/api/v1/admin/risk-entities/${entityId}`)
}
export function batchDeleteRiskEntities(ids: number[]) {
  return request.post('/api/v1/admin/risk-entities/batch-delete', { ids })
}
export function batchAiAnalyzeEntities(ids: number[]) {
  return request.post('/api/v1/admin/risk-entities/batch-ai-analyze', { ids })
}

export interface PersonAIProcessParams {
  person_ids?: number[]
  flow_code?: string
  mode?: 'immediate' | 'scheduled'
  scheduled_at?: string
}

export function startPersonAIProcess(params: PersonAIProcessParams) {
  return request.post('/api/v1/admin/risk-persons/ai-process', params)
}

export function getPersonAIProcessStreamUrl(taskId: string): string {
  const base = (import.meta as any).env?.VITE_API_BASE_URL || ''
  return `${base}/api/v1/admin/risk-persons/ai-process/${taskId}/stream`
}

export function getPersonDifyFlows() {
  return request.get('/api/v1/admin/risk-persons/dify-flows')
}

export interface EntityAIProcessParams {
  entity_ids?: number[]
  flow_code?: string
  mode?: 'immediate' | 'scheduled'
  scheduled_at?: string
}

export function startEntityAIProcess(params: EntityAIProcessParams) {
  return request.post('/api/v1/admin/risk-entities/ai-process', params)
}

export function getEntityAIProcessStreamUrl(taskId: string): string {
  const base = (import.meta as any).env?.VITE_API_BASE_URL || ''
  return `${base}/api/v1/admin/risk-entities/ai-process/${taskId}/stream`
}

export function getEntityDifyFlows() {
  return request.get('/api/v1/admin/risk-entities/dify-flows')
}

// ============================================================
// 风险地点管理
// ============================================================
export interface RiskLocationForm {
  location_name: string
  location_type?: string
  location_alias?: string
  region_code?: string
  region_name?: string
  province?: string
  city?: string
  district?: string
  street?: string
  address?: string
  longitude?: number
  latitude?: number
  risk_level?: string
  description?: string
  tags?: string
}

export function listRiskLocations(params: BasePageParams & { risk_level?: string; location_type?: string }) {
  return request.get('/api/v1/admin/risk-locations', { params })
}
export function getRiskLocationDetail(locationId: number) {
  return request.get(`/api/v1/admin/risk-locations/${locationId}`)
}
export function createRiskLocation(data: RiskLocationForm) {
  return request.post('/api/v1/admin/risk-locations', data)
}
export function updateRiskLocation(locationId: number, data: RiskLocationForm) {
  return request.put(`/api/v1/admin/risk-locations/${locationId}`, data)
}
export function deleteRiskLocation(locationId: number) {
  return request.delete(`/api/v1/admin/risk-locations/${locationId}`)
}
export function batchDeleteRiskLocations(ids: number[]) {
  return request.post('/api/v1/admin/risk-locations/batch-delete', { ids })
}
export function batchAiAnalyzeLocations(ids: number[]) {
  return request.post('/api/v1/admin/risk-locations/batch-ai-analyze', { ids })
}

// ============================================================
// 仪表盘统计
// ============================================================
export function getDashboardStats() {
  return request.get('/api/v1/admin/dashboard/stats')
}

// ============================================================
// 角色管理
// ============================================================
export interface RoleItem {
  roleId: number
  roleName: string
  roleCode: string
  description?: string
  status?: string
}

export interface RoleForm {
  roleName: string
  roleCode: string
  description?: string
}

export function getRoleList(params?: { tenant_id?: number | null }) {
  return request.get<any>('/api/v1/admin/roles', { params })
}
export function createRole(data: RoleForm) {
  return request.post('/api/v1/admin/roles', data)
}
export function updateRole(roleId: number, data: RoleForm) {
  return request.put(`/api/v1/admin/roles/${roleId}`, data)
}

// ============================================================
// 审计日志
// ============================================================
export interface AuditLogParams {
  skip?: number
  limit?: number
  user_id?: number | string
  operation_type?: string
  tenant_id?: number | null
}

export function getAuditLogs(params: AuditLogParams) {
  return request.get('/api/v1/admin/audit-logs', { params })
}

/**
 * 获取最近N条审计日志（仪表盘用）
 */
export function getRecentAuditLogs(limit = 10) {
  return request.get<{ code: number; message: string; data: AuditLogItem[]; total: number }>(
    '/api/v1/admin/audit-logs',
    { params: { skip: 0, limit } }
  )
}

export interface AuditLogItem {
  logId: number
  userId: number | null
  username: string | null
  operationType: string
  operationModule: string | null
  operationDesc: string | null
  /** 请求 IP */
  requestIp: string | null
  /** 完整请求 URL（含 query string） */
  requestUrl: string | null
  /** HTTP 方法 */
  requestMethod?: string | null
  /** User-Agent */
  userAgent?: string | null
  /** 响应耗时（毫秒） */
  responseTimeMs?: number | null
  createdAt: string | null
  status: number | null
  /** 附件详情（来自 sys_audit_log.new_data.attachment_info） */
  newData?: {
    attachment_info?: {
      file_db_ids?: number[]
      file_db_id_count?: number
      file_ids?: string[]
      file_id_count?: number
      file_id?: string
    }
  } | null
  /** 请求参数 JSON（脱敏后） */
  requestParams?: Record<string, any> | null
}

// ============================================================
// 用户列表（兼容旧接口参数格式）
// ============================================================
export function getUserListBySkip(params: { skip?: number; limit?: number; tenant_id?: number | null }) {
  return request.get('/api/v1/admin/users', { params })
}

// ============================================================
// 菜单管理
// ============================================================
export interface MenuItem {
  id: number
  name: string
  permission?: string
  path?: string
  type: number  // 1=目录 2=菜单 3=按钮
  sort: number
  parentId: number | null
  icon?: string
  component?: string
  componentName?: string
  status: number  // 0=开启 1=关闭
  visible: number  // 1=显示 0=隐藏
  keepAlive: number  // 1=缓存 0=不缓存
  alwaysShow: number  // 1=总是 0=不是
  i18nKey?: string  // 多语言翻译 key
  children?: MenuItem[]
}

export interface MenuSimpleItem {
  id: number
  parentId: number | null
  name: string
}

export interface MenuForm {
  id?: number
  name: string
  permission?: string
  path?: string
  type: number
  sort: number
  parentId: number
  icon?: string
  component?: string
  componentName?: string
  status: number
  visible: number
  keepAlive: number
  alwaysShow: number
  i18nKey?: string  // 多语言翻译 key
}

export function getMenuList(params?: { name?: string; status?: number }) {
  return request.get<any>('/api/v1/admin/menus', { params })
}
export function getMenuFlatList(params?: { name?: string; status?: number }) {
  return request.get<any>('/api/v1/admin/menus/flat', { params })
}
export function getMenuSimpleList() {
  return request.get<any>('/api/v1/admin/menus/simple')
}
export function getMenuDetail(menuId: number) {
  return request.get<any>(`/api/v1/admin/menus/${menuId}`)
}
export function createMenu(data: MenuForm) {
  return request.post<any>('/api/v1/admin/menus', data)
}
export function updateMenu(menuId: number, data: Partial<MenuForm>) {
  return request.put<any>(`/api/v1/admin/menus/${menuId}`, data)
}
export function deleteMenu(menuId: number) {
  return request.delete<any>(`/api/v1/admin/menus/${menuId}`)
}

// ============================================================
// 角色权限关联
// ============================================================
export function getRolePermissions(roleId: number) {
  return request.get<any>(`/api/v1/admin/roles/${roleId}/menus`)
}
export function assignRolePermissions(roleId: number, permissionIds: number[]) {
  return request.put(`/api/v1/admin/roles/${roleId}/menus`, { menuIds: permissionIds })
}

// ============================================================
// 用户角色关联（获取用户已分配角色）
// ============================================================
export function getUserRoles(userId: number | string) {
  return request.get<any>(`/api/v1/admin/users/${userId}/roles`)
}
