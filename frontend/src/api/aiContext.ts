/**
 * AI Context Stats API - 前端集成层
 * 用于与 AI Context 后端 API 交互
 */

import api from '@/utils/request'
import type { ContextStats, ModeStats, CompactionRequest, CompactionResponse, SessionStats } from './aiContext.types'

/**
 * 获取上下文统计信息
 * POST /api/v1/ai/context/stats
 */
export function getContextStats(params?: { session_id?: string | number }) {
  return api.post<{ data: ContextStats }>('/api/v1/ai/context/stats', params)
}

/**
 * 批量获取多个会话的上下文统计信息
 * POST /api/v1/ai/context/stats/batch
 */
export function getStatsForSessions(session_ids: Array<string | number>) {
  return api.post<{ items: Record<number, SessionStats> }>(
    '/api/v1/ai/context/stats/batch',
    { session_ids }
  )
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
export function triggerCompaction(request: CompactionRequest): Promise<{ data: CompactionResponse }> {
  return api.post<{ data: CompactionResponse }>(
    '/api/v1/ai/context/compaction',
    request
  ) as Promise<{ data: CompactionResponse }>
}

// ─────────────────────────────────────────────────────────────
// PR-3 Task 10: 跨模式上下文 3 个 API（GET /strategies / POST /breakdown / POST /entries）
// ─────────────────────────────────────────────────────────────

import type { ContextEntriesRequest as CrossModeEntriesRequest, ContextBreakdownBucket, FinalizeStrategy as CrossModeFinalizeStrategy, ContextEntry as CrossModeContextEntry } from './aiContext.types'

/** POST /api/v1/ai/context/entries — 跨模式条目检索 */
export function getContextEntries(req: CrossModeEntriesRequest) {
  return api.post<{ items: CrossModeContextEntry[]; total: number }>(
    '/api/v1/ai/context/entries',
    req,
  )
}

/** POST /api/v1/ai/context/breakdown — 按 source_mode 聚合统计 */
export function getCrossModeBreakdown(req: { session_id: number }) {
  return api.post<{ items: ContextBreakdownBucket[] }>(
    '/api/v1/ai/context/breakdown',
    req,
  )
}

/** GET /api/v1/ai/context/strategies — 9 模式策略清单 */
export function listFinalizeStrategies() {
  return api.get<{ strategies: CrossModeFinalizeStrategy[] }>(
    '/api/v1/ai/context/strategies',
  )
}
