import { useUserStore } from '@/stores/user'

export function usePermission() {
  const hasPermission = (value: string | string[], mode: 'AND' | 'OR' = 'OR') => {
    const userStore = useUserStore()
    const permissions = userStore.permissions || []
    const roles = userStore.roles || []

    // 超级管理员角色拥有全部权限（原通配符 '*:*' 已由后端改为真实菜单权限）
    if (permissions.includes('*:*') || roles.includes('super_admin')) return true
    if (!value) return true

    const required = Array.isArray(value) ? value : [value]
    if (required.length === 0) return false

    if (mode === 'OR') {
      return required.some(p => permissions.includes(p))
    } else {
      return required.every(p => permissions.includes(p))
    }
  }

  return { hasPermission }
}
