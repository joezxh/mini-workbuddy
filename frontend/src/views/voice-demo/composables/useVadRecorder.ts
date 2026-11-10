/**
 * ASR 录音 VAD 分段（参考工程同款 @ricky0123/vad-web；16k mono WAV 分段回调）。
 * VAD 参数对齐参考：positive 0.5 / negative 0.35 / minSpeech≈250ms / redemption≈700ms。
 */
import { ref } from 'vue'
import { MicVAD } from '@ricky0123/vad-web'

export interface VadSegment { blob: Blob; startMs: number; endMs: number }

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

export function useVadRecorder(opts: { onSegment: (blob: Blob, startMs: number, endMs: number) => void }) {
  const isRecording = ref(false)
  let vad: MicVAD | null = null
  let segStart = 0

  async function start() {
    // vad-web 0.0.31：回调直接在 options 内（参考工程同款版本）
    vad = await MicVAD.new({
      positiveSpeechThreshold: 0.5,
      negativeSpeechThreshold: 0.35,
      minSpeechMs: 250,    // 对齐参考 minSpeech≈250ms
      redemptionMs: 700,   // 对齐参考 redemption≈700ms
      onSpeechStart: () => { segStart = performance.now() },
      onSpeechEnd: (audio: Float32Array) => {
        opts.onSegment(floatToWav(audio), Math.round(segStart), Math.round(performance.now()))
      },
    })
    await vad.start()
    isRecording.value = true
  }
  function stop() { vad?.pause(); vad = null; isRecording.value = false } // 0.0.31 无 stop，用 pause
  return { start, stop, isRecording }
}
