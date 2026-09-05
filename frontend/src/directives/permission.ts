import type { DirectiveBinding, ObjectDirective } from 'vue'
import { usePermission } from '@/composables/usePermission'

export const permissionDirective: ObjectDirective = {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    const { hasPermission } = usePermission()
    const { value, arg } = binding
    
    if (value) {
      const mode = arg === 'and' ? 'AND' : 'OR'
      const hasAuth = hasPermission(value, mode)
      if (!hasAuth) {
        el.parentNode && el.parentNode.removeChild(el)
      }
    } else {
      throw new Error(`need custom permissions! Like v-permission="['admin:users:read']"`)
    }
  },
  updated(el: HTMLElement, binding: DirectiveBinding) {
    const { hasPermission } = usePermission()
    const { value, arg } = binding
    
    if (value) {
      const mode = arg === 'and' ? 'AND' : 'OR'
      const hasAuth = hasPermission(value, mode)
      if (!hasAuth) {
        // Since updated can fire multiple times, we need to ensure we only remove it if it exists
        if (el.parentNode) {
            el.style.display = 'none' 
            // Better to hide than remove so v-if etc don't crash
        }
      } else {
          el.style.display = ''
      }
    }
  }
}
