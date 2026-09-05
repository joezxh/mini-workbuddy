import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { MenuNode } from '@/types/menu'

// 将后端菜单节点（permissionCode / sortOrder / i18nKey ...）映射为前端 MenuNode
function mapMenu(m: any): MenuNode {
  return {
    id: m.id,
    name: m.name ?? '',
    path: m.permissionCode || m.path || '',
    icon: m.icon || 'FileOutlined',
    i18nKey: m.i18nKey ?? undefined,
    titleKey: m.i18nKey ?? m.titleKey,
    type: m.type ?? 2,
    sort: m.sortOrder ?? 0,
    status: m.status ?? 1,
    visible: m.visible ?? 1,
    keepAlive: m.keepAlive ?? 0,
    alwaysShow: m.alwaysShow ?? 0,
    children: Array.isArray(m.children) ? m.children.map(mapMenu) : [],
  }
}

/**
 * 菜单 store：缓存后端按当前登录用户权限下发的菜单树。
 * 数据来源于 /me 响应里的 menus 字段，避免每次进入页面都重新拉取菜单。
 */
export const useMenuStore = defineStore('menu', () => {
  const menus = ref<MenuNode[]>([])
  const loaded = ref(false)

  function setMenus(raw: any[] | undefined) {
    menus.value = Array.isArray(raw) ? raw.map(mapMenu) : []
    loaded.value = true
  }

  function clear() {
    menus.value = []
    loaded.value = false
  }

  return { menus, loaded, setMenus, clear }
})
