// useVadRecorder 单测：mock @ricky0123/vad-web（node 环境无麦克风/AudioContext）
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const micCallbacks: Record<string, (...args: any[]) => any> = {}
const vadInstances: { start: ReturnType<typeof vi.fn>; pause: ReturnType<typeof vi.fn> }[] = []
// vad-web 0.0.31：MicVAD.new(options) 单参数，回调直接在 options 内
vi.mock('@ricky0123/vad-web', () => ({
  MicVAD: {
    new: vi.fn(async (opts: any) => {
      Object.assign(micCallbacks, opts)
      const inst = { start: vi.fn(async () => {}), pause: vi.fn(async () => {}) }
      vadInstances.push(inst)
      return inst
    }),
  },
}))

describe('useVadRecorder', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    for (const k of Object.keys(micCallbacks)) delete micCallbacks[k]
    vadInstances.length = 0
    // start() 前置安全上下文检查在 node 环境需 stub navigator.mediaDevices
    vi.stubGlobal('navigator', { mediaDevices: { getUserMedia: async () => ({}) } })
  })
  afterEach(() => vi.unstubAllGlobals())

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

  it('语音态帧累计达 maxSpeechMs → 强制收束（pause 交段 + start 继续）', async () => {
    const { useVadRecorder } = await import('../composables/useVadRecorder')
    const rec = useVadRecorder({ onSegment: () => {}, maxSpeechMs: 1000 })
    await rec.start()
    const vad = vadInstances.at(-1)!
    micCallbacks.onSpeechStart?.()
    // 512 样本 @16k = 32ms/帧；isSpeech=1 计语音态，40 帧 ≈ 1280ms > 1000ms
    const frame = new Float32Array(512)
    for (let i = 0; i < 40; i++) micCallbacks.onFrameProcessed?.({ isSpeech: 1, notSpeech: 0 }, frame)
    await vi.waitFor(() => {
      expect(vad.pause).toHaveBeenCalled() // 交段（真实库中 pause 触发 onSpeechEnd）
      expect(vad.start).toHaveBeenCalledTimes(2) // start 初次 + 强制收束后重启
    })
  })

  it('静音帧不计入强制收束时长', async () => {
    const { useVadRecorder } = await import('../composables/useVadRecorder')
    const rec = useVadRecorder({ onSegment: () => {}, maxSpeechMs: 1000 })
    await rec.start()
    const vad = vadInstances.at(-1)!
    micCallbacks.onSpeechStart?.()
    const frame = new Float32Array(512)
    for (let i = 0; i < 100; i++) micCallbacks.onFrameProcessed?.({ isSpeech: 0.2, notSpeech: 0.8 }, frame)
    expect(vad.pause).not.toHaveBeenCalled()
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
