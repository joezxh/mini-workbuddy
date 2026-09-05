/**
 * AI技能进化管理 API
 */
import request from '@/utils/request'

const BASE_URL = '/api/v1/skill-evolution'

// ── Types ──────────────────────────────────────────────────────────────────

export interface SkillMetrics {
  skill_id: string
  execution_count: number
  success_rate: number
  avg_latency: number
  user_rating: number
}

export interface EvolutionConfig {
  skill_id: string
  threshold: number
  weight_success: number
  weight_latency: number
  weight_user_rating: number
  resource_score: number
  is_auto_enabled: boolean
  model_code?: string | null
}

/** 可选 LLM 文本模型 */
export interface ChatModelOption {
  code: string
  name?: string | null
  model?: string | null
  platform?: string | null
}

export interface EvolveResult {
  success: boolean
  score: number
  evolved: boolean
  message: string
}

export interface SkillVersion {
  version_number: number
  is_stable: boolean
  changes?: Record<string, any>
  created_at?: string
}

export interface EvolutionLog {
  id: number
  skill_id: string
  from_version?: number
  to_version?: number
  trigger_type: string
  result: string
  created_at?: string
}

// ── API ────────────────────────────────────────────────────────────────────

/** 获取技能执行指标 */
export function getSkillMetrics(skillId: string) {
  return request.get<SkillMetrics>(`${BASE_URL}/${skillId}/metrics`)
}

/** 获取进化配置 */
export function getEvolutionConfig(skillId: string) {
  return request.get<EvolutionConfig>(`${BASE_URL}/${skillId}/config`)
}

/** 更新进化配置 */
export function updateEvolutionConfig(skillId: string, data: Partial<EvolutionConfig>) {
  return request.put<EvolutionConfig>(`${BASE_URL}/${skillId}/config`, data)
}

/** 手动触发进化评估（可指定 model_code，覆盖配置默认值） */
export function triggerEvolution(skillId: string, modelCode?: string | null) {
  return request.post<EvolveResult>(`${BASE_URL}/${skillId}/evolve`, null, {
    params: modelCode ? { model_code: modelCode } : {},
  })
}

/** 获取系统已配置的可用 LLM 文本模型列表 */
export function getChatModels() {
  return request.get<ChatModelOption[]>(`${BASE_URL}/chat-models`)
}

/** 获取版本列表 */
export function getSkillVersions(skillId: string) {
  return request.get<SkillVersion[]>(`${BASE_URL}/${skillId}/versions`)
}

/** 回滚到指定版本 */
export function rollbackVersion(skillId: string, version: number) {
  return request.post<any>(`${BASE_URL}/${skillId}/rollback`, null, { params: { version } })
}

/** 获取进化日志 */
export function getEvolutionLogs(skillId: string, limit = 50) {
  return request.get<EvolutionLog[]>(`${BASE_URL}/${skillId}/logs`, { params: { limit } })
}
