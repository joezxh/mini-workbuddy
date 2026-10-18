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

/** 重试：用留存的原始文件重新执行 解析→清洗→切块→向量化 */
export function retryDocument(uuid: string) {
  return request.post(`${BASE}/documents/${uuid}/retry`)
}

/** 重新向量化：仅重嵌已有切片，不重新分段 */
export function reprocessDocument(uuid: string) {
  return request.post(`${BASE}/documents/${uuid}/reprocess`)
}

/** 文档处理流程：各步产出摘要 + 失败步骤 + 错误信息 */
export function getDocumentFlow(uuid: string) {
  return request.get(`${BASE}/documents/${uuid}/flow`)
}

/** 按知识库当前切片方案，对全部留存原文件的文档重新分段 */
export function rechunkKnowledge(kid: number) {
  return request.post(`${BASE}/knowledges/${kid}/rechunk`)
}

/** 已注册切片方案（含展示名与参数 Schema），供新建/编辑知识库选择 */
export function listChunkers() {
  return request.get(`${BASE}/chunkers`)
}

export function retrieve(collectionId: number, data: {
  query: string
  top_k?: number
  hybrid?: boolean
  metadata_filters?: Record<string, unknown>
}) {
  return request.post(`${BASE}/collections/${collectionId}/retrieve`, data)
}

/** 知识库检索：跨该知识库全部集合合并取 Top-K（表格库多集合场景） */
export function retrieveKnowledge(kid: number, data: {
  query: string
  top_k?: number
  hybrid?: boolean
  metadata_filters?: Record<string, unknown>
}) {
  return request.post(`${BASE}/knowledges/${kid}/retrieve`, data)
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

/** 表格导入前预览：解析前 N 行并按列定义校验（不落库、不嵌入） */
export function previewTableRecords(collectionId: number, file: File, limit = 20) {
  const fd = new FormData()
  fd.append('file', file)
  return request.post(`${BASE}/collections/${collectionId}/table-records/preview`, fd, {
    params: { limit },
  })
}

/** 表格文件导入到**指定集合**（collectionId）：无列定义则自动定义（默认全字段为向量化字段），有列定义则校验（不符 422 不落数据） */
export function importTableRecords(
  collectionId: number,
  file: File,
  embedFields?: string | string[],
) {
  const fd = new FormData()
  fd.append('file', file)
  const fields = Array.isArray(embedFields)
    ? embedFields
    : embedFields
      ? [embedFields]
      : []
  if (fields.length) fd.append('embed_fields', fields.join(','))
  return request.post(`${BASE}/collections/${collectionId}/table-records/import`, fd)
}

/** 表格文件导入（**可不指定集合**）：未指定时后端按文件表头自动新建该知识库下的集合 */
export function importTableRecordsToKnowledge(
  kid: number,
  file: File,
  opts: { collectionId?: number; embedFields?: string[] } = {},
) {
  const fd = new FormData()
  fd.append('file', file)
  // 0 = 不指定集合（后端自动新建并自动生成字段定义）
  fd.append('collection_id', String(opts.collectionId || 0))
  if (opts.embedFields?.length) fd.append('embed_fields', opts.embedFields.join(','))
  return request.post(`${BASE}/knowledges/${kid}/table-records/import`, fd)
}

/** 集合（kms_collection）简要信息 */
export interface KbCollectionItem {
  id: number
  name: string
  dimensions: number
  field_count: number
  embed_fields: string[]
  knowledge_id: number
  schema_config?: KbSchemaField[]
}

/** 某知识库下的集合列表（表格知识库上传时选择「所属集合」、展示所属集合名用） */
export function listKnowledgeCollections(kid: number) {
  return request.get(`${BASE}/knowledges/${kid}/collections`)
}

/** 新建集合（可选 slug 与字段定义）；slug 缺省自动命名 */
export function createKnowledgeCollection(
  kid: number,
  body: { slug?: string; schema_config?: KbSchemaField[]; dimensions?: number },
) {
  return request.post(`${BASE}/knowledges/${kid}/collections`, body)
}

/** 编辑集合：重命名（slug）与/或更新字段定义（schema_config）/ 维度 */
export function updateKnowledgeCollection(
  kid: number,
  id: number,
  body: { slug?: string; schema_config?: KbSchemaField[]; dimensions?: number },
) {
  return request.put(`${BASE}/knowledges/${kid}/collections/${id}`, body)
}

/** 删除集合（级联删其下全部文档与切片；不可恢复） */
export function deleteKnowledgeCollection(kid: number, id: number) {
  return request.delete(`${BASE}/knowledges/${kid}/collections/${id}`)
}

/** Q&A 直构 Chunk：仅问题被嵌入，答案随 metadata 返回 */
export function createQaRecords(collectionId: number, records: { question: string; answer: string; tags?: string[] }[]) {
  return request.post(`${BASE}/collections/${collectionId}/qa-records`, { records })
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
  params: { chunk_type?: string; q?: string; page?: number; page_size?: number } = {},
) {
  return request.get(`${BASE}/documents/${uuid}/segments`, { params })
}

/** 集合内条目列表：表格知识库「表格条目」（不传 document_id = 全部文件） */
export function listCollectionSegments(
  collectionId: number,
  params: {
    document_id?: string
    chunk_type?: string
    q?: string
    page?: number
    page_size?: number
  } = {},
) {
  return request.get(`${BASE}/collections/${collectionId}/segments`, { params })
}

/** 知识库条目列表（跨该知识库全部集合）：表格知识库「表格条目 → 全部文件」用 */
export function listKnowledgeSegments(
  kid: number,
  params: {
    document_id?: string
    chunk_type?: string
    q?: string
    page?: number
    page_size?: number
  } = {},
) {
  return request.get(`${BASE}/knowledges/${kid}/segments`, { params })
}

// ── 表格列定义（kms_collection.schema_config）───────────────────────────

/** 列定义：[{name, type, enabled, embedding(可为多个，组合成向量化内容), filterable, order}] */
export interface KbSchemaField {
  name: string
  type: 'string' | 'number' | 'boolean'
  enabled: boolean
  embedding: boolean
  filterable: boolean
  order?: number
}

export function getCollectionSchema(collectionId: number) {
  return request.get(`${BASE}/collections/${collectionId}/schema`)
}

export function updateCollectionSchema(collectionId: number, fields: KbSchemaField[]) {
  return request.put(`${BASE}/collections/${collectionId}/schema`, { fields })
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

export function getCollectionSettings(collectionId: number) {
  return request.get(`${BASE}/collections/${collectionId}/settings`)
}

export function updateCollectionSettings(collectionId: number, data: {
  embedding_provider?: string
  embedding_model?: string
  embedding_dimensions?: number
  rerank_provider?: string
  rerank_model?: string
  top_k?: number
  score_threshold?: number
  index_mode?: string
}) {
  return request.put(`${BASE}/collections/${collectionId}/settings`, data)
}

// ── 表格 / Q&A 批量（spec §10.5）───────────────────────────────────────

export function listQaRecords(collectionId: number) {
  return request.get(`${BASE}/collections/${collectionId}/qa-records`)
}

/** 表格行新增（spec §10.5 行级 CRUD）：content 为被嵌入列 */
export function createTableRecord(collectionId: number, data: {
  document_id: string
  content: string
  metadata?: Record<string, unknown>
}) {
  return request.post(`${BASE}/collections/${collectionId}/table-records`, data)
}

export function importQaFile(collectionId: number, file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return request.post(`${BASE}/collections/${collectionId}/qa-records/import`, fd)
}

export function exportQaRecords(collectionId: number) {
  return request.get(`${BASE}/collections/${collectionId}/qa-records/export`, {
    responseType: 'blob',
  })
}

/** 知识库级 Q&A 列表（问答 / 文档型知识库不依赖集合，按 kb_{kid} 标签作用域） */
export function listKnowledgeQaRecords(kid: number) {
  return request.get(`${BASE}/knowledges/${kid}/qa-records`)
}

export function createKnowledgeQaRecords(
  kid: number,
  records: { question: string; answer: string; tags?: string[] }[],
) {
  return request.post(`${BASE}/knowledges/${kid}/qa-records`, { records })
}

export function importKnowledgeQaFile(kid: number, file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return request.post(`${BASE}/knowledges/${kid}/qa-records/import`, fd)
}

export function exportKnowledgeQaRecords(kid: number) {
  return request.get(`${BASE}/knowledges/${kid}/qa-records/export`, {
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
 * 宽容导入 OKF Bundle（spec §9.4）：上传导出的 zip，由服务端解包导入并返回报告。
 *
 * 早期实现是浏览器直读 .md 文本后提交 [{path, content}]，导致导出的 zip 无法导回；
 * 现在两端都以 zip 为单位，解析与安全限制统一放在服务端。
 */
export function importOkfBundle(kid: number, file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return request.post(`/api/v1/wiki/knowledges/${kid}/okf-import`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120_000,
  })
}

// ── 知识库 / 分类管理（由 wiki.ts 迁移；前缀 /api/v1/kb） ──

export function listCategories() {
  return request.get(`${BASE}/categories`)
}

export function createCategory(data: {
  name: string
  slug?: string
  description?: string
  parent_id?: number
  knowledge_id?: number
  owl_class_uri?: string
  sort_order?: number
}) {
  return request.post(`${BASE}/categories`, data)
}

export function updateCategory(id: number, data: {
  name?: string
  description?: string
  parent_id?: number
  sort_order?: number
}) {
  return request.put(`${BASE}/categories/${id}`, data)
}

export function deleteCategory(id: number) {
  return request.delete(`${BASE}/categories/${id}`)
}

export function listKnowledges() {
  return request.get(`${BASE}/knowledges`)
}

export function createKnowledge(data: {
  name: string
  description?: string
  type?: number
  kb_format?: string | null
  /** 外部知识库平台类型（type=3/connector）：feishu/yuque/dingtalk/wecom/notion/web */
  external_type?: string | null
  index_mode?: string
  multimodal_enabled?: boolean
  pipeline_config?: Record<string, unknown> | null
  category_id?: number | null
}) {
  return request.post(`${BASE}/knowledges`, data)
}

export function updateKnowledge(id: number, data: {
  name?: string
  description?: string
  status?: number
  category_id?: number | null
  /** 外部知识库平台类型（编辑态可改平台） */
  external_type?: string | null
  /** 摄取编排（spec §10.7）：切片方案 + 嵌入模型，原生键名 */
  pipeline_config?: Record<string, unknown> | null
}) {
  return request.put(`${BASE}/knowledges/${id}`, data)
}

export function deleteKnowledge(id: number) {
  return request.delete(`${BASE}/knowledges/${id}`)
}
