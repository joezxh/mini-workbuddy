import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSandboxStore } from '../sandbox'

describe('useSandboxStore 游标', () => {
  beforeEach(() => setActivePinia(createPinia()))
  it('默认游标', () => {
    const s = useSandboxStore()
    expect(s.sceneId).toBeNull(); expect(s.tick).toBe(0); expect(s.execMode).toBe('auto')
  })
  it('setCursor 局部更新', () => {
    const s = useSandboxStore()
    s.setCursor({ sceneId: 7, branchId: 3, tick: 5, execMode: 'replay' })
    expect(s.sceneId).toBe(7); expect(s.branchId).toBe(3); expect(s.tick).toBe(5); expect(s.execMode).toBe('replay')
  })
  it('reset 清空', () => {
    const s = useSandboxStore(); s.setCursor({ sceneId: 7, tick: 5 }); s.reset()
    expect(s.sceneId).toBeNull(); expect(s.tick).toBe(0)
  })
})
