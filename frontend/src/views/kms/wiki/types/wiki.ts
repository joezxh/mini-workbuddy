// Wiki 模块共享类型定义（G1/G7/G8/G9）

export type SearchMode = 'semantic' | 'keyword' | 'hybrid'

export interface SearchItem {
  id: number
  slug: string
  title: string
  summary?: string
  snippet: string
  score: number
  category_id?: number
}

export interface SearchResult {
  query: string
  mode: SearchMode
  total: number
  items: SearchItem[]
}

export interface CitationItem {
  ref: number
  article_id: number
  slug: string
  title: string
  snippet: string
}

export interface LLMWikiAnswer {
  answer: string
  citations: CitationItem[]
  mode: string
}

export interface WikiKnowledge {
  id: number
  name: string
  description?: string
  status: number
  doc_count?: number
  created_at?: string
  updated_at?: string
}

export interface CategoryNode {
  id: number
  name: string
  knowledge_id?: number
  parent_id?: number
  article_count?: number
  children?: CategoryNode[]
}

export interface VersionItem {
  id: number
  article_id: number
  version: number
  title: string
  slug?: string
  change_note?: string
  editor_id?: number
  operation_type: string
  created_at?: string
}

export interface SearchLogItem {
  id: number
  query: string
  mode: string
  result_count: number
  latency_ms?: number
  created_at?: string
}
