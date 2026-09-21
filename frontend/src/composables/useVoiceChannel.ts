/**
 * 语音 Channel Composable（差距分析 §3 实现核心）
 *
 * 封装调解语音 WebSocket 连接，负责：
 * - 能力协商（voice.ready 后拿到采样率/VAD 等）
 * - 上行：麦克风采集(PCM16 二进制) / 文本 / 打断
 * - 下行：音频播放(二进制) / 转写 / 工具调用 / 状态帧
 * - 代际仲裁：丢弃被打断前的过期帧（turn.isStale）
 * - 断线自动重连（useReconnect 指数退避）
 *
 * 语音质量修复（方案 A，设计文档 docs/superpowers/specs/2026-09-14-voice-audio-quality-design.md）：
 * - AudioContext 显式 48kHz；麦克风显式 AEC/NS/AGC（根治外放回声自激）
 * - 上行流式重采样 ctx.sampleRate → input_sample_rate（根治 48k/16k 错配）
 * - 上行软噪声门 + 去直流；下行播放链/调度交给 useVoicePlayback
 */
import { ref, onUnmounted } from 'vue'
import { buildVoiceWsUrl } from '@/api/voice'
import type {
  ConnectConfig,
  VoiceFrame,
  VoiceReadyPayload,
  VoiceTurn,
  ToolConfirmPayload,
} from '@/types/voice'
import { useTurnState } from './useTurnState'
import { useReconnect } from './useReconnect'
import { useToolCalls } from './useToolCalls'
import { useVoicePlayback } from './useVoicePlayback'
import { createMicLifecycle, classifyMicError, type MicState } from './useMicLifecycle'
import {
  DcBlocker,
  NoiseGate,
  createStreamingResampler,
  encodeFloatToPcm16,
  AUDIO_DSP_CONFIG,
} from '@/utils/audioDsp'

export type ChannelStatus = 'idle' | 'connecting' | 'open' | 'closed' | 'error'

function randomId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2)
}

export function useVoiceChannel(cfg: ConnectConfig) {
  const status = ref<ChannelStatus>('idle')
  const ready = ref<VoiceReadyPayload | null>(null)
  const errorMsg = ref<string | null>(null)
  const transcripts = ref<VoiceTurn[]>([])
  const audioLevel = ref(0)
  const micOn = ref(false)
  const micState = ref<MicState | null>(null)

  const turn = useTurnState()
  const reconnect = useReconnect()
  const toolCalls = useToolCalls()

  let ws: WebSocket | null = null
  let audioCtx: AudioContext | null = null
  let mediaStream: MediaStream | null = null
  let processor: ScriptProcessorNode | null = null
  let reconnectTimer: number | null = null
  let closedByUser = false

  // 上行 DSP 状态（跨采集帧保持；重连/停止采集时复位）
  const uplinkDcBlocker = new DcBlocker()
  // 噪声门按实际 ctx.sampleRate 惰性创建（浏览器回退采样率时攻放时间才准确）
  let uplinkGate: NoiseGate | null = null
  const uplinkResampler = createStreamingResampler()

  function ensureAudioCtx(): AudioContext {
    if (!audioCtx) {
      const Ctor =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      // 显式 48kHz：与下行协商采样率的换算、上行重采样源率保持一致；
      // 旧浏览器不支持 sampleRate 选项时回退设备默认（以其为重采样源率）。
      try {
        audioCtx = new Ctor({ sampleRate: AUDIO_DSP_CONFIG.contextSampleRate })
      } catch {
        audioCtx = new Ctor()
      }
    }
    if (audioCtx.state === 'suspended') void audioCtx.resume()
    return audioCtx
  }

  const playback = useVoicePlayback({
    getContext: () => audioCtx,
    getSampleRate: () => ready.value?.output_sample_rate || 24000,
    onLevel: (peak) => {
      audioLevel.value = peak
    },
  })

  /** 将过期代际的迟到帧丢弃 */
  function acceptGeneration(gen?: number): boolean {
    if (gen === undefined) return true
    return !turn.isStale(gen)
  }

  /** 累积式追加一条转写：assistant 角色的 delta 追加到当前气泡，user 角色每次新建 */
  function appendTranscript(role: string, text: string, finalize = false) {
    const list = transcripts.value
    if (role === 'assistant') {
      const last = list[list.length - 1]
      if (last && last.role === 'assistant' && !last.finalized) {
        last.text += text
        last.final_transcript = last.text
        if (finalize) last.finalized = true
        return
      }
    }
    list.push({
      id: randomId(),
      role: role as VoiceTurn['role'],
      text,
      final_transcript: text,
      started_at: new Date().toISOString(),
      generation: frameGen,
      finalized: role !== 'assistant' ? true : finalize,
    })
  }

  /** 新的一轮助理回复开始前，定稿上一条 assistant 气泡（避免多次回复被合并） */
  function finalizeAssistant() {
    const list = transcripts.value
    const last = list[list.length - 1]
    if (last && last.role === 'assistant') last.finalized = true
  }

  // 最近一次下行帧的代际，用于新建转写轮次标记
  let frameGen = 0

  function handleFrame(frame: VoiceFrame) {
    if (!acceptGeneration(frame.generation)) return
    frameGen = frame.generation ?? 0

    switch (frame.type) {
      case 'voice.ready':
        ready.value = frame.data as VoiceReadyPayload
        break
      case 'transcript.delta':
      case 'transcript':
      case 'transcript.final': {
        const d = frame.data as { text?: string; role?: string }
        const role = d.role || 'user'
        const finalize = frame.type === 'transcript.final'
        if (d.text) appendTranscript(role, d.text, finalize)
        break
      }
      case 'response_started':
        finalizeAssistant()
        turn.onAssistantStart()
        break
      case 'audio.delta':
        turn.markSpeaking()
        if (typeof frame.data === 'string') playback.push(frame.data)
        else if (frame.data) playback.push((frame.data as { audio?: string }).audio)
        break
      case 'audio':
        turn.markSpeaking()
        playback.push(frame.data?.audio)
        break
      case 'playback_cancelled':
        playback.interrupt()
        turn.onInterrupt()
        toolCalls.clearPending()
        break
      case 'tool_call': {
        // 工具调用开始（AgentScope ToolCallStartEvent）；结果由 tool_result 落位
        const d = frame.data as { call_id?: string; name?: string }
        if (d.call_id) {
          toolCalls.add({
            id: d.call_id,
            name: d.name || '',
            arguments: {},
          })
        }
        break
      }
      case 'tool.confirm_required': {
        const p = frame.data as ToolConfirmPayload
        toolCalls.addConfirm({
          confirmId: p.confirm_id,
          name: p.tool_name,
          arguments: p.arguments ?? {},
          timeoutMs: p.timeout_ms ?? 300000,
        })
        break
      }
      case 'tool_result': {
        const r = frame.data as { call_id?: string; state?: string }
        if (r.call_id) {
          toolCalls.update(r.call_id, {
            ok: r.state === 'success',
            result: r.state,
          })
        }
        break
      }
      case 'error':
        errorMsg.value = frame.data?.message || '语音服务错误'
        break
      case 'pong':
        break
    }
  }

  function onMessage(ev: MessageEvent) {
    if (typeof ev.data === 'string') {
      let frame: VoiceFrame
      try {
        frame = JSON.parse(ev.data)
      } catch {
        return
      }
      handleFrame(frame)
    } else if (ev.data instanceof ArrayBuffer) {
      playback.push(ev.data)
    } else if (ev.data instanceof Blob) {
      ev.data.arrayBuffer().then((buf) => playback.push(buf))
    }
  }

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return
    status.value = 'connecting'
    closedByUser = false
    // 新连接：上行重采样相位与 DSP 状态必须复位，避免跨会话残留
    uplinkResampler.reset()
    uplinkDcBlocker.reset()
    uplinkGate?.reset()
    playback.reset()
    const url = buildVoiceWsUrl(cfg)
    ws = new WebSocket(url)
    ws.binaryType = 'arraybuffer'
    ws.onopen = () => {
      status.value = 'open'
      reconnect.reset()
    }
    ws.onmessage = onMessage
    ws.onclose = () => {
      status.value = 'closed'
      if (!closedByUser) scheduleReconnect()
    }
    ws.onerror = () => {
      status.value = 'error'
      errorMsg.value = '语音连接异常'
    }
  }

  function scheduleReconnect() {
    if (!reconnect.shouldRetry()) return
    const delay = reconnect.nextDelay()
    reconnectTimer = window.setTimeout(() => connect(), delay * 1000)
  }

  function sendText(text: string) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    ws.send(JSON.stringify({ type: 'input.message', text }))
    // 本地回显：用户键入的文字立即显示在对话流中
    appendTranscript('user', text, true)
  }

  function sendInterrupt() {
    toolCalls.clearPending()
    ws?.send(JSON.stringify({ type: 'interrupt' }))
  }

  /** 回传工具确认结果（tool.confirm_required → 用户同意/拒绝） */
  function respondToolConfirm(confirmId: string, approved: boolean) {
    toolCalls.clearPending()
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(
        JSON.stringify({ type: 'tool.confirm', data: { confirm_id: confirmId, approved } }),
      )
    }
  }

  function sendAudio(bytes: Uint8Array) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(bytes)
  }

  /** 将新 MediaStream 接入既有 48kHz 采集链（设备切换只重连 source，不动 AudioContext/WS） */
  function attachStream(stream: MediaStream) {
    mediaStream = stream
    const ctx = ensureAudioCtx()
    // 噪声门按实际采样率创建（仅首次或采样率变化时重建）
    if (!uplinkGate || uplinkGate.sampleRate !== ctx.sampleRate) {
      uplinkGate = new NoiseGate({
        sampleRate: ctx.sampleRate,
        thresholdDb: AUDIO_DSP_CONFIG.capture.gateThresholdDb,
        attackMs: AUDIO_DSP_CONFIG.capture.gateAttackMs,
        releaseMs: AUDIO_DSP_CONFIG.capture.gateReleaseMs,
      })
    }
    processor?.disconnect()
    const source = ctx.createMediaStreamSource(stream)
    const node = ctx.createScriptProcessor(AUDIO_DSP_CONFIG.capture.bufferSize, 1, 1)
    node.onaudioprocess = (e) => {
      const socket = ws
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        uplinkResampler.reset()
        return
      }
      const samples = e.inputBuffer.getChannelData(0)
      uplinkDcBlocker.process(samples)
      uplinkGate?.process(samples)
      // 流式重采样到协商的上行采样率（默认 16k）——根治 48k 直发的错配
      const targetRate = ready.value?.input_sample_rate || 16000
      const resampled = uplinkResampler.process(samples, ctx.sampleRate, targetRate)
      if (!resampled.length) return
      sendAudio(new Uint8Array(encodeFloatToPcm16(resampled).buffer))
    }
    source.connect(node)
    node.connect(ctx.destination)
    processor = node
    micOn.value = true
  }

  // 麦克风捕获生命周期：设备切换/track ended/退避重试独立于 WS 通道（spec §9.7）
  const mic = createMicLifecycle({
    acquire: async () => {
      // 显式声明浏览器端 AEC/NS/AGC：外放场景下抑制扬声器回采（根治模型"听到自己"）
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
      return { media: stream, track: stream.getAudioTracks()[0] }
    },
    release: (c) => {
      c.media?.getTracks().forEach((t) => t.stop())
    },
    onState: (s) => {
      micState.value = s
      if (s.state === 'unavailable' && s.error) {
        errorMsg.value = `麦克风不可用（${classifyMicError(s.error)}）：请检查权限或设备后重试`
      }
    },
    onCapture: (c) => {
      if (c.media) attachStream(c.media)
    },
  })

  function startMic() {
    mic.start()
  }

  function stopMic() {
    mic.stop()
    mediaStream?.getTracks().forEach((t) => t.stop())
    mediaStream = null
    processor?.disconnect()
    processor = null
    micOn.value = false
  }

  function disconnect() {
    closedByUser = true
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    stopMic()
    playback.reset()
    uplinkResampler.reset()
    ws?.close()
    ws = null
    status.value = 'closed'
  }

  onUnmounted(disconnect)

  return {
    // 状态
    status,
    ready,
    errorMsg,
    transcripts,
    audioLevel,
    micOn,
    micState,
    // 子状态机
    turn,
    reconnect,
    toolCalls,
    // 操作
    connect,
    disconnect,
    sendText,
    sendInterrupt,
    sendAudio,
    respondToolConfirm,
    startMic,
    stopMic,
  }
}
