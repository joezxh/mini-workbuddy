/**
 * ReAct HITL API — 暂停/恢复/确认/取消运行中的 ReAct 编排器
 */
import request from '@/utils/request'

const BASE = '/api/v1/react'

/** 获取 ReAct 运行状态 */
export function getReactStatus(runId: string) {
  return request.get(`${BASE}/${runId}/status`)
}

/** 批准 ReAct 计划 */
export function approveReact(runId: string) {
  return request.post(`${BASE}/${runId}/approve`)
}

/** 响应 HITL 确认请求 */
export function respondReact(runId: string, data: { step_id?: string; answer: string; action: string }) {
  return request.post(`${BASE}/${runId}/respond`, data)
}

/** 暂停 ReAct 执行 */
export function pauseReact(runId: string) {
  return request.post(`${BASE}/${runId}/pause`)
}

/** 恢复 ReAct 执行 */
export function resumeReact(runId: string) {
  return request.post(`${BASE}/${runId}/resume`)
}

/** 取消 ReAct 执行 */
export function cancelReact(runId: string) {
  return request.post(`${BASE}/${runId}/cancel`)
}
