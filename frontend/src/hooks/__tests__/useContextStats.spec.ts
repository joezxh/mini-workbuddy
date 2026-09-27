import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// Stub the contexts store to avoid pulling in axios/network for composable unit tests
vi.mock('@/stores/contexts', () => {
  const strategies = { value: [] as any[] }
  const breakdown = { value: [] as any[] }
  const entriesByMode = { value: {} as Record<string, any[]> }
  const loading = { value: false }
  const lastError = { value: null as any }
  return {
    useContextsStore: () => ({
      strategies,
      breakdown,
      entriesByMode,
      loading,
      lastError,
      loadStrategies: vi.fn(async () => {
        strategies.value = [
          { session_type: 'general', source_mode: 'general' },
        ]
      }),
      loadBreakdown: vi.fn(async (sid: number) => {
        breakdown.value = [{ source_mode: 'general', entry_count: 3 }]
      }),
      loadEntriesByMode: vi.fn(async (sid: number, mode: string) => {
        entriesByMode.value[mode] = [{ id: 1, source_mode: mode }]
      }),
      loadAll: vi.fn(async (sid: number) => {
        await Promise.resolve()
        breakdown.value = [{ source_mode: 'general', entry_count: 3 }]
      }),
      findBucket: (mode: string) =>
        breakdown.value.find((b: any) => b.source_mode === mode),
      reset: vi.fn(() => {
        strategies.value = []
        breakdown.value = []
        entriesByMode.value = {}
        lastError.value = null
      }),
    }),
  }
})

import { useCrossModeStats } from '../useCrossModeStats'

describe('useCrossModeStats (PR-3 Task 11)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('exposes reactive strategies/breakdown/entriesByMode/loading refs', () => {
    const cm = useCrossModeStats()
    expect(cm.strategies.value).toEqual([])
    expect(cm.breakdown.value).toEqual([])
    expect(cm.entriesByMode.value).toEqual({})
    expect(cm.loading.value).toBe(false)
  })

  it('loadAll(sessionId) triggers Pinia store', async () => {
    const cm = useCrossModeStats()
    await cm.loadAll(42)
    expect(cm.breakdown.value).toEqual([
      { source_mode: 'general', entry_count: 3 },
    ])
  })

  it('loadEntriesByMode proxies to store with sessionId + mode', async () => {
    const cm = useCrossModeStats()
    await cm.loadEntriesByMode(1, 'skill')
    expect(cm.entriesByMode.value.skill).toEqual([
      { id: 1, source_mode: 'skill' },
    ])
  })

  it('findBucket resolves breakdown entry for source_mode', async () => {
    const cm = useCrossModeStats()
    await cm.loadAll(1)
    const bucket = cm.findBucket('general')
    expect(bucket).toEqual({ source_mode: 'general', entry_count: 3 })
    expect(cm.findBucket('unknown')).toBeUndefined()
  })

  it('reset clears everything', async () => {
    const cm = useCrossModeStats()
    await cm.loadAll(1)
    await cm.loadEntriesByMode(1, 'skill')
    cm.reset()
    expect(cm.strategies.value).toEqual([])
    expect(cm.breakdown.value).toEqual([])
    expect(cm.entriesByMode.value).toEqual({})
  })
})