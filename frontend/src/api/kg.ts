/**
 * 图谱知识库 API（type=4 实例层）。
 *
 * 与既有 `api/kb.ts` / `api/knowledgeBase.ts` 并列而不复用：那两个模块职责已重复，
 * 图谱实例层单独成模块，避免继续加剧耦合（spec 决策 F7）。
 *
 * 端点前缀：/api/v1/kb/knowledges/{kid}/graph
 * 鉴权：读 kb:view / 写 kb:admin（后端 require_kb_permission 闭合，前端隐藏非授权操作仅为 UX）
 */
import request from '@/utils/request'

const BASE = '/api/v1/kb/knowledges'

export type KgEntityStatus = 'suggested' | 'active' | 'deprecated'
export type KgRelationStatus = 'suggested' | 'accepted' | 'rejected'

export interface KgEntity {
  id: number
  name: string
  /** 规范化去重键（后端生成，前端只读展示） */
  entity_key: string
  /** 实体类型 → CDM meta_object_standard.code */
  type_code: string | null
  aliases: string[]
  properties: Record<string, unknown>
  status: KgEntityStatus
  mention_count: number
  source_segment_ids: number[]
  source_document_ids: string[]
  has_vector: boolean
  created_at: string | null
  updated_at: string | null
  /** 仅详情接口返回 */
  adjacent_relations?: KgRelation[]
}

export interface KgRelation {
  id: number
  /** 关系类型 → CDM meta_object_relation.code；空串 = 自由谓词 */
  relation_code: string
  predicate: string | null
  from_entity_id: number
  from_entity_name: string | null
  to_entity_id: number
  to_entity_name: string | null
  /** 抽取置信度 0~1 */
  weight: number | null
  status: KgRelationStatus
  properties: Record<string, unknown>
  evidence: Record<string, unknown> | null
  created_at: string | null
  updated_at: string | null
}

export interface KgListResult<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface KgStats {
  entities: number
  relations: number
  by_type: Record<string, number>
  by_relation: Record<string, number>
}

export interface KgEntityQuery {
  type_code?: string
  status?: string
  keyword?: string
  limit?: number
  offset?: number
}

export interface KgRelationQuery {
  relation_code?: string
  status?: string
  from_entity_id?: number
  to_entity_id?: number
  limit?: number
  offset?: number
}

export interface KgEntityPayload {
  name: string
  entity_key?: string
  type_code?: string
  aliases?: string[]
  properties?: Record<string, unknown>
}

export interface KgRelationPayload {
  from_entity_id: number
  to_entity_id: number
  relation_code?: string
  predicate?: string
  weight?: number
  properties?: Record<string, unknown>
}

export function listEntities(kid: number, params?: KgEntityQuery) {
  return request.get<KgListResult<KgEntity>>(`${BASE}/${kid}/graph/entities`, { params })
}

export function createEntity(kid: number, body: KgEntityPayload) {
  return request.post<KgEntity>(`${BASE}/${kid}/graph/entities`, body)
}

export function getEntity(kid: number, entityId: number) {
  return request.get<KgEntity>(`${BASE}/${kid}/graph/entities/${entityId}`)
}

export function updateEntity(kid: number, entityId: number, body: Partial<KgEntityPayload>) {
  return request.put<KgEntity>(`${BASE}/${kid}/graph/entities/${entityId}`, body)
}

export function deleteEntity(kid: number, entityId: number) {
  return request.delete<{ ok: boolean; id: number }>(`${BASE}/${kid}/graph/entities/${entityId}`)
}

/** 实体评审：suggested -> active */
export function acceptEntity(kid: number, entityId: number) {
  return request.patch<KgEntity>(`${BASE}/${kid}/graph/entities/${entityId}/accept`)
}

export function listRelations(kid: number, params?: KgRelationQuery) {
  return request.get<KgListResult<KgRelation>>(`${BASE}/${kid}/graph/relations`, { params })
}

export function createRelation(kid: number, body: KgRelationPayload) {
  return request.post<KgRelation>(`${BASE}/${kid}/graph/relations`, body)
}

export function getRelation(kid: number, relationId: number) {
  return request.get<KgRelation>(`${BASE}/${kid}/graph/relations/${relationId}`)
}

export function deleteRelation(kid: number, relationId: number) {
  return request.delete<{ ok: boolean; id: number }>(`${BASE}/${kid}/graph/relations/${relationId}`)
}

/** 关系评审：suggested -> accepted | rejected */
export function reviewRelation(kid: number, relationId: number, verdict: 'accepted' | 'rejected') {
  return request.patch<KgRelation>(`${BASE}/${kid}/graph/relations/${relationId}/review`, { verdict })
}

export function getGraphStats(kid: number) {
  return request.get<KgStats>(`${BASE}/${kid}/graph/stats`)
}

// ── 构建管理（P3）───────────────────────────────────────────────────────
export type KgBuildState =
  | 'not_built' | 'pending' | 'running' | 'ready' | 'partial_failed'

export interface KgBuildStatus {
  state: KgBuildState
  running: boolean
  neo4j_available: boolean
  segments: number
  structure_done: number
  vector_done: number
  failed: number
}

export interface KgFailedSegment {
  segment_id: number
  document_id: string
  chunk_index: number
  structure_indexed: boolean | null
  vector_indexed: boolean | null
  details: Record<string, unknown> | null
}

export interface KgGraphConfig {
  extractor_type: string
  model_spec: Record<string, unknown> | null
  schema_source: 'none' | 'cdm' | 'free_text'
  catalog_id: number | null
  schema: string
  concurrency_count: number
  timeout_seconds: number
  use_graph_retrieval: boolean
  graph_entity_top_k: number
  graph_triple_top_k: number
  graph_max_nodes: number
  graph_top_k: number
  graph_weight: number
  ppr_damping: number
}

export type KgBuildAction = 'build' | 'clear_document' | 'rebuild' | 'reconcile'

export function submitGraphBuild(
  kid: number,
  action: KgBuildAction = 'build',
  documentUuid?: string,
) {
  return request.post<{ accepted: boolean; action: string; knowledge_id: number }>(
    `${BASE}/${kid}/graph-build/submit`,
    { action, document_uuid: documentUuid },
  )
}

export function getGraphBuildStatus(kid: number) {
  return request.get<KgBuildStatus>(`${BASE}/${kid}/graph-build/status`)
}

export function listFailedSegments(kid: number) {
  return request.get<{ items: KgFailedSegment[]; total: number }>(
    `${BASE}/${kid}/graph/failed-segments`,
  )
}

export function getGraphConfig(kid: number) {
  return request.get<KgGraphConfig>(`${BASE}/${kid}/graph/config`)
}

export function saveGraphConfig(kid: number, body: Partial<KgGraphConfig>) {
  return request.put<KgGraphConfig>(`${BASE}/${kid}/graph/config`, body)
}

export function rebuildDocumentGraph(kid: number, documentUuid: string) {
  return request.post<{ accepted: boolean }>(
    `${BASE}/${kid}/graph/documents/rebuild`,
    { document_uuid: documentUuid },
  )
}

// ── 图查询（P5）──────────────────────────────────────────────────────────
export interface KgGraphNode {
  id: number
  name: string
  code: string
  type_code?: string
  entity_key?: string
  status?: string
}

export interface KgGraphEdge {
  id: number
  from: number
  to: number
  relation_type: string
  predicate?: string | null
  weight?: number | null
  status?: string
}

export interface KgSubgraph {
  nodes: KgGraphNode[]
  edges: KgGraphEdge[]
}

export interface KgPath {
  nodes: KgGraphNode[]
  edges: KgGraphEdge[]
}

export interface KgLabel {
  code: string
  name: string
  count: number
}

export function getSubgraph(
  kid: number,
  entityIds: number[],
  depth = 1,
  limit = 200,
) {
  return request.get<KgSubgraph>(`${BASE}/${kid}/graph/subgraph`, {
    params: { entity_ids: entityIds.join(','), depth, limit },
  })
}

export function getSeedSubgraph(kid: number, seedIds: number[], depth = 2, limit = 1000) {
  return request.get<KgSubgraph>(`${BASE}/${kid}/graph/subgraph/seed`, {
    params: { seed_ids: seedIds.join(','), depth, limit },
  })
}

export function getEntityMentions(kid: number, entityId: number) {
  return request.get<{
    items: {
      segment_id: number
      chunk_index: number
      document_id: string
      content: string
      evidence: unknown
    }[]
  }>(`${BASE}/${kid}/graph/entities/${entityId}/mentions`)
}

export function getNeighbors(kid: number, entityId: number, depth = 1, limit = 100) {
  return request.get<KgSubgraph>(`${BASE}/${kid}/graph/entities/${entityId}/neighbors`, {
    params: { depth, limit },
  })
}

export function getPaths(
  kid: number,
  fromEntityId: number,
  toEntityId: number,
  maxDepth = 2,
  limit = 20,
) {
  return request.post<{ paths: KgPath[] }>(`${BASE}/${kid}/graph/paths`, {
    from_entity_id: fromEntityId,
    to_entity_id: toEntityId,
    max_depth: maxDepth,
    limit,
  })
}

export function getLabels(kid: number) {
  return request.get<{ items: KgLabel[] }>(`${BASE}/${kid}/graph/labels`)
}

// ── CDM 双向校验（P6）────────────────────────────────────────────────────
export type KgVerdict = 'hit' | 'missing' | 'conflict'

export interface KgCdmCheckItem {
  verdict: KgVerdict
  relation_code: string
  relation_name: string
  from_type: string
  to_type: string
  cardinality: string
  count: number
  detail: string
}

export interface KgCdmCheck {
  hit: number
  missing: number
  conflict: number
  items: KgCdmCheckItem[]
  uncovered: { relation_code: string; count: number }[]
  total_relations: number
  total_triples: number
}

export function getCdmCheck(kid: number) {
  return request.get<KgCdmCheck>(`${BASE}/${kid}/graph/cdm-check`)
}

// ── 导出（P6）───────────────────────────────────────────────────────────
export function exportGraph(kid: number, fmt: 'json' | 'csv' = 'json') {
  return request.get<Record<string, unknown>>(`${BASE}/${kid}/graph/export`, {
    params: { fmt },
  })
}

// ── 图谱增强检索（P4）────────────────────────────────────────────────────
export interface KgRetrieveHit {
  score: number
  document_id: string
  chunk_index: number
  content: string
  metadata?: {
    fusion_sources?: string[]
    score_type?: string
    graph_path?: unknown[]
    graph_seed_entities?: string[]
    [k: string]: unknown
  }
}

export interface KgRetrieveResponse {
  results: KgRetrieveHit[]
  index_mode?: string
  graph_enabled?: boolean
}

export function retrieveGraph(kid: number, query: string, topK = 10) {
  return request.post<KgRetrieveResponse>(`${BASE}/${kid}/retrieve`, {
    query,
    top_k: topK,
  })
}
