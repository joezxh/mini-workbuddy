import { getToken } from '@/utils/auth'

const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface SkillRule {
  id: number
  name: string
  conditions?: Record<string, any>
  package_id: string
  agent_name?: string
  priority: number
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface SkillRuleCreate {
  name: string
  package_id: string
  agent_name?: string
  priority: number
  is_active?: boolean
  conditions?: Record<string, any>
}

export interface SkillRuleUpdate {
  name?: string
  package_id?: string
  agent_name?: string
  priority?: number
  is_active?: boolean
  conditions?: Record<string, any>
}

async function authHeader(): Promise<Record<string, string>> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function getSkillRules(params: {
  page?: number
  page_size?: number
  package_id?: string
  agent_name?: string
  keyword?: string
}) {
  const query = new URLSearchParams()
  if (params.page) query.set('page', String(params.page))
  if (params.page_size) query.set('page_size', String(params.page_size))
  if (params.package_id) query.set('package_id', params.package_id)
  if (params.agent_name) query.set('agent_name', params.agent_name)
  if (params.keyword) query.set('keyword', params.keyword)

  const res = await fetch(`${baseUrl}/api/v1/skill-rules?${query}`, {
    headers: { ...(await authHeader()) },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getSkillRuleById(id: number): Promise<SkillRule> {
  const res = await fetch(`${baseUrl}/api/v1/skill-rules/${id}`, {
    headers: { ...(await authHeader()) },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function createSkillRule(data: SkillRuleCreate): Promise<SkillRule> {
  const res = await fetch(`${baseUrl}/api/v1/skill-rules`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeader()) },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function updateSkillRule(id: number, data: SkillRuleUpdate): Promise<SkillRule> {
  const res = await fetch(`${baseUrl}/api/v1/skill-rules/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...(await authHeader()) },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function deleteSkillRule(id: number) {
  const res = await fetch(`${baseUrl}/api/v1/skill-rules/${id}`, {
    method: 'DELETE',
    headers: { ...(await authHeader()) },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}