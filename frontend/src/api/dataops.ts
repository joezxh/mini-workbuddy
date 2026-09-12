/**
 * DataOps 数据源 API（P2 知识治理 · 数据源）
 * 后端前缀：/api/v1/dataops（app/routers/dataops/dataops.py）
 */
import request from '@/utils/request'

const BASE = '/api/v1/dataops'

// ── 数据源 ───────────────────────────────────────────────────────
export function listSources() {
  return request.get(`${BASE}/sources`)
}
export function getSource(id: number) {
  return request.get(`${BASE}/sources/${id}`)
}
export function createSource(data: Record<string, any>) {
  return request.post(`${BASE}/sources`, data)
}
export function updateSource(id: number, data: Record<string, any>) {
  return request.put(`${BASE}/sources/${id}`, data)
}
export function deleteSource(id: number) {
  return request.delete(`${BASE}/sources/${id}`)
}
/** 探活：后端 dataops router 暂未提供 /sources/{id}/test，需补齐（见设计文档 §7.1） */
export function testSource(id: number) {
  return request.post(`${BASE}/sources/${id}/test`)
}

// ── 元数据扫描 / 浏览 ──────────────────────────────────────────────
export function scanSource(id: number, database: string, withProfile = false) {
  return request.post(`${BASE}/sources/${id}/scan`, { database, with_profile: withProfile })
}
export function listTables(id: number, database?: string) {
  return request.get(`${BASE}/sources/${id}/tables`, { params: { database } })
}
export function runQuery(id: number, sql: string, limit = 200) {
  return request.post(`${BASE}/sources/${id}/query`, { sql, limit })
}

// ── 写操作申请 / 审批 / 执行 ───────────────────────────────────────
export function createWriteRequest(body: { source_id: number; sql_text: string; database?: string }) {
  return request.post(`${BASE}/write-requests`, body)
}
export function listWriteRequests(sourceId?: number) {
  return request.get(`${BASE}/write-requests`, { params: { source_id: sourceId } })
}
export function getWriteRequest(requestId: number) {
  return request.get(`${BASE}/write-requests/${requestId}`)
}
export function approveWriteRequest(requestId: number) {
  return request.post(`${BASE}/write-requests/${requestId}/approve`)
}
export function executeWriteRequest(requestId: number, token: string) {
  return request.post(`${BASE}/write-requests/${requestId}/execute`, { token })
}

// ── 元数据标准 / 绑定 / 关系推断 ───────────────────────────────────
export function listStandards() {
  return request.get(`${BASE}/standards`)
}
export function createStandard(data: Record<string, any>) {
  return request.post(`${BASE}/standards`, data)
}
export function seedStandards() {
  return request.post(`${BASE}/standards/seed`)
}
export function bindSource(id: number, database?: string) {
  return request.post(`${BASE}/sources/${id}/bind`, { database })
}
export function inferRelations(id: number, database?: string, withOverlap = false) {
  return request.post(`${BASE}/sources/${id}/infer-relations`, { database, with_overlap: withOverlap })
}
