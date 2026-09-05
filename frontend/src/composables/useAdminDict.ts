/**
 * 管理端通用数据字典加载（按 dict_code 缓存，多页面复用）
 */
import { reactive } from 'vue'
import { getDictionary, type DictionaryItem } from '@/api/dictionary'

export const adminDictItems = reactive<Record<string, DictionaryItem[]>>({})

const loadedCodes = new Set<string>()

export async function loadAdminDicts(codes: string[]): Promise<void> {
  const pending = [...new Set(codes)].filter(c => !loadedCodes.has(c))
  if (!pending.length) return
  await Promise.all(
    pending.map(async code => {
      try {
        const res = await getDictionary(code, true)
        adminDictItems[code] = (res.items || [])
          .filter(i => i.is_active)
          .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
      } catch {
        adminDictItems[code] = []
      } finally {
        loadedCodes.add(code)
      }
    })
  )
}

export function dictItems(dictCode: string): DictionaryItem[] {
  return adminDictItems[dictCode] || []
}

export function dictLabel(dictCode: string, itemCode?: string | null): string {
  if (itemCode == null || itemCode === '') return ''
  const it = dictItems(dictCode).find(i => i.item_code === itemCode)
  return it?.item_name ?? String(itemCode)
}

/** 按 item_code 或历史存的 item_name 匹配，返回展示名 */
export function dictDisplay(dictCode: string, raw?: string | null): string {
  if (raw == null || raw === '') return ''
  const items = dictItems(dictCode)
  const byCode = items.find(i => i.item_code === raw)
  if (byCode) return byCode.item_name
  const byName = items.find(i => i.item_name === raw)
  if (byName) return byName.item_name
  return String(raw)
}

/** 返回字典项 color（合法时给 a-tag，否则 undefined 走兜底） */
export function dictColor(dictCode: string, itemCode?: string | null): string | undefined {
  if (itemCode == null || itemCode === '') return undefined
  const c = dictItems(dictCode).find(i => i.item_code === itemCode)?.color
  if (!c) return undefined
  const fixed = ['red', 'orange', 'gold', 'green', 'blue', 'cyan', 'purple', 'magenta', 'volcano', 'geekblue', 'lime', 'default', 'success', 'processing', 'error', 'warning']
  if (fixed.includes(c)) return c
  return c
}

const RISK_FALLBACK: Record<string, string> = {
  critical: 'red', high: 'red', medium: 'orange', low: 'green',
}
const DISPOSAL_FALLBACK: Record<string, string> = {
  pending: 'orange', pending_review: 'orange', processing: 'blue',
  completed: 'green', resolved: 'green', closed: 'default', failed: 'red',
}

export function tagColorRisk(level?: string | null): string {
  return dictColor('risk_level', level) || RISK_FALLBACK[level || ''] || 'default'
}

export function tagColorDisposal(s?: string | null): string {
  return dictColor('disposal_status', s) || DISPOSAL_FALLBACK[s || ''] || 'default'
}
