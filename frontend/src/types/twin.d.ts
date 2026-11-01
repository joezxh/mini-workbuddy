/** 孪生应用领域类型 —— 逐字对齐后端已交付契约（Plan 2 spec §3/§4），禁止臆造字段 */

export type AccessLevel = 'owner' | 'edit' | 'read' | 'restricted'
export type RuntimeState = 'draft' | 'live' | 'paused'
export type ResultShape = 'kpi' | 'trend' | 'bar' | 'donut' | 'table' | 'entity_set' | 'graph'
export type WidgetState = 'ok' | 'empty' | 'error' | 'masked'
export type WidgetReason = 'unbound' | 'zero_rows'
export type TwinMode = 'edit' | 'run'
export type PublishAccess = 'org' | 'role'

export interface ApiErrorBody { code: string; message: string; detail?: unknown }

export interface TwinCard {
  id: number; name: string; icon: string | null; description: string | null
  source_template_key: string | null
  ontology_id: number; ontology_version: number; ontology_current_version: number
  stale: boolean
  scene_key: string | null; runtime_state: RuntimeState
  owner_id: number; access: AccessLevel; restricted: boolean
  share_expires_at: string | null; updated_at: string | null
}
export interface CardsByGroup { mine: TwinCard[]; shared: TwinCard[]; restricted: TwinCard[] }

export interface TwinPage {
  id: number; card_id: number; name: string; sort_order: number
  refresh_json: Record<string, unknown> | null; widget_count: number; updated_at: string | null
}

export interface TwinWidget {
  id: number; page_id: number; widget_key: string; title: string | null
  query_id: number | null
  param_values_json: Record<string, unknown> | null
  display_json: Record<string, unknown> | null
  grid_json: Record<string, unknown> | null
  refresh_json: Record<string, unknown> | null
  sort_order: number; updated_at: string | null
}

/** T8 items 元素：后端 WidgetItem 恰 15 键（twin_data_service.py _blank_item） */
export interface WidgetDatum {
  widget_id: number; widget_key: string; title: string | null
  query_id: number | null
  state: WidgetState
  reason: WidgetReason | null
  result_shape: ResultShape | null
  columns: string[]
  data: Record<string, any>          // 后端 shape_result 已归一；键名是 data，不是 rows
  row_count: number
  truncated: boolean
  masked_fields: string[]
  error: { code: string; message: string } | null
  cached: boolean
  updated_at: string
}
export interface LoadPageResp {
  page_id: number; card_id: number; runtime_state: RuntimeState
  refresh: Record<string, unknown> | null
  collected_at: string; count: number; items: WidgetDatum[]
}

export interface WidgetCreateBody {
  widget_key: string; title?: string; query_id?: number | null
  param_values_json?: Record<string, unknown>
  display_json?: Record<string, unknown>
  grid_json?: Record<string, unknown>
  refresh_json?: Record<string, unknown> | null
}
/** 解绑 = 显式 { query_id: null }；省略字段 ≠ 解绑（后端 exclude_unset） */
export interface WidgetPatchBody {
  widget_key?: string; title?: string; query_id?: number | null
  param_values_json?: Record<string, unknown>
  display_json?: Record<string, unknown>
  grid_json?: Record<string, unknown>
  refresh_json?: Record<string, unknown> | null
}
export interface LayoutItem { widget_id: number; grid_json: Record<string, unknown> }

export interface PublishInfo {
  publish_id: number; page_id: number; card_id: number
  slug: string; url: string; api_path: string
  version: number; access: PublishAccess
  role_codes: string[] | null; status: string
  widget_count: number; published_at: string | null; snapshot_schema: number
}
export interface PublishedMeta {
  slug: string; version: number; access: PublishAccess; published_at: string | null
  card: Record<string, any>; page: Record<string, any>
  widgets: Array<Record<string, any>>; refresh: Record<string, unknown> | null
  snapshot_schema: number
}
export interface PublishedData {
  slug: string; version: number; page_id: number; card_id: number
  collected_at: string; count: number; items: WidgetDatum[]
}

export interface AccessRequestItem extends Record<string, any> {}
/** 键名逐字对齐 twin_access_service.list_requests()（:261-262）：incoming / outgoing / incoming_pending */
export interface AccessListResp { incoming: AccessRequestItem[]; outgoing: AccessRequestItem[]; incoming_pending: number }

/** Q2 行（BindDrawer 消费的最小面） */
export interface OntologyQueryRow {
  id: number; code: string; name: string; result_shape: ResultShape
  verify_status: string; status: string
}
