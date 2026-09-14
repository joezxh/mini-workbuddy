/**
 * 调解语音 RTC 协议类型定义（差距分析 §3）
 *
 * 与后端 app.duplex.voice 的常量/协议帧一一对应，供语音 Channel
 * Composable、组件使用。
 */

/** 轮次语音状态（对应后端 VoiceState） */
export type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking'

/** 下行协议帧类型（对应后端 EventType） */
export type VoiceEventType =
  | 'voice.ready'
  | 'audio'
  | 'audio.delta'
  | 'transcript'
  | 'transcript.delta'
  | 'transcript.final'
  | 'response_started'
  | 'playback_cancelled'
  | 'tool_call'
  | 'turn_update'
  | 'error'
  | 'pong'

/** Provider 标识（对应后端 ProviderKey；s2s = 本地 Docker qwen-audio-s2s） */
export type VoiceProvider = 'dashscope' | 'local' | 's2s' | 'openai' | 'loopback'

/** 协商后的能力集合（对应后端 build_ready_payload） */
export interface VoiceCapabilities {
  input_sample_rate: number
  output_sample_rate: number
  server_vad: boolean
  native_transcription: boolean
  supports_interrupt: boolean
  vad_mode: string
}

/** voice.ready 载荷 */
export interface VoiceReadyPayload extends VoiceCapabilities {
  session_id: string
  provider: VoiceProvider
}

/** 一条转写/轮次记录 */
export interface VoiceTurn {
  id: string
  role: 'user' | 'assistant' | 'system'
  text: string
  started_at: string
  final_transcript: string
  generation: number
  /** 是否为已定稿轮次（用于流式累积时判断是否还可追加） */
  finalized?: boolean
}

/** 会话级工具调用（对应后端 ToolCallHandler 结果） */
export interface ToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
  result?: unknown
  ok: boolean
  error?: string
}

/** 通用下行帧 */
export interface VoiceFrame {
  type: VoiceEventType
  data: any
  /** 代际标记：用于丢弃过期（被打断前）的音频/文本帧 */
  generation?: number
}

/** 连接配置 */
export interface ConnectConfig {
  caseNumber: string
  participantId: string
  provider?: VoiceProvider
  agentId?: string
  clientCaps?: Record<string, unknown>
  /** 可选语音模型 ID；缺省时后端使用数据库默认语音模型 */
  modelId?: number
}

/** 语音模型（来自 ai_chat_model，type=语音实时） */
export interface VoiceModel {
  id: number
  name: string
  model: string
  platform?: string
  key_id?: number
  key_name?: string
  is_default: boolean
  status: number
  sort: number
}

/** 默认语音模型解析结果 */
export interface VoiceModelDefault {
  configured: boolean
  model_id?: number
  model?: string
  key_name?: string
  platform?: string
  is_default?: boolean
}

// ── M3 配置化：三张配置表 ────────────────────────────────

/** Agent 配置（ai_agent_config） */
export interface AgentConfig {
  agent_id: string
  name: string
  type: string
  model: string
  system_prompt: string
  tool_bindings: string[]
  mcp_bindings: string[]
  max_react_iters: number
  enable_plan: boolean
}

/** 角色语音配置（duplex_voice_config） */
export interface VoiceRoleConfig {
  role_id: string
  role_name: string
  greeting: string
  voice_identity: string
  language: string
  agent_id?: string
  case_type?: string
}

/** 工具调用策略（tool_policy） */
export interface ToolPolicy {
  tool_name: string
  enabled: boolean
  timeout_ms: number
  max_calls_per_turn: number
  max_result_bytes: number
}
