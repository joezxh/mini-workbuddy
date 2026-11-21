/**
 * 全双工语音演示页共享类型（主页面与子组件的数据契约）
 */

// ── 输入 / 输出流 ──
export type IoRole = 'user' | 'assistant' | 'system'
export type VoiceStatus = 'playing' | 'done' | 'none' | 'failed'
export type IoSource = 'live' | 'history'

export interface IoMessage {
  key: string
  role: IoRole
  text: string
  time: string
  source: IoSource
  voiceStatus?: VoiceStatus
  channelTargets?: string[]
  statusLabel?: string
}

// ── 输出渠道 ──
export type OutputMode = 'text' | 'voice' | 'both' | 'off'
export const OUTPUT_MODE_LABEL: Record<OutputMode, string> = {
  text: '文字',
  voice: '语音',
  both: '文字+语音',
  off: '关闭 / 不发送',
}
/** 下发后端的合法模式（后端仅接受 text/voice/both） */
export type BackendOutputMode = 'text' | 'voice' | 'both'

/** 渠道真实外发成熟度，如实标注不伪造 */
export type ChannelCapability = 'enabled' | 'configured' | 'pending_backend' | 'unsupported'
export const CHANNEL_CAPABILITY_LABEL: Record<ChannelCapability, string> = {
  enabled: '已启用',
  configured: '已配置',
  pending_backend: '待后端启用',
  unsupported: '暂不支持',
}

export interface ChannelStats {
  dispatched: number
  succeeded: number
  successRate: string
}

export interface ChannelItem {
  key: string
  name: string
  icon: string
  desc: string
  active: boolean
  output: OutputMode
  capability: ChannelCapability
  stats?: ChannelStats
  /** 上一次合法的后端输出模式，用于「关闭/不发送」时保留 */
  lastValidOutput: BackendOutputMode
}

// ── Agent 编排 ──
export type ActivationReason = 'voice' | 'text' | 'intent' | 'default' | 'manual' | 'processing'
export const ACTIVATION_LABEL: Record<ActivationReason, string> = {
  voice: '语音激活',
  text: '文字激活',
  intent: '意图命中 · intent',
  default: '当前会话默认 Agent',
  manual: '手动切换',
  processing: '正在处理…',
}
export type AgentRuntimeStatus = 'running' | 'standby' | 'disabled'

export interface AgentView {
  key: string
  name: string
  icon: string
  desc: string
  enabled: boolean
  priority: number
  prompt: string
  rules: string[]
  tools: string[]
  runtimeStatus: AgentRuntimeStatus
  activationReason?: ActivationReason
  activationLabel?: string
}

// ── 会话 ──
export interface SessionItem {
  session_id: number
  session_title: string
  message_count: number
  updated_at: string
  session_type?: string
  status?: string
}

// ── 事件日志 ──
export interface LogEntry {
  ts: string
  evt: string
  msg: string
}

// ── 工具 ──
/** 将 ISO 时间转换为 HH:mm:ss */
export function formatClock(val?: string | null): string {
  if (!val) return '--:--:--'
  const d = new Date(val)
  if (isNaN(d.getTime())) return val
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

/** 将 ISO 时间转换为 YYYY-MM-DD HH:mm */
export function formatDateTime(val?: string | null): string {
  if (!val) return '-'
  const d = new Date(val)
  if (isNaN(d.getTime())) return val
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
