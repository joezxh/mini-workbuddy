/** i18n 国际化配置 */
import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN'
import zhTW from './locales/zh-TW'
import enUS from './locales/en-US'
import jaJP from './locales/ja-JP'

export type LocaleKey = 'zh-CN' | 'zh-TW' | 'en-US' | 'ja-JP'

const savedLocale = (localStorage.getItem('app-locale') || 'zh-CN') as LocaleKey

const i18n = createI18n({
  legacy: false,
  locale: savedLocale,
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    'zh-TW': zhTW,
    'en-US': enUS,
    'ja-JP': jaJP,
  },
})

if (typeof document !== 'undefined') {
  document.documentElement.setAttribute('lang', savedLocale)
}

export function setLocale(locale: LocaleKey) {
  i18n.global.locale.value = locale
  localStorage.setItem('app-locale', locale)
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('lang', locale)
  }
}

export function getLocale(): LocaleKey {
  return (localStorage.getItem('app-locale') as LocaleKey) || 'zh-CN'
}

export const SUPPORTED_LOCALES = ['zh-CN', 'zh-TW', 'en-US', 'ja-JP'] as const

export const LOCALE_LABELS: Record<LocaleKey, string> = {
  'zh-CN': '简体中文',
  'zh-TW': '繁體中文',
  'en-US': 'English',
  'ja-JP': '日本語',
}

/** 语言切换器使用的下拉选项（沿用原有结构） */
export const LOCALE_OPTIONS = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'zh-TW', label: '繁體中文' },
  { value: 'en-US', label: 'English' },
  { value: 'ja-JP', label: '日本語' },
]

export function isSupportedLocale(value: unknown): value is LocaleKey {
  return typeof value === 'string' && (SUPPORTED_LOCALES as readonly string[]).includes(value)
}

/**
 * 解析菜单标题：优先取当前语言的映射，其次英文，最后退回默认文案。
 */
export function localise(
  i18nMap: Partial<Record<string, string>> | undefined,
  fallback: string,
): string {
  const current = i18n.global.locale.value as string
  return i18nMap?.[current] ?? i18nMap?.['en-US'] ?? fallback
}

export default i18n
