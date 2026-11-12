/**
 * ASR 录音 VAD 分段（参考工程同款 @ricky0123/vad-web；16k mono WAV 分段回调）。
 * 切段判据：语音置信度 < negativeSpeechThreshold 持续 redemptionMs 即收尾（无长语音强制切分选项，
 * 也无说话人/声纹概念——换人不切段，只因静音切段）。
 * 参数：positive 0.5 / negative 0.4 / minSpeech≈250ms / redemption≈400ms（对自然换气更跟手，
 * 长句可在句中停顿处提前分段送转写；代价是偶发把一个句子拆成两段）。
 * 超长独白兜底：逐帧累计语音态时长，达 maxSpeechMs（默认 20s）即强制收束当前段送转写
 * （pause 触发 onSpeechEnd + 随即 start 继续录音），避免不停顿时必须等说完才出字。
 */
import { ref } from 'vue'
import { MicVAD } from '@ricky0123/vad-web'
import { rmsLevel } from '@/utils/audioDsp'

export interface VadSegment { blob: Blob; startMs: number; endMs: number }

export interface VadRecorderOptions {
  onSegment: (blob: Blob, startMs: number, endMs: number) => void
  /** 语音时长强制收束阈值 ms（只计语音态帧，非墙钟）；<=0 关闭，默认 20000 */
  maxSpeechMs?: number
}

/** Float32 → 16kHz mono WAV（AudioBuffer 采样率由 getUserMedia constrain 到 16k） */
export function floatToWav(samples: Float32Array, sampleRate = 16000): Blob {
  const buf = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buf)
  const ws = (off: number, s: string) => { for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i)) }
  ws(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); ws(8, 'WAVE')
  ws(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true); view.setUint16(34, 16, true)
  ws(36, 'data'); view.setUint32(40, samples.length * 2, true)
  let off = 44
  for (let i = 0; i < samples.length; i++, off += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return new Blob([buf], { type: 'audio/wav' })
}

export function useVadRecorder(opts: VadRecorderOptions) {
  const maxSpeechMs = opts.maxSpeechMs ?? 20_000
  const isRecording = ref(false)
  const level = ref(0) // 麦克风输入电平 0..1（每帧 RMS，供 VoiceWaveform）
  let vad: MicVAD | null = null
  let segStart = 0
  let speechMs = 0 // 当前段内累计的语音态时长（ms）
  let forcing = false // 强制收束进行中，防 onFrameProcessed 重入

  /** 强制收束：pause（submitUserSpeechOnPause → 触发 onSpeechEnd 送转写）后随即 start 继续录音 */
  async function forceFlush() {
    if (!vad || forcing || !isRecording.value) return
    forcing = true
    speechMs = 0
    try {
      await vad.pause()
      if (isRecording.value) await vad.start()
    } catch (e) {
      console.warn('[voice-demo] 强制分段后重启 VAD 失败:', e)
    } finally {
      forcing = false
    }
  }

  async function start() {
    // 非 localhost 的 http 下 navigator.mediaDevices 为 undefined（非安全上下文）
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('麦克风 API 不可用：当前页面非安全上下文。请改用 localhost 或 https 访问（Chrome 也可将该地址加入「不安全来源视为安全」标记后重启浏览器）')
    }
    // vad-web 0.0.31：回调直接在 options 内（参考工程同款版本）
    vad = await MicVAD.new({
      // worklet+模型放 public/vad/（fetch 语义可服务）
      baseAssetPath: '/vad/',
      // ort wasm 定位：vad-web 会先把 wasmPaths 设为 './'（相对预打包 chunk → 404），
      // ortConfig 在其赋值之后执行，统一指向 /vad/（dev 由 vite 插件静态服务
      // node_modules 源文件；build 时 public/vad/ 拷入 dist，均为静态可达路径）
      ortConfig: (o) => {
        o.env.logLevel = 'error'
        o.env.wasm.wasmPaths = {
          mjs: '/vad/ort-wasm-simd-threaded.mjs',
          wasm: '/vad/ort-wasm-simd-threaded.wasm',
        }
      },
      positiveSpeechThreshold: 0.5,
      negativeSpeechThreshold: 0.4, // 抬高静音判定：换气/短停更快脱离语音态
      minSpeechMs: 250,    // 对齐参考 minSpeech≈250ms
      redemptionMs: 400,   // 700→400ms：长句可在句中停顿处切段，无需等全部说完
      // stop/强制分段时若正在说话，pause 会触发 onSpeechEnd 交出当前段（尾部语音不丢）
      submitUserSpeechOnPause: true,
      // 0.0.31 签名：(probabilities{isSpeech,notSpeech 数值}, frame 16k Float32)：逐帧算电平 + 累计语音时长
      onFrameProcessed: (probs, frame) => {
        level.value = rmsLevel(frame)
        if (maxSpeechMs > 0 && probs.isSpeech >= 0.5) {
          speechMs += frame.length / 16 // 16kHz：样本数/16 = ms
          if (speechMs >= maxSpeechMs) void forceFlush()
        }
      },
      onSpeechStart: () => { segStart = performance.now(); speechMs = 0 },
      onSpeechEnd: (audio: Float32Array) => {
        speechMs = 0
        opts.onSegment(floatToWav(audio), Math.round(segStart), Math.round(performance.now()))
      },
    })
    await vad.start()
    isRecording.value = true
  }
  function stop() { vad?.pause(); vad = null; isRecording.value = false; level.value = 0; speechMs = 0 } // 0.0.31 无 stop，用 pause
  return { start, stop, isRecording, level }
}
