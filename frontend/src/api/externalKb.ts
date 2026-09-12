/**
 * 外部知识库 API（P3 知识治理 · 外部知识库）
 *
 * ⚠️ 后端 router 当前未注册（仅 models/connectors/connector_record.py 存在），
 * 下列路径为设计文档契约（/api/v1/connectors），需补齐后端 router 后方可连通。
 * 声明式表单依赖 getCreateParamsConfig() 返回的 schema（见设计文档 §9.1）。
 */
import request from '@/utils/request'

const BASE = '/api/v1/connectors'

export function listInstances() {
  return request.get(`${BASE}`)
}
export function getCreateParamsConfig(type: string) {
  return request.get(`${BASE}/params-config`, { params: { type } })
}
export function createInstance(data: Record<string, any>) {
  return request.post(`${BASE}`, data)
}
export function updateInstance(id: number, data: Record<string, any>) {
  return request.put(`${BASE}/${id}`, data)
}
export function deleteInstance(id: number) {
  return request.delete(`${BASE}/${id}`)
}
export function setSync(id: number, enabled: boolean, payload?: Record<string, any>) {
  return request.post(`${BASE}/${id}/sync`, { enabled, ...payload })
}
export function listSyncJobs(instanceId?: number) {
  return request.get(`${BASE}/sync-jobs`, { params: { instance_id: instanceId } })
}
