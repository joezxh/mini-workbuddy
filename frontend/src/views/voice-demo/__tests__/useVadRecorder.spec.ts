// useVadRecorder 单测：mock @ricky0123/vad-web（node 环境无麦克风/AudioContext）
import { describe, it, expect, vi, beforeEach } from 'vitest'

const micCallbacks: Record<string, (...args: any[]) => any> = {}
// vad-web 0.0.31：MicVAD.new(options) 单参数，回调直接在 options 内
vi.mock('@ricky0123/vad-web', () => ({
  MicVAD: {
    new: vi.fn(async (opts: any) => {
      Object.assign(micCallbacks, opts)
      return { start: vi.fn(async () => {}), pause: vi.fn(async () => {}) }
    }),
  },
}))

describe('useVadRecorder', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    for (const k of Object.keys(micCallbacks)) delete micCallbacks[k]
  })

  it('speech end 时回调分段（startMs/endMs）', async () => {
    const { useVadRecorder } = await import('../composables/useVadRecorder')
    const segments: any[] = []
    const rec = useVadRecorder({ onSegment: (_b, s, e) => segments.push({ s, e }) })
    await rec.start()
    micCallbacks.onSpeechStart?.()
    micCallbacks.onSpeechEnd?.(new Float32Array(16000))
    expect(segments.length).toBe(1)
    expect(segments[0].e).toBeGreaterThanOrEqual(segments[0].s)
    expect(rec.isRecording.value).toBe(true)
  })

  it('floatToWav 产出可解析 WAV 头（RIFF/mono/16bit/16k）', async () => {
    const { floatToWav } = await import('../composables/useVadRecorder')
    const blob = floatToWav(new Float32Array(1600))
    const buf = new DataView(await blob.arrayBuffer())
    expect(String.fromCharCode(buf.getUint8(0), buf.getUint8(1), buf.getUint8(2), buf.getUint8(3))).toBe('RIFF')
    expect(buf.getUint16(22, true)).toBe(1) // nchannels = mono
    expect(buf.getUint32(24, true)).toBe(16000)
    expect(buf.getUint16(34, true)).toBe(16) // sampwidth = 16bit
  })
})
