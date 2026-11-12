/**
 * 语音 Demo API（spec docs/superpowers/specs/2026-11-10-voice-demo-design.md §3.2）
 * — REST 经 @/utils/request，WS URL 单独构造（token query，对齐 api/voice.ts 先例）。
 */
import request from '@/utils/request'

const BASE = '/api/v1/voice-demo'

export interface VoiceDemoHealth {
  base_url: string
  realtime_ws_url: string
  pool: { size: number; in_use: number; units: string[] } | null
}

export function getVoiceDemoHealth() {
  return request.get<VoiceDemoHealth>(`${BASE}/health`)
}

export function transcribeAsr(form: FormData) {
  return request.post<{ text: string; language: string; cost_ms: number }>(
    `${BASE}/asr/transcribe`, form)
}

/** LLM 文本纠正（后端取 AiChatModel is_default 默认对话模型；仅修同音字/断句/标点） */
export function correctAsrText(text: string) {
  return request.post<{ text: string; cost_ms: number }>(`${BASE}/asr/correct`, { text })
}

export function synthesizeTts(p: { text: string; voice: string }) {
  // blob 返回：audio/wav（实测仅 wav）
  return request.post<Blob>(`${BASE}/tts/synthesize`, p, { responseType: 'blob' })
}

/** 构建语音对话 WS URL：?token=<JWT>（对齐 duplex/voice 网关先例，spec D3） */
export function buildVoiceDemoWsUrl(token: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || ''
  const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost'
  const url = new URL(`${base}${BASE}/ws`, origin)
  url.searchParams.set('token', token)
  return url.toString().replace(/^http/, 'ws')
}

/** 9 音色按语种分组（与参考前端核对：Vivian/Serena/Uncle_Fu/Dylan 中文，Eric/Ryan/Aiden 英文，Ono_Anna 日文，Sohee 韩文） */
export const VOICES_BY_LANG: Record<string, string[]> = {
  中文: ['Vivian', 'Serena', 'Uncle_Fu', 'Dylan'],
  英文: ['Eric', 'Ryan', 'Aiden'],
  日文: ['Ono_Anna'],
  韩文: ['Sohee'],
}
