import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/utils/request', () => {
  const post = vi.fn()
  const get = vi.fn()
  return { default: { post, get } }
})

import api from '@/utils/request'
import {
  getContextEntries,
  getCrossModeBreakdown,
  listFinalizeStrategies,
} from '../aiContext'

const postMock = api.post as unknown as ReturnType<typeof vi.fn>
const getMock = api.get as unknown as ReturnType<typeof vi.fn>

describe('aiContext cross-mode API (PR-3 Task 10)', () => {
  beforeEach(() => {
    postMock.mockReset()
    getMock.mockReset()
  })

  it('getContextEntries POSTs /entries and unwraps .data', async () => {
    const payload = {
      session_id: 1,
      allow_cross_mode: true,
      include_tags: ['x'],
      source_mode: 'skill',
      limit: 10,
    }
    // 后端直接返回 {items, total},axios 拦截器再解一次包成 response.data
    postMock.mockResolvedValueOnce({
      items: [{ id: 1, source_mode: 'skill' }],
      total: 1,
    })

    const res = await getContextEntries(payload)
    expect(postMock).toHaveBeenCalledWith(
      '/api/v1/ai/context/entries',
      payload,
    )
    // 经拦截器解包后,实际 res 形如 {items, total}
    expect((res as any).items).toEqual([{ id: 1, source_mode: 'skill' }])
    expect((res as any).total).toBe(1)
  })

  it('getCrossModeBreakdown POSTs /breakdown with session_id', async () => {
    postMock.mockResolvedValueOnce({
      items: [{ source_mode: 'agent', entry_count: 4 }],
    })
    const res = await getCrossModeBreakdown({ session_id: 99 })
    expect(postMock).toHaveBeenCalledWith(
      '/api/v1/ai/context/breakdown',
      { session_id: 99 },
    )
    expect((res as any).items).toEqual([{ source_mode: 'agent', entry_count: 4 }])
  })

  it('listFinalizeStrategies GETs /strategies and returns 9 modes', async () => {
    const nineModes = [
      'general', 'react', 'thinking', 'deep_research', 'skill',
      'agent', 'team', 'scheduled', 'shared',
    ].map((m) => ({
      session_type: m,
      source_mode: m,
      priority: 3,
      ttl_hours: 168,
      write_mem0: true,
      is_cross_mode_accessible: false,
      display_label: m,
      display_color: 'blue',
    }))
    getMock.mockResolvedValueOnce({ strategies: nineModes })

    const res = await listFinalizeStrategies()
    expect(getMock).toHaveBeenCalledWith('/api/v1/ai/context/strategies')
    expect((res as any).strategies).toHaveLength(9)
  })

  it('preserves existing public exports (regression check)', async () => {
    // Re-import dynamically so we don't have to import the whole module here.
    const mod = await import('../aiContext')
    expect(typeof mod.getContextStats).toBe('function')
    expect(typeof mod.getStatsForSessions).toBe('function')
    expect(typeof mod.retrieveContext).toBe('function')
    expect(typeof mod.triggerCompaction).toBe('function')
    expect(typeof mod.getContextEntries).toBe('function')
    expect(typeof mod.getCrossModeBreakdown).toBe('function')
    expect(typeof mod.listFinalizeStrategies).toBe('function')
  })
})