/**
 * audioDsp 单元测试（语音质量修复方案 A 验证标准）
 *
 * 设计文档：docs/superpowers/specs/2026-09-14-voice-audio-quality-design.md §3.1
 * 运行：npm test（Node 24 原生类型剥离 + 内置 node:test，无需额外依赖）。
 * WebAudio 节点在 Node 环境不可用，滤波链用 RBJ cookbook 双二阶直接形式仿真
 * （与 createPlaybackChain 的 4 阶 Butterworth 配置一致）。
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  DcBlocker,
  NoiseGate,
  createStreamingResampler,
  decodePcm16ToFloat,
  encodeFloatToPcm16,
  rmsDb,
  AUDIO_DSP_CONFIG,
} from '../audioDsp.ts'

const SR = 48000

/** 生成正弦（float, -1..1） */
function sine(freq: number, seconds: number, amp: number): Float32Array {
  const n = Math.round(seconds * SR)
  const out = new Float32Array(n)
  for (let i = 0; i < n; i++) {
    out[i] = amp * Math.sin((2 * Math.PI * freq * i) / SR)
  }
  return out
}

// ── RBJ cookbook 双二阶（测试专用仿真，与 WebAudio BiquadFilterNode 等价）──

interface Biquad {
  b0: number; b1: number; b2: number; a1: number; a2: number
}

function rbj(type: 'highpass' | 'lowpass', f0: number, q: number): Biquad {
  const w0 = (2 * Math.PI * f0) / SR
  const cos = Math.cos(w0)
  const alpha = Math.sin(w0) / (2 * q)
  const a0 = 1 + alpha
  const raw =
    type === 'highpass'
      ? { b0: (1 + cos) / 2, b1: -(1 + cos), b2: (1 + cos) / 2, a1: -2 * cos, a2: 1 - alpha }
      : { b0: (1 - cos) / 2, b1: 1 - cos, b2: (1 - cos) / 2, a1: -2 * cos, a2: 1 - alpha }
  return {
    b0: raw.b0 / a0, b1: raw.b1 / a0, b2: raw.b2 / a0, a1: raw.a1 / a0, a2: raw.a2 / a0,
  }
}

/** 直接形式 I 滤波（返回新数组） */
function applyBiquad(x: Float32Array, c: Biquad): Float32Array {
  const y = new Float32Array(x.length)
  let x1 = 0, x2 = 0, y1 = 0, y2 = 0
  for (let i = 0; i < x.length; i++) {
    const xn = x[i]
    y[i] = c.b0 * xn + c.b1 * x1 + c.b2 * x2 - c.a1 * y1 - c.a2 * y2
    x2 = x1; x1 = xn; y2 = y1; y1 = y[i]
  }
  return y
}

/** 复刻 createPlaybackChain 的滤波段：HPF(80)×2 → LPF(8000)×2（4 阶 Butterworth） */
function filterCascade(x: Float32Array): Float32Array {
  const [q1, q2] = AUDIO_DSP_CONFIG.playback.butterworthQ
  const hp = AUDIO_DSP_CONFIG.playback.highpassHz
  const lp = AUDIO_DSP_CONFIG.playback.lowpassHz
  let y = applyBiquad(x, rbj('highpass', hp, q1))
  y = applyBiquad(y, rbj('highpass', hp, q2))
  y = applyBiquad(y, rbj('lowpass', lp, q1))
  y = applyBiquad(y, rbj('lowpass', lp, q2))
  return y
}

// ── 1. 重采样正确性 ──────────────────────────────────────────

describe('createStreamingResampler', () => {
  it('48k→16k：输出长度约 1/3，1kHz 频率保持', () => {
    const resampler = createStreamingResampler()
    const input = sine(1000, 1, 0.5) // 48000 样本
    // 分 10 个 chunk 流式输入，验证跨 chunk 相位连续
    const chunkSize = input.length / 10
    const output: number[] = []
    for (let i = 0; i < 10; i++) {
      const chunk = input.subarray(i * chunkSize, (i + 1) * chunkSize)
      const resampled = resampler.process(chunk, SR, 16000)
      for (const v of resampled) output.push(v)
    }
    for (const v of resampler.flush()) output.push(v)

    assert.ok(output.length >= 15990 && output.length <= 16010, `输出长度异常: ${output.length}`)

    // 过零率 → 频率：1kHz 正弦每秒 2000 次过零
    let crossings = 0
    for (let i = 1; i < output.length; i++) {
      if (output[i - 1] < 0 && output[i] >= 0) crossings++
    }
    const freq = (crossings * 16000) / output.length
    assert.ok(Math.abs(freq - 1000) < 10, `频率偏差过大: ${freq}`)
  })

  it('同采样率直通，reset 后重新配置', () => {
    const resampler = createStreamingResampler()
    const input = new Float32Array([0.1, 0.2, 0.3])
    assert.strictEqual(resampler.process(input, 16000, 16000), input)
    const out = resampler.process(new Float32Array([0.4, 0.5]), SR, 16000)
    assert.ok(out.length > 0)
    resampler.reset()
    assert.strictEqual(resampler.process(input, 16000, 16000), input)
  })
})

// ── 2. 噪声门：静音段抑制 + 语音保留 ─────────────────────────

describe('NoiseGate', () => {
  const mkGate = (rate = SR) =>
    new NoiseGate({ sampleRate: rate, thresholdDb: -60, attackMs: 5, releaseMs: 120 })

  it('静音段（-80dBFS 底噪）输出 ≤ -60dBFS', () => {
    const gate = mkGate()
    // 伪随机白噪声近似底噪
    const noise = new Float32Array(SR) // 1s
    let seed = 42
    const rand = () => {
      seed = (seed * 1103515245 + 12345) % 2147483648
      return seed / 2147483648 - 0.5
    }
    for (let i = 0; i < noise.length; i++) noise[i] = 0.0001 * (2 * rand())
    assert.ok(rmsDb(noise) < -60)

    gate.process(noise)
    assert.ok(rmsDb(noise) <= -60, `静音段残留过大: ${rmsDb(noise)}dBFS`)
  })

  it('语音段（-6dBFS 正弦）能量保留 ≥ 90%', () => {
    const gate = mkGate()
    const speech = sine(300, 0.5, 0.5) // -6dBFS
    const energyBefore = speech.reduce((s, v) => s + v * v, 0)
    gate.process(speech)
    const energyAfter = speech.reduce((s, v) => s + v * v, 0)
    assert.ok(energyAfter / energyBefore >= 0.9)
  })

  it('门状态跨 buffer 保持：先静音后语音，字头不被截', () => {
    const gate = mkGate()
    const silence = new Float32Array(SR / 2)
    gate.process(silence)
    const speech = sine(300, 0.1, 0.5)
    gate.process(speech)
    // 语音段开头 attack 平滑进入（5ms），中段应完全打开
    const tail = speech.slice(speech.length - 1200) // 最后 25ms
    assert.ok(rmsDb(tail) > -10, `门未完全打开: ${rmsDb(tail)}dBFS`)
  })
})

// ── 3. SNR 提升（验证标准：≥15dB）────────────────────────────

describe('播放链 SNR 提升', () => {
  it('带外噪声（50Hz 哼声 + 16kHz 嘶声）衰减 ≥ 15dB，带内信号增益 ≈ 0dB', () => {
    // 带外噪声：哼声 + 嘶声
    const hum = sine(50, 1, 0.2)
    const hiss = sine(16000, 1, 0.2)
    const noiseIn = new Float32Array(hum.length)
    for (let i = 0; i < noiseIn.length; i++) noiseIn[i] = hum[i] + hiss[i]
    const noiseOut = filterCascade(noiseIn)
    const noiseAttDb = rmsDb(noiseOut) - rmsDb(noiseIn)
    assert.ok(noiseAttDb <= -15, `带外噪声衰减不足: ${noiseAttDb}dB`)

    // 带内信号（1kHz 人声基频区）几乎无衰减
    const signal = sine(1000, 1, 0.1)
    const signalOut = filterCascade(signal)
    // 跳过前 50ms 稳态建立期
    const skip = SR / 20
    const gainDb =
      rmsDb(signalOut.slice(skip)) - rmsDb(Float32Array.from(signal.slice(skip)))
    assert.ok(Math.abs(gainDb) < 1, `带内增益异常: ${gainDb}dB`)
  })
})

// ── 4. PCM roundtrip ─────────────────────────────────────────

describe('PCM16 编解码', () => {
  it('Float → Int16 → Float 误差 ≤ 1/32767', () => {
    const input = new Float32Array(1000)
    let seed = 7
    const rand = () => {
      seed = (seed * 1103515245 + 12345) % 2147483648
      return seed / 2147483648 - 0.5
    }
    for (let i = 0; i < input.length; i++) input[i] = rand()
    const pcm = encodeFloatToPcm16(input)
    const decoded = decodePcm16ToFloat(new Uint8Array(pcm.buffer))
    let maxErr = 0
    for (let i = 0; i < input.length; i++) {
      maxErr = Math.max(maxErr, Math.abs(input[i] - decoded[i]))
    }
    assert.ok(maxErr <= 1 / 32767 + 1e-9)
  })

  it('clamp 越界值', () => {
    const out = encodeFloatToPcm16(new Float32Array([2, -2]))
    assert.strictEqual(out[0], 32767)
    assert.strictEqual(out[1], -32767)
  })
})

// ── 5. 去直流 ────────────────────────────────────────────────

describe('DcBlocker', () => {
  it('去除直流偏置（稳态均值 < 1e-4）', () => {
    const blocker = new DcBlocker()
    const signal = sine(300, 1, 0.5)
    for (let i = 0; i < signal.length; i++) signal[i] += 0.01
    blocker.process(signal)
    // 整周期窗口（300Hz@48k = 160 样本/周期），避免非整周期正弦泄漏污染均值
    const tail = signal.slice(1920, 1920 + 160 * 288)
    const mean = tail.reduce((s, v) => s + v, 0) / tail.length
    assert.ok(Math.abs(mean) < 1e-4, `直流残留过大: ${mean}`)
  })
})
