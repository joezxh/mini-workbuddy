/**
 * 技能仓库（Skill Hub）API
 * 支持多 Git 仓库浏览、检索、分页与一键安装 skill。
 */
import request from '@/utils/request'

const BASE_URL = '/api/v1'

export interface HubRepo {
  id: number
  name: string
  url: string
  branch: string
  is_official: boolean
  source_type?: string
  sort_order: number
  created_at?: string
  updated_at?: string
}

export interface HubCategory {
  key: string
  name: string
  count: number
}

export interface HubSkillItem {
  id: string
  name: string
  version?: string
  description?: string
  category?: string
  category_name?: string
  tags?: string[]
  path?: string
  /** UI 瞬时状态：是否正在安装（非接口字段） */
  _installing?: boolean
}

export interface HubSkillListResp {
  total: number
  page: number
  page_size: number
  items: HubSkillItem[]
}

export interface RepoCreatePayload {
  name: string
  url: string
  branch: string
}

export interface RepoUpdatePayload {
  name: string
  url: string
  branch: string
}

// ── 仓库管理 ──────────────────────────────────────────────────
export function listHubRepos(): Promise<HubRepo[]> {
  return request.get(`${BASE_URL}/ai-system/skill-hub/repos`)
}

export function createHubRepo(data: RepoCreatePayload): Promise<HubRepo> {
  return request.post(`${BASE_URL}/ai-system/skill-hub/repos`, data)
}

export function updateHubRepo(id: number, data: RepoUpdatePayload): Promise<HubRepo> {
  return request.put(`${BASE_URL}/ai-system/skill-hub/repos/${id}`, data)
}

export function deleteHubRepo(id: number): Promise<{ ok: boolean }> {
  return request.delete(`${BASE_URL}/ai-system/skill-hub/repos/${id}`)
}

export function refreshHubRepo(id: number): Promise<{ ok: boolean }> {
  return request.post(`${BASE_URL}/ai-system/skill-hub/repos/${id}/refresh`)
}

// ── 列表 / 检索 / 分页 ────────────────────────────────────────
export function listHubCategories(repoId: number): Promise<HubCategory[]> {
  return request.get(`${BASE_URL}/ai-system/skill-hub/repos/${repoId}/categories`)
}

export function listHubSkills(
  repoId: number,
  params: { category?: string; q?: string; page?: number; page_size?: number }
): Promise<HubSkillListResp> {
  return request.get(`${BASE_URL}/ai-system/skill-hub/repos/${repoId}/skills`, { params })
}

export function installHubSkill(repoId: number, skillId: string): Promise<{ package_id: string; name: string; scripts_count: number }> {
  // 安装可能触发首次 clone（大仓库耗时），单独放宽超时避免被误报为网络错误
  return request.post(`${BASE_URL}/ai-system/skill-hub/repos/${repoId}/skills/${encodeURIComponent(skillId)}/install`, undefined, { timeout: 120000 })
}
