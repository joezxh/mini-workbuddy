import request from '@/utils/request'

const API_PREFIX = '/api/v1'

// ── 文章 ──

export function listArticles(params: {
  page?: number
  page_size?: number
  category_id?: number
  knowledge_id?: number
  status?: number
  keyword?: string
}) {
  return request.get(`${API_PREFIX}/wiki/articles`, { params })
}

export function getArticleBySlug(slug: string) {
  return request.get(`${API_PREFIX}/wiki/articles/${slug}`)
}

/** 按 ID 获取文章（消除 slug hack，配套后端 GET /wiki/articles/{id}） */
export function getArticle(id: number) {
  return request.get(`${API_PREFIX}/wiki/articles/${id}`)
}

/** OKF §10 Attested Computation 契约 */
export interface AttestedComputation {
  /** 必填（spec §10.2）：bigquery | postgres | dbt | python | Looker 等 */
  runtime?: string
  /** 参数声明：[{ name, type, required }] */
  parameters?: { name: string; type: string; required?: boolean }[]
  /** 计算文件相对路径（§6.2）；缺省用正文 # Computation 代码块 */
  computation?: string
  /** 运行指令（resource）+ 运行必须返回的收据字段（receipt） */
  executor?: { resource?: string; receipt?: string[] }
  /** 确定性检查代码路径（无 LLM） */
  attester?: { resource?: string }
}

export function createArticle(data: {
  title: string
  slug?: string
  content?: string
  summary?: string
  category_id?: number
  knowledge_id?: number | null
  tags?: string[]
  owl_class_uris?: string[]
  wiki_links?: string[]
  status?: number
  okf_type?: string | null
  resource?: string | null
  sources?: DocSource[]
  /** OKF §10 Attested Computation 契约 */
  attested_computation?: AttestedComputation | null
}) {
  return request.post(`${API_PREFIX}/wiki/articles`, data)
}

export function updateArticle(id: number, data: {
  title?: string
  content?: string
  summary?: string
  category_id?: number
  knowledge_id?: number | null
  tags?: string[]
  owl_class_uris?: string[]
  wiki_links?: string[]
  status?: number
  change_note?: string
  okf_type?: string | null
  resource?: string | null
  sources?: DocSource[]
  /** OKF §5.2 验证事件列表 [{by, at}] */
  verified?: { by?: string; at?: string }[]
  /** OKF §5.5 绝对过期时间点（ISO 8601） */
  stale_after?: string
  /** OKF §10 Attested Computation 契约 */
  attested_computation?: AttestedComputation | null
}) {
  return request.put(`${API_PREFIX}/wiki/articles/${id}`, data)
}

export function deleteArticle(id: number) {
  return request.delete(`${API_PREFIX}/wiki/articles/${id}`)
}

export function getArticleVersions(articleId: number) {
  return request.get(`${API_PREFIX}/wiki/articles/${articleId}/versions`)
}

/** 版本 diff：目标版本 vs 当前版本；传 target 时为两历史版本互比 */
export function diffArticle(articleId: number, versionId: number, target?: number) {
  return request.get(`${API_PREFIX}/wiki/articles/${articleId}/versions/${versionId}/diff`, {
    params: target ? { target } : undefined,
  })
}

/** 非破坏式回滚：以历史版本内容生成新的当前版本 */
export function rollbackArticle(articleId: number, versionId: number, changeNote?: string) {
  return request.post(`${API_PREFIX}/wiki/articles/${articleId}/rollback`, {
    version_id: versionId,
    change_note: changeNote,
  })
}

export function searchArticles(q: string, top_k?: number) {
  return request.get(`${API_PREFIX}/wiki/search`, { params: { q, top_k } })
}

export function searchWiki(data: {
  query: string
  mode?: 'semantic' | 'keyword' | 'hybrid'
  top_k?: number
  knowledge_id?: number
}) {
  return request.post(`${API_PREFIX}/wiki/search`, data)
}

export function askWiki(data: { query: string; top_k?: number; knowledge_id?: number }) {
  return request.post(`${API_PREFIX}/wiki/ask`, data)
}

export function listSearchLogs(params: { page?: number; page_size?: number; mode?: string }) {
  return request.get(`${API_PREFIX}/wiki/search-logs`, { params })
}

/**
 * 后台重建文章向量索引（存量为 NULL 的 content_vector 的唯一修复入口）。
 * 返回 { started, tenant_id, knowledge_id }，索引在后台线程执行，不阻塞界面。
 */
export function reindexWiki(knowledgeId?: number | null) {
  return request.post(
    `${API_PREFIX}/wiki/reindex`,
    null,
    { params: knowledgeId ? { knowledge_id: knowledgeId } : undefined },
  )
}

// ── 文档导入（上传转 Markdown + 字段提取，不写库）──

export interface DocSource {
  resource: string
  /** OKF §6.1：footnote 的 join 键（正文 [^id] ↔ sources[].id） */
  id?: string | null
  title?: string | null
  author?: string | null
  last_modified?: string | null
  usage_count?: number | null
}

export interface ArticleConvertResult {
  markdown: string
  resource: string
  filename: string
  title?: string | null
  summary?: string | null
  tags: string[]
  okf_type?: string | null
  sources: DocSource[]
}

/** 上传文档 → 后端转 Markdown 并提取字段（结果需人工确认后再保存） */
export function convertDocument(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request.post(`${API_PREFIX}/wiki/articles/convert-document`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
}

// ── 分类 ──

export function listCategories() {
  return request.get(`${API_PREFIX}/wiki/categories`)
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
  return request.post(`${API_PREFIX}/wiki/categories`, data)
}

export function updateCategory(id: number, data: {
  name?: string
  description?: string
  parent_id?: number
  sort_order?: number
}) {
  return request.put(`${API_PREFIX}/wiki/categories/${id}`, data)
}

export function deleteCategory(id: number) {
  return request.delete(`${API_PREFIX}/wiki/categories/${id}`)
}

// ── 知识库（仅 wiki 类型） ──

export function listKnowledges() {
  return request.get(`${API_PREFIX}/wiki/knowledges`)
}

export function createKnowledge(data: {
  name: string
  description?: string
  type?: number
  kb_format?: string | null
  index_mode?: string
  multimodal_enabled?: boolean
  pipeline_config?: Record<string, unknown> | null
  category_id?: number | null
}) {
  return request.post(`${API_PREFIX}/wiki/knowledges`, data)
}

export function updateKnowledge(id: number, data: {
  name?: string
  description?: string
  status?: number
  category_id?: number | null
}) {
  return request.put(`${API_PREFIX}/wiki/knowledges/${id}`, data)
}

export function deleteKnowledge(id: number) {
  return request.delete(`${API_PREFIX}/wiki/knowledges/${id}`)
}

// ── OWL ──

export function listOwlClasses() {
  return request.get(`${API_PREFIX}/wiki/owl/classes`)
}

export function createOwlClass(data: {
  uri: string
  label: string
  comment?: string
  parent_uris?: string[]
}) {
  return request.post(`${API_PREFIX}/wiki/owl/classes`, data)
}

export function getOwlHierarchy() {
  return request.get(`${API_PREFIX}/wiki/owl/hierarchy`)
}

export function getOwlStats() {
  return request.get(`${API_PREFIX}/wiki/owl/stats`)
}

export function getArticlesByOwlClass(classUri: string) {
  return request.get(`${API_PREFIX}/wiki/owl/articles/${encodeURIComponent(classUri)}`)
}
