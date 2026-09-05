/**
 * 权限状态管理
 */

import { defineStore } from 'pinia'
import { computed } from 'vue'
import { useUserStore } from './user'

export const usePermissionStore = defineStore('permission', () => {
  const userStore = useUserStore()

  /**
   * 检查是否有权限
   */
  const hasPermission = computed(() => {
    return (permission: string | string[]) => {
      if (!userStore.userInfo) return false
      
      const permissions = userStore.userInfo.permissions || []
      
      if (Array.isArray(permission)) {
        return permission.some(p => permissions.includes(p))
      }
      
      return permissions.includes(permission)
    }
  })

  /**
   * 检查是否有角色
   */
  const hasRole = computed(() => {
    return (role: string | string[]) => {
      if (!userStore.userInfo) return false
      
      const roles = userStore.userInfo.roles || []
      
      if (Array.isArray(role)) {
        return role.some(r => roles.includes(r))
      }
      
      return roles.includes(role)
    }
  })

  /**
   * 是否是管理员
   */
  const isAdmin = computed(() => {
    return hasRole.value('admin') || hasRole.value('super_admin')
  })

  return {
    hasPermission,
    hasRole,
    isAdmin
  }
})

