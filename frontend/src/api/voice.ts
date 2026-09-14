/**
 * 调解语音 WebSocket API 构造层（差距分析 §3.4 协议 v2）
 *
 * 后端语音网关挂载于 /api/v1/duplex/voice/ws（router prefix=/duplex/voice，
 * 应用挂载前缀 /api/v1）。本文件负责把 ConnectConfig 组装成完整 ws(s) URL。
 */
import request from '@/utils/request'
import type {
  ConnectConfig,
  AgentConfig,
  VoiceRoleConfig,
  ToolPolicy,
  VoiceModel,
  VoiceModelDefault,
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

// ── M3 语音配置管理（角色语音 / Agent / 工具策略） ──────────

/** 保存（UPSERT）角色语音配置 */
export function upsertVoiceRole(cfg: VoiceRoleConfig) {
  return request.post(`${ADMIN_BASE}/voice-roles`, cfg)
}

/** 获取角色语音配置列表 */
export function listVoiceRoles() {
  return request.get<VoiceRoleConfig[]>(`${ADMIN_BASE}/voice-roles`)
}

/** 保存（UPSERT）Agent 配置 */
export function upsertAgentConfig(cfg: AgentConfig) {
  return request.post(`${ADMIN_BASE}/agents`, cfg)
}

/** 获取 Agent 配置列表 */
export function listAgentConfigs() {
  return request.get<AgentConfig[]>(`${ADMIN_BASE}/agents`)
}

/** 保存（UPSERT）工具调用策略 */
export function upsertToolPolicy(cfg: ToolPolicy) {
  return request.post(`${ADMIN_BASE}/tool-policy`, cfg)
}

/** 获取工具调用策略列表 */
export function listToolPolicies() {
  return request.get<ToolPolicy[]>(`${ADMIN_BASE}/tool-policy`)
}

// ── 语音模型配置（来自 ai_api_key / ai_chat_model） ──────────

/** 列出所有启用的语音模型 */
export function listVoiceModels() {
  return request.get<VoiceModel[]>(`${ADMIN_BASE}/voice-models`)
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
