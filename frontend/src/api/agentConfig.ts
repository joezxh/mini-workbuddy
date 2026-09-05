import { getToken } from '@/utils/auth'

const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface AgentConfig {
  id: number
  agent_code: string
  name: string
  agent_type: string
  category?: string
  description?: string
  config?: Record<string, any>
  is_active: boolean
  sort_order: number
  strategy_code?: string
  execution_mode?: string
  system_prompt?: string
  tools?: string[]
  skills?: string[]
  mcp_servers?: Array<Record<string, any>>
  knowledge_bases?: number[]
  model_config?: AgentModelConfig
  hitl_config?: Record<string, any>
  react_config?: Record<string, any>
  context_config?: Record<string, any>
  created_by?: number
  created_at: string
  updated_at: string
  is_deleted: boolean
  /** 调用次数（前端从 trace 聚合） */
  invocation_count?: number
  /** 平均耗时（前端从 trace 聚合） */
  avg_duration?: number
}

export interface AgentStats {
  total_agents: number
  active_agents: number
  inactive_agents: number
  active_sessions: number
  total_sessions: number
  today_invocations: number
  today_success: number
  today_error: number
  avg_duration_ms: number
  total_traces: number
}

export interface AgentStrategy {
  strategy_code?: string
  execution_mode?: string
  system_prompt?: string
}

export interface AgentToolsConfig {
  tools?: string[]
  skills?: string[]
  mcp_servers?: Array<Record<string, any>>
  knowledge_bases?: number[]
}

export interface AgentModelConfig {
  provider: string
  model: string
  base_url?: string
  temperature?: number
  max_tokens?: number
  api_key_ref?: string
  /** 关联的已注册 ChatModel 代码（如已选择系统模型），用于回显 */
  model_code?: string
}

export interface AgentExecutionConfig {
  hitl_config?: Record<string, any>
  react_config?: Record<string, any>
  context_config?: Record<string, any>
}

/** 可视化配置提交体（与后端 AgentConfigCreate 嵌套结构对齐） */
export interface AgentConfigUpsert {
  agent_code: string
  name: string
  agent_type: string
  category?: string
  description?: string
  is_active?: boolean
  sort_order?: number
  strategy?: AgentStrategy
  tools?: AgentToolsConfig
  model_config?: AgentModelConfig
  execution?: AgentExecutionConfig
  config?: Record<string, any>
}

export interface AgentCreate {
  agent_code: string
  name: string
  agent_type: string
  category?: string
  description?: string
  config?: Record<string, any>
  is_active?: boolean
  sort_order?: number
}

export interface AgentUpdate {
  name?: string
  agent_type?: string
  category?: string
  description?: string
  config?: Record<string, any>
  is_active?: boolean
  sort_order?: number
}

export interface SkillPackage {
  package_id: string
  name: string
  description?: string
  icon?: string
  enabled?: boolean
}

export interface DifyFlow {
  flow_id: number
  flow_code: string
  name: string
  enabled: boolean
}

async function authHeader(): Promise<Record<string, string>> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function getAgentList(params: {
  page?: number
  page_size?: number
  agent_type?: string
  category?: string
  is_active?: boolean
  keyword?: string
}) {
  const query = new URLSearchParams()
  if (params.page) query.set('page', String(params.page))
  if (params.page_size) query.set('page_size', String(params.page_size))
  if (params.agent_type) query.set('agent_type', params.agent_type)
  if (params.category) query.set('category', params.category)
  if (params.is_active !== undefined) query.set('is_active', String(params.is_active))

  const res = await fetch(`${baseUrl}/api/v1/agent-config?${query}`, {
    headers: { ...(await authHeader()) },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getAgentDetail(id: number): Promise<AgentConfig> {
  const res = await fetch(`${baseUrl}/api/v1/agent-config/${id}`, {
    headers: { ...(await authHeader()) },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function createAgent(data: AgentCreate): Promise<AgentConfig> {
  const res = await fetch(`${baseUrl}/api/v1/agent-config`, {
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

export async function updateAgent(id: number, data: AgentUpdate): Promise<AgentConfig> {
  const res = await fetch(`${baseUrl}/api/v1/agent-config/${id}`, {
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

/** 可视化配置保存：创建或更新（嵌套结构化提交体） */
export async function saveAgentConfig(
  data: AgentConfigUpsert,
  id?: number,
): Promise<AgentConfig> {
  const url = id
    ? `${baseUrl}/api/v1/agent-config/${id}`
    : `${baseUrl}/api/v1/agent-config`
  const res = await fetch(url, {
    method: id ? 'PUT' : 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeader()) },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

/** 启用/禁用 Agent */
export async function toggleAgent(id: number, is_active?: boolean): Promise<AgentConfig> {
  const query = is_active !== undefined ? `?is_active=${is_active}` : ''
  const res = await fetch(`${baseUrl}/api/v1/agent-config/${id}/toggle${query}`, {
    method: 'POST',
    headers: { ...(await authHeader()) },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function deleteAgent(id: number) {
  const res = await fetch(`${baseUrl}/api/v1/agent-config/${id}`, {
    method: 'DELETE',
    headers: { ...(await authHeader()) },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getAgentStats(): Promise<AgentStats> {
  try {
    const res = await fetch(`${baseUrl}/api/v1/agent-config/stats/overview`, {
      headers: { ...(await authHeader()) },
    })
    if (!res.ok) return getDefaultStats()
    return res.json()
  } catch {
    return getDefaultStats()
  }
}

function getDefaultStats(): AgentStats {
  return {
    total_agents: 0,
    active_agents: 0,
    inactive_agents: 0,
    active_sessions: 0,
    total_sessions: 0,
    today_invocations: 0,
    today_success: 0,
    today_error: 0,
    avg_duration_ms: 0,
    total_traces: 0,
  }
}

export async function getSkillPackages(): Promise<SkillPackage[]> {
  const res = await fetch(`${baseUrl}/api/v1/ai-assistant/skills`, {
    headers: { ...(await authHeader()) },
  })
  if (!res.ok) return []
  const data = await res.json()
  return data.packages || data.items || data || []
}

export async function getDifyFlows(): Promise<DifyFlow[]> {
  const res = await fetch(`${baseUrl}/api/v1/dify-flows?page=1&page_size=100`, {
    headers: { ...(await authHeader()) },
  })
  if (!res.ok) return []
  const data = await res.json()
  return data.items || data || []
}

export async function getToolSimpleList(): Promise<
  Array<{ id: number; toolKey: string; displayName: string; category?: string }>
> {
  const res = await fetch(`${baseUrl}/api/v1/admin/ai/tool/simple-list`, {
    headers: { ...(await authHeader()) },
  })
  if (!res.ok) return []
  return res.json()
}