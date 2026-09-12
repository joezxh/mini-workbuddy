/**
 * 知识库 API（P1 知识治理 · 知识库）
 * 后端挂载点：/agentscope/knowledge_bases（app/services/kb/kb_app.py，AgentScope RAG Service 内核）
 * 能力发现端点见设计文档 §8.0；数据集/文档/检索走原生 RAG Service 端点。
 * 注意：具体路径需与 kb_app.py 路由一致（下列为 AgentScope RAG Service 约定路径）。
 */
import request from '@/utils/request'

const BASE = '/agentscope/knowledge_bases'

// ── 能力发现（零硬编码动态渲染） ───────────────────────────────────
export function getEmbeddingModels() {
  return request.get(`${BASE}/embedding_models`)
}
export function getSupportedContentTypes() {
  return request.get(`${BASE}/supported_content_types`)
}
export function getChunkers() {
  return request.get(`${BASE}/chunkers`)
}
export function getMiddlewareParams() {
  return request.get(`${BASE}/middleware/parameters_schema`)
}

// ── 数据集（kb_ref 映射显示名/权限，列表以它为准） ──────────────────
export function listDatasets() {
  return request.get(`${BASE}`)
}
export function getDataset(kbId: string) {
  return request.get(`${BASE}/${kbId}`)
}
export function createDataset(data: Record<string, any>) {
  return request.post(`${BASE}`, data)
}
export function deleteDataset(kbId: string) {
  return request.delete(`${BASE}/${kbId}`)
}

// ── 文档 ──────────────────────────────────────────────────────────
export function uploadDocument(kbId: string, formData: FormData) {
  return request.post(`${BASE}/${kbId}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
export function listDocuments(kbId: string) {
  return request.get(`${BASE}/${kbId}/documents`)
}
export function getDocumentStatus(ids: string[]) {
  return request.get(`${BASE}/documents/status`, { params: { ids: ids.join(',') } })
}

// ── 检索测试 ──────────────────────────────────────────────────────
export function retrieve(kbId: string, query: string, topK = 5, hybrid = false) {
  return request.post(`${BASE}/${kbId}/retrieve`, { query, top_k: topK, hybrid })
}
