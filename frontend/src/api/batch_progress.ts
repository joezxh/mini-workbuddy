/**
 * 批量任务进度查询 API
 */
import request from '@/utils/request'

const BASE_URL = '/api/v1/batch-progress'

export interface BatchGroup {
  batch_group_id: string
  task_code: string
  started_at: string
  total_persons: number
  success: number
  failed: number
  in_progress: number
  progress_percent: number
  estimated_completion?: string
  subtasks?: BatchSubtask[]
}

export interface BatchSubtask {
  person_id: string
  status: 'success' | 'failed' | 'in_progress' | 'pending'
  start_time?: string
  end_time?: string
  duration_seconds?: number
  error_message?: string
  agent_stage?: string
}

export interface BatchProgressListResp {
  data: BatchGroup[]
  total: number
  page: number
  pageSize: number
}

// 获取活跃批次列表
export function getBatchProgressList(params?: {
  page?: number
  pageSize?: number
  task_code?: string
  status?: 'active' | 'completed' | 'failed'
}) {
  return request.get<BatchProgressListResp>(`${BASE_URL}/groups`, { params })
}

// 获取批次详情（含子任务明细）
export function getBatchDetail(batchGroupId: string) {
  return request.get<{ group: BatchGroup; subtasks: BatchSubtask[] }>(`${BASE_URL}/groups/${batchGroupId}`)
}

// 获取个人执行日志
export function getPersonExecutionLogs(personId: string, params?: {
  page?: number
  pageSize?: number
  stage?: string
  status?: string
}) {
  return request.get<{ data: BatchSubtask[]; total: number; page: number; pageSize: number }>(
    `${BASE_URL}/persons/${personId}/logs`,
    { params }
  )
}
