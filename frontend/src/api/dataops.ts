/**
 * DataOps 数据源 API（P2 知识治理 · 数据源）
 * 后端前缀：/api/v1/dataops（app/routers/dataops/dataops.py）
 */
import request from '@/utils/request'

const BASE = '/api/v1/dataops'

// ── 数据源类型字典（sys_dictionary：data_source_type） ────────────────
/** 启用项含 item_name/color/sort/family/default_port/fields，下拉与展示同源 */
export function listSourceTypes() {
  return request.get(`${BASE}/source-types`)
}

// ── 数据源 ───────────────────────────────────────────────────────
export function listSources() {
  return request.get(`${BASE}/sources`)
}
export function getSource(id: number) {
  return request.get(`${BASE}/sources/${id}`)
}
export function createSource(data: Record<string, any>) {
  return request.post(`${BASE}/sources`, data)
}
export function updateSource(id: number, data: Record<string, any>) {
  return request.put(`${BASE}/sources/${id}`, data)
}
export function deleteSource(id: number) {
  return request.delete(`${BASE}/sources/${id}`)
}
/** 已存数据源探活：回写 status，返回 {ok, error, status} */
export function testSource(id: number) {
  return request.post(`${BASE}/sources/${id}/test`)
}
/** 未保存表单探活：不落库，返回 {ok, error} */
export function testSourceDraft(data: Record<string, any>) {
  return request.post(`${BASE}/sources/test`, data)
}
/** Excel/CSV 型上传入库（落隔离 schema excel_ds_<id>） */
export function ingestExcel(id: number, file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return request.post(`${BASE}/sources/${id}/excel/ingest`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// ── 远端浏览 / 选表导入（SQLBot 式先探后选再导入） ────────────────────
export function listRemoteDatabases(id: number) {
  return request.get(`${BASE}/sources/${id}/remote/databases`)
}
/** PG 族导入向导第二级：按所选物理库列其用户 schema（非 PG 族返回空） */
export function listRemoteSchemas(id: number, database: string) {
  return request.get(`${BASE}/sources/${id}/remote/schemas`, { params: { database } })
}
export function listRemoteTables(id: number, database: string, schema?: string) {
  return request.get(`${BASE}/sources/${id}/remote/tables`, { params: { database, schema } })
}
export function importTables(id: number, body: { database: string; schema?: string; tables: string[]; with_profile?: boolean }) {
  return request.post(`${BASE}/sources/${id}/import-tables`, body)
}

// ── 元数据扫描 / 浏览 ──────────────────────────────────────────────
export function scanSource(id: number, database: string, withProfile = false, connectDatabase?: string) {
  return request.post(`${BASE}/sources/${id}/scan`,
    { database, with_profile: withProfile, connect_database: connectDatabase })
}
export function listTables(id: number, database?: string, dbName?: string) {
  return request.get(`${BASE}/sources/${id}/tables`, { params: { database, db_name: dbName } })
}
/** 已入库的列快照（按表 ID） */
export function listMetaColumns(id: number, tableId: number) {
  return request.get(`${BASE}/sources/${id}/tables/${tableId}/columns`)
}
export function runQuery(id: number, sql: string, limit = 200) {
  return request.post(`${BASE}/sources/${id}/query`, { sql, limit })
}

// ── 写操作申请 / 审批 / 执行 ───────────────────────────────────────
export function createWriteRequest(body: { source_id: number; sql_text: string; database?: string }) {
  return request.post(`${BASE}/write-requests`, body)
}
export function listWriteRequests(sourceId?: number) {
  return request.get(`${BASE}/write-requests`, { params: { source_id: sourceId } })
}
export function getWriteRequest(requestId: number) {
  return request.get(`${BASE}/write-requests/${requestId}`)
}
export function approveWriteRequest(requestId: number) {
  return request.post(`${BASE}/write-requests/${requestId}/approve`)
}
export function executeWriteRequest(requestId: number, token: string) {
  return request.post(`${BASE}/write-requests/${requestId}/execute`, { token })
}

// ── 元数据标准 / 绑定 / 关系推断 ───────────────────────────────────
/** withUsage=true 时每项多带 `usage`（列/对象/关系三类引用计数），供字典治理用 */
export function listStandards(withUsage = false) {
  return request.get(`${BASE}/standards`, { params: { with_usage: withUsage } })
}
export function createStandard(data: Record<string, any>) {
  return request.post(`${BASE}/standards`, data)
}
export function updateStandard(id: number, data: Record<string, any>) {
  return request.put(`${BASE}/standards/${id}`, data)
}
export function deleteStandard(id: number) {
  return request.delete(`${BASE}/standards/${id}`)
}
export function seedStandards() {
  return request.post(`${BASE}/standards/seed`)
}
export function bindSource(id: number, database?: string) {
  return request.post(`${BASE}/sources/${id}/bind`, { database })
}
export function inferRelations(id: number, database?: string, withOverlap = false) {
  return request.post(`${BASE}/sources/${id}/infer-relations`, { database, with_overlap: withOverlap })
}

// ── 标准中心（CDM）：目录/场景 + 对象标准 + 引用属性 ─────────────────
/** 整棵目录树（每节点带 children） */
export function listCatalogs() {
  return request.get(`${BASE}/standards/catalogs`)
}
export function createCatalog(data: Record<string, any>) {
  return request.post(`${BASE}/standards/catalogs`, data)
}
export function updateCatalog(id: number, data: Record<string, any>) {
  return request.put(`${BASE}/standards/catalogs/${id}`, data)
}
/** 挂到新父节点（null=移为根）；后端拒绝移入自身子树 */
export function moveCatalog(id: number, parentId: number | null) {
  return request.put(`${BASE}/standards/catalogs/${id}/move`, { parent_id: parentId })
}
export function deleteCatalog(id: number) {
  return request.delete(`${BASE}/standards/catalogs/${id}`)
}

/** catalogId 省略=全部对象，传值=该目录下的对象 */
export function listObjects(catalogId?: number) {
  return request.get(`${BASE}/standards/objects`, { params: { catalog_id: catalogId } })
}
/** 详情多带 `attributes`（引用属性列表） */
export function getObject(id: number) {
  return request.get(`${BASE}/standards/objects/${id}`)
}
export function createObject(data: Record<string, any>) {
  return request.post(`${BASE}/standards/objects`, data)
}
export function updateObject(id: number, data: Record<string, any>) {
  return request.put(`${BASE}/standards/objects/${id}`, data)
}
export function deleteObject(id: number) {
  return request.delete(`${BASE}/standards/objects/${id}`)
}
/** 全量替换对象的引用属性（先清后插） */
export function setObjectAttributes(id: number, items: any[]) {
  return request.put(`${BASE}/standards/objects/${id}/attributes`, { items })
}
/** 对象标准被哪些物理表绑定（检视面板下钻入口） */
export function listObjectBindings(id: number) {
  return request.get(`${BASE}/standards/objects/${id}/bindings`)
}

// ── 标准中心（CDM）：关系标准 + 标准图 + 统计 + NL 检索 ─────────────────
/** nodes=对象标准、edges=关系标准；传 catalogId 只取该子树 */
export function listGraph(catalogId?: number) {
  return request.get(`${BASE}/standards/graph`, { params: { catalog_id: catalogId } })
}
export function listRelations(catalogId?: number) {
  return request.get(`${BASE}/standards/relations`, { params: { catalog_id: catalogId } })
}
export function createRelation(data: Record<string, any>) {
  return request.post(`${BASE}/standards/relations`, data)
}
export function updateRelation(id: number, data: Record<string, any>) {
  return request.put(`${BASE}/standards/relations/${id}`, data)
}
export function deleteRelation(id: number) {
  return request.delete(`${BASE}/standards/relations/${id}`)
}
/** 关系标准在各数据源上的校验结论（hit/missing/conflict） */
export function listRelationChecks(id: number) {
  return request.get(`${BASE}/standards/relations/${id}/checks`)
}

// ── 标准中心（CDM）：总览统计 + 自然语言检索 ──────────────────────────
/** 目录/对象/关系计数 + 关系校验三态分布 */
export function getStats() {
  return request.get(`${BASE}/standards/stats`)
}
/** 自然语言 → 高亮对象/关系 code + 一句话解释；AI 不可用时返回 degraded:true */
export function nlQuery(question: string, catalogId?: number) {
  return request.post(`${BASE}/standards/nl-query`, { question, catalog_id: catalogId })
}

// ═══════════════════════════════════════════════════════════════════
// 本体治理（spec 2026-10-31 §6.1，E1-E40 共 40 函数）
// 前缀同为 /api/v1/dataops；错误契约 R3：本体端点返回 {code,message,detail?}
// ═══════════════════════════════════════════════════════════════════

// ── E1-E3 本体注册 CRUD ──────────────────────────────────────────
/** 本体列表：status/keyword/sort 均为可选查询参数（AF-09） */
export function listOntologies(params?: { status?: string; keyword?: string; sort?: string }) {
  return request.get(`${BASE}/ontologies`, { params })
}
export function createOntology(data: Record<string, any>) {
  return request.post(`${BASE}/ontologies`, data)
}
export function getOntology(id: number) {
  return request.get(`${BASE}/ontologies/${id}`)
}
export function updateOntology(id: number, data: Record<string, any>) {
  return request.put(`${BASE}/ontologies/${id}`, data)
}
export function deleteOntology(id: number) {
  return request.delete(`${BASE}/ontologies/${id}`)
}

// ── E40/E28 资产目录树 + 全文检索 ─────────────────────────────────
/** 按 external_type 分组的数据源目录树（含每组表数角标，AF-01） */
export function assetsTree() {
  return request.get(`${BASE}/assets/tree`)
}
/** 表/字段/注释检索（AF-02/05）：返回表卡片含 column_digest/pii_max_level/tags/score */
export function assetsSearch(params: {
  kw?: string; source_id?: number; tag_ids?: number[]; kind?: 'table' | 'column'; page?: number; size?: number
}) {
  return request.get(`${BASE}/assets/search`, { params })
}

// ── E4-E8 构建任务 + SSE ─────────────────────────────────────────
/** 创建构建任务（幂等）：返回 {job, created}；created=false 表示命中既有任务 */
export function createBuildJob(ontologyId: number, body: { mode: string; scope: Record<string, any>; idempotency_key?: string }) {
  return request.post(`${BASE}/ontologies/${ontologyId}/build-jobs`, body)
}
export function listBuildJobs(ontologyId: number) {
  return request.get(`${BASE}/ontologies/${ontologyId}/build-jobs`)
}
export function getBuildJob(jobId: number) {
  return request.get(`${BASE}/build-jobs/${jobId}`)
}
export function cancelBuildJob(jobId: number) {
  return request.post(`${BASE}/build-jobs/${jobId}/cancel`)
}
/** SSE 进度流相对路径（供 connectEventStream 消费，§6.2） */
export function buildJobStreamPath(jobId: number) {
  return `${BASE}/build-jobs/${jobId}/stream`
}

// ── E9-E10 审阅台 ────────────────────────────────────────────────
/** 审阅队列：kind/status/origin/page/size */
export function reviewQueue(ontologyId: number, params?: {
  kind?: string; status?: string; origin?: string; page?: number; size?: number
}) {
  return request.get(`${BASE}/ontologies/${ontologyId}/review-queue`, { params })
}
/** 批量审阅：{items:[{id,action:accept|reject}], accept_all, reject_all} */
export function reviewOntology(ontologyId: number, body: { items?: { id: number; action: string }[]; accept_all?: boolean; reject_all?: boolean }) {
  return request.post(`${BASE}/ontologies/${ontologyId}/review`, body)
}

// ── E11-E13 发布与版本 ───────────────────────────────────────────
/** 发布：{change_note, override_pending, mask_exemptions[]}；门禁失败按 code 报错 */
export function publishOntology(ontologyId: number, body?: { change_note?: string; override_pending?: boolean; mask_exemptions?: number[] }) {
  return request.post(`${BASE}/ontologies/${ontologyId}/publish`, body || {})
}
export function listOntologyVersions(ontologyId: number) {
  return request.get(`${BASE}/ontologies/${ontologyId}/versions`)
}
export function getOntologyVersion(ontologyId: number, version: number) {
  return request.get(`${BASE}/ontologies/${ontologyId}/versions/${version}`)
}

// ── E16-E17 schema 图 + 证据链 ───────────────────────────────────
/** 双视图：view=workflow（表→对象）| architecture（对象↔关系） */
export function ontologyGraph(ontologyId: number, view: 'workflow' | 'architecture' = 'workflow') {
  return request.get(`${BASE}/ontologies/${ontologyId}/graph`, { params: { view } })
}
/** 证据链：按元素 kind/code 检索原始依据（AF-13） */
export function ontologyEvidence(ontologyId: number, params?: { element_kind?: string; element_code?: string }) {
  return request.get(`${BASE}/ontologies/${ontologyId}/evidence`, { params })
}

// ── E24-E26 Agent 只读导航 ───────────────────────────────────────
export function agentManifest(ontologyId: number) {
  return request.get(`${BASE}/ontologies/${ontologyId}/manifest`)
}
/** 空 query 拒绝全量枚举（§6.4） */
export function agentBrowse(ontologyId: number, query: string) {
  return request.post(`${BASE}/ontologies/${ontologyId}/semantics/browse`, { query })
}
/** ≤5 个 code */
export function agentResolve(ontologyId: number, codes: string[]) {
  return request.post(`${BASE}/ontologies/${ontologyId}/semantics/resolve`, { codes })
}

// ── E21-E22 LLM 语义补全 + 采纳 ──────────────────────────────────
export function semanticsSuggest(ontologyId: number, body: { element_kind?: string; element_codes?: string[]; model_id?: number }) {
  return request.post(`${BASE}/ontologies/${ontologyId}/semantics/suggest`, body)
}
export function semanticsAdopt(ontologyId: number, semanticId: number) {
  return request.post(`${BASE}/ontologies/${ontologyId}/semantics/${semanticId}/adopt`)
}

// ── E33 作用域草稿送数 ───────────────────────────────────────────
export function getDraftScope(ontologyId: number) {
  return request.get(`${BASE}/ontologies/${ontologyId}/draft-scope`)
}
/** 全量覆盖：{mode,source_id,db_name,database,tables[],tag_ids[],catalog_ids[],origin,clear} */
export function putDraftScope(ontologyId: number, body: Record<string, any>) {
  return request.put(`${BASE}/ontologies/${ontologyId}/draft-scope`, body)
}
export function deleteDraftScope(ontologyId: number) {
  return request.delete(`${BASE}/ontologies/${ontologyId}/draft-scope`)
}

// ── E29-E32 资产标签体系 ─────────────────────────────────────────
export function listAssetTags(kind?: string) {
  return request.get(`${BASE}/asset-tags`, { params: { kind } })
}
export function createAssetTag(data: Record<string, any>) {
  return request.post(`${BASE}/asset-tags`, data)
}
export function updateAssetTag(id: number, data: Record<string, any>) {
  return request.put(`${BASE}/asset-tags/${id}`, data)
}
export function deleteAssetTag(id: number) {
  return request.delete(`${BASE}/asset-tags/${id}`)
}
/** 批量打标/摘标：{tag_id, asset_kind, asset_ids[], op:bind|unbind} */
export function bindAssetTag(body: { tag_id: number; asset_kind: string; asset_ids: number[]; op: 'bind' | 'unbind' }) {
  return request.post(`${BASE}/asset-tags/bind`, body)
}

// ── E34-E36 应用发布登记 ─────────────────────────────────────────
/** 应用发布登记列表（含 stale 标记，AF-17） */
export function listAppPublishes(ontologyId: number) {
  return request.get(`${BASE}/ontologies/${ontologyId}/publishes`)
}
/** 登记一个发布目标：{target_type,code,name,description,payload}；仅钉 current_version */
export function createAppPublish(ontologyId: number, body: { target_type: string; code: string; name?: string; description?: string; payload?: Record<string, any> }) {
  return request.post(`${BASE}/ontologies/${ontologyId}/publishes`, body)
}
export function toggleAppPublish(ontologyId: number, publishId: number, status: 'enabled' | 'disabled') {
  return request.put(`${BASE}/ontologies/${ontologyId}/publishes/${publishId}/toggle`, { status })
}

// ── E37-E38 建模助手 + 链路拓扑 ──────────────────────────────────
/** 四档统一入口：{intent,utterance,context,commit}（§5.6，build 两步提交） */
export function ontologyAssistant(ontologyId: number, body: { intent: string; utterance?: string; context?: Record<string, any>; commit?: boolean }) {
  return request.post(`${BASE}/ontologies/${ontologyId}/assistant`, body)
}
/** 五步链路拓扑计数与状态（§6.6，供 PipelineBar 只读渲染，AF-10） */
export function ontologyPipeline(ontologyId: number) {
  return request.get(`${BASE}/ontologies/${ontologyId}/pipeline`)
}
