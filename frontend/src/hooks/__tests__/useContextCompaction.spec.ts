import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/utils/request', () => {
  const post = vi.fn()
  return { default: { post } }
})

import api from '@/utils/request'
import { useCrossModeCompaction } from '../useContextCompaction'

const postMock = api.post as unknown as ReturnType<typeof vi.fn>

describe('useCrossModeCompaction (PR-3 Task 12)', () => {
  beforeEach(() => {
    postMock.mockReset()
  })

  it('triggerCompaction proxies request to /compaction and updates state', async () => {
    const c = useCrossModeCompaction()
    postMock.mockResolvedValueOnce({
      data: {
        success: true,
        mode: 'shared',
        key: 'conv',
        strategy: 'summary_and_keep_latest',
        entries_before: 10,
        entries_after: 5,
        tokens_before: 1000,
        tokens_after: 600,
        compaction_ratio: 1.67,
        compacted_at: '2026-09-27T00:00:00Z',
        error: null,
      },
    })

    const res = await c.triggerCompaction({
      mode: 'shared',
      key: 'conv',
      strategy: 'summary_and_keep_latest',
      target_tokens: 8000,
    })

    expect(postMock).toHaveBeenCalledWith(
      '/api/v1/ai/context/compaction',
      {
        mode: 'shared',
        key: 'conv',
        strategy: 'summary_and_keep_latest',
        target_tokens: 8000,
      },
    )
    expect(res.success).toBe(true)
    expect(c.isCompacting.value).toBe(false)
    expect(c.lastResult.value).not.toBe(null)
    expect(c.lastError.value).toBe(null)
    expect(c.history.value.length).toBe(1)
  })

  it('triggerCompaction captures errors and toggles isCompacting back', async () => {
    const c = useCrossModeCompaction()
    postMock.mockRejectedValueOnce(new Error('compaction-failed'))

    await expect(
      c.triggerCompaction({
        mode: 'skill',
        key: 'k',
        strategy: 'priority_eviction',
      }),
    ).rejects.toThrow('compaction-failed')

    expect(c.isCompacting.value).toBe(false)
    expect(c.lastError.value).toBe('compaction-failed')
    expect(c.lastResult.value).toBe(null)
    expect(c.history.value).toHaveLength(0)
  })

  it('history keeps last 10 results', async () => {
    const c = useCrossModeCompaction()
    for (let i = 0; i < 12; i++) {
      postMock.mockResolvedValueOnce({
        data: {
          success: true,
          mode: 'shared',
          key: `k${i}`,
          strategy: 'sliding_window',
          entries_before: i,
          entries_after: 0,
          tokens_before: 100,
          tokens_after: 0,
          compaction_ratio: 1,
          compacted_at: `2026-09-27T00:00:0${i % 10}Z`,
          error: null,
        },
      })
      await c.triggerCompaction({
        mode: 'shared',
        key: `k${i}`,
        strategy: 'sliding_window',
      })
    }
    expect(c.history.value).toHaveLength(10)
    expect(c.history.value[0].key).toBe('k11') // newest first
  })

  it('clearHistory empties the list', async () => {
    const c = useCrossModeCompaction()
    postMock.mockResolvedValueOnce({
      data: {
        success: true, mode: 'x', key: 'y', strategy: 'sliding_window',
        entries_before: 0, entries_after: 0, tokens_before: 0, tokens_after: 0,
        compaction_ratio: 1, compacted_at: 't', error: null,
      },
    })
    await c.triggerCompaction({ mode: 'x', key: 'y', strategy: 'sliding_window' })
    expect(c.history.value).toHaveLength(1)
    c.clearHistory()
    expect(c.history.value).toHaveLength(0)
  })
})