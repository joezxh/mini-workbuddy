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

/** 摄取编排 Schema（spec §10.7 / D8）：原生键名 + chunker/rag 参数 Schema */
export function getPipelineSchema() {
  return request.get(`${BASE}/pipelines/schema`)
}

/** 表格导入前预览：解析前 N 行，返回列名（用于字段映射面板） */
export function previewTableRecords(collection: string, file: File, limit = 20) {
  const fd = new FormData()
  fd.append('file', file)
  return request.post(`${BASE}/collections/${collection}/table-records/preview`, fd, {
    params: { limit },
  })
}

/** 表格行导入（Dify 对齐）：embed_field 列被嵌入，其余列进可过滤 metadata */
export function importTableRecords(collection: string, file: File, embedField: string) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('embed_field', embedField)
  return request.post(`${BASE}/collections/${collection}/table-records/import`, fd)
}

/** Q&A 直构 Chunk：仅问题被嵌入，答案随 metadata 返回 */
export function createQaRecords(collection: string, records: { question: string; answer: string; tags?: string[] }[]) {
  return request.post(`${BASE}/collections/${collection}/qa-records`, { records })
}

/** 管线 dry-run：样例文件走解析→切块，返回中间产物，不落库不嵌入 */
export function pipelineDryRun(file: File, opts: { chunkerType?: string; chunkerParams?: string; pipelineConfig?: string } = {}) {
  const fd = new FormData()
  fd.append('file', file)
  if (opts.chunkerType) fd.append('chunker_type', opts.chunkerType)
  if (opts.chunkerParams) fd.append('chunker_params', opts.chunkerParams)
  if (opts.pipelineConfig) fd.append('pipeline_config', opts.pipelineConfig)
  return request.post(`${BASE}/pipelines/dry-run`, fd)
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

// ── 分段详情（spec §10.5）───────────────────────────────────────────────

export interface KbSegment {
  id: number
  collection: string
  document_id: string
  chunk_index: number
  chunk_type: string
  content: string | null
  answer: string | null
  keywords: unknown
  metadata: Record<string, unknown> | null
  parent_id: number | null
  has_embedding: boolean
}

export function listDocumentSegments(
  uuid: string,
  params: { chunk_type?: string; page?: number; page_size?: number } = {},
) {
  return request.get(`${BASE}/documents/${uuid}/segments`, { params })
}

export function getSegment(id: number) {
  return request.get(`${BASE}/segments/${id}`)
}

export function updateSegment(id: number, data: {
  content?: string
  keywords?: string[]
  metadata?: Record<string, unknown>
}) {
  return request.put(`${BASE}/segments/${id}`, data)
}

export function deleteSegment(id: number) {
  return request.delete(`${BASE}/segments/${id}`)
}

export function updateSegmentKeywords(id: number, keywords: string[]) {
  return request.patch(`${BASE}/segments/${id}/keywords`, { keywords })
}

export function getSegmentCitations(id: number) {
  return request.get(`${BASE}/segments/${id}/citations`)
}

// ── 设置面板（spec §10.5）───────────────────────────────────────────────

export function getCollectionSettings(collection: string) {
  return request.get(`${BASE}/collections/${collection}/settings`)
}

export function updateCollectionSettings(collection: string, data: {
  embedding_provider?: string
  embedding_model?: string
  embedding_dimensions?: number
  rerank_provider?: string
  rerank_model?: string
  top_k?: number
  score_threshold?: number
  index_mode?: string
}) {
  return request.put(`${BASE}/collections/${collection}/settings`, data)
}

// ── 表格 / Q&A 批量（spec §10.5）───────────────────────────────────────

export function listQaRecords(collection: string) {
  return request.get(`${BASE}/collections/${collection}/qa-records`)
}

/** 表格行新增（spec §10.5 行级 CRUD）：content 为被嵌入列 */
export function createTableRecord(collection: string, data: {
  document_id: string
  content: string
  metadata?: Record<string, unknown>
}) {
  return request.post(`${BASE}/collections/${collection}/table-records`, data)
}

export function importQaFile(collection: string, file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return request.post(`${BASE}/collections/${collection}/qa-records/import`, fd)
}

export function exportQaRecords(collection: string) {
  return request.get(`${BASE}/collections/${collection}/qa-records/export`, {
    responseType: 'blob',
  })
}

// ── 外部代理端点（spec §10.2 proxy 形态）─────────────────────────────────

const PROXY_BASE = '/api/v1/external-kb-endpoints'

export function createProxyEndpoint(data: {
  name: string
  endpoint_url: string
  index_name?: string
  auth_key?: string
  metadata_mapping?: string
}) {
  return request.post(PROXY_BASE, data)
}

export function listProxyEndpoints() {
  return request.get(PROXY_BASE)
}

export function updateProxyEndpoint(id: number, data: {
  name: string
  endpoint_url: string
  index_name?: string
  auth_key?: string
  metadata_mapping?: string
}) {
  return request.put(`${PROXY_BASE}/${id}`, data)
}

export function deleteProxyEndpoint(id: number) {
  return request.delete(`${PROXY_BASE}/${id}`)
}

export function testProxyEndpoint(id: number) {
  return request.post(`${PROXY_BASE}/${id}/test`)
}

/** 调用方白名单（spec §10.6）：null 表示不限制 */
export function getProxyCallers(id: number) {
  return request.get(`${PROXY_BASE}/${id}/callers`)
}

export function updateProxyCallers(id: number, callers: string[] | null) {
  return request.put(`${PROXY_BASE}/${id}/callers`, { callers })
}

/**
 * 宽容导入 OKF Bundle（spec §9.4）：后端按 path→content 导入并返回报告。
 * 浏览器侧直读 .md 文件，避免为解析 zip 引入额外依赖。
 */
export function importOkfBundle(kid: number, files: { path: string; content: string }[]) {
  return request.post(`/api/v1/wiki/knowledges/${kid}/okf-import`, files)
}
