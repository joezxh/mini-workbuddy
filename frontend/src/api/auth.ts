import request from '@/utils/request'

const BASE_URL = '/api/v1/auth'

/**
 * 登录
 */
export function login(data: { username: string; password: string; tenant_id?: number }) {
  return request.post(`${BASE_URL}/login`, data)
}

/**
 * 登出
 */
export function logout() {
  return request.post(`${BASE_URL}/logout`)
}

/**
 * 获取当前用户信息
 */
export function getUserInfo() {
  return request.get(`${BASE_URL}/me`)
}

/**
 * 更新个人信息
 */
export function updateProfile(data: any) {
  return request.put(`${BASE_URL}/me/profile`, data)
}

/**
 * 获取用户可访问的地区树
 */
export function getRegions() {
  return request.get(`${BASE_URL}/regions`)
}

/**
 * 修改密码
 */
export function changePassword(data: { old_password: string; new_password: string }) {
  return request.post(`${BASE_URL}/change-password`, data)
}

/**
 * 获取当前用户菜单树
 */
export function getUserMenus() {
  return request.get(`${BASE_URL}/me/menus`)
}

/**
 * 获取行政区划树
 */
export function getRegionsTree(parentCode?: string) {
  const params: Record<string, string> = {}
  if (parentCode) {
    params.parent_code = parentCode
  }
  return request.get('/api/v1/dictionary/dict/regions/tree', { params })
}

/**
 * 获取登录页租户下拉列表（公开接口）
 */
export function getTenantSimpleList() {
  return request.get(`${BASE_URL}/tenant-simple-list`)
}

