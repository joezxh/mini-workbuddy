/**
 * 外部知识库文档导入 API（/api/v1/kb/external-sources）。
 *
 * 驱动「五步导入向导」：平台元数据 → 凭据测试 → 目录/文档浏览 → 导入。
 * 凭据只入不出：后端保存走 Fernet 加密，列表接口不回传明文。
 */
import request from '@/utils/request'

const BASE = '/api/v1/kb/external-sources'

/** 凭据字段 schema（由后端下发，前端动态渲染表单） */
export interface CredFieldSchema {
  name: string
  label: string
  secret: boolean
  required: boolean
  placeholder: string
  hint: string
  multiline?: boolean
}

export interface ExternalProvider {
  source_type: string
  name: string
  desc: string
  host: string
  credential_fields: CredFieldSchema[]
}

export interface ExternalNode {
  doc_id: string
  title: string
  node_type: 'space' | 'folder' | 'doc'
  parent_id: string | null
  updated_at: string | null
  url: string | null
}

export interface ImportItem {
  external_doc_id: string
  title: string
  action: 'created' | 'updated' | 'unchanged' | 'failed'
  detail: string
}

export interface ImportSummary {
  total: number
  created: number
  updated: number
  unchanged: number
  failed: number
  items: ImportItem[]
}

export interface ExternalDocumentItem {
  external_doc_id: string
  source_type: string
  title: string
  external_updated_at: string | null
  document_id: number | null
  document_uuid: string | null
  status: string | null
  segment_count: number | null
  error_detail: string | null
  updated_at: string | null
  deleted: string
}

/** 五个平台元数据 + 各自凭据字段 schema */
export function listExternalProviders() {
  return request.get<{ items: ExternalProvider[] }>(`${BASE}/providers`)
}

/** 连通性测试 */
export function testExternalSource(sourceType: string, credentials: Record<string, any>) {
  return request.post<{ ok: boolean; message: string; identity: string }>(`${BASE}/test`, {
    source_type: sourceType,
    credentials,
  })
}

/** 浏览目录/文档（懒加载当前层级）。
 * 传 knowledgeId 且 credentials 为空时，由服务端回退读取已保存（加密）凭据，
 * 使导入向导可跳过「配置凭据」一步。 */
export function listExternalNodes(
  sourceType: string,
  credentials: Record<string, any>,
  parentId?: string | null,
  knowledgeId?: number | null,
) {
  return request.post<{ items: ExternalNode[] }>(`${BASE}/nodes`, {
    source_type: sourceType,
    credentials,
    parent_id: parentId ?? null,
    knowledge_id: knowledgeId ?? null,
  })
}

/** 固化平台凭据到指定外部知识库（创建/编辑向导在容器建好后调用） */
export function saveExternalCredentials(data: {
  knowledge_id: number
  source_type: string
  credentials: Record<string, any>
}) {
  return request.post(`${BASE}/credentials`, data)
}

/** 读取外部知识库的平台类型与是否已配置凭据 */
export function getExternalConfig(knowledgeId: number) {
  return request.get<{ external_type: string | null; has_credentials: boolean }>(
    `${BASE}/knowledges/${knowledgeId}/external-config`,
  )
}

/** 导入 / 重新导入（幂等：已存在则覆盖，不存在则新建） */
export function importExternalDocuments(data: {
  knowledge_id: number
  source_type: string
  doc_refs: { doc_id: string; title: string }[]
  credentials?: Record<string, any> | null
  chunker_type?: string
  chunker_params?: Record<string, any> | null
  save_credentials?: boolean
}) {
  return request.post<ImportSummary>(`${BASE}/import`, data)
}

/** 已导入文档列表 */
export function listExternalDocuments(knowledgeId: number) {
  return request.get<{ items: ExternalDocumentItem[] }>(
    `${BASE}/knowledges/${knowledgeId}/external-documents`,
  )
}
