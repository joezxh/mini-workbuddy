/**
 * 行政区域 API 接口（基于 sys_region 表）
 */
import request from '@/utils/request'

// 区域响应接口
export interface RegionItem {
  region_id: number
  region_code: string
  region_name: string
  parent_code?: string
  region_level: string
  full_path?: string
  sort_order: number
  longitude?: string
  latitude?: string
}

// 区域树节点
export interface RegionTreeNode extends RegionItem {
  children: RegionTreeNode[]
}

// 区域级别常量
export const RegionLevel = {
  PROVINCE: 'province',  // 省
  CITY: 'city',          // 市
  DISTRICT: 'district',  // 区/县
  STREET: 'street',      // 街道/乡镇
  COMMUNITY: 'community' // 社区/村
} as const

export const RegionLevelLabel: Record<string, string> = {
  province: '省',
  city: '市',
  district: '区/县',
  street: '街道/乡镇',
  community: '社区/村'
}

/**
 * 获取各级别区域数量统计
 */
export function getRegionStats() {
  return request.get<Record<string, number>>('/api/v1/dictionary/dict/regions/stats')
}

/**
 * 获取区域列表（平铺）
 */
export function getRegions(parentCode?: string) {
  return request.get<RegionItem[]>('/api/v1/dictionary/dict/regions', {
    params: { parent_code: parentCode }
  })
}

/**
 * 获取区域树形结构
 */
export function getRegionTree(parentCode?: string) {
  return request.get<RegionTreeNode[]>('/api/v1/dictionary/dict/regions/tree', {
    params: { parent_code: parentCode }
  })
}

/**
 * 新增区域
 */
export function createRegion(data: Partial<RegionItem>) {
  return request.post<RegionItem>('/api/v1/dictionary/regions', data)
}

/**
 * 更新区域
 */
export function updateRegion(regionCode: string, data: Partial<RegionItem>) {
  return request.put<RegionItem>(`/api/v1/dictionary/regions/${regionCode}`, data)
}

/**
 * 删除区域（级联删除子区域）
 */
export function deleteRegion(regionCode: string) {
  return request.delete(`/api/v1/dictionary/regions/${regionCode}`)
}

