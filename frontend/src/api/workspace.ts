/**
 * 工作空间管理 API
 */
import request from '@/utils/request'

// ========== Types ==========

export interface Workspace {
  id: number
  workspaceId: string
  name: string
  description?: string | null
  scope: 'public' | 'private'
  executionMode: 'remote' | 'local'
  workspaceType: 'local' | 'docker' | 'opensandbox'
  userId?: number | null
  config: Record<string, any>
  mcpIds?: number[] | null
  skillIds?: number[] | null
  isDefault: boolean
  is_default?: boolean | string
  status: 'active' | 'disabled'
  createdBy?: string | null
  createdAt?: string
  updatedAt?: string
}

export interface WorkspaceSimple {
  id: number
  workspaceId: string
  name: string
  scope: string
  workspaceType: string
  isDefault: boolean
}

export interface WorkspaceCreate {
  name: string
  description?: string
  scope: 'public' | 'private'
  executionMode: 'remote' | 'local'
  workspaceType: 'local' | 'docker' | 'opensandbox'
  config?: Record<string, any>
  mcpIds?: number[]
  skillIds?: number[]
}

export interface WorkspaceUpdate {
  name?: string
  description?: string
  scope?: 'public' | 'private'
  executionMode?: 'remote' | 'local'
  workspaceType?: 'local' | 'docker' | 'opensandbox'
  config?: Record<string, any>
  mcpIds?: number[]
  skillIds?: number[]
  status?: 'active' | 'disabled'
}

// ========== API ==========

export function getWorkspaces(params?: { scope?: string; keyword?: string }) {
  return request.get<Workspace[]>('/api/v1/ai/workspaces', { params })
}

export function getWorkspacesSimple() {
  return request.get<WorkspaceSimple[]>('/api/v1/ai/workspaces/simple')
}

export function getWorkspace(id: number) {
  return request.get<Workspace>(`/api/v1/ai/workspaces/${id}`)
}

export function createWorkspace(data: WorkspaceCreate) {
  return request.post<Workspace>('/api/v1/ai/workspaces', data)
}

export function updateWorkspace(id: number, data: WorkspaceUpdate) {
  return request.put<Workspace>(`/api/v1/ai/workspaces/${id}`, data)
}

export function deleteWorkspace(id: number) {
  return request.delete<{ message: string }>(`/api/v1/ai/workspaces/${id}`)
}

export function activateWorkspace(id: number) {
  return request.post<{ message: string }>(`/api/v1/ai/workspaces/${id}/activate`)
}

// ── 资源关联 ──

export function getWorkspaceMcps(id: number) {
  return request.get<{ mcpIds: number[] }>(`/api/v1/ai/workspaces/${id}/mcps`)
}

export function linkMcp(workspaceId: number, mcpId: number) {
  return request.post<{ message: string }>(`/api/v1/ai/workspaces/${workspaceId}/mcps`, { mcpId })
}

export function unlinkMcp(workspaceId: number, mcpId: number) {
  return request.delete<{ message: string }>(`/api/v1/ai/workspaces/${workspaceId}/mcps/${mcpId}`)
}

export function getWorkspaceSkills(id: number) {
  return request.get<{ skillIds: number[] }>(`/api/v1/ai/workspaces/${id}/skills`)
}

export function linkSkill(workspaceId: number, skillId: number) {
  return request.post<{ message: string }>(`/api/v1/ai/workspaces/${workspaceId}/skills`, { skillId })
}

export function unlinkSkill(workspaceId: number, skillId: number) {
  return request.delete<{ message: string }>(`/api/v1/ai/workspaces/${workspaceId}/skills/${skillId}`)
}
