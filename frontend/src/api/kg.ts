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
