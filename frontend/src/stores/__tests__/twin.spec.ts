import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const callCounts: Record<string, number> = {}

const datum = (wid: number, over = {}) => ({
  widget_id: wid, widget_key: `w${wid}`, title: `T${wid}`, query_id: 1,
  state: 'ok', reason: null, result_shape: 'kpi', columns: ['v'],
  data: { value: 1, records: [{ v: 1 }] }, row_count: 1, truncated: false,
  masked_fields: [], error: null, cached: false, updated_at: 'x', ...over,
})

// 计划注（:605）授权：mock 工厂按 URL 模式返回样本；各条断言意图不弱化
vi.mock('@/utils/request', () => {
  const respond = (url: string): unknown => {
    if (url.includes('/pages/') && url.endsWith('/data'))
      return { page_id: 7, card_id: 9, runtime_state: 'live', refresh: null,
               collected_at: 'x', count: 2,
               items: [datum(1), datum(2, { state: 'empty', reason: 'zero_rows' })] }
    if (/\/widgets\/\d+\/data$/.test(url)) return datum(1)   // T9：重试回一条 ok datum
    if (url.endsWith('/pages')) return []                    // openCard(99) → 空页面列表
    if (/\/cards\/\d+$/.test(url)) return { id: 99, name: 'c', access: 'owner' }
    return {}
  }
  const mk = (key: string) => (...args: unknown[]) => {
    callCounts[key] = (callCounts[key] ?? 0) + 1
    return Promise.resolve(respond(String(args[0])))
  }
  return { default: { get: mk('get'), post: mk('post'), patch: mk('patch'), delete: mk('delete') } }
})

import { useTwinStore } from '../twin'

beforeEach(() => {
  setActivePinia(createPinia())
  for (const k of Object.keys(callCounts)) delete callCounts[k]
})

describe('stores/twin', () => {
  it('W8：refreshPage 只发 1 次 pages/{id}/data 且按 widget_id 填充', async () => {
    const s = useTwinStore()
    s.activePageId = 7
    await s.refreshPage()
    expect(callCounts['post']).toBe(1)
    expect(s.pageData[1].state).toBe('ok')
    expect(s.pageData[2].reason).toBe('zero_rows')
  })

  it('W7：默认 10s 档；applyRefreshCfg({interval:30000}) 改档；off 停表', async () => {
    vi.useFakeTimers()
    const s = useTwinStore()
    s.activePageId = 7
    s.startScheduler()
    expect(s.intervalMs).toBe(10000)
    s.applyRefreshCfg({ interval: 30000 })
    expect(s.intervalMs).toBe(30000)
    s.stopScheduler(); s.applyRefreshCfg({ interval: 0 }); s.startScheduler()
    expect(vi.getTimerCount()).toBe(0)
    s.stopScheduler()
    vi.useRealTimers()
  })

  it('W7：隐藏标签页暂停，回前台立即刷一次并重启定时器', async () => {
    const s = useTwinStore()
    s.activePageId = 7
    s.startScheduler()
    s.onVisibility(true)                     // hidden → 停表
    s.onVisibility(false)                    // visible → 立刷一次
    await vi.waitFor(() => expect(callCounts['post']).toBe(1))
    s.stopScheduler()
  })

  it('W11 旁证：切卡即弃 pageData，且无 storage 写入', async () => {
    const setItem = vi.fn()
    ;(globalThis as any).localStorage = { setItem, getItem: vi.fn() }
    const s = useTwinStore()
    s.pageData = { 1: datum(1) as any }
    await s.openCard(99)
    expect(Object.keys(s.pageData)).toHaveLength(0)
    expect(setItem).not.toHaveBeenCalled()
  })

  it('retryWidget 走 T9 且只更新该组件', async () => {
    const s = useTwinStore()
    s.pageData = { 1: datum(1, { state: 'error' }) as any, 2: datum(2) as any }
    await s.retryWidget(1)
    expect(callCounts['get']).toBe(1)
    expect(s.pageData[1].state).toBe('ok')
  })
})
