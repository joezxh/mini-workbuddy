/**
 * 控制台外壳（admin/index.vue）Tab 系统的编程式打开工具。
 *
 * 背景：控制台以「Tab 页签」承载各页面（componentMap）。但有些页面（如 Wiki 文章
 * 查看/编辑、RAG 测试）带有动态参数（slug / id），无法通过静态 `route.query.tab`
 * 打开。为避免这些导航 `router.push` 跳到外壳（AppLayout）下的独立路由、从而
 * 脱离 Tab 页签系统，统一改为「在控制台 Tab 系统中打开/激活一个 Tab」。
 *
 * 约定：
 *  - 外壳挂载时把 ADMIN_SHELL_ACTIVE.value 置 true，卸载时置 false。
 *  - 若外壳未挂载（例如直接访问 /wiki 深链），则回退到旧路由导航。
 *
 * 注意：router 实例采用「按需动态 import」，避免在本模块加载时执行
 * createWebHistory()（依赖 window），否则会在 node / SSR 测试环境下报错。
 */
export interface DynamicTabDetail {
  /** 唯一 Tab key；可包含 slug / id 以让不同文章各自成 Tab */
  key: string
  /** 组件注册名（dynamicComponentRegistry 或 componentMap 的 key） */
  component: string
  name?: string
  titleKey?: string
  icon?: string
  props?: Record<string, any>
}

/** 由 admin/index.vue 在 onMounted/onUnmounted 时维护，表示外壳是否在线 */
export const ADMIN_SHELL_ACTIVE = { value: false }

const EVENTS = {
  openStatic: 'open-shell-tab',
  openDynamic: 'open-dynamic-tab',
  closeTab: 'close-shell-tab',
  setTitle: 'set-shell-tab-title',
} as const

function shellActive(): boolean {
  return ADMIN_SHELL_ACTIVE.value
}

/** 仅在「外壳不可用、需要回退路由」时按需加载路由实例（避免模块加载期触碰 window） */
function fallbackNavigate(to: { path: string; query?: Record<string, any> } | string) {
  import('@/router').then((mod) => {
    const router = mod.default
    if (typeof to === 'string') router.push(to)
    else router.push(to)
  })
}

/** 打开/激活一个静态 Tab（componentMap 中已注册、无需参数的页面） */
export function openStaticTab(key: string) {
  if (shellActive()) {
    window.dispatchEvent(new CustomEvent(EVENTS.openStatic, { detail: { key } }))
  } else {
    fallbackNavigate({ path: '/admin', query: { tab: key } })
  }
}

/** 打开/激活一个带动态参数的 Tab；外壳不可用时回退到 fallbackRoute */
export function openDynamicTab(detail: DynamicTabDetail, fallbackRoute?: string) {
  if (shellActive()) {
    window.dispatchEvent(new CustomEvent(EVENTS.openDynamic, { detail }))
  } else if (fallbackRoute) {
    fallbackNavigate(fallbackRoute)
  }
}

/** 关闭指定 Tab；外壳不可用时跳转到 fallbackRoute（等价「返回上一页」） */
export function closeShellTab(key: string, fallbackRoute?: string) {
  if (shellActive()) {
    window.dispatchEvent(new CustomEvent(EVENTS.closeTab, { detail: { key } }))
  } else if (fallbackRoute) {
    fallbackNavigate(fallbackRoute)
  }
}

/** 更新某个已打开 Tab 的标题（例如文章加载完后用文章标题命名 Tab） */
export function setShellTabTitle(key: string, name: string) {
  if (shellActive()) {
    window.dispatchEvent(new CustomEvent(EVENTS.setTitle, { detail: { key, name } }))
  }
}
