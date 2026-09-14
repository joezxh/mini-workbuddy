/**
 * 音频 DSP 工具集（语音质量修复方案 A：根因修复 + 轻量 DSP 播放链）
 *
 * 设计文档：docs/superpowers/specs/2026-09-14-voice-audio-quality-design.md
 * 对标实现：qwen-audio-agent web/src/realtime/audio.js
 *
 * 本模块只包含可脱离 DOM/WebAudio 单测的纯函数与轻量类；
 * WebAudio 节点链的组装见 createPlaybackChain（仅依赖 AudioContext 参数）。
 */

/** 全部 DSP 参数集中于此：一行即可切换电话带宽（300–3400Hz）等配置 */
export const AUDIO_DSP_CONFIG = {
  /** AudioContext 目标采样率（浏览器不支持时回退设备默认，以其为重采样源率） */
  contextSampleRate: 48000,
  playback: {
    /** 下行噪声门：静音段（嘶声/底噪）压到 ≤ -60dBFS */
    gateThresholdDb: -60,
    gateAttackMs: 5,
    gateReleaseMs: 120,
    /** 高通截止：切隆隆声/工频哼声（电话带宽方案改为 300） */
    highpassHz: 80,
    /** 低通截止：切高频嘶声（电话带宽方案改为 3400） */
    lowpassHz: 8000,
    /** 4 阶 Butterworth（每侧两级 biquad 级联），Q 值对 */
    butterworthQ: [0.541, 1.307],
    compressor: { threshold: -12, knee: 6, ratio: 3, attack: 0.003, release: 0.25 },
    /** 压缩器后的增益补偿（dB） */
    makeupGainDb: 2,
  },
  capture: {
    /** 上行软噪声门：只衰减房间底噪，不改变语音包络（-50dBFS） */
    gateThresholdDb: -50,
    gateAttackMs: 5,
    gateReleaseMs: 120,
    /** ScriptProcessor 采集帧长 */
    bufferSize: 2048,
  },
  /** 播放调度：WebAudio 时间轴提前量（秒） */
  scheduleLeadSeconds: 0.02,
} as const

/** PCM16（小端）字节流 → Float32（-1..1） */
export function decodePcm16ToFloat(bytes: Uint8Array): Float32Array {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const count = Math.floor(bytes.byteLength / 2)
  const out = new Float32Array(count)
  for (let i = 0; i < count; i++) out[i] = view.getInt16(i * 2, true) / 0x8000
  return out
}

/** Float32 → PCM16（小端，clamp 到 [-1,1]） */
export function encodeFloatToPcm16(samples: Float32Array): Int16Array {
  const out = new Int16Array(samples.length)
  for (let i = 0; i < samples.length; i++) {
    const clamped = Math.max(-1, Math.min(1, samples[i]))
    out[i] = Math.round(clamped * 0x7fff)
  }
  return out
}

/**
 * 一阶直流阻断器（DC blocker）：y[n] = x[n] - x[n-1] + R·y[n-1]
 * 跨 buffer 保持状态，避免逐 buffer 独立处理引入边界跳变。
 */
export class DcBlocker {
  private readonly radius: number
  private prevIn = 0
  private prevOut = 0

  constructor(radius = 0.995) {
    this.radius = radius
  }

  reset(): void {
    this.prevIn = 0
    this.prevOut = 0
  }

  /** 原地处理 */
  process(samples: Float32Array): void {
    for (let i = 0; i < samples.length; i++) {
      const x = samples[i]
      const y = x - this.prevIn + this.radius * this.prevOut
      samples[i] = y
      this.prevIn = x
      this.prevOut = y
    }
  }
}

/**
 * 样本域软噪声门（包络跟随 + 平滑增益，无硬切click）。
 * 状态跨 buffer 保持：静音段持续输出被压制到门限以下，
 * 语音段按 attack/release 平滑开合，不截字头字尾。
 */
export class NoiseGate {
  /** 创建时的采样率（供外部判断是否需要重建） */
  readonly sampleRate: number
  private readonly threshold: number
  private readonly attackCoef: number
  private readonly releaseCoef: number
  private envelope = 0
  private gain = 0

  constructor(options: {
    sampleRate: number
    thresholdDb: number
    attackMs: number
    releaseMs: number
  }) {
    this.sampleRate = options.sampleRate
    this.threshold = 10 ** (options.thresholdDb / 20)
    const frames = (ms: number) => Math.max(1, (options.sampleRate * ms) / 1000)
    this.attackCoef = Math.exp(-1 / frames(options.attackMs))
    this.releaseCoef = Math.exp(-1 / frames(options.releaseMs))
  }

  reset(): void {
    this.envelope = 0
    this.gain = 0
  }

  /** 原地处理：门开时样本保持原样，门关时增益平滑衰减到 0 */
  process(samples: Float32Array): void {
    for (let i = 0; i < samples.length; i++) {
      const level = Math.abs(samples[i])
      // 包络跟随：快攻慢放
      const coef = level > this.envelope ? this.attackCoef : this.releaseCoef
      this.envelope = coef * this.envelope + (1 - coef) * level
      // 目标增益：超门限全开、低于门限全关；增益本身按攻放时间平滑
      const targetGain = this.envelope > this.threshold ? 1 : 0
      const smooth = targetGain > this.gain ? this.attackCoef : this.releaseCoef
      this.gain = smooth * this.gain + (1 - smooth) * targetGain
      samples[i] *= this.gain
    }
  }
}

/**
 * 流式线性插值重采样：跨 chunk 保留插值相位（逐字节移植 qwen-audio-agent
 * web/src/realtime/audio.js 的 createStreamingResampler），
 * 避免逐 chunk 独立重采样的相位断裂导致的周期性噪声。
 */
export function createStreamingResampler() {
  let inputRate = 0
  let outputRate = 0
  let pending = new Float32Array(0)
  let position = 0
  let totalInput = 0
  let outputCount = 0

  const reset = () => {
    inputRate = 0
    outputRate = 0
    pending = new Float32Array(0)
    position = 0
    totalInput = 0
    outputCount = 0
  }

  const emit = (final: boolean): Float32Array => {
    const ratio = inputRate / outputRate
    const targetCount = Math.max(1, Math.round(totalInput / ratio))
    const values: number[] = []
    while (position + 1 < pending.length && outputCount < targetCount) {
      const before = Math.floor(position)
      const fraction = position - before
      const after = Math.min(pending.length - 1, before + 1)
      values.push(pending[before] * (1 - fraction) + pending[after] * fraction)
      position += ratio
      outputCount += 1
    }
    if (final) {
      while (position < pending.length && outputCount < targetCount) {
        const before = Math.floor(position)
        const fraction = position - before
        values.push(pending[before] * (1 - fraction) + pending[after] * fraction)
        position += ratio
        outputCount += 1
      }
    }
    const consumed = Math.min(pending.length, Math.floor(position))
    if (consumed > 0) {
      pending = pending.slice(consumed)
      position -= consumed
    }
    return Float32Array.from(values)
  }

  return {
    reset,
    process(input: Float32Array, from: number, to: number): Float32Array {
      if (!input.length) return new Float32Array(0)
      if (from !== inputRate || to !== outputRate) {
        reset()
        inputRate = from
        outputRate = to
      }
      if (from === to) return input
      const merged = new Float32Array(pending.length + input.length)
      merged.set(pending)
      merged.set(input, pending.length)
      pending = merged
      totalInput += input.length
      return emit(false)
    },
    flush(): Float32Array {
      if (!inputRate || !outputRate || inputRate === outputRate) {
        reset()
        return new Float32Array(0)
      }
      const out = emit(true)
      reset()
      return out
    },
  }
}

/** 播放链各节点的句柄（dispose 时统一断开） */
export interface PlaybackChain {
  /** 源 BufferSource 应连接到该节点 */
  input: AudioNode
  dispose(): void
}

type BiquadCtor = AudioContext | { createBiquadFilter: AudioContext['createBiquadFilter'] }

/**
 * 组装下行播放处理链（在 AudioContext 上创建节点）：
 *   source → HPF(80Hz, 4阶) → LPF(8kHz, 4阶) → 压缩器(-12dB, 3:1) → 补偿增益 → destination
 *
 * 每侧两级 biquad 级联成 4 阶 Butterworth（24dB/oct），
 * 对带外哼声/嘶声的抑制量满足单测「SNR 提升 ≥15dB」的验证标准。
 */
export function createPlaybackChain(ctx: BiquadCtor, destination: AudioNode): PlaybackChain {
  const { playback } = AUDIO_DSP_CONFIG
  const created: AudioNode[] = []

  const biquad = (type: BiquadFilterType, freq: number, q: number): BiquadFilterNode => {
    const node = ctx.createBiquadFilter()
    node.type = type
    node.frequency.value = freq
    node.Q.value = q
    created.push(node)
    return node
  }

  const [q1, q2] = playback.butterworthQ
  const hpf1 = biquad('highpass', playback.highpassHz, q1)
  const hpf2 = biquad('highpass', playback.highpassHz, q2)
  const lpf1 = biquad('lowpass', playback.lowpassHz, q1)
  const lpf2 = biquad('lowpass', playback.lowpassHz, q2)

  const compressor = ctx.createDynamicsCompressor()
  compressor.threshold.value = playback.compressor.threshold
  compressor.knee.value = playback.compressor.knee
  compressor.ratio.value = playback.compressor.ratio
  compressor.attack.value = playback.compressor.attack
  compressor.release.value = playback.compressor.release
  created.push(compressor)

  const makeup = ctx.createGain()
  makeup.gain.value = 10 ** (playback.makeupGainDb / 20)
  created.push(makeup)

  hpf1.connect(hpf2)
  hpf2.connect(lpf1)
  lpf1.connect(lpf2)
  lpf2.connect(compressor)
  compressor.connect(makeup)
  makeup.connect(destination)

  return {
    input: hpf1,
    dispose: () => {
      for (const node of created) node.disconnect()
    },
  }
}

/** 计算 RMS 分贝（dBFS），空/静音返回 -Infinity 语义上按 -120 处理由调用方决定 */
export function rmsDb(samples: Float32Array): number {
  if (!samples.length) return -120
  let sum = 0
  for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i]
  const rms = Math.sqrt(sum / samples.length)
  return rms <= 1e-10 ? -120 : 20 * Math.log10(rms)
}
