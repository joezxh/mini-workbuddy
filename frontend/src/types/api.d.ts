/**
 * API 响应类型定义
 */

// 通用响应结构
export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

// 分页请求参数
export interface PageParams {
  page: number
  pageSize: number
  [key: string]: any
}

// 分页响应数据
export interface PageData<T = any> {
  list: T[]
  total: number
  page: number
  pageSize: number
}

// 时间范围
export interface TimeRange {
  startTime: string
  endTime: string
}

// 地区信息
export interface Region {
  code: string
  name: string
  level: string
  parentCode?: string
}

