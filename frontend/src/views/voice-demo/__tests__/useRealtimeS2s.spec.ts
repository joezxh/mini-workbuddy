// 实时 S2S 对话状态机测试（plan Task 7）：stub WebSocket + 音频层全 stub
import { describe, it, expect, vi, beforeEach } from 'vitest'

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
// 音频层全部 stub（状态机测试不依赖真实解码）
vi.mock('@/utils/audioDsp', () => ({
  createStreamingResampler: () => ({ process: () => new Float32Array(0), flush: () => new Float32Array(0) }),
  encodeFloatToPcm16: () => new Int16Array(0),
  decodePcm16ToFloat: () => new Float32Array(0),
  createPlaybackChain: () => ({}),
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
