/** 实时 S2S 对话状态机（spec §2.2 WS 链）— 事件形状与 Mock/真实逐一同构。 */
import { ref } from 'vue'
import { buildVoiceDemoWsUrl } from '@/api/voiceDemo'
import { getToken } from '@/utils/auth'
import {
  createStreamingResampler,
  encodeFloatToPcm16,
  decodePcm16ToFloat,
  createPlaybackChain,
} from '@/utils/audioDsp'

export type S2sState = 'idle' | 'connecting' | 'listening' | 'responding' | 'closed'
export interface Msg { role: 'user' | 'assistant'; text: string; partial?: boolean; interrupted?: boolean }
export interface Ev { dir: 'in' | 'out'; type: string; at: number }

const PLAY_RATE = 24000 // 下行 PCM16 采样率（真实服务实测 24kHz mono）
const MIC_RATE = 16000 // 上行 PCM16 采样率（Realtime API 要求 16k）

export function useRealtimeS2s() {
  const state = ref<S2sState>('idle')
  const messages = ref<Msg[]>([])
  const events = ref<Ev[]>([])
  const micActive = ref(false)
  let ws: WebSocket | null = null
  let assistantDraft: Msg | null = null

  // 麦克风采集通道（AudioWorklet → 48k→16k 重采样 → PCM16 base64 append）
  let micStream: MediaStream | null = null
  let micCtx: AudioContext | null = null
  let micNode: AudioWorkletNode | null = null
  let micResampler: ReturnType<typeof createStreamingResampler> | null = null

  const log = (dir: 'in' | 'out', type: string) => events.value.push({ dir, type, at: Date.now() })
  const send = (data: unknown) => { ws?.send(JSON.stringify(data)); log('out', (data as any).type) }

  function upsertDraft(role: 'user' | 'assistant', text: string) {
    const list = messages.value
    let m = list.at(-1)
    if (!m || m.role !== role || !m.partial) {
      m = { role, text: '', partial: true }
      list.push(m)
      if (role === 'assistant') assistantDraft = m
    }
    m.text += text
  }

  function handle(evt: any) {
    const type = evt.type ?? ''
    log('in', type)
    switch (type) {
      case 'session.created':
      case 'session.updated':
        state.value = 'listening'; break
      case 'input_audio_buffer.speech_started':
        if (state.value === 'responding') interrupt() // 服务端 VAD 打断
        break
      case 'conversation.item.input_audio_transcription.completed':
      case 'input_audio_transcription.completed':
        messages.value.push({ role: 'user', text: evt.transcript ?? evt.delta ?? '' })
        break
      case 'response.created':
        state.value = 'responding'; assistantDraft = null; break
      case 'response.audio_transcription.delta':
        upsertDraft('assistant', evt.delta ?? ''); break
      case 'response.audio.delta':
        playback.push(evt.delta); break
      case 'response.done':
        if (assistantDraft?.partial) assistantDraft.partial = false
        if (evt.response?.status === 'cancelled' || evt.response?.status === 'incomplete') {
          const last = messages.value.at(-1); if (last) last.interrupted = true
        }
        state.value = 'listening'; break
      case 'error':
        events.value.push({ dir: 'in', type: `error:${evt.code ?? ''}`, at: Date.now() })
        state.value = 'listening'; break
    }
  }

  // 播放链：PCM16/24k base64 → Float32 → PlaybackChain → AudioContext（懒建）
  const playback = createPlayback()

  function connect() {
    state.value = 'connecting'
    ws = new WebSocket(buildVoiceDemoWsUrl(getToken() || ''))
    ws.onopen = () => {
      log('out', 'ws.open')
      // 通知桥接端会话意图（voice/instructions 由网关 build_session_update 决定，此处空 patch 不覆盖）
      send({ type: 'session.update', session: {} })
    }
    ws.onmessage = e => { try { handle(JSON.parse(e.data)) } catch (err) { console.warn('[voice-demo] 非法 WS 消息', err) } }
    ws.onclose = () => { state.value = 'closed'; stopMic() }
    ws.onerror = () => { state.value = 'closed' }
  }
  function disconnect() {
    stopMic()
    ws?.close(); ws = null
    state.value = 'closed'
  }
  function interrupt() {
    send({ type: 'response.cancel' })
    playback.clear()
    const last = messages.value.at(-1)
    if (last && last.role === 'assistant') last.interrupted = true
  }
  /** 文字模拟一句语音（Mock/真实模式 s2s 均可接 input text，桥接透传） */
  function sendSimText(text: string) {
    send({ type: 'conversation.item.create', item: { role: 'user', content: [{ type: 'input_text', text }] } })
    send({ type: 'response.create' })
  }

  // ── 麦克风采集（spec §4.3）：getUserMedia → AudioWorklet → 重采样 → append ──
  async function startMic() {
    if (!ws || state.value === 'closed' || micActive.value) return
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    })
    micStream = stream
    micCtx = new AudioContext()
    micResampler = createStreamingResampler()
    await micCtx.audioWorklet.addModule('/worklets/mic-pcm-collector.js')
    const node = new AudioWorkletNode(micCtx, 'mic-pcm-collector')
    micNode = node
    node.port.onmessage = (e: MessageEvent) => {
      const chunk = e.data as Float32Array
      if (!chunk?.length || !micCtx) return
      sendPcmChunk(micResampler!.process(chunk, micCtx.sampleRate, MIC_RATE))
    }
    // 采集节点不连 destination：避免回声啸叫
    micCtx.createMediaStreamSource(stream).connect(node)
    micActive.value = true
  }
  function stopMic() {
    if (micNode) { try { micNode.port.close(); micNode.disconnect() } catch { /* noop */ } micNode = null }
    if (micStream) { for (const t of micStream.getAudioTracks()) t.stop(); micStream = null }
    if (micCtx) { try { micCtx.close().catch(() => { /* noop */ }) } catch { /* noop */ } micCtx = null }
    if (micResampler) { sendPcmChunk(micResampler.flush()); micResampler = null }
    micActive.value = false
  }
  function sendPcmChunk(samples: Float32Array) {
    if (!samples.length) return
    const pcm = encodeFloatToPcm16(samples)
    if (!pcm.length) return
    send({ type: 'input_audio_buffer.append', audio: pcm16ToBase64(pcm) })
  }

  return { state, messages, events, micActive, connect, disconnect, interrupt, sendSimText, startMic, stopMic }
}

/** 下行播放器：base64 PCM16 块顺序播放；clear() 即刻停播（打断） */
function createPlayback() {
  let ctx: AudioContext | null = null
  let chain: ReturnType<typeof createPlaybackChain> | null = null
  let queue: string[] = []
  let playing = false
  let cancelled = false

  const supported = () => typeof AudioContext !== 'undefined'

  function ensureCtx(): AudioContext {
    if (!ctx) {
      ctx = new AudioContext({ sampleRate: PLAY_RATE })
      chain = createPlaybackChain(ctx, ctx.destination)
    }
    return ctx
  }

  function base64ToBytes(b64: string): Uint8Array {
    const bin = atob(b64)
    const bytes = new Uint8Array(bin.length)
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
    return bytes
  }

  async function drain() {
    if (playing || !supported()) return
    playing = true
    try {
      while (queue.length && !cancelled) {
        const b64 = queue.shift()!
        const samples = decodePcm16ToFloat(base64ToBytes(b64))
        if (!samples.length) continue
        const c = ensureCtx()
        if (c.state === 'suspended') { try { await c.resume() } catch { /* 忽略 */ } }
        const buf = c.createBuffer(1, samples.length, PLAY_RATE)
        // TS5.7+：decodePcm16ToFloat 返回 ArrayBufferLike 背书，copyToChannel 要求 ArrayBuffer
        buf.copyToChannel(samples as Float32Array<ArrayBuffer>, 0)
        const src = c.createBufferSource()
        src.buffer = buf
        src.connect(chain!.input)
        src.start()
        await new Promise<void>(r => { src.onended = () => r() })
      }
    } catch (e) {
      console.warn('[voice-demo] s2s 播放中断:', e)
    } finally {
      playing = false
    }
  }

  return {
    push(b64: string) { cancelled = false; queue.push(b64); void drain() },
    clear() {
      cancelled = true
      queue = []
      if (chain) { try { chain.dispose() } catch { /* noop */ } chain = null }
      if (ctx) { try { ctx.close().catch(() => { /* noop */ }) } catch { /* noop */ } ctx = null }
    },
  }
}

/** Int16 PCM → base64（分块转换避免 fromCharCode 栈溢出） */
function pcm16ToBase64(pcm: Int16Array): string {
  const bytes = new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength)
  let bin = ''
  const CHUNK = 0x8000
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode(...bytes.subarray(i, i + CHUNK))
  }
  return btoa(bin)
}
