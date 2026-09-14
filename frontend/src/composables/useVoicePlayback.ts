/**
 * 语音下行播放 Composable（语音质量修复方案 A）
 *
 * 职责（对标 qwen-audio-agent web/src/realtime/useRealtimeVoice.js 的播放调度）：
 * - 连续时间轴调度：cursor = max(ctx.currentTime + lead, cursor)，杜绝 delta
 *   重叠播放（咔哒声）与缝隙断裂
 * - 抖动缓冲：小 delta 合并（~100ms）后建 Buffer，减少源数量与 underrun
 * - 采样域 DSP：去直流 + 噪声门（静音段嘶声压到 ≤ -60dBFS）
 * - 节点链：HPF/LPF/压缩器/补偿增益（createPlaybackChain），全部运行于 48kHz ctx
 * - 打断：立即停掉所有未播 source 并复位时间轴
 */
import {
  DcBlocker,
  NoiseGate,
  PlaybackChain,
  createPlaybackChain,
  decodePcm16ToFloat,
  AUDIO_DSP_CONFIG,
} from '@/utils/audioDsp'

export interface VoicePlaybackOptions {
  /** 惰性取 AudioContext（连接前可能尚未创建） */
  getContext: () => AudioContext | null
  /** 下行 PCM 采样率（voice.ready.output_sample_rate） */
  getSampleRate: () => number
  /** 电平回调（波形条），0..1 */
  onLevel?: (peak: number) => void
}

interface PendingChunk {
  samples: Float32Array
  sampleRate: number
}

const BATCH_SECONDS = 0.1
const BATCH_DELAY_MS = 60

export function useVoicePlayback(options: VoicePlaybackOptions) {
  let chain: PlaybackChain | null = null
  let chainContext: AudioContext | null = null
  let gate: NoiseGate | null = null
  let gateSampleRate = 0
  const dcBlocker = new DcBlocker()

  let sources: AudioBufferSourceNode[] = []
  let cursor = 0
  let pending: PendingChunk[] = []
  let pendingSeconds = 0
  let flushTimer: number | null = null

  function ensureChain(ctx: AudioContext): PlaybackChain {
    if (chainContext !== ctx) {
      chain?.dispose()
      chain = createPlaybackChain(ctx, ctx.destination)
      chainContext = ctx
    }
    return chain
  }

  function ensureGate(sampleRate: number): NoiseGate {
    if (gateSampleRate !== sampleRate) {
      gate = new NoiseGate({
        sampleRate,
        thresholdDb: AUDIO_DSP_CONFIG.playback.gateThresholdDb,
        attackMs: AUDIO_DSP_CONFIG.playback.gateAttackMs,
        releaseMs: AUDIO_DSP_CONFIG.playback.gateReleaseMs,
      })
      gateSampleRate = sampleRate
    }
    return gate
  }

  /** 将一批待播样本调度到连续时间轴上 */
  function schedule(samples: Float32Array, sampleRate: number): void {
    const ctx = options.getContext()
    if (!ctx || !samples.length) return
    if (ctx.state === 'suspended') void ctx.resume()

    const audioChain = ensureChain(ctx)
    const buffer = ctx.createBuffer(1, samples.length, sampleRate)
    buffer.copyToChannel(samples, 0)
    const source = ctx.createBufferSource()
    source.buffer = buffer
    source.connect(audioChain.input)

    const start = Math.max(ctx.currentTime + AUDIO_DSP_CONFIG.scheduleLeadSeconds, cursor)
    cursor = start + buffer.duration
    sources.push(source)
    source.onended = () => {
      sources = sources.filter((item) => item !== source)
    }
    source.start(start)
  }

  function flush(): void {
    if (flushTimer !== null) {
      clearTimeout(flushTimer)
      flushTimer = null
    }
    if (!pending.length) return
    // 合并同采样率的连续 chunk，减少 BufferSource 数量
    const groups: PendingChunk[] = []
    for (const chunk of pending) {
      const last = groups[groups.length - 1]
      if (last && last.sampleRate === chunk.sampleRate) {
        const merged = new Float32Array(last.samples.length + chunk.samples.length)
        merged.set(last.samples)
        merged.set(chunk.samples, last.samples.length)
        last.samples = merged
      } else {
        groups.push({ samples: new Float32Array(chunk.samples), sampleRate: chunk.sampleRate })
      }
    }
    pending = []
    pendingSeconds = 0
    for (const group of groups) schedule(group.samples, group.sampleRate)
  }

  function scheduleFlush(): void {
    if (flushTimer !== null) return
    flushTimer = window.setTimeout(flush, BATCH_DELAY_MS)
  }

  /**
   * 入队一段下行 PCM（二进制帧或 base64 字符串）。
   * sampleRate 缺省时取 options.getSampleRate()（voice.ready 协商值）。
   */
  function push(pcm: ArrayBuffer | Uint8Array | string, sampleRate?: number): void {
    if (!pcm) return
    let bytes: Uint8Array
    if (typeof pcm === 'string') {
      const binary = atob(pcm)
      bytes = new Uint8Array(binary.length)
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
    } else if (pcm instanceof Uint8Array) {
      bytes = pcm
    } else {
      bytes = new Uint8Array(pcm)
    }
    if (bytes.byteLength < 2) return

    const rate = sampleRate || options.getSampleRate() || 24000
    const samples = decodePcm16ToFloat(bytes)
    dcBlocker.process(samples)
    ensureGate(rate).process(samples)

    let peak = 0
    for (let i = 0; i < samples.length; i++) {
      const abs = Math.abs(samples[i])
      if (abs > peak) peak = abs
    }
    options.onLevel?.(peak)

    pending.push({ samples, sampleRate: rate })
    pendingSeconds += samples.length / rate
    if (pendingSeconds >= BATCH_SECONDS) flush()
    else scheduleFlush()
  }

  /** 打断：立即停止所有未播 source，复位时间轴（丢弃已排程未播内容） */
  function interrupt(): void {
    flush()
    for (const source of sources) {
      source.onended = null
      try {
        source.stop()
      } catch {
        /* 已结束的 source stop 会抛错，忽略 */
      }
      source.disconnect()
    }
    sources = []
    const ctx = options.getContext()
    cursor = ctx ? ctx.currentTime : 0
  }

  /** 重连/换会话时复位全部状态（时间轴、DSP 状态、待播队列） */
  function reset(): void {
    interrupt()
    pending = []
    pendingSeconds = 0
    dcBlocker.reset()
    gate?.reset()
    options.onLevel?.(0)
  }

  return { push, interrupt, reset }
}
