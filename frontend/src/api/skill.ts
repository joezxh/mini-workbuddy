/**
 * AI技能 API
 */
import request from '@/utils/request'
import { resolveApiUrl } from '@/utils/apiBase'

const BASE_URL = '/api/v1'

export type SkillParamType = 'text' | 'select' | 'textarea'

export interface SkillParam {
  name: string
  type?: SkillParamType
  label?: string
  required?: boolean
  options?: string[]
  default?: string
}

export interface SkillScript {
  id?: number
  script_id: string
  name: string
  description?: string
  command: string
  params?: SkillParam[]
  sort_order?: number
  enabled?: boolean
  created_at?: string
}

export interface SkillPackage {
  id?: number
  package_id: string
  name: string
  description?: string
  icon?: string
  category?: string
  version?: string
  enabled?: boolean
  file_path?: string
  created_by?: number
  created_at?: string
  updated_at?: string
  skill_markdown?: string | null
  scripts?: SkillScript[]
}

export interface SkillListResponse {
  packages: SkillPackage[]
  total: number
}

// ── 管理 API ──────────────────────────────────────────────────────────────────

export function getSkills(params?: { category?: string; enabled?: boolean }): Promise<SkillListResponse> {
  return request.get(`${BASE_URL}/ai-assistant/skills`, { params })
}

export function getSkillPackage(packageId: string): Promise<{ data: SkillPackage }> {
  return request.get(`${BASE_URL}/ai-assistant/skills/${packageId}`)
}

export function createSkillPackage(data: {
  package_id: string
  name: string
  category?: string
  description?: string
  icon?: string
  version?: string
}): Promise<{ data: { package_id: string } }> {
  return request.post(`${BASE_URL}/ai-assistant/skills`, data)
}

export function updateSkillPackage(
  packageId: string,
  data: Partial<Pick<SkillPackage, 'name' | 'category' | 'description' | 'icon' | 'version' | 'enabled'>>
): Promise<{ data: { ok: boolean } }> {
  return request.put(`${BASE_URL}/ai-assistant/skills/${packageId}`, data)
}

export function deleteSkillPackage(packageId: string): Promise<{ data: { deleted: boolean } }> {
  return request.delete(`${BASE_URL}/ai-assistant/skills/${packageId}`)
}

export function importSkillPackage(file: File): Promise<{ data: { package_id: string; name: string; scripts_count: number } }> {
  const form = new FormData()
  form.append('file', file)
  // 关键：axios 实例默认 Content-Type 为 application/json，会干扰 FormData 的
  // multipart 自动识别（导致后端收不到 file 字段 → 422）。
  // 此处显式将 Content-Type 置为 undefined，交由 axios 自动补全
  // multipart/form-data; boundary=...，确保后端能正确解析。
  return request.post(`${BASE_URL}/ai-assistant/skills/import`, form, {
    headers: { 'Content-Type': undefined as unknown as string },
  })
}

export function exportSkillPackage(packageId: string): Promise<Blob> {
  return request.get(`${BASE_URL}/ai-assistant/skills/${packageId}/export`, {
    responseType: 'blob',
  })
}

export function createScript(
  packageId: string,
  data: {
    script_id: string
    name: string
    command: string
    description?: string
    params?: SkillParam[]
    sort_order?: number
  }
): Promise<{ data: { script_id: string } }> {
  return request.post(`${BASE_URL}/ai-assistant/skills/${packageId}/scripts`, data)
}

export function updateScript(
  packageId: string,
  scriptId: string,
  data: Partial<Pick<SkillScript, 'name' | 'command' | 'description' | 'params' | 'sort_order' | 'enabled'>>
): Promise<{ data: { ok: boolean } }> {
  return request.put(`${BASE_URL}/ai-assistant/skills/${packageId}/scripts/${scriptId}`, data)
}

export function deleteScript(packageId: string, scriptId: string): Promise<{ data: { deleted: boolean } }> {
  return request.delete(`${BASE_URL}/ai-assistant/skills/${packageId}/scripts/${scriptId}`)
}

// ── SKILL.md 文档 API ────────────────────────────────────────────────────────────────────────────

// 技能执行统一走 POST /ai-agent/chat/stream（SSE 流式），历史回放走
// GET /ai-agent/skill-execution/{execution_id}/events，旧版同步任务轮询接口（V1）已删除。

export function getSkillMarkdown(packageId: string): Promise<{ package_id: string; content: string }> {
  return request.get(`${BASE_URL}/ai-assistant/skills/${packageId}/skill-md`)
}

/** 保存 SKILL.md 内容（数据库优先 + 同步文件系统） */
export function saveSkillMarkdown(packageId: string, content: string): Promise<{ data: { ok: boolean; package: SkillPackage } }> {
  return request.put(`${BASE_URL}/ai-assistant/skills/${packageId}/skill-md`, { content })
}

// ── 工具 ─────────────────────────────────────────────────────────────────────

export const ICON_OPTIONS = [
  { value: 'tool', label: '🔧' },
  { value: 'database', label: '💾' },
  { value: 'file', label: '📄' },
  { value: 'search', label: '🔍' },
  { value: 'chart', label: '📊' },
  { value: 'gavel', label: '⚖️' },
  { value: 'bell', label: '🔔' },
  { value: 'code', label: '💻' },
  { value: 'other', label: '📦' },
]

// ── 技能产物 ────────────────────────────────────────────────────────────

export interface ArtifactItem {
  file_id: string
  filename: string
  size_bytes: number
  mime_type: string
}

export interface ArtifactListResp {
  execution_id: string
  total: number
  items: ArtifactItem[]
}

/** 列出指定执行的产物文件 */
export function listArtifacts(executionId: string) {
  return request.get<ArtifactListResp>(`${BASE_URL}/ai-agent/skill-execution/${executionId}/artifacts`)
}

/** 构造产物下载 URL（直接用于 fetch 下载） */
export function artifactDownloadUrl(fileId: string): string {
  return resolveApiUrl(`/api/v1/ai-agent/skill-artifacts/${fileId}/download`)
}
