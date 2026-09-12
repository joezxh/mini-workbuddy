import request from '@/utils/request'

const BASE = '/api/v1/workflow'

// ── Flow CRUD ──────────────────────────────────────────
export function listFlows(params: Record<string, any> = {}) {
  return request.get(`${BASE}/flows`, { params })
}
export function createFlow(data: Record<string, any>) {
  return request.post(`${BASE}/flows`, data)
}
export function getFlow(id: number) {
  return request.get(`${BASE}/flows/${id}`)
}
export function updateFlow(id: number, data: Record<string, any>) {
  return request.put(`${BASE}/flows/${id}`, data)
}
export function deleteFlow(id: number) {
  return request.delete(`${BASE}/flows/${id}`)
}
export function testFlow(id: number, data: Record<string, any>) {
  return request.post(`${BASE}/flows/${id}/test`, data)
}

// ── Execution Log ──────────────────────────────────────
export function listExecutions(params: Record<string, any> = {}) {
  return request.get(`${BASE}/executions`, { params })
}

// ── Chain ──────────────────────────────────────────────
export function listChains(params: Record<string, any> = {}) {
  return request.get(`${BASE}/chains`, { params })
}
export function createChain(data: Record<string, any>) {
  return request.post(`${BASE}/chains`, data)
}
export function updateChain(id: number, data: Record<string, any>) {
  return request.put(`${BASE}/chains/${id}`, data)
}
export function deleteChain(id: number) {
  return request.delete(`${BASE}/chains/${id}`)
}

// ── 枚举 ──────────────────────────────────────────────
export function getPlatformTypes() {
  return request.get(`${BASE}/platforms/types`)
}
