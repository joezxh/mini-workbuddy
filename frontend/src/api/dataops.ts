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
export function listStandards() {
  return request.get(`${BASE}/standards`)
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
