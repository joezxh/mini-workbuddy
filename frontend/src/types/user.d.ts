/**
 * 用户相关类型定义
 */
import type { MenuNode } from './menu'

// 用户信息
export interface UserInfo {
  userId: string
  username: string
  realName: string
  phone: string
  email?: string
  avatar?: string
  roles: string[]
  permissions: string[]
  /** 后端按当前用户权限下发的菜单树（由 /me 一并返回，避免额外调用） */
  menus?: MenuNode[]
  regionCode: string
  regionName: string
  regionLevel: string
  createTime?: string
  updateTime?: string
}

// 登录参数
export interface LoginParams {
  username: string
  password: string
}

// 登录响应
export interface LoginResponse {
  token: string
  userInfo: UserInfo
}

// 用户列表项
export interface UserListItem {
  userId: string
  username: string
  realName: string
  phone: string
  roles: string[]
  regionName: string
  status: number
  createTime: string
}

