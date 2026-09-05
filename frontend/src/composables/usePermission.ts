import { useUserStore } from '@/stores/user'

export function usePermission() {
  const hasPermission = (value: string | string[], mode: 'AND' | 'OR' = 'OR') => {
    const userStore = useUserStore()
    const permissions = userStore.permissions || []
    
    if (permissions.includes('*:*')) return true
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
