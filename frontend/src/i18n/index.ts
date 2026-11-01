/** i18n 国际化配置 */
import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN'
import zhTW from './locales/zh-TW'
import enUS from './locales/en-US'
import jaJP from './locales/ja-JP'

export type LocaleKey = 'zh-CN' | 'zh-TW' | 'en-US' | 'ja-JP'

/** 受支持的语言列表（须在 normalizeLocale 之前初始化，否则顶层调用会触发 TDZ） */
export const SUPPORTED_LOCALES = ['zh-CN', 'zh-TW', 'en-US', 'ja-JP'] as const

/** 归一化语言：历史版本可能存了 'en' 等旧值，统一收敛到受支持的 LocaleKey */
function normalizeLocale(value: unknown): LocaleKey {
  if (isSupportedLocale(value)) return value
  return 'en-US'
}

const savedLocale = normalizeLocale(localStorage.getItem('app-locale'))
// 旧版本可能存了不受支持的值（如 'en'），就地纠正，避免每次都走 fallback
if (localStorage.getItem('app-locale') !== savedLocale) {
  localStorage.setItem('app-locale', savedLocale)
}

const i18n = createI18n({
  legacy: false,
  locale: savedLocale,
  fallbackLocale: 'en-US',
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
  return normalizeLocale(localStorage.getItem('app-locale'))
}

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

// ── 运行时翻译覆盖 ──────────────────────────────────────────
/**
 * 菜单管理「多语言预览」支持在线修改翻译：
 * 通过 mergeLocaleMessage 立即生效，并写入 localStorage 在本浏览器持久化。
 * 永久对所有用户生效需同步前端语言包源文件（src/i18n/locales/*.ts）。
 */
const I18N_OVERRIDES_KEY = 'app-i18n-overrides'

function readTranslationOverrides(): Record<string, Record<string, string>> {
  try {
    const raw = localStorage.getItem(I18N_OVERRIDES_KEY)
    const parsed = raw ? JSON.parse(raw) : null
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

/** 'a.b.c' + value → { a: { b: { c: value } } }（mergeLocaleMessage 深合并，不影响兄弟 key） */
function buildNestedMessage(key: string, value: string): Record<string, unknown> {
  const parts = key.split('.')
  const root: Record<string, any> = {}
  let cur: Record<string, any> = root
  for (const p of parts.slice(0, -1)) {
    if (!cur[p] || typeof cur[p] !== 'object') cur[p] = {}
    cur = cur[p]
  }
  cur[parts[parts.length - 1]] = value
  return root
}

/** 修改某个 key 的翻译：运行时立即生效并持久化到本浏览器 */
export function setTranslationOverride(locale: string, key: string, value: string): void {
  if (!isSupportedLocale(locale) || !key) return
  ;(i18n.global as any).mergeLocaleMessage(locale, buildNestedMessage(key, value))
  const overrides = readTranslationOverrides()
  if (!overrides[locale]) overrides[locale] = {}
  overrides[locale][key] = value
  try {
    localStorage.setItem(I18N_OVERRIDES_KEY, JSON.stringify(overrides))
  } catch {
    // 存储配额异常时忽略：运行时翻译已生效
  }
}

// 启动时把历史覆盖叠加到语言包上
for (const [locale, entries] of Object.entries(readTranslationOverrides())) {
  if (!isSupportedLocale(locale)) continue
  for (const [key, value] of Object.entries(entries)) {
    if (typeof value === 'string') {
      ;(i18n.global as any).mergeLocaleMessage(locale, buildNestedMessage(key, value))
    }
  }
}

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
