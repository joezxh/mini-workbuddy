/**
 * AI Context Stats API - 前端集成层
 * 用于与 AI Context 后端 API 交互
 */

import api from '@/utils/request'
import type { ContextStats, ModeStats, CompactionRequest } from './types'

/**
 * 获取上下文统计信息
 * POST /api/v1/ai/context/stats
 */
export function getContextStats(params: { session_id?: string | number }) {
  return api.post<{ data: ContextStats }>('/api/v1/ai/context/stats', params)
}

/**
 * 获取孤立模式的上下文记录
 * POST /api/v1/ai/context/retrieve/{mode}/{key}
 */
export function retrieveContext(mode: string, key: string) {
  return api.post<any>(`/api/v1/ai/context/retrieve/${mode}/${key}`)
}

/**
 * 触发上下文压缩
 * POST /api/v1/ai/context/compaction
 */
export function triggerCompaction(request: CompactionRequest) {
  return api.post<{ data: { success: boolean; message: string } }>(
    '/api/v1/ai/context/compaction',
    request
  )
}
