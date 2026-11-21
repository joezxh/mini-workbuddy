/**
 * 调解语音 WebSocket API 构造层（差距分析 §3.4 协议 v2）
 *
 * 后端语音网关挂载于 /api/v1/duplex/voice/ws（router prefix=/duplex/voice，
 * 应用挂载前缀 /api/v1）。本文件负责把 ConnectConfig 组装成完整 ws(s) URL。
 */
import request from '@/utils/request'
import type {
  ConnectConfig,
  VoiceModel,
  VoiceModelDefault,
  VoiceProviderCatalog,
} from '@/types/voice'

const BASE = '/api/v1/duplex'
const ADMIN_BASE = '/api/v1/admin/duplex/config'

/** 构建语音 WebSocket URL（http→ws，https→wss） */
export function buildVoiceWsUrl(cfg: ConnectConfig): string {
  const base = import.meta.env.VITE_API_BASE_URL || ''
  const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost'
  const url = new URL(`${base}${BASE}/voice/ws`, origin)
  // case_number / participant_id 为网关必需查询参数，缺失会导致 422 握手失败
  url.searchParams.set('case_number', cfg.caseNumber)
  url.searchParams.set('session_id', cfg.caseNumber)
  url.searchParams.set('participant_id', cfg.participantId)
  url.searchParams.set('provider', cfg.provider || 'dashscope')
  if (cfg.agentId) url.searchParams.set('agent_id', cfg.agentId)
  if (cfg.modelId != null) url.searchParams.set('model_id', String(cfg.modelId))
  if (cfg.clientCaps) url.searchParams.set('client_caps', JSON.stringify(cfg.clientCaps))
  return url.toString().replace(/^http/, 'ws')
}

// ── 语音模型配置（来自 ai_api_key / ai_chat_model） ──────────

/** 列出所有启用的语音模型 */
export function listVoiceModels() {
  return request.get<VoiceModel[]>(`${ADMIN_BASE}/voice-models`)
}

/** 获取全双工语音厂商目录（含各厂商官方模型清单 + 文档链接） */
export function getVoiceProviderCatalog() {
  return request.get<VoiceProviderCatalog>(`${ADMIN_BASE}/voice-models/provider-catalog`)
}

/** 获取当前默认语音模型解析结果 */
export function getVoiceModelDefault() {
  return request.get<VoiceModelDefault>(`${ADMIN_BASE}/voice-models/default`)
}

/** 创建或更新语音模型 */
export function upsertVoiceModel(payload: Partial<VoiceModel> & { key_id: number; name: string; model: string }) {
  return request.post(`${ADMIN_BASE}/voice-models`, payload)
}

/** 将指定语音模型设为默认 */
export function setDefaultVoiceModel(modelId: number) {
  return request.post(`${ADMIN_BASE}/voice-models/set-default`, { model_id: modelId })
}

// ── 双工编排管理（Agent 编排设计 + 输出渠道 + voice 会话） ──
const DUPLEX_BASE = `/api/v1/duplex`

export interface DuplexAgentConfig {
  key: string
  name: string
  icon?: string
  desc?: string
  enabled: boolean
  priority: number
  prompt: string
  rules: string[]
  tools: string[]
}

export interface DuplexChannelConfig {
  key: string
  name: string
  icon?: string
  desc?: string
  active: boolean
  output: 'text' | 'voice' | 'both' | 'off'
  capability?: 'enabled' | 'configured' | 'pending_backend' | 'unsupported'
}

/** 列出 Agent 设计配置 */
export function listDuplexAgents() {
  return request.get<{ items: DuplexAgentConfig[] }>(`${DUPLEX_BASE}/agents`)
}

/** 新增/更新 Agent 设计配置 */
export function upsertDuplexAgent(data: Partial<DuplexAgentConfig> & { key: string }) {
  return request.post<DuplexAgentConfig>(`${DUPLEX_BASE}/agents`, data)
}

/** 删除 Agent 设计配置 */
export function deleteDuplexAgent(key: string) {
  return request.delete(`${DUPLEX_BASE}/agents/${encodeURIComponent(key)}`)
}

/** 列出输出渠道配置 */
export function listDuplexChannels() {
  return request.get<{ items: DuplexChannelConfig[] }>(`${DUPLEX_BASE}/channels`)
}

/** 新增/更新输出渠道配置 */
export function upsertDuplexChannel(data: Partial<DuplexChannelConfig> & { key: string }) {
  return request.post<DuplexChannelConfig>(`${DUPLEX_BASE}/channels`, data)
}

/** 删除输出渠道配置 */
export function deleteDuplexChannel(key: string) {
  return request.delete(`${DUPLEX_BASE}/channels/${encodeURIComponent(key)}`)
}
