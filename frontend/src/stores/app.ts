// 控制台级 UI 偏好：皮肤（深色 / 浅色）、侧栏状态与当前语言镜像。
//
// 语言本身由 vue-i18n 持有（@/i18n），这里只做镜像，让组件能响应语言变化。
// 皮肤默认浅色；选择持久化到 localStorage。
import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import i18n, { getLocale, isSupportedLocale, setLocale } from '@/i18n'
import type { LocaleKey } from '@/i18n'
import dayjs from 'dayjs'

const THEME_KEY = 'app-theme'
const SIDEBAR_KEY = 'app-sidebar-collapsed'

export type ThemeName = 'dark' | 'light'

function readStored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const raw = globalThis.localStorage?.getItem(key)
    if (raw && (allowed as readonly string[]).includes(raw)) return raw as T
  } catch {
    /* 存储不可用（隐私模式等） */
  }
  return fallback
}

function syncDayjs(locale: LocaleKey) {
  // 让日期 / 时间格式化跟随界面语言（en 为 dayjs 内置，zh-cn 已在 main.ts 引入）
  dayjs.locale(locale === 'zh-CN' || locale === 'zh-TW' ? 'zh-cn' : 'en')
}

export const useAppStore = defineStore('app', () => {
  const THEMES = ['dark', 'light'] as const

  const theme = ref<ThemeName>(readStored(THEME_KEY, THEMES, 'light'))
  const locale = ref<LocaleKey>(getLocale())
  const sidebarCollapsed = ref(readStored(SIDEBAR_KEY, ['true', 'false'], 'false') === 'true')

  /** 兼容旧字段名：折叠状态 */
  const collapsed = computed(() => sidebarCollapsed.value)
  /** 当前选中的菜单 */
  const selectedMenu = ref<string[]>([])
  /** 面包屑 */
  const breadcrumbs = ref<Array<{ name: string; path?: string }>>([])

  const isDark = computed(() => theme.value === 'dark')

  function applyTheme(next: ThemeName = theme.value) {
    if (typeof document === 'undefined') return
    document.documentElement.setAttribute('data-theme', next)
    document.documentElement.style.colorScheme = next
  }

  function setTheme(next: ThemeName) {
    theme.value = next
    applyTheme(next)
    try {
      globalThis.localStorage?.setItem(THEME_KEY, next)
    } catch {
      /* ignore */
    }
  }

  function toggleTheme() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  function setAppLocale(next: LocaleKey) {
    if (!isSupportedLocale(next)) return
    locale.value = next
    setLocale(next)
    syncDayjs(next)
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
    try {
      globalThis.localStorage?.setItem(SIDEBAR_KEY, String(sidebarCollapsed.value))
    } catch {
      /* ignore */
    }
  }

  /** 兼容旧 API */
  function toggleCollapsed() {
    toggleSidebar()
  }

  function setSelectedMenu(keys: string[]) {
    selectedMenu.value = keys
  }

  function setBreadcrumbs(items: Array<{ name: string; path?: string }>) {
    breadcrumbs.value = items
  }

  /** 首屏绘制前应用已保存的皮肤，避免闪白 */
  function hydrate() {
    applyTheme()
    locale.value = getLocale()
    syncDayjs(locale.value)
  }

  // 当语言在别处被切换时同步镜像值
  watch(
    () => i18n.global.locale.value as LocaleKey,
    (value) => {
      if (value !== locale.value) locale.value = value
    },
  )

  return {
    theme,
    locale,
    sidebarCollapsed,
    collapsed,
    selectedMenu,
    breadcrumbs,
    isDark,
    setTheme,
    toggleTheme,
    setAppLocale,
    toggleSidebar,
    toggleCollapsed,
    setSelectedMenu,
    setBreadcrumbs,
    hydrate,
  }
})
