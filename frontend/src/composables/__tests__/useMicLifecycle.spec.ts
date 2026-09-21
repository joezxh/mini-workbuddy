import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createMicLifecycle } from '../useMicLifecycle'

describe('useMicLifecycle', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  function makeEnv() {
    const states: any[] = []
    const track = makeTrack()
    let stream: any = { track }
    const acquire = vi.fn(async () => stream)
    const release = vi.fn()
    function makeTrack() {
      const listeners: Record<string, Function[]> = {}
      return {
        muted: false,
        addEventListener: (n: string, f: Function) => {
          ;(listeners[n] ??= []).push(f)
        },
        removeEventListener: () => {},
        __emit: (n: string) => (listeners[n] || []).forEach((f) => f()),
      }
    }
    const mediaDevices = {
      listeners: {} as Record<string, Function[]>,
      addEventListener(n: string, f: Function) {
        ;(this.listeners[n] ??= []).push(f)
      },
      removeEventListener() {},
      __emitDeviceChange() {
        ;(this.listeners['devicechange'] || []).forEach((f) => f())
      },
    }
    const lc = createMicLifecycle({
      acquire,
      release,
      onState: (s: any) => states.push(s),
      schedule: (cb: () => void, ms: number) => setTimeout(cb, ms),
      cancel: (t: any) => clearTimeout(t),
      mediaDevices,
    })
    return { lc, states, acquire, release, track, mediaDevices }
  }

  it('track ended 立即重启', async () => {
    const { lc, acquire, track } = makeEnv()
    lc.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(acquire).toHaveBeenCalledTimes(1)
    track.__emit('ended')
    await vi.advanceTimersByTimeAsync(0)
    expect(acquire).toHaveBeenCalledTimes(2)
    lc.stop()
  })

  it('mute 宽限内 unmute 不重启', async () => {
    const { lc, acquire, track } = makeEnv()
    lc.start()
    await vi.advanceTimersByTimeAsync(0)
    track.__emit('mute')
    await vi.advanceTimersByTimeAsync(1000)
    track.muted = false
    track.__emit('unmute')
    await vi.advanceTimersByTimeAsync(1000)
    expect(acquire).toHaveBeenCalledTimes(1)
    lc.stop()
  })

  it('mute 超宽限触发重启', async () => {
    const { lc, acquire, track } = makeEnv()
    lc.start()
    await vi.advanceTimersByTimeAsync(0)
    track.muted = true
    track.__emit('mute')
    await vi.advanceTimersByTimeAsync(1600)
    expect(acquire).toHaveBeenCalledTimes(2)
    lc.stop()
  })

  it('不可恢复错误直接 unavailable', async () => {
    const { lc, states, acquire } = makeEnv()
    acquire.mockRejectedValueOnce(
      Object.assign(new Error('denied'), { name: 'NotAllowedError' }),
    )
    lc.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(states.at(-1).state).toBe('unavailable')
    expect(states.at(-1).recoverable).toBe(false)
    lc.stop()
  })

  it('可恢复错误按 500ms 退避重试', async () => {
    const { lc, acquire } = makeEnv()
    acquire.mockRejectedValueOnce(
      Object.assign(new Error('busy'), { name: 'NotReadableError' }),
    )
    lc.start()
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(500)
    expect(acquire).toHaveBeenCalledTimes(2)
    lc.stop()
  })

  it('devicechange 重置重试计数并重启', async () => {
    const { lc, acquire, mediaDevices } = makeEnv()
    // 一次可恢复失败，消耗一次重试预算
    acquire.mockRejectedValueOnce(
      Object.assign(new Error('busy'), { name: 'NotReadableError' }),
    )
    lc.start()
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(500)
    expect(acquire).toHaveBeenCalledTimes(2)
    // devicechange（300ms 去抖）→ 计数重置后仍执行重启
    mediaDevices.__emitDeviceChange()
    await vi.advanceTimersByTimeAsync(300)
    expect(acquire).toHaveBeenCalledTimes(3)
    lc.stop()
  })
})
