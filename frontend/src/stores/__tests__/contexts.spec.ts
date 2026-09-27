import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useContextsStore } from '../contexts'

// Mock the api module so store does not depend on axios instance at import time
vi.mock('@/utils/request', () => {
  const post = vi.fn()
  const get = vi.fn()
  return {
    default: { post, get },
  }
})

import api from '@/utils/request'

const postMock = api.post as unknown as ReturnType<typeof vi.fn>
const getMock = api.get as unknown as ReturnType<typeof vi.fn>

describe('useContextsStore (PR-3 Task 9)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    postMock.mockReset()
    getMock.mockReset()
  })

  it('initial state: empty strategies / breakdown / entries / loading=false', () => {
    const store = useContextsStore()
    expect(store.strategies).toEqual([])
    expect(store.breakdown).toEqual([])
    expect(store.entriesByMode).toEqual({})
    expect(store.loading).toBe(false)
    expect(store.lastError).toBe(null)
  })

  it('loadStrategies calls /strategies and stores items', async () => {
    const items = [
      {
        session_type: 'general', source_mode: 'general', priority: 3,
        ttl_hours: 168, write_mem0: true, is_cross_mode_accessible: false,
        display_label: '通用对话', display_color: 'blue',
      },
    ]
    getMock.mockResolvedValueOnce({ strategies: items })

    const store = useContextsStore()
    await store.loadStrategies()

    expect(getMock).toHaveBeenCalledWith('/api/v1/ai/context/strategies')
    expect(store.strategies).toEqual(items)
    expect(store.loading).toBe(false)
  })

  it('loadBreakdown calls /breakdown and stores items for given sessionId', async () => {
    postMock.mockResolvedValueOnce({
      items: [{ source_mode: 'skill', entry_count: 5 }],
    })

    const store = useContextsStore()
    await store.loadBreakdown(42)

    expect(postMock).toHaveBeenCalledWith(
      '/api/v1/ai/context/breakdown',
      { session_id: 42 },
    )
    expect(store.breakdown).toEqual([
      { source_mode: 'skill', entry_count: 5 },
    ])
  })

  it('loadEntriesByMode fetches entries scoped by source_mode', async () => {
    postMock.mockResolvedValueOnce({
      items: [{ id: 1, source_mode: 'skill' }],
      total: 1,
    })

    const store = useContextsStore()
    await store.loadEntriesByMode(10, 'skill')

    expect(postMock).toHaveBeenCalledWith(
      '/api/v1/ai/context/entries',
      {
        session_id: 10,
        source_mode: 'skill',
        allow_cross_mode: true,
        limit: 50,
      },
    )
    expect(store.entriesByMode.skill).toHaveLength(1)
  })

  it('findBucket resolves strategy.source_mode → breakdown entry', async () => {
    postMock.mockResolvedValueOnce({
      items: [
        { source_mode: 'skill', entry_count: 3 },
        { source_mode: 'agent', entry_count: 1 },
      ],
    })

    const store = useContextsStore()
    await store.loadBreakdown(99)
    const bucket = store.findBucket('agent')
    expect(bucket).toEqual({ source_mode: 'agent', entry_count: 1 })
    // unknown mode returns undefined
    expect(store.findBucket('unknown')).toBeUndefined()
  })

  it('graceful fallback on API failure: console.error + keeps previous state', async () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    postMock.mockRejectedValueOnce(new Error('boom'))

    const store = useContextsStore()
    // pre-seed: strategies was previously loaded successfully
    store.strategies = [{ session_type: 'general', source_mode: 'general' } as any]

    await expect(store.loadBreakdown(1)).rejects.toThrow('boom')
    expect(store.lastError).toBe('boom')
    expect(errSpy).toHaveBeenCalled()
    // existing state preserved
    expect(store.strategies).toHaveLength(1)

    errSpy.mockRestore()
  })

  it('reset clears all in-memory state', async () => {
    const store = useContextsStore()
    store.strategies = [{ session_type: 'x' } as any]
    store.breakdown = [{ source_mode: 'y', entry_count: 1 }]
    store.entriesByMode = { general: [{ id: 1 } as any] }
    store.lastError = 'some-error'

    store.reset()

    expect(store.strategies).toEqual([])
    expect(store.breakdown).toEqual([])
    expect(store.entriesByMode).toEqual({})
    expect(store.lastError).toBe(null)
  })

  it('loadAll sequentially loads strategies + breakdown', async () => {
    getMock.mockResolvedValueOnce({ strategies: [{ session_type: 'g', source_mode: 'g' }] })
    postMock.mockResolvedValueOnce({ items: [{ source_mode: 'g', entry_count: 7 }] })

    const store = useContextsStore()
    await store.loadAll(1)

    expect(getMock).toHaveBeenCalledTimes(1)
    expect(postMock).toHaveBeenCalledTimes(1)
    expect(store.strategies).toHaveLength(1)
    expect(store.breakdown).toEqual([{ source_mode: 'g', entry_count: 7 }])
  })
})