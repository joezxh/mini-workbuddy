import request from '@/utils/request'

const TENANT_BASE = '/api/v1/admin/tenant'
const PACKAGE_BASE = '/api/v1/admin/tenant-package'

// ── 类型定义 ──────────────────────────────────────────────────────

export interface TenantVO {
  tenant_id?: number
  name: string
  package_id?: number | null
  contact_name?: string
  contact_mobile?: string
  status: string
  account_count?: number
  expire_time?: string | null
  websites?: string[]
  username?: string
  password?: string
  created_at?: string
  updated_at?: string
}

export interface TenantSimpleVO {
  tenant_id: number
  name: string
}

export interface TenantPackageVO {
  package_id?: number
  name: string
  status: string
  remark?: string
  menu_ids?: number[]
  created_at?: string
  updated_at?: string
}

export interface TenantPackageSimpleVO {
  package_id: number
  name: string
}

export interface PageResult<T> {
  list: T[]
  total: number
}

// ── 租户管理 ──────────────────────────────────────────────────────

export function getTenantPage(params: {
  name?: string
  contact_name?: string
  contact_mobile?: string
  status?: string
  page_no?: number
  page_size?: number
}) {
  return request.get(`${TENANT_BASE}/page`, { params })
}

export function getTenant(tenantId: number) {
  return request.get(`${TENANT_BASE}/${tenantId}`)
}

export function createTenant(data: TenantVO) {
  return request.post(`${TENANT_BASE}/create`, data)
}

export function updateTenant(data: TenantVO) {
  return request.put(`${TENANT_BASE}/update`, data)
}

export function deleteTenant(tenantId: number) {
  return request.delete(`${TENANT_BASE}/delete/${tenantId}`)
}

export function deleteTenantList(ids: number[]) {
  return request.delete(`${TENANT_BASE}/delete-list`, { params: { ids } })
}

export function getTenantSimpleList() {
  return request.get<TenantSimpleVO[]>(`${TENANT_BASE}/simple-list`)
}

// ── 套餐管理 ──────────────────────────────────────────────────────

export function getPackagePage(params: {
  name?: string
  status?: string
  page_no?: number
  page_size?: number
}) {
  return request.get(`${PACKAGE_BASE}/page`, { params })
}

export function getPackage(packageId: number) {
  return request.get(`${PACKAGE_BASE}/${packageId}`)
}

export function createPackage(data: TenantPackageVO) {
  return request.post(`${PACKAGE_BASE}/create`, data)
}

export function updatePackage(data: TenantPackageVO) {
  return request.put(`${PACKAGE_BASE}/update`, data)
}

export function deletePackage(packageId: number) {
  return request.delete(`${PACKAGE_BASE}/delete/${packageId}`)
}

export function deletePackageList(ids: number[]) {
  return request.delete(`${PACKAGE_BASE}/delete-list`, { params: { ids } })
}

export function getPackageSimpleList() {
  return request.get<TenantPackageSimpleVO[]>(`${PACKAGE_BASE}/simple-list`)
}
