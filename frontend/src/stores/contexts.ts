/**
 * Cross-Mode Context Store (PR-3 Task 9)
 *
 * Drives the 9-mode cross-mode context stats page and history drawer.
 * - `strategies`: full 9-mode `FinalizeStrategy` list (from GET /strategies).
 * - `breakdown`: per-`source_mode` aggregated counts (from POST /breakdown).
 * - `entriesByMode`: historical L2 entries keyed by `source_mode`
 *   (from POST /entries).
 *
 * Design notes:
 * - Strategies API may be disabled or fail; store keeps the last successful
 *   snapshot and exposes `lastError` for UI display.
 * - `loadEntriesByMode` is on-demand (called when user opens history drawer).
 * - `findBucket(source_mode)` is a convenience accessor used by the
 *   data-driven `ModeContextCard` component.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/utils/request'

export interface FinalizeStrategy {
  session_type: string
  source_mode: string
  priority: number
  ttl_hours: number
  write_mem0: boolean
  is_cross_mode_accessible: boolean
  display_label: string
  display_color: string
}

export interface ContextBreakdownBucket {
  source_mode: string
  entry_count: number
}

export interface ContextEntry {
  id: number
  session_id: number
  source_mode: string
  context_key: string
  context_data: Record<string, unknown>
  context_tags: string[]
  priority: number
  is_cross_mode_accessible: boolean
  case_number: string | null
  expires_at: string | null
  created_at: string
  last_accessed: string | null
}

export const useContextsStore = defineStore('contexts', () => {
  const strategies = ref<FinalizeStrategy[]>([])
  const breakdown = ref<ContextBreakdownBucket[]>([])
  const entriesByMode = ref<Record<string, ContextEntry[]>>({})
  const loading = ref(false)
  const lastError = ref<string | null>(null)

  async function loadStrategies(): Promise<void> {
    loading.value = true
    try {
      const res = await api.get<{ strategies: FinalizeStrategy[] }>(
        '/api/v1/ai/context/strategies',
      )
      strategies.value = (res as { strategies: FinalizeStrategy[] }).strategies
      lastError.value = null
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      console.error('[contexts] loadStrategies failed:', msg)
      lastError.value = msg
      throw err
    } finally {
      loading.value = false
    }
  }

  async function loadBreakdown(sessionId: number): Promise<void> {
    loading.value = true
    try {
      const res = await api.post<{ items: ContextBreakdownBucket[] }>(
        '/api/v1/ai/context/breakdown',
        { session_id: sessionId },
      )
      breakdown.value = (res as { items: ContextBreakdownBucket[] }).items
      lastError.value = null
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      console.error('[contexts] loadBreakdown failed:', msg)
      lastError.value = msg
      throw err
    } finally {
      loading.value = false
    }
  }

  async function loadEntriesByMode(
    sessionId: number,
    sourceMode: string,
    allowCrossMode = true,
    limit = 50,
  ): Promise<void> {
    loading.value = true
    try {
      const res = await api.post<{ items: ContextEntry[]; total: number }>(
        '/api/v1/ai/context/entries',
        {
          session_id: sessionId,
          source_mode: sourceMode,
          allow_cross_mode: allowCrossMode,
          limit,
        },
      )
      const items = (res as { items: ContextEntry[]; total: number }).items
      entriesByMode.value = { ...entriesByMode.value, [sourceMode]: items }
      lastError.value = null
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      console.error('[contexts] loadEntriesByMode failed:', msg)
      lastError.value = msg
      throw err
    } finally {
      loading.value = false
    }
  }

  function findBucket(sourceMode: string): ContextBreakdownBucket | undefined {
    return breakdown.value.find((b) => b.source_mode === sourceMode)
  }

  async function loadAll(sessionId: number): Promise<void> {
    loading.value = true
    try {
      // Strategies first (independent of session), then breakdown (per session).
      await loadStrategies()
      await loadBreakdown(sessionId)
    } finally {
      loading.value = false
    }
  }

  function reset(): void {
    strategies.value = []
    breakdown.value = []
    entriesByMode.value = {}
    lastError.value = null
  }

  return {
    strategies,
    breakdown,
    entriesByMode,
    loading,
    lastError,
    loadStrategies,
    loadBreakdown,
    loadEntriesByMode,
    findBucket,
    loadAll,
    reset,
  }
})