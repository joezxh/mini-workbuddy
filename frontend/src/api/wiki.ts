import request from '@/utils/request'

const API_PREFIX = '/api/v1'

// ── 文章 ──

export function listArticles(params: {
  page?: number
  page_size?: number
  category_id?: number
  status?: number
  keyword?: string
}) {
  return request.get(`${API_PREFIX}/wiki/articles`, { params })
}

export function getArticleBySlug(slug: string) {
  return request.get(`${API_PREFIX}/wiki/articles/${slug}`)
}

export function createArticle(data: {
  title: string
  slug?: string
  content?: string
  summary?: string
  category_id?: number
  tags?: string[]
  owl_class_uris?: string[]
  wiki_links?: string[]
  status?: number
}) {
  return request.post(`${API_PREFIX}/wiki/articles`, data)
}

export function updateArticle(id: number, data: {
  title?: string
  content?: string
  summary?: string
  category_id?: number
  tags?: string[]
  owl_class_uris?: string[]
  wiki_links?: string[]
  status?: number
  change_note?: string
}) {
  return request.put(`${API_PREFIX}/wiki/articles/${id}`, data)
}

export function deleteArticle(id: number) {
  return request.delete(`${API_PREFIX}/wiki/articles/${id}`)
}

export function getArticleVersions(articleId: number) {
  return request.get(`${API_PREFIX}/wiki/articles/${articleId}/versions`)
}

export function searchArticles(q: string, top_k?: number) {
  return request.get(`${API_PREFIX}/wiki/search`, { params: { q, top_k } })
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
  owl_class_uri?: string
  sort_order?: number
}) {
  return request.post(`${API_PREFIX}/wiki/categories`, data)
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
