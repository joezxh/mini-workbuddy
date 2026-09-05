import request from '@/utils/request'
const BASE_URL = '/api/v1'
import type { DictionaryItem } from '@/api/dictionary'

export type BatchDictResult = Record<string, DictionaryItem[]>

const DICT_STORAGE_KEY = 'app_dict_cache'


/**
 * 批量获取字典项
 * POST /api/v1/dictionary/dict/batch
 */
export function batchGetDictItems(dictCodes: string[]) {
  return request.post<BatchDictResult>(`${BASE_URL}/dictionary/dict/batch`, dictCodes)
}

/**
 * 将批量字典数据写入 localStorage
 */
export function saveDictToStorage(data: BatchDictResult) {
  localStorage.setItem(DICT_STORAGE_KEY, JSON.stringify(data))
}

/**
 * 从 localStorage 读取批量字典数据
 */
export function getDictFromStorage(): BatchDictResult {
  try {
    const raw = localStorage.getItem(DICT_STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

/**
 * 清除 localStorage 中的字典缓存
 */
export function clearDictStorage() {
  localStorage.removeItem(DICT_STORAGE_KEY)
}
