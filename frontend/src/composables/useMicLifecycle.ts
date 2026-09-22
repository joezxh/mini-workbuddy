/**
 * 麦克风捕获生命周期：只负责媒体流获取与 track 监听，独立于 WS 通道与
 * 播放链——设备切换只重建流，不重连、不打断播放（spec §9.7）。
 *
 * 移植自 qwen-audio-agent `createMicrophoneCaptureLifecycle`：
 * - devicechange → 300ms 去抖重启，并重置重试计数（主动行为不累计退避）
 * - track ended → 立即重启（USB 拔出/被抢占）
 * - track mute → 1.5s 宽限后仍 muted 才重启；unmute 取消（过滤瞬时静音）
 * - 可恢复错误 → 500ms/1s/2s/4s 四次退避；耗尽转 unavailable
 * - 不可恢复错误（NotAllowedError 等）→ 直接 unavailable，不重试
 * - generation 代际仲裁：迟到的 acquire 结果直接 release 丢弃
 */
export interface MicState {
  state: 'starting' | 'ready' | 'recovering' | 'unavailable'
  reason: string
  error?: unknown
  recoverable?: boolean
}

const FATAL_ERRORS = ['NotAllowedError', 'NotSupportedError', 'SecurityError', 'TypeError']

/** 错误分类（供 UI 文案） */
export function classifyMicError(error: unknown): string {
  const name = String((error as any)?.name || '')
  const message = String((error as any)?.message || '')
  if (
    ['NotAllowedError', 'SecurityError'].includes(name) ||
    /permission\s+denied|not\s+allowed/i.test(message)
  )
    return 'permission_denied'
  if (name === 'NotFoundError') return 'device_missing'
  if (name === 'NotReadableError') return 'device_unavailable'
  if (name === 'NotSupportedError') return 'unsupported'
  return 'unknown'
}

interface MicCapture {
  track?: MediaStreamTrack
  media?: MediaStream
  close?: () => void
  handleEnded?: () => void
  handleMute?: () => void
  handleUnmute?: () => void
}

interface MicLifecycleOpts {
  acquire: (ctx: { reason: string; generation: number }) => Promise<MicCapture>
  release: (capture: MicCapture) => void
  onState: (s: MicState) => void
  /** 代际验证通过的新流就绪（消费方据此重连采集链，如 WebAudio source） */
  onCapture?: (capture: MicCapture) => void
  retryDelays?: number[]
  debounceMs?: number
  muteGraceMs?: number
  schedule?: (cb: () => void, ms: number) => any
  cancel?: (timer: any) => void
  mediaDevices?: {
    addEventListener?: (n: string, f: EventListenerOrEventListenerObject) => void
    removeEventListener?: (n: string, f: EventListenerOrEventListenerObject) => void
  }
}

export function createMicLifecycle(opts: MicLifecycleOpts) {
  const retryDelays = opts.retryDelays ?? [500, 1000, 2000, 4000]
  const debounceMs = opts.debounceMs ?? 300
  const muteGraceMs = opts.muteGraceMs ?? 1500
  const schedule = opts.schedule ?? ((cb: () => void, ms: number) => setTimeout(cb, ms))
  const cancel = opts.cancel ?? ((t: any) => clearTimeout(t))

  let running = false
  let generation = 0
  let current: MicCapture | null = null
  let restartTimer: any = null
  let retryTimer: any = null
  let muteTimer: any = null
  let retryAttempt = 0

  const trackOf = (c: MicCapture | null) =>
    c?.track || (c?.media as MediaStream | undefined)?.getAudioTracks?.()[0] || null

  const clearTimer = (kind: 'restart' | 'retry' | 'mute') => {
    const t = kind === 'restart' ? restartTimer : kind === 'retry' ? retryTimer : muteTimer
    if (t !== null) cancel(t)
    if (kind === 'restart') restartTimer = null
    else if (kind === 'retry') retryTimer = null
    else muteTimer = null
  }

  const detach = () => {
    const c = current
    if (!c) return
    current = null
    clearTimer('mute')
    const track = trackOf(c)
    track?.removeEventListener?.('ended', c.handleEnded as EventListener)
    track?.removeEventListener?.('mute', c.handleMute as EventListener)
    track?.removeEventListener?.('unmute', c.handleUnmute as EventListener)
    opts.release(c)
  }

  const installListeners = (c: MicCapture) => {
    const track = trackOf(c)
    if (!track?.addEventListener) return
    c.handleEnded = () => requestRestart('track-ended', 0)
    c.handleMute = () => {
      clearTimer('mute')
      muteTimer = schedule(() => {
        muteTimer = null
        if (track.muted !== false) requestRestart('track-muted', 0)
      }, muteGraceMs)
    }
    c.handleUnmute = () => clearTimer('mute')
    track.addEventListener('ended', c.handleEnded as EventListener)
    track.addEventListener('mute', c.handleMute as EventListener)
    track.addEventListener('unmute', c.handleUnmute as EventListener)
  }

  const replaceCapture = async (reason: string) => {
    if (!running) return
    clearTimer('restart')
    clearTimer('retry')
    const gen = ++generation
    detach()
    opts.onState({ state: reason === 'initial' ? 'starting' : 'recovering', reason })
    try {
      const capture = await opts.acquire({ reason, generation: gen })
      if (!running || gen !== generation) {
        opts.release(capture)
        return
      }
      current = capture
      retryAttempt = 0
      installListeners(capture)
      opts.onCapture?.(capture)
      opts.onState({ state: 'ready', reason })
    } catch (error) {
      if (!running || gen !== generation) return
      const recoverable = !FATAL_ERRORS.includes(String((error as any)?.name || ''))
      const delay = recoverable ? retryDelays[retryAttempt] : undefined
      retryAttempt += 1
      const retrying = recoverable && Number.isFinite(delay as number)
      opts.onState({
        state: retrying ? 'recovering' : 'unavailable',
        reason,
        error,
        recoverable,
      })
      if (retrying) {
        retryTimer = schedule(() => {
          retryTimer = null
          void replaceCapture('retry')
        }, delay as number)
      }
    }
  }

  function requestRestart(reason = 'devicechange', delay = debounceMs) {
    if (!running) return
    if (reason === 'devicechange') retryAttempt = 0
    clearTimer('restart')
    clearTimer('retry')
    restartTimer = schedule(() => {
      restartTimer = null
      void replaceCapture(reason)
    }, delay)
  }

  const handleDeviceChange = () => requestRestart('devicechange')

  return {
    start() {
      if (running) return
      running = true
      opts.mediaDevices?.addEventListener?.('devicechange', handleDeviceChange)
      void replaceCapture('initial')
    },
    stop() {
      if (!running) return
      running = false
      generation += 1
      opts.mediaDevices?.removeEventListener?.('devicechange', handleDeviceChange)
      clearTimer('restart')
      clearTimer('retry')
      clearTimer('mute')
      detach()
    },
    restart(reason = 'manual') {
      retryAttempt = 0
      requestRestart(reason, 0)
    },
  }
}
