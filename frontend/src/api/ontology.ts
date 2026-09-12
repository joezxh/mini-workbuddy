/**
 * 本体 API（P4 知识治理 · 本体）
 *
 * ⚠️ 后端 router 当前未注册（仅 models/ontology + services/ontology/ontology_repository.py 存在），
 * 下列路径为设计文档契约（/api/v1/ontology），需补齐后端 router 后方可连通。
 */
import request from '@/utils/request'

const BASE = '/api/v1/ontology'

// ── 本体列表 / CRUD / TTL 导入导出 ─────────────────────────────────
export function listOntologies() {
  return request.get(`${BASE}`)
}
export function getOntology(id: number) {
  return request.get(`${BASE}/${id}`)
}
export function createOntology(data: Record<string, any>) {
  return request.post(`${BASE}`, data)
}
export function updateOntology(id: number, data: Record<string, any>) {
  return request.put(`${BASE}/${id}`, data)
}
export function deleteOntology(id: number) {
  return request.delete(`${BASE}/${id}`)
}
export function importTtl(id: number, file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return request.post(`${BASE}/${id}/import`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
}
export function exportTtl(id: number) {
  return request.get(`${BASE}/${id}/export`, { responseType: 'blob' })
}

// ── 类层级 ────────────────────────────────────────────────────────
export function listClasses(ontologyId: number) {
  return request.get(`${BASE}/${ontologyId}/classes`)
}
export function createClass(ontologyId: number, data: Record<string, any>) {
  return request.post(`${BASE}/${ontologyId}/classes`, data)
}
export function updateClass(ontologyId: number, classId: number, data: Record<string, any>) {
  return request.put(`${BASE}/${ontologyId}/classes/${classId}`, data)
}
export function deleteClass(ontologyId: number, classId: number) {
  return request.delete(`${BASE}/${ontologyId}/classes/${classId}`)
}

// ── 建模（对象类型/属性/关系/CQ） ──────────────────────────────────
export function listObjectTypes(ontologyId: number) {
  return request.get(`${BASE}/${ontologyId}/object-types`)
}
export function createObjectType(ontologyId: number, data: Record<string, any>) {
  return request.post(`${BASE}/${ontologyId}/object-types`, data)
}
export function listRelations(ontologyId: number) {
  return request.get(`${BASE}/${ontologyId}/relations`)
}
export function listCqs(ontologyId: number) {
  return request.get(`${BASE}/${ontologyId}/cqs`)
}

// ── 评审与版本 ────────────────────────────────────────────────────
export function listReviewItems(ontologyId: number) {
  return request.get(`${BASE}/${ontologyId}/review`)
}
export function reviewItem(ontologyId: number, itemId: number, decision: 'accepted' | 'rejected') {
  return request.post(`${BASE}/${ontologyId}/review/${itemId}`, { decision })
}
export function listVersions(ontologyId: number) {
  return request.get(`${BASE}/${ontologyId}/versions`)
}
