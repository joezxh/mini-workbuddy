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

/**
 * 外壳的规范路径：登录首页 /dashboard 即控制台壳本身，
 * /admin 只是带 query 透传的历史别名（见 router）。
 */
export const SHELL_PATH = '/dashboard'

/** 默认门户页签 key，与后端 sys_menu 中 dashboard 菜单 path 的末段一致 */
export const CONSOLE_TAB_KEY = 'dashboard'

/** 控制台页签定义（不可关闭、恒在首位），供壳首屏同步建签而不必等菜单接口 */
export interface ConsoleTabDefinition {
  key: string
  name: string
  titleKey: string
  icon: string
  closable: false
}

export function consoleTabDefinition(): ConsoleTabDefinition {
  return {
    key: CONSOLE_TAB_KEY,
    name: 'Dashboard',
    titleKey: 'userMenu.dashboard',
    icon: 'DashboardOutlined',
    closable: false,
  }
}

/**
 * 解析 URL 上的 `?tab=` 应激活的页签 key：
 * 命中 `availableKeys`（componentMap 的键集）则用它，否则一律回落控制台页签。
 * 重复参数取首个，非字符串值当作未传。
 */
export function resolveInitialTab(queryTab: unknown, availableKeys: Iterable<string>): string {
  const raw = Array.isArray(queryTab) ? queryTab[0] : queryTab
  if (typeof raw !== 'string' || !raw) return CONSOLE_TAB_KEY
  for (const key of availableKeys) {
    if (key === raw) return raw
  }
  return CONSOLE_TAB_KEY
}

/** 菜单 path 末段即页签 key（去掉尾部斜杠）；无有效段时原样返回 */
function menuKeyFromPath(menuPath: string): string {
  const segments = menuPath.replace(/\/+$/, '').split('/').filter(Boolean)
  return segments.length ? segments[segments.length - 1] : menuPath
}

/**
 * 菜单/快捷入口的目标地址：
 * 壳内页面（`/admin/<key>`）统一转为 `/dashboard?tab=<key>`，
 * 裸 `/admin` 等价于壳首页；更深的路径与其他业务路由保持真实路由。
 */
export function resolveMenuTarget(path: string): { path: string; query?: Record<string, string> } {
  if (path === '/admin' || path === '/admin/') return { path: SHELL_PATH }
  const shellPage = /^\/admin\/([^/?#]+)\/?$/.exec(path)
  if (shellPage) return { path: SHELL_PATH, query: { tab: shellPage[1] } }
  return { path }
}

/**
 * 左侧菜单高亮判定：
 * 壳内（routePath === SHELL_PATH）页签地址是 `/dashboard?tab=<key>`，
 * 菜单 path 却是 `/admin/<key>`，故按末段与当前 tab 比对，无 tab 时只高亮 dashboard；
 * 非壳路由（真实深链）沿用等值/前缀判定。
 */
export function isMenuActive(
  menuPath: string | undefined,
  routePath: string,
  routeTab?: string,
): boolean {
  if (!menuPath) return false
  if (routePath === SHELL_PATH) {
    return menuKeyFromPath(menuPath) === (routeTab || CONSOLE_TAB_KEY)
  }
  return routePath === menuPath || routePath.startsWith(menuPath + '/')
}

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
    fallbackNavigate({ path: SHELL_PATH, query: { tab: key } })
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
