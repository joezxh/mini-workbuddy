/**
 * 推演沙盘沙箱域 API（S1–S21 + 检查点列表）。
 * 后端前缀：/api/v1/dataops/ontologies/sandbox（app/routers/sandbox/sandbox.py 挂 dataops 父 router）
 *
 * 全部端点需登录 + 租户上下文（后端 get_current_user / _tenant）。错误契约 R3：
 * 领域错误由后端返回 {code,message,detail?}，request 拦截器统一弹文案，本层不 try/catch。
 */
import request from '@/utils/request'

const BASE = '/api/v1/dataops/ontologies/sandbox'

// ── 类型（与后端服务返回逐字对齐，供页面强类型消费） ────────────────────
export interface SandboxBranch {
  id: number
  name: string
  tick_now: number
  color: string | null
  status: string
  base_checkpoint_id: number | null
}

export interface SandboxScene {
  scene_id: number
  ontology_id: number
  ontology_version: number
  name: string
  clone_scope: Record<string, any>
  exec_mode: string
  tick_now: number
  tick_max: number
  status: string
  clone_stats: Record<string, any> | null
  error_detail: string | null
  branches: SandboxBranch[]
  checkpoint_count: number
}

export interface WorldEntity {
  entity_code: string
  object_code: string
  props: Record<string, any>
  risk_score: number
  masked: boolean
  origin: string
  source_ref: Record<string, any> | null
}

export interface WorldRelation {
  rel_code: string
  link_type_code: string
  from_entity_code: string
  to_entity_code: string
  props: Record<string, any>
  origin: string
}

export interface CausalEdge {
  code: string
  label: string
  from_ref: string | null
  to_ref: string | null
  activation_tick: number | null
}

export interface WorldView {
  scene_id: number
  branch_id: number
  tick: number
  view: string
  entities: WorldEntity[]
  relations: WorldRelation[]
  causal_edges: CausalEdge[]
}

export interface Observation {
  id?: number
  tick: number | null
  kind: string
  severity: string
  title: string
  detail_json: Record<string, any>
}

export interface KpiPoint {
  tick: number
  kind: string
  detail_json: Record<string, any>
}

export interface Checkpoint {
  id: number
  branch_id: number
  tick: number
  seq: number
  label: string
  stats: Record<string, any> | null
}

export interface Element {
  id: number
  scene_id: number
  kind: string
  code: string
  label: string
  from_ref: string | null
  to_ref: string | null
  condition_expr_json: Record<string, any> | null
  effect_expr_json: Record<string, any> | null
  activation_tick: number | null
  origin: string
  status: string
  confidence: number | null
}

export interface ActionTemplate {
  code: string
  name: string
  description: string | null
  domain_hint: string | null
  param_schema_json: Record<string, any>
  effect_spec_json: Record<string, any>
}

export interface ActionLog {
  id: number
  branch_id: number
  tick: number
  template_code: string
  target_entity_code: string
  gate_result: string
  gate_reason: string | null
  params_json: Record<string, any>
}

// ── S1–S5 场景生命周期 ─────────────────────────────────────────────
export function createScene(body: {
  ontology_id: number
  name: string
  clone_scope?: Record<string, any>
  tick_max?: number
  exec_mode?: string
}) {
  return request.post<SandboxScene | { scene_id: number; status: string }>(`${BASE}/scenes`, body)
}
export function listScenes(params?: { ontology_id?: number; status?: string }) {
  return request.get<SandboxScene[]>(`${BASE}/scenes`, { params })
}
export function getScene(sceneId: number) {
  return request.get<SandboxScene>(`${BASE}/scenes/${sceneId}`)
}
export function patchScene(sceneId: number, body: { name?: string; exec_mode?: string }) {
  return request.patch<SandboxScene>(`${BASE}/scenes/${sceneId}`, body)
}
export function deleteScene(sceneId: number) {
  return request.delete(`${BASE}/scenes/${sceneId}`)
}

// ── S6–S12 引擎：世界 / 实体 / 推进 / 检查点 / 派生 / 回放 ──────────
export function getWorld(sceneId: number, params: { branch_id: number; tick?: number; view?: string }) {
  return request.get<WorldView>(`${BASE}/scenes/${sceneId}/world`, { params })
}
export function getEntity(sceneId: number, entityCode: string, params: { branch_id: number }) {
  return request.get<WorldEntity & { origin: string; can_act: boolean }>(
    `${BASE}/scenes/${sceneId}/entities/${entityCode}`, { params })
}
export function advance(sceneId: number, branchId: number, n: number) {
  return request.post<{ branch_id: number; tick_before: number; tick_after: number; observations_created: number }>(
    `${BASE}/scenes/${sceneId}/branches/${branchId}/advance`, { n })
}
export function saveCheckpoint(sceneId: number, branchId: number, label: string) {
  return request.post<Checkpoint & { count_used: number }>(
    `${BASE}/scenes/${sceneId}/branches/${branchId}/checkpoints`, { label })
}
export function listCheckpoints(sceneId: number, params?: { branch_id?: number }) {
  return request.get<Checkpoint[]>(`${BASE}/scenes/${sceneId}/checkpoints`, { params })
}
export function deleteCheckpoint(checkpointId: number) {
  return request.delete(`${BASE}/checkpoints/${checkpointId}`)
}
export function deriveBranch(sceneId: number, body: { checkpoint_id: number; name: string }) {
  return request.post<{ branch_id: number; name: string; tick_now: number; restored_entities: number }>(
    `${BASE}/scenes/${sceneId}/branches`, body)
}
export function replay(sceneId: number, branchId: number, toTick: number) {
  return request.post<{ tick_now: number; restored_entities: number }>(
    `${BASE}/scenes/${sceneId}/branches/${branchId}/replay`, { to_tick: toTick })
}

// ── S19 对比 / S21 观察 / KPI ──────────────────────────────────────
export interface BranchSummary {
  branch_id: number; name: string; final_tick: number
  final_health: string | null; health_delta: string | null
  goal_reached_count: number; rule_fired_count: number; action_count: number
}
export function compare(sceneId: number, branchIds: number[]) {
  return request.get<{
    branches: { branch_id: number; name: string }[]
    series: { tick: number; values: Record<string, any> }[]
    diff_table: any[]
    branch_summary: BranchSummary[]
  }>(`${BASE}/scenes/${sceneId}/compare`, { params: { branches: branchIds.join(',') } })
}
export function listObservations(sceneId: number, params: {
  branch_id: number; kind?: string; tick_from?: number; tick_to?: number
}) {
  return request.get<Observation[]>(`${BASE}/scenes/${sceneId}/observations`, { params })
}
export function listKpis(sceneId: number, params: { branch_id: number }) {
  return request.get<KpiPoint[]>(`${BASE}/scenes/${sceneId}/kpis`, { params })
}

// ── S13–S15 配置元素（因果边 / 规则 / 目标 / 未来事件） ─────────────
export function listElements(sceneId: number, params?: { kind?: string; status?: string }) {
  return request.get<Element[]>(`${BASE}/scenes/${sceneId}/elements`, { params })
}
export function createElement(sceneId: number, body: Partial<Element> & { kind: string; code: string }) {
  return request.post<Element>(`${BASE}/scenes/${sceneId}/elements`, body)
}
export function updateElement(elementId: number, body: Partial<Element>) {
  return request.put<Element>(`${BASE}/elements/${elementId}`, body)
}
export function deleteElement(elementId: number) {
  return request.delete(`${BASE}/elements/${elementId}`)
}
export function draftElementsLlm(sceneId: number, modelId?: number) {
  return request.post<Element[]>(`${BASE}/scenes/${sceneId}/elements/llm-draft`, undefined,
    { params: { model_id: modelId } })
}
export function reviewElement(elementId: number, decision: 'accept' | 'reject') {
  return request.post<Element>(`${BASE}/elements/${elementId}/review`, { decision })
}

// ── S16–S18 行动门禁 ───────────────────────────────────────────────
export function listActionTemplates(sceneId: number) {
  return request.get<ActionTemplate[]>(`${BASE}/scenes/${sceneId}/action-templates`)
}
export function applyAction(sceneId: number, branchId: number, body: {
  template_code: string; target_entity_code: string; params?: Record<string, any>
}) {
  return request.post<{ gate_result: string; action_id: number; reason?: string; confirm_token?: string; tick_after?: number }>(
    `${BASE}/scenes/${sceneId}/branches/${branchId}/actions`, body)
}
export function confirmAction(sceneId: number, actionId: number, token: string) {
  return request.post<{ gate_result: string; action_id: number; tick_after: number }>(
    `${BASE}/scenes/${sceneId}/actions/${actionId}/confirm`, { token })
}
export function listActions(sceneId: number, params?: { branch_id?: number; result?: string }) {
  return request.get<ActionLog[]>(`${BASE}/scenes/${sceneId}/actions`, { params })
}

// ── S20 AI 顾问 ────────────────────────────────────────────────────
export function ask(sceneId: number, body: { branch_id: number; question: string; model_id?: number }) {
  return request.post<{ answer: string; cited_evidence: number[]; degraded: boolean }>(
    `${BASE}/scenes/${sceneId}/ask`, body)
}
