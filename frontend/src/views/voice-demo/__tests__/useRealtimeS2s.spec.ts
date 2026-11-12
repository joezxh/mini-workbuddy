// 实时 S2S 对话状态机测试（plan Task 7）：stub WebSocket + 音频层全 stub
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

class FakeWS {
  static last: FakeWS | null = null
  sent: string[] = []
  onopen: any = null; onmessage: any = null; onclose: any = null; onerror: any = null
  constructor() { FakeWS.last = this }
  send(d: string) { this.sent.push(d) }
  close() { this.onclose?.() }
  emit(data: any) { this.onmessage?.({ data: JSON.stringify(data) }) }
}
vi.stubGlobal('WebSocket', FakeWS as any)
vi.mock('@/utils/auth', () => ({ getToken: () => 'jwt-x' }))
// 纯工厂：不 importOriginal（真实 voiceDemo.ts 会拉入 request/router 链，node 环境无 window）
vi.mock('@/api/voiceDemo', () => ({
  buildVoiceDemoWsUrl: () => 'ws://fake/ws?token=jwt-x',
  VOICES_BY_LANG: {},
}))
// 音频层全部 stub（状态机测试不依赖真实解码；采集链路测试需要非空 PCM→故 process/encode 透传长度）
vi.mock('@/utils/audioDsp', () => ({
  createStreamingResampler: () => ({ process: (i: Float32Array) => i, flush: () => new Float32Array(0) }),
  encodeFloatToPcm16: (s: Float32Array) => new Int16Array(s.length),
  decodePcm16ToFloat: () => new Float32Array(0),
  createPlaybackChain: () => ({}),
  rmsLevel: () => 0,
}))

import { useRealtimeS2s } from '../composables/useRealtimeS2s'

const B64 = 'AAAA' // base64 静音

describe('useRealtimeS2s 状态机', () => {
  beforeEach(() => { FakeWS.last = null })

  it('connect → session.created → listening；脚本轮次 → responding → listening', async () => {
    const s2s = useRealtimeS2s()
    s2s.connect()
    FakeWS.last!.onopen?.()
    FakeWS.last!.emit({ type: 'session.created', session: { id: 's1' } })
    expect(s2s.state.value).toBe('listening')

    FakeWS.last!.emit({ type: 'input_audio_buffer.speech_started' })
    FakeWS.last!.emit({ type: 'conversation.item.input_audio_transcription.completed', transcript: '现在几点了？' })
    FakeWS.last!.emit({ type: 'response.created', response: {} })
    expect(s2s.state.value).toBe('responding')
    FakeWS.last!.emit({ type: 'response.audio_transcription.delta', delta: '你好' })
    FakeWS.last!.emit({ type: 'response.audio.delta', delta: B64 })
    FakeWS.last!.emit({ type: 'response.done', response: { status: 'completed' } })
    expect(s2s.state.value).toBe('listening')
    const texts = s2s.messages.value.map(m => `${m.role}:${m.text}`)
    expect(texts).toContain('user:现在几点了？')
    expect(texts).toContain('assistant:你好')
    // 事件流已记录双向事件
    expect(s2s.events.value.some(e => e.dir === 'out' && e.type === 'session.update')).toBe(true)
  })

  it('interrupt → response.cancel 出站 + 气泡标记 interrupted', async () => {
    const s2s = useRealtimeS2s()
    s2s.connect(); FakeWS.last!.onopen?.()
    FakeWS.last!.emit({ type: 'session.created', session: {} })
    FakeWS.last!.emit({ type: 'response.created', response: {} })
    FakeWS.last!.emit({ type: 'response.audio_transcription.delta', delta: '长句' })
    s2s.interrupt()
    expect(FakeWS.last!.sent.some(d => JSON.parse(d).type === 'response.cancel')).toBe(true)
    const last = s2s.messages.value.at(-1)!
    expect(last.interrupted).toBe(true)
  })
})

describe('useRealtimeS2s 麦克风采集链路（startMic）', () => {
  afterEach(() => vi.unstubAllGlobals())

  // 模型真实浏览器行为：AudioContext 若在 suspended，AudioWorklet.process 不会运行，
  // 只有 resume() 后才开始向主线程 postMessage 非空 PCM 块（→ onmessage → append）。
  class FakeNode {
    port: { onmessage: ((e: any) => void) | null; close: () => void } = { onmessage: null, close: () => {} }
    disconnect() {}
  }
  class FakeCtx {
    static instances: FakeCtx[] = []
    state = 'suspended'
    sampleRate = 48000
    audioWorklet = { addModule: vi.fn(async () => {}) }
    node: FakeNode | null = null
    resumed = 0
    constructor() { FakeCtx.instances.push(this) }
    createMediaStreamSource() { return { connect: (n: any) => { this.node = n } } }
    async resume() { this.resumed++; this.state = 'running'; this.node?.port.onmessage?.({ data: new Float32Array(160) }) }
    close() { return Promise.resolve() }
  }

  function stubMicEnv(secure = true) {
    FakeCtx.instances = []
    vi.stubGlobal('navigator', secure
      ? { mediaDevices: { getUserMedia: async () => ({ getAudioTracks: () => [{ stop: () => {} }] }) } }
      : {})
    vi.stubGlobal('AudioContext', FakeCtx as any)
    vi.stubGlobal('AudioWorkletNode', FakeNode as any)
  }

  it('suspended 的 AudioContext 应在 startMic 内被 resume，并上行 input_audio_buffer.append', async () => {
    stubMicEnv()
    const s2s = useRealtimeS2s()
    s2s.connect(); FakeWS.last!.onopen?.()
    FakeWS.last!.emit({ type: 'session.created', session: {} })
    await s2s.startMic()
    const ctx = FakeCtx.instances[0]
    expect(ctx.state).toBe('running')   // 现状未 resume → 停在 suspended（红）
    expect(s2s.micActive.value).toBe(true)
    expect(FakeWS.last!.sent.some(d => JSON.parse(d).type === 'input_audio_buffer.append')).toBe(true)
  })

  it('非安全上下文（无 navigator.mediaDevices）startMic 抛出可诊断错误', async () => {
    stubMicEnv(false)
    const s2s = useRealtimeS2s()
    s2s.connect(); FakeWS.last!.onopen?.()
    FakeWS.last!.emit({ type: 'session.created', session: {} })
    // 现状抛 cryptic TypeError（不含「非安全」）→ 红；修复后抛明确提示 → 绿
    await expect(s2s.startMic()).rejects.toThrow(/非安全/)
  })
})
