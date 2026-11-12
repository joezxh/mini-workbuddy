/**
 * 调解语音 RTC 协议类型定义（差距分析 §3）
 *
 * 与后端 app.duplex.voice 的常量/协议帧一一对应，供语音 Channel
 * Composable、组件使用。
 */

/** 轮次语音状态（对应后端 VoiceState） */
export type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking'

/** 下行协议帧类型（对应后端 EventType）
 *
 * 注意：handleFrame 会把点号帧名归一化为下划线（见 useVoiceChannel.ts），
 * 因此点号版本（如 tool.confirm_required）和下划线版本（如 tool_confirm_required）
 * 都需要在类型中声明，switch case 才可正常分发。
 */
export type VoiceEventType =
  | 'voice.ready'
  | 'voice_ready'
  | 'audio'
  | 'audio.delta'
  | 'audio_delta'
  | 'transcript'
  | 'transcript.delta'
  | 'transcript_delta'
  | 'transcript.final'
  | 'transcript_final'
  | 'response_started'
  | 'playback_cancelled'
  | 'tool_call'
  | 'tool_result'
  | 'tool.confirm_required'
  | 'tool_confirm_required'
  | 'turn_update'
  | 'agent_switched'
  | 'error'
  | 'pong'

/** Provider 标识（对应后端厂商目录 voice_catalog.VOICE_PROVIDER_CATALOG） */
export type VoiceProvider = 'dashscope' | 'openai' | 'google' | 'volcengine' | 'iflytek'

/** 厂商目录中的单个全双工语音模型 */
export interface VoiceProviderCatalogModel {
  code: string
  name: string
  is_default: boolean
}

/** 厂商目录条目（含官方全双工语音模型清单 + 文档链接） */
export interface VoiceProviderCatalogItem {
  key: VoiceProvider
  label: string
  default_base_url: string
  api_key_url: string
  docs_url: string
  models: VoiceProviderCatalogModel[]
}

/** 厂商目录（key -> 条目） */
export type VoiceProviderCatalog = Record<VoiceProvider, VoiceProviderCatalogItem>

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

/** 工具确认请求载荷（对应后端 tool.confirm_required 帧） */
export interface ToolConfirmPayload {
  confirm_id: string
  tool_name: string
  arguments: Record<string, unknown>
  timeout_ms: number
}

/** 会话级工具调用（AgentScope 原生 Toolkit；status 驱动确认 UI） */
export interface ToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
  result?: unknown
  ok?: boolean
  error?: string
  /** pending：等待用户确认；executed/rejected：确认后终态 */
  status?: 'pending' | 'executed' | 'rejected'
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
  /** 归一化后的厂商 key（与目录对齐，如 dashscope / openai） */
  provider_key?: VoiceProvider | string
  key_id?: number
  key_name?: string
  is_default: boolean
  status: number
  sort: number
  /** 是否可用于建立实时连接（需为目录内全双工模型且 Key 非空） */
  usable?: boolean
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
