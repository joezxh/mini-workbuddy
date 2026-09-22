import { describe, it, expect } from 'vitest'
import { useToolCalls } from '../useToolCalls'

describe('useToolCalls confirm flow', () => {
  it('addConfirm 入 pending，update 补全结果', () => {
    const tc = useToolCalls()
    tc.addConfirm({
      confirmId: 'c1',
      name: 'db_query',
      arguments: { q: 'x' },
      timeoutMs: 300000,
    })
    expect(tc.pending.value).toHaveLength(1)
    expect(tc.pending.value[0].status).toBe('pending')
    tc.update('c1', { ok: true, result: 'done' })
    expect(tc.pending.value).toHaveLength(0)
    expect(tc.calls.value.find((c) => c.id === 'c1')?.status).toBe('executed')
  })

  it('clearPending 打断时清空待确认', () => {
    const tc = useToolCalls()
    tc.addConfirm({
      confirmId: 'c2',
      name: 't',
      arguments: {},
      timeoutMs: 1000,
    })
    tc.clearPending()
    expect(tc.pending.value).toHaveLength(0)
  })

  it('update 失败结果落位 rejected', () => {
    const tc = useToolCalls()
    tc.addConfirm({
      confirmId: 'c3',
      name: 't',
      arguments: {},
      timeoutMs: 1000,
    })
    tc.update('c3', { ok: false, error: 'denied' })
    expect(tc.calls.value.find((c) => c.id === 'c3')?.status).toBe('rejected')
  })
})
