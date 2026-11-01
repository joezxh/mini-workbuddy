/** 本体查询定义 Q2/Q3/Q4/Q5（Plan 2 消费面）：挂在 dataops 前缀下（dataops.py include_router(ontology_router)）。 */
import request from '@/utils/request'
import type { OntologyQueryRow } from '@/types/twin'

const BASE = '/api/v1/dataops'

export const listQueries = (
  ontologyId: number, opts?: { shape?: string; kw?: string; verifiedOnly?: boolean },
) => {
  const q = new URLSearchParams()
  if (opts?.shape) q.set('shape', opts.shape)
  if (opts?.kw) q.set('kw', opts.kw)
  if (opts?.verifiedOnly) q.set('verified_only', 'true')
  const tail = q.toString() ? `?${q.toString()}` : ''
  return request.get(`${BASE}/ontologies/${ontologyId}/queries${tail}`) as unknown as Promise<OntologyQueryRow[]>
}

export const previewQuery = (queryId: number, params: Record<string, unknown> = {}, limit = 200) =>
  request.post(`${BASE}/queries/${queryId}/preview`, { params, limit }) as unknown as Promise<Record<string, any>>

export const patchQuery = (queryId: number, b: Record<string, unknown>) =>
  request.patch(`${BASE}/queries/${queryId}`, b) as unknown as Promise<OntologyQueryRow>

export const deleteQuery = (queryId: number) => request.delete(`${BASE}/queries/${queryId}`)

export const queryBindings = (queryId: number) =>
  request.get(`${BASE}/queries/${queryId}/bindings`) as unknown as Promise<Record<string, any>>
