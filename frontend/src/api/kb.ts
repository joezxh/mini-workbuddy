/**
 * 统一知识库工作台 API（spec §5/§10.5）。
 * 全部走主应用认证面 /api/v1；子应用 /agentscope/knowledge_bases 仅内核间调用。
 */
import request from '@/utils/request'

const BASE = '/api/v1/kb'

export interface KbDocument {
  document_id: string
  name: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  file_type: string | null
  file_size: number | null
  segment_count: number
  error_detail: string | null
}

export interface RetrieveResult {
  score: number
  document_id: string
  chunk_index: number
  content: string
  metadata: Record<string, unknown>
}

export function uploadDocument(kid: number, formData: FormData) {
  return request.post(`${BASE}/knowledges/${kid}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function listDocuments(kid: number) {
  return request.get(`${BASE}/knowledges/${kid}/documents`)
}

export function deleteDocument(uuid: string) {
  return request.delete(`${BASE}/documents/${uuid}`)
}

export function getDocumentStatus(ids: string[]) {
  return request.get(`${BASE}/documents/status`, { params: { ids: ids.join(',') } })
}

export function retrieve(collection: string, data: {
  query: string
  top_k?: number
  hybrid?: boolean
  metadata_filters?: Record<string, unknown>
}) {
  return request.post(`${BASE}/collections/${collection}/retrieve`, data)
}

export function getSupportedContentTypes() {
  return request.get(`${BASE}/supported_content_types`)
}

export function getChunkers() {
  return request.get(`${BASE}/chunkers`)
}

/** OKF 合规层（spec §9.4） */
export function exportOkfBundle(kid: number) {
  return request.get(`/api/v1/wiki/knowledges/${kid}/okf-export`, {
    responseType: 'blob',
  })
}

export function getArticleOkf(articleId: number) {
  return request.get(`/api/v1/wiki/articles/${articleId}/okf`)
}
