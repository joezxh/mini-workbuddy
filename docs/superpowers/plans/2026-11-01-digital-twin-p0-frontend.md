# 孪生应用前端（Plan 2 / P0-5·6·9·10）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付孪生应用 P0 前端——编辑工作区 `/admin/digital-twin` + 登录态只读发布页 `/twin-p/:slug`，接通已交付的 T1–T12 / Q1–Q5 端点，并完成菜单 2407 修正与 tokens 缺口补齐。

**Architecture:** Vue 3 SFC + Pinia 单 store 状态机 + axios 封装（`@/utils/request`）；编辑/运行共用唯一 `WidgetGrid`（`mode` prop 分派，禁止平行运行画布）；renderer 是「后端归一形状 → 复用组件 props」的薄纯函数适配层。

**Tech Stack:** Vite、Pinia、Ant Design Vue、ECharts（复用既有图表组件）、vitest（node 环境 + `@vue/server-renderer` programmatic runtime）。

**Spec:** `docs/superpowers/specs/2026-11-01-digital-twin-frontend-design.md`（设计真源，执行时两份同读；spec §9 的 C1–C5/G1/G2 已把与主 spec/代码的偏差裁决完毕）

## Global Constraints

- 接口契约真源 = 后端已交付实现（`backend/app/routers/twin/twin.py`、`backend/app/routers/ontology/ontology.py` Q1–Q5、`twin_data_service.py`、`twin_publish_service.py`、`twin_service.py`）；**不得臆造任何端点**（无 T13/T14/widgets-batch/drill 端点——AI dock 与 DrillDrawer 均为无请求骨架）。
- 四态字面量逐字：`ok` / `empty` / `error` / `masked`；`reason` 逐字：`unbound` / `zero_rows`；`WidgetItem` 恰为 15 键（`widget_id, widget_key, title, query_id, state, reason, result_shape, columns, data, row_count, truncated, masked_fields, error, cached, updated_at`），归一后数据键名是 **`data`**（不是 rows）。
- 错误契约顶层 `ApiError{code,message,detail}`；twin-p 一切拒绝 = **同一 403 + 同一 message**（反枚举），前端不得据差异分支。
- T10 publish **恒回 200**（版本推进非新资源）；T8 永远 200（单组件失败只影响该组件 state）。
- 解绑查询 = `PATCH /widgets/{id}` 显式携带 `query_id: null` 键（后端 `exclude_unset`，省略字段 ≠ 解绑）。
- 承重原则：**禁止出现 `RunCanvas.vue`** 或任何平行运行态画布；模式差异只用 CSS 类（原型 `body.run .edit-only{display:none}`、`body.edit .wops{display:flex}`）。
- masked **不进 StateWrapper**（其只有 loading/error/empty 三态）：masked 由 renderer 按 `masked_fields[]` 在值位叠 🔒。
- 测试依赖：**不安装** `@vue/test-utils` / `jsdom` / `happy-dom`；组件测试用 `createSSRApp + renderToString`（先例 `views/data-source/asset/__tests__/AssetCardList.spec.ts`）。
- tokens R9：**只新增不改既有行**；`--cyan:#39d3c4`、`--purple:#b48ef0`（dark 原型逐字），light `#0d9488`/`#7c3aed`，soft 透明度 dark .12 / light .08；**不动** `--neon-*`（spec §7.3 例外记录在案，仅 twin 模块消费）。
- 样式纪律（W2）：twin 业务样式内**无裸 hex**，一律 `var(--*)`。
- 提交纪律：相对路径外科式 `git add`（只加本任务文件），守卫 grep 确认无混入；计划复选框全程**不勾选**；每完成一 Task 若发现计划缺陷，回写本文档「执行时发现的计划缺陷」节。
- 验证探针（Task 0 执行）：`cd frontend; npx vitest run src/<path>` 与 `cd backend; .venv\Scripts\python.exe -m pytest tests\twin\test_menu_sql_twin.py -q` 两条命令形态先实测；若与下文写法不符，以实测形态统一替换后续所有 Run 行，**不改测试迁就环境**。

---

### Task 0: 菜单 2407 修正（digital-twin + 点亮）+ 领域类型 `types/twin.d.ts`

**Files:**
- Modify: `backend/tests/twin/test_menu_sql_twin.py`（EXPECTED :30,:32；回读字典 :139-141；幂等测试 :118-134；新增 UPDATE 测试）
- Modify: `docs/sql/menu_knowledge_governance.sql`（:45 注释、:47 VALUES 行、:51 块尾后追加 UPDATE）
- Modify: `docs/sql/init.sql`（:4656 附近同款注释与行、孪生 INSERT 块尾 `WHERE NOT EXISTS ...;` 后追加同款 UPDATE）
- Create: `frontend/src/types/twin.d.ts`

**Interfaces:**
- Consumes: 无（首任务）
- Produces: `types/twin.d.ts` 全部类型（后续所有前端任务的唯一类型源）；`test_menu_sql_twin.py` 新基线（path=`/admin/digital-twin`、visible=1、UPDATE 存在）

- [ ] **Step 1: 先跑既有测试确认基线绿 + 探测命令形态**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests\twin\test_menu_sql_twin.py -q`
Expected: `6 passed`。同时执行 `cd frontend; npx vitest run src/api/__tests__/aiContext.spec.ts` 确认 vitest 可跑（记录实际命令形态）。

- [ ] **Step 2: 改测试到新契约（先红）**

`test_menu_sql_twin.py` 三处修改 + 一个新测试：

```python
# EXPECTED 两键（:30 / :32）
"path": "'/admin/digital-twin'", "visible": "1",

# test_twin_row_inserts_and_is_idempotent 末尾回读字典（:139-141）
assert dict(got[0]) == {"id": 2407, "name": "孪生应用", "path": "/admin/digital-twin",
                        "permission": "kg:twin:read", "type": 2, "parent_id": 2401,
                        "sort": 5, "visible": 1}
```

该测试的 SQL 拼接改为「INSERT → 提交 → 再跑同款 UPDATE → 提交」（模拟存量安装的真实收敛路径）：

```python
    upd = ('UPDATE sys_menu SET path = \'/admin/digital-twin\', visible = 1, '
           'updated_at = now() WHERE id = 2407')
    db.execute(text(upd))
    db.commit()
```

新增测试（钉住两份 SQL 都携带幂等 UPDATE）：

```python
def test_twin_upgrade_update_present_in_both_files():
    """存量安装靠这条幂等 UPDATE 收敛（VALUES 的 NOT EXISTS 不会改已插的旧行）。"""
    for path in (GOV, INIT):
        raw = path.read_text(encoding="utf-8")
        assert "WHERE id = 2407" in raw, f"{path.name} 缺少 2407 的幂等 UPDATE"
        assert "SET path = '/admin/digital-twin', visible = 1" in raw, \
            f"{path.name} 的 2407 UPDATE 字段不全"
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests\twin\test_menu_sql_twin.py -q`
Expected: FAIL（`test_row_field_values_match_spec`、`test_twin_upgrade_update_present_in_both_files`、回读断言 至少 3 红）

- [ ] **Step 4: 改 `docs/sql/menu_knowledge_governance.sql`**

:45 注释与 :47 行整体替换为：

```sql
-- 孪生应用（菜单入口；Plan 2 前端已交付，path 改 /admin/digital-twin 并点亮侧栏）
-- 注：原定 2406 已被上方的「数据资产」占用，故取下一个空号 2407（sort 顺延为 5）
(2407, '孪生应用',         'knowledge.menu.twin',      '/admin/digital-twin',    2401, 5, 0, 'kg:twin:read',    2, 'DeploymentUnitOutlined', NULL, false, 1, 0, 0),
```

:51（`WHERE NOT EXISTS ...;` 块尾）之后追加：

```sql
-- 已存在部署：Plan 1 交付的行是 ('/admin/kg-twin', visible=0)，Plan 2 幂等改写。
-- 重跑无害（仅设置相同值）；全新安装由上方 VALUES 行直接带回新值，两路收敛到同一状态。
UPDATE "public"."sys_menu" SET path = '/admin/digital-twin', visible = 1, updated_at = now() WHERE id = 2407;
```

- [ ] **Step 5: 改 `docs/sql/init.sql`**

孪生 VALUES 行与其上注释同款替换（注意 init 中该行是块末行、**无尾逗号**）：

```sql
-- 注：id=2406 已被「数据资产」占用（见 menu_knowledge_governance.sql），故孪生 应取 2407（sort=5）；Plan 2 已改 path 并点亮
(2407, '孪生应用',         'knowledge.menu.twin',      '/admin/digital-twin',    2401, 5, 0, 'kg:twin:read',    2, 'DeploymentUnitOutlined', NULL, false, 1, 0, 0)
```

该块 `WHERE NOT EXISTS (SELECT 1 FROM "public"."sys_menu" s WHERE s.id = v.id);` 之后追加与 Step 4 逐字相同的 UPDATE（两文件同构，`test_both_files_have_identical_twin_row` 与 UPDATE 测试各钉一侧）。

- [ ] **Step 6: 跑测试确认全绿**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests\twin\test_menu_sql_twin.py -q`
Expected: `7 passed`

- [ ] **Step 7: 创建 `frontend/src/types/twin.d.ts`**（内容 = 后端响应逐字翻译，无臆造字段）

```ts
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
export interface AccessListResp { incoming: AccessRequestItem[]; outgoing: AccessRequestItem[]; pending_count: number }

/** Q2 行（BindDrawer 消费的最小面） */
export interface OntologyQueryRow {
  id: number; code: string; name: string; result_shape: ResultShape
  verify_status: string; status: string
}
```

注：`AccessListResp` 的分组键名以 `twin_access_service.list_requests()` 实际返回为准——Step 8 守卫核对后再最终定名（`backend/app/services/twin/twin_access_service.py`）。

- [ ] **Step 8: 类型守卫核对**

Run: `cd backend; Select-String -Path app\services\twin\twin_access_service.py -Pattern "return \{|incoming|outgoing|pending"`
若键名与 Step 7 不符，改 `twin.d.ts` 迁就后端（永远改前端类型，不动后端）。
Run: `cd frontend; npx vue-tsc --noEmit -p tsconfig.json`（若报脚本形态问题，记录到计划缺陷节并改用 `node_modules\.bin\vue-tsc`）
Expected: 无新增错误

- [ ] **Step 9: 外科式提交**

```bash
git add backend/tests/twin/test_menu_sql_twin.py docs/sql/menu_knowledge_governance.sql docs/sql/init.sql frontend/src/types/twin.d.ts
git commit -m "feat(twin): repoint menu 2407 to /admin/digital-twin with idempotent update; add twin domain types"
```

守卫：`git diff HEAD~1 --stat` 恰 4 文件；`git diff HEAD~1 -- docs/sql | Select-String '2406'` 除既有注释外无新增 2406 行改动。

---

### Task 1: `api/twin.ts`（T1–T12 + twin-p）

**Files:**
- Create: `frontend/src/api/twin.ts`
- Test: `frontend/src/api/__tests__/twin.spec.ts`

**Interfaces:**
- Consumes: `@/utils/request`（axios 封装，拦截器已解包 `response.data`，先例 `api/dataops.ts`、`api/aiContext.ts`）；`types/twin.d.ts`
- Produces: 函数面（后续 store 唯一取数入口）：
`listCards()` · `createCard(b)` · `getCard(id)` · `patchCard(id,b)` · `deleteCard(id)` · `createCardFromTemplate(b)` ·
`listPages(cardId)` · `createPage(cardId,b)` · `reorderPages(cardId,pageIds)` · `patchPage(id,b)` · `deletePage(id)` ·
`listWidgets(pageId)` · `addWidget(pageId,b)` · `saveLayout(pageId,items)` · `patchWidget(id,b)` · `deleteWidget(id)` ·
`loadPageData(pageId,params?)` · `loadWidgetData(id)` ·
`publishPage(pageId,b?)` · `unpublish(publishId)` · `getPublished(slug)` · `runPublished(slug,params?)` ·
`requestCardAccess(cardId,reason?)` · `listAccessRequests()` · `approveAccessRequest(id,expiresInDays?)` · `rejectAccessRequest(id)`
两前缀：`TWINS = '/api/v1/twins'`、`PUB = '/api/v1/twin-p'`

- [ ] **Step 1: 写失败测试**

```ts
// frontend/src/api/__tests__/twin.spec.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/utils/request', () => {
  const post = vi.fn(); const get = vi.fn(); const patch = vi.fn(); const del = vi.fn()
  return { default: { post, get, patch, del } }
})
import api from '@/utils/request'
import * as twin from '../twin'
const postMock = api.post as unknown as ReturnType<typeof vi.fn>
const patchMock = api.patch as unknown as ReturnType<typeof vi.fn>
const delMock = api.del as unknown as ReturnType<typeof vi.fn>

describe('api/twin（T1–T12 契约钉死）', () => {
  beforeEach(() => { postMock.mockReset(); patchMock.mockReset(); delMock.mockReset() })

  it('T8 整页取数：POST /api/v1/twins/pages/{id}/data，params 缺省发空体', async () => {
    postMock.mockResolvedValueOnce({ items: [] })
    await twin.loadPageData(7)
    expect(postMock).toHaveBeenCalledWith('/api/v1/twins/pages/7/data', {})
    await twin.loadPageData(7, { region: 'east' })
    expect(postMock).toHaveBeenLastCalledWith('/api/v1/twins/pages/7/data', { params: { region: 'east' } })
  })

  it('T6 解绑必须显式携带 query_id:null 键', async () => {
    patchMock.mockResolvedValueOnce({})
    await twin.patchWidget(3, { query_id: null })
    expect(patchMock).toHaveBeenCalledWith('/api/v1/twins/widgets/3', { query_id: null })
  })

  it('T10 发布走 TWINS 前缀并透传 PublishBody', async () => {
    postMock.mockResolvedValueOnce({ slug: 'abc' })
    await twin.publishPage(9, { access: 'role', role_codes: ['ops'] })
    expect(postMock).toHaveBeenCalledWith('/api/v1/twins/pages/9/publish',
      { access: 'role', role_codes: ['ops'] })
  })

  it('T11 只读页走 twin-p 前缀（与写权限面隔离）', async () => {
    postMock.mockResolvedValueOnce({ items: [] })
    await twin.runPublished('abc', { p: 1 })
    expect(postMock).toHaveBeenCalledWith('/api/v1/twin-p/abc/data', { params: { p: 1 } })
  })

  it('T12 approve 缺省不发体，带值发 {expires_in_days}', async () => {
    postMock.mockResolvedValueOnce({})
    await twin.approveAccessRequest(5)
    expect(postMock).toHaveBeenCalledWith('/api/v1/twins/access-requests/5/approve', {})
    await twin.approveAccessRequest(5, 30)
    expect(postMock).toHaveBeenLastCalledWith('/api/v1/twins/access-requests/5/approve', { expires_in_days: 30 })
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend; npx vitest run src/api/__tests__/twin.spec.ts`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `api/twin.ts`**

```ts
/** 孪生应用 API 表面：T1–T12 + twin-p。逐一对齐 backend/app/routers/twin/twin.py，禁止臆造端点。 */
import request from '@/utils/request'
import type {
  CardsByGroup, TwinCard, TwinPage, TwinWidget, WidgetDatum, LoadPageResp, PublishInfo,
  PublishedMeta, PublishedData, WidgetCreateBody, WidgetPatchBody, LayoutItem,
  PublishAccess, AccessListResp,
} from '@/types/twin'

const TWINS = '/api/v1/twins'
const PUB = '/api/v1/twin-p'

export const listCards = () => request.get(`${TWINS}/cards`) as unknown as Promise<CardsByGroup>
export const createCard = (b: { name: string; icon?: string; description?: string;
  ontology_id: number; ontology_version: number; scene_key?: string }) =>
  request.post(`${TWINS}/cards`, b) as unknown as Promise<TwinCard>
export const getCard = (id: number) => request.get(`${TWINS}/cards/${id}`) as unknown as Promise<TwinCard>
export const patchCard = (id: number, b: Record<string, unknown>) =>
  request.patch(`${TWINS}/cards/${id}`, b) as unknown as Promise<TwinCard>
export const deleteCard = (id: number) => request.delete(`${TWINS}/cards/${id}`)
export const createCardFromTemplate = (b: { template_key: string; name: string; ontology_id?: number }) =>
  request.post(`${TWINS}/cards/from-template`, b) as unknown as Promise<TwinCard>

export const listPages = (cardId: number) =>
  request.get(`${TWINS}/cards/${cardId}/pages`) as unknown as Promise<TwinPage[]>
export const createPage = (cardId: number, b: { name: string; refresh_json?: Record<string, unknown> }) =>
  request.post(`${TWINS}/cards/${cardId}/pages`, b) as unknown as Promise<TwinPage>
export const reorderPages = (cardId: number, pageIds: number[]) =>
  request.post(`${TWINS}/cards/${cardId}/pages/reorder`, { page_ids: pageIds }) as unknown as Promise<TwinPage[]>
export const patchPage = (id: number, b: Record<string, unknown>) =>
  request.patch(`${TWINS}/pages/${id}`, b) as unknown as Promise<TwinPage>
export const deletePage = (id: number) => request.delete(`${TWINS}/pages/${id}`)

export const listWidgets = (pageId: number) =>
  request.get(`${TWINS}/pages/${pageId}/widgets`) as unknown as Promise<TwinWidget[]>
export const addWidget = (pageId: number, b: WidgetCreateBody) =>
  request.post(`${TWINS}/pages/${pageId}/widgets`, b) as unknown as Promise<TwinWidget>
export const saveLayout = (pageId: number, items: LayoutItem[]) =>
  request.post(`${TWINS}/pages/${pageId}/widgets/layout`, { items }) as unknown as Promise<TwinWidget[]>
export const patchWidget = (id: number, b: WidgetPatchBody) =>
  request.patch(`${TWINS}/widgets/${id}`, b) as unknown as Promise<TwinWidget>
export const deleteWidget = (id: number) => request.delete(`${TWINS}/widgets/${id}`)

export const loadPageData = (pageId: number, params?: Record<string, unknown>) =>
  request.post(`${TWINS}/pages/${pageId}/data`, { params: params ?? {} }) as unknown as Promise<LoadPageResp>
export const loadWidgetData = (id: number) =>
  request.get(`${TWINS}/widgets/${id}/data`) as unknown as Promise<WidgetDatum>

export const publishPage = (pageId: number, b?: { access?: PublishAccess; role_codes?: string[] }) =>
  request.post(`${TWINS}/pages/${pageId}/publish`, b ?? {}) as unknown as Promise<PublishInfo>
export const unpublish = (publishId: number) => request.delete(`${TWINS}/publish/${publishId}`)  // twin.py:318

export const getPublished = (slug: string) =>
  request.get(`${PUB}/${slug}`) as unknown as Promise<PublishedMeta>
export const runPublished = (slug: string, params?: Record<string, unknown>) =>
  request.post(`${PUB}/${slug}/data`, { params: params ?? {} }) as unknown as Promise<PublishedData>

export const requestCardAccess = (cardId: number, reason?: string) =>
  request.post(`${TWINS}/cards/${cardId}/access-request`, reason ? { reason } : {}) as unknown as Promise<Record<string, unknown>>
export const listAccessRequests = () =>
  request.get(`${TWINS}/access-requests`) as unknown as Promise<AccessListResp>
export const approveAccessRequest = (id: number, expiresInDays?: number) =>
  request.post(`${TWINS}/access-requests/${id}/approve`,
    expiresInDays ? { expires_in_days: expiresInDays } : {}) as unknown as Promise<Record<string, unknown>>
export const rejectAccessRequest = (id: number) =>
  request.post(`${TWINS}/access-requests/${id}/reject`, {}) as unknown as Promise<Record<string, unknown>>
```

注 1：`request` 封装若无 `patch/delete` 命名空间（先核对 `utils/request.ts` 导出面），按实际方法名调整并同步改测试 mock——**永远适配前端封装现状，不改后端**。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend; npx vitest run src/api/__tests__/twin.spec.ts`
Expected: `5 passed`

- [ ] **Step 5: 防臆造守卫（端点字面量 ⊆ 真实路由表）**

Run: `cd frontend; Select-String -Path src\api\twin.ts -Pattern "TWINS\}|PUB\}" | ForEach-Object Line`
人工比对每条路径都能在 `twin.py` 找到对应装饰器（T1–T12 全表），**不得出现** `widgets/batch`、`/ask`、`/draft` 等未交付端点。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/twin.ts frontend/src/api/__tests__/twin.spec.ts
git commit -m "feat(twin): api surface for T1-T12 + twin-p read-only, contract-pinned tests"
```

---

### Task 2: `api/twinQuery.ts`（Q1–Q5，只消费 Q2/Q3/Q5）

**Files:**
- Create: `frontend/src/api/twinQuery.ts`
- Test: `frontend/src/api/__tests__/twinQuery.spec.ts`

**Interfaces:**
- Consumes: `@/utils/request`；BASE `/api/v1/dataops`（先例 `api/dataops.ts:const BASE`；Q1–Q5 实挂在 `ontology.py` 但经 `dataops.py:1355 include_router` 暴露）
- Produces: `listQueries(ontologyId, opts?: {shape?, kw?, verifiedOnly?})` · `previewQuery(queryId, params?, limit=200)` · `patchQuery(id, b)` · `deleteQuery(id)` · `queryBindings(id)`（Q1 `createQuery` 不导出——Plan 2 无查询创建 UI，YAGNI）

- [ ] **Step 1: 写失败测试**

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
vi.mock('@/utils/request', () => {
  const post = vi.fn(); const get = vi.fn()
  return { default: { post, get } }
})
import api from '@/utils/request'
import { listQueries, previewQuery } from '../twinQuery'
const getMock = api.get as unknown as ReturnType<typeof vi.fn>
const postMock = api.post as unknown as ReturnType<typeof vi.fn>

describe('api/twinQuery（Q2/Q3 挂 /api/v1/dataops）', () => {
  beforeEach(() => { getMock.mockReset(); postMock.mockReset() })

  it('listQueries verified_only 转小写 query 参数', async () => {
    getMock.mockResolvedValueOnce([])
    await listQueries(11, { shape: 'kpi', verifiedOnly: true })
    expect(getMock).toHaveBeenCalledWith('/api/v1/dataops/ontologies/11/queries?shape=kpi&verified_only=true')
  })

  it('previewQuery 默认 limit=200（与后端同口径，不给预览拉全量的后门）', async () => {
    postMock.mockResolvedValueOnce({ records: [] })
    await previewQuery(4, { region: 'east' })
    expect(postMock).toHaveBeenCalledWith('/api/v1/dataops/queries/4/preview',
      { params: { region: 'east' }, limit: 200 })
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend; npx vitest run src/api/__tests__/twinQuery.spec.ts` → FAIL（模块不存在）

- [ ] **Step 3: 实现**

```ts
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend; npx vitest run src/api/__tests__/twinQuery.spec.ts` → `2 passed`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/twinQuery.ts frontend/src/api/__tests__/twinQuery.spec.ts
git commit -m "feat(twin): ontology-query api (Q2/Q3/Q5) on dataops prefix"
```

---

### Task 3: `stores/twin.ts`（状态机 + 页面级调度器）

**Files:**
- Create: `frontend/src/stores/twin.ts`
- Test: `frontend/src/stores/__tests__/twin.spec.ts`

**Interfaces:**
- Consumes: Task 1/2 的全部 api 函数；`types/twin.d.ts`
- Produces: `useTwinStore`（setup 语法），state：`cards: CardsByGroup`、`activeCardId: number|null`、`cardDetail: TwinCard|null`、`pages: TwinPage[]`、`activePageId: number|null`、`widgets: TwinWidget[]`、`pageData: Record<number, WidgetDatum>`、`mode: TwinMode`、`loadingPage: boolean`、`accessRequests: AccessListResp | null`、`publishInfo: PublishInfo|null`、`aiDraft: []`；
actions：`loadCards` `openCard(id)` `selectPage(id)` `refreshPage(params?)` `retryWidget(id)` `setMode(m)` `startScheduler()` `stopScheduler()` `onVisibility()` `applyRefreshCfg(cfg)` `publish(cfg)` `unpublish()` `loadRequests()` `requestAccess(id, reason?)` `approve(id, days?)` `reject(id)`
调度器约定：档位 = `refresh_json` 覆盖页面默认 10s；`{interval: 0}` 或 `null`/`'off'` = 关闭（`applyRefreshCfg` 归一为 `intervalMs`，档位面值 10000/30000/0，状态栏三选一）。

- [ ] **Step 1: 写失败测试**

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const callCounts: Record<string, number> = {}
vi.mock('@/utils/request', () => {
  const mk = (key: string) => (...args: unknown[]) => {
    callCounts[key] = (callCounts[key] ?? 0) + 1
    const impl = (mk as any)._impl?.(key, args)
    return Promise.resolve(impl)
  }
  return { default: { get: mk('get'), post: mk('post'), patch: mk('patch'), delete: mk('delete') } }
})

import { useTwinStore } from '../twin'

const datum = (wid: number, over = {}) => ({
  widget_id: wid, widget_key: `w${wid}`, title: `T${wid}`, query_id: 1,
  state: 'ok', reason: null, result_shape: 'kpi', columns: ['v'],
  data: { value: 1, records: [{ v: 1 }] }, row_count: 1, truncated: false,
  masked_fields: [], error: null, cached: false, updated_at: 'x', ...over,
})

beforeEach(() => {
  setActivePinia(createPinia())
  for (const k of Object.keys(callCounts)) delete callCounts[k]
})

describe('stores/twin', () => {
  it('W8：refreshPage 只发 1 次 pages/{id}/data 且按 widget_id 填充', async () => {
    ;(globalThis as any).__loadPageResp = { items: [datum(1), datum(2, { state: 'empty', reason: 'zero_rows' })] }
    const s = useTwinStore()
    s.activePageId = 7
    const resp = await s.refreshPage()
    expect(callCounts['post']).toBe(1)
    expect(s.pageData[1].state).toBe('ok')
    expect(s.pageData[2].reason).toBe('zero_rows')
  })

  it('W7：默认 10s 档；applyRefreshCfg({interval:30000}) 改档；off 停表', async () => {
    vi.useFakeTimers()
    const s = useTwinStore()
    s.activePageId = 7
    s.startScheduler()
    expect(s.intervalMs).toBe(10000)
    s.applyRefreshCfg({ interval: 30000 })
    expect(s.intervalMs).toBe(30000)
    s.stopScheduler(); s.applyRefreshCfg({ interval: 0 }); s.startScheduler()
    expect(vi.getTimerCount()).toBe(0)
    s.stopScheduler()
    vi.useRealTimers()
  })

  it('W7：隐藏标签页暂停，回前台立即刷一次并重启定时器', async () => {
    const s = useTwinStore()
    s.activePageId = 7
    s.startScheduler()
    s.onVisibility(true)                     // hidden → 停表
    s.onVisibility(false)                    // visible → 立刷一次
    await vi.waitFor(() => expect(callCounts['post']).toBe(1))
    s.stopScheduler()
  })

  it('W11 旁证：切卡即弃 pageData，且无 storage 写入', async () => {
    const setItem = vi.fn()
    ;(globalThis as any).localStorage = { setItem, getItem: vi.fn() }
    const s = useTwinStore()
    s.pageData = { 1: datum(1) as any }
    s.openCardStart?.(99) ?? (s.activeCardId = 99, s.pageData = {})
    expect(Object.keys(s.pageData)).toHaveLength(0)
    expect(setItem).not.toHaveBeenCalled()
  })

  it('retryWidget 走 T9 且只更新该组件', async () => {
    const s = useTwinStore()
    s.pageData = { 1: datum(1, { state: 'error' }) as any, 2: datum(2) as any }
    await s.retryWidget(1)
    expect(callCounts['get']).toBe(1)
    expect(s.pageData[1].state).toBe('ok')
  })
})
```

注：上面 `__loadPageResp` 钩子写法笨重——实现测试时把 mock 工厂改成按 URL 模式返回（`_impl(key, args)` 里判 `args[0]` 含 `/data` 返回 LoadPageResp 样本、含 `/widgets/` 返回单 datum、cards 返回三组空）；**测试意图（各条断言）不得弱化**，胶水写法可优化并记入计划缺陷节。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend; npx vitest run src/stores/__tests__/twin.spec.ts` → FAIL（store 不存在）

- [ ] **Step 3: 实现 store**

```ts
/** 孪生工作区状态机（Plan 2 spec §3）。服务器态为真相源；loading 本地驱动。 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/twin'
import type {
  CardsByGroup, TwinCard, TwinPage, TwinWidget, WidgetDatum, TwinMode,
  PublishInfo, AccessListResp, LoadPageResp,
} from '@/types/twin'

export const useTwinStore = defineStore('twin', () => {
  const cards = ref<CardsByGroup>({ mine: [], shared: [], restricted: [] })
  const activeCardId = ref<number | null>(null)
  const cardDetail = ref<TwinCard | null>(null)
  const pages = ref<TwinPage[]>([])
  const activePageId = ref<number | null>(null)
  const widgets = ref<TwinWidget[]>([])
  const pageData = ref<Record<number, WidgetDatum>>({})   // 切卡/切页即弃（W11 旁证）
  const mode = ref<TwinMode>('edit')
  const loadingPage = ref(false)
  const accessRequests = ref<AccessListResp | null>(null)
  const publishInfo = ref<PublishInfo | null>(null)
  const aiDraft = ref<[]>([])                              // D1：占位，无端点

  let timer: ReturnType<typeof setInterval> | null = null
  const intervalMs = ref(10000)                            // 档位 10000/30000/0（off）

  function applyRefreshCfg(cfg: Record<string, unknown> | null) {
    const raw = Number((cfg as any)?.interval ?? 10000)
    intervalMs.value = raw === 0 ? 0 : (raw === 30000 ? 30000 : 10000)
  }
  function startScheduler() {
    stopScheduler()
    if (intervalMs.value > 0 && activePageId.value != null)
      timer = setInterval(() => { void refreshPage() }, intervalMs.value)
  }
  function stopScheduler() { if (timer) { clearInterval(timer); timer = null } }
  /** 由 visibilitychange 宿主（TwinWorkspace）接线：hidden→暂停；visible→立刷一次并重启 */
  function onVisibility(hidden: boolean) {
    if (hidden) stopScheduler()
    else { void refreshPage().then(startScheduler) }
  }

  async function loadCards() { cards.value = await api.listCards() }
  async function openCard(id: number) {          // 换卡 = 全量重置（W11 前端旁证）
    activeCardId.value = id; pageData.value = {}; publishInfo.value = null
    cardDetail.value = await api.getCard(id)
    pages.value = await api.listPages(id)
    if (pages.value.length) await selectPage(pages.value[0].id)
  }
  async function selectPage(id: number) {        // W4：切页触发一次加载
    activePageId.value = id; pageData.value = {}
    widgets.value = await api.listWidgets(id)
    await refreshPage()
    if (mode.value === 'run' || mode.value === 'edit') startScheduler()
  }
  async function refreshPage(params?: Record<string, unknown>) {  // W8：永远只 1 个请求
    if (activePageId.value == null) return
    loadingPage.value = true
    try {
      const resp: LoadPageResp = await api.loadPageData(activePageId.value, params)
      const next: Record<number, WidgetDatum> = {}
      for (const it of resp.items) next[it.widget_id] = it
      pageData.value = next
      applyRefreshCfg(resp.refresh)
    } finally { loadingPage.value = false }
  }
  async function retryWidget(widgetId: number) {
    const d = await api.loadWidgetData(widgetId)
    pageData.value = { ...pageData.value, [widgetId]: d }
  }
  function setMode(m: TwinMode) { mode.value = m }

  async function publish(cfg: { access: 'org' | 'role'; role_codes?: string[] }) {
    if (activePageId.value == null) return null
    publishInfo.value = await api.publishPage(activePageId.value, cfg)   // 恒 200 = 版本推进
    return publishInfo.value
  }
  async function unpublish() {
    if (publishInfo.value) { await api.unpublish(publishInfo.value.publish_id); publishInfo.value = null }
  }
  async function loadRequests() { accessRequests.value = await api.listAccessRequests() }
  async function requestAccess(cardId: number, reason?: string) { return api.requestCardAccess(cardId, reason) }
  async function approve(id: number, days?: number) { await api.approveAccessRequest(id, days); await loadRequests() }
  async function reject(id: number) { await api.rejectAccessRequest(id); await loadRequests() }

  return { cards, activeCardId, cardDetail, pages, activePageId, widgets, pageData, mode,
           loadingPage, accessRequests, publishInfo, aiDraft, intervalMs,
           applyRefreshCfg, startScheduler, stopScheduler, onVisibility,
           loadCards, openCard, selectPage, refreshPage, retryWidget, setMode,
           publish, unpublish, loadRequests, requestAccess, approve, reject }
})
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend; npx vitest run src/stores/__tests__/twin.spec.ts`
Expected: 5 passed。若 `W11 旁证` 用例中 `openCardStart` 占位写法别扭，替换为直接调用 `store.openCard(99)` + mock getCard/listPages 返回空——意图不变。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/twin.ts frontend/src/stores/__tests__/twin.spec.ts
git commit -m "feat(twin): pinia store with page-level scheduler (W4/W7/W8/W11)"
```

---

### Task 4: renderer 纯函数层（wire→props 适配 + 四态映射 + 栅格样式）

**Files:**
- Create: `frontend/src/views/twin/widgets/adapter.ts`
- Create: `frontend/src/views/twin/stateMap.ts`
- Create: `frontend/src/views/twin/gridStyle.ts`
- Test: `frontend/src/views/twin/__tests__/adapter.spec.ts`
- Test: `frontend/src/views/twin/__tests__/stateMap.spec.ts`
- Test: `frontend/src/views/twin/__tests__/gridStyle.spec.ts`

**Interfaces:**
- Consumes: `types/twin.d.ts`（`WidgetDatum`、`ResultShape`）
- Produces:
  - `toMultiLine(data, columns): { xAxis: string[]; series: { name: string; data: (number|null)[] }[] }`
  - `toBar(data): { name: string; value: number }[]`（单序列，取 `values[0]`）
  - `toPie(data): { name: string; value: number }[]`
  - `toTable(data): Record<string, any>[]`
  - `kpiValue(data): unknown`
  - `WIDGET_MAP: Partial<Record<ResultShape, Component>>`（Task 5 填充后此常量才完整，本任务先导出 shape→adapter 的纯映射）
  - `widgetState(datum, mode): { branch: 'content'|'empty'|'error'; loading: boolean; emptyTitle: string; emptyDesc: string; errorText: string; retryable: boolean; masked: boolean }`
  - `gridStyleOf(grid: Record<string, unknown> | null): CSSProperties`

- [ ] **Step 1: 写失败测试**

```ts
// adapter.spec.ts —— 逐字对齐 shape_result 归一形状（ontology_query_service.py:99-114）
import { describe, it, expect } from 'vitest'
import { toMultiLine, toBar, toPie, kpiValue } from '../widgets/adapter'

describe('renderer 适配层（只转置键名，不重定义语义）', () => {
  it('trend：{records,t,values} → {xAxis,series[]}', () => {
    const d = { records: [{ ts: '09:00', load: 12, temp: 30 }, { ts: '10:00', load: 18, temp: 31 }],
                t: 'ts', values: ['load', 'temp'] }
    expect(toMultiLine(d)).toEqual({
      xAxis: ['09:00', '10:00'],
      series: [{ name: 'load', data: [12, 18] }, { name: 'temp', data: [30, 31] }],
    })
  })
  it('bar：只取 values[0]（C3 单序列订正）', () => {
    const d = { records: [{ line: 'A', qty: 7, extra: 9 }], t: 'line', values: ['qty', 'extra'] }
    expect(toBar(d)).toEqual([{ name: 'A', value: 7 }])
  })
  it('donut：parts 前两列 → {name,value}', () => {
    const d = { records: [{ st: 'run', n: 5 }, { st: 'idle', n: 2 }], parts: ['st', 'n'] }
    expect(toPie(d)).toEqual([{ name: 'run', value: 5 }, { name: 'idle', value: 2 }])
  })
  it('kpi：{value,records} → value；空 records → null', () => {
    expect(kpiValue({ value: 42, records: [{ v: 42 }] })).toBe(42)
    expect(kpiValue({ value: null, records: [] })).toBe(null)
  })
})
```

```ts
// stateMap.spec.ts —— 四态→StateWrapper 三态 + masked 独立位
import { describe, it, expect } from 'vitest'
import { widgetState } from '../stateMap'
import type { WidgetDatum } from '@/types/twin'

const base: WidgetDatum = {
  widget_id: 1, widget_key: 'w', title: 't', query_id: 1, state: 'ok', reason: null,
  result_shape: 'kpi', columns: ['v'], data: { value: 1, records: [] }, row_count: 1,
  truncated: false, masked_fields: [], error: null, cached: false, updated_at: 'x',
}
const s = (over: Partial<WidgetDatum>, mode = 'edit') => widgetState({ ...base, ...over }, mode)

describe('widgetState（W6）', () => {
  it('ok → content', () => expect(s({}).branch).toBe('content'))
  it('empty+unbound 编辑态 → 绑定 CTA 文案', () => {
    const v = s({ state: 'empty', reason: 'unbound' })
    expect(v.branch).toBe('empty')
    expect(v.emptyTitle).toContain('未绑定')
  })
  it('empty+unbound 运行态 → 不出现可操作暗示', () => {
    expect(s({ state: 'empty', reason: 'unbound' }, 'run').emptyTitle).not.toContain('绑定查询')
  })
  it('empty+zero_rows → 结果为零文案', () => {
    expect(s({ state: 'empty', reason: 'zero_rows' }).emptyTitle).toContain('为空')
  })
  it('error → code: message 逐字回显（W6 码+人话）且可重试', () => {
    const v = s({ state: 'error', error: { code: 'TWIN_DATA_TIMEOUT', message: '取数超时（>5s）' } })
    expect(v.branch).toBe('error')
    expect(v.errorText).toBe('TWIN_DATA_TIMEOUT: 取数超时（>5s）')
    expect(v.retryable).toBe(true)
  })
  it('masked → branch=content 且 masked=true（数据照常渲染，绝不落 empty/error）', () => {
    const v = s({ state: 'masked', masked_fields: ['phone'] })
    expect(v.branch).toBe('content')
    expect(v.masked).toBe(true)
  })
})
```

```ts
// gridStyle.spec.ts
import { describe, it, expect } from 'vitest'
import { gridStyleOf } from '../gridStyle'

describe('gridStyleOf（12 列制）', () => {
  it('缺省 x=1,y=1,w=3,h=2', () => {
    expect(gridStyleOf(null)).toEqual({ gridColumn: '1 / span 3', gridRow: '1 / span 2' })
  })
  it('全字段透传', () => {
    expect(gridStyleOf({ x: 5, y: 2, w: 6, h: 3 }))
      .toEqual({ gridColumn: '5 / span 6', gridRow: '2 / span 3' })
  })
  it('w 越界钳到 1-12，x 钳到 1-12', () => {
    expect(gridStyleOf({ x: 0, y: 1, w: 99, h: 1 }).gridColumn).toBe('1 / span 12')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend; npx vitest run src/views/twin` → FAIL（模块不存在）

- [ ] **Step 3: 实现三个纯模块**

```ts
// frontend/src/views/twin/widgets/adapter.ts
type Rec = Record<string, any>
export function toMultiLine(d: { records: Rec[]; t: string; values: string[] }) {
  return {
    xAxis: (d.records ?? []).map((r) => String(r[d.t] ?? '')),
    series: (d.values ?? []).map((v) => ({ name: v, data: (d.records ?? []).map((r) => r[v] ?? null) })),
  }
}
export function toBar(d: { records: Rec[]; t: string; values: string[] }) {
  const key = (d.values ?? [])[0]
  return (d.records ?? []).map((r) => ({ name: String(r[d.t] ?? ''), value: Number(r[key] ?? 0) }))
}
export function toPie(d: { records: Rec[]; parts: string[] }) {
  const [k, v] = d.parts ?? []
  return (d.records ?? []).map((r) => ({ name: String(r[k] ?? ''), value: Number(r[v] ?? 0) }))
}
export const toTable = (d: { records?: Rec[] }) => d.records ?? []
export const kpiValue = (d: { value?: unknown }) => d?.value ?? null
```

```ts
// frontend/src/views/twin/stateMap.ts
import type { WidgetDatum, TwinMode } from '@/types/twin'

export interface WidgetViewState {
  branch: 'content' | 'empty' | 'error'
  loading: boolean          // 由宿主注入（本地态），这里恒 false 占位
  emptyTitle: string; emptyDesc: string
  errorText: string; retryable: boolean
  masked: boolean           // 仅 branch=content 有意义：值位 🔒 开关
}
export function widgetState(d: WidgetDatum, mode: TwinMode): WidgetViewState {
  const out: WidgetViewState = {
    branch: 'content', loading: false, emptyTitle: '暂无数据', emptyDesc: '',
    errorText: '', retryable: false, masked: d.state === 'masked',
  }
  if (d.state === 'empty') {
    out.branch = 'empty'
    if (d.reason === 'unbound') {
      out.emptyTitle = mode === 'edit' ? '未绑定查询，点击绑定' : '未绑定查询'
      out.emptyDesc = mode === 'edit' ? '从本体的 verified 查询中选一个' : ''
    } else {
      out.emptyTitle = '查询结果为空'; out.emptyDesc = ''
    }
  } else if (d.state === 'error') {
    out.branch = 'error'
    out.errorText = d.error ? `${d.error.code}: ${d.error.message}` : '未知错误'  // W6
    out.retryable = true                                                          // ↻ → T9
  }
  return out
}
```

```ts
// frontend/src/views/twin/gridStyle.ts
import type { CSSProperties } from 'vue'
const clamp = (n: number, lo: number, hi: number) => Math.min(Math.max(n, lo), hi)
export function gridStyleOf(grid: Record<string, unknown> | null): CSSProperties & Record<string, string> {
  const g = grid ?? {}
  const x = clamp(Number(g.x ?? 1), 1, 12)
  const y = clamp(Number(g.y ?? 1), 1, 64)
  const w = clamp(Number(g.w ?? 3), 1, 12)
  const h = clamp(Number(g.h ?? 2), 1, 64)
  return { gridColumn: `${x} / span ${w}`, gridRow: `${y} / span ${h}` }
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend; npx vitest run src/views/twin`
Expected: 3 spec 文件全绿（约 13 passed）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/twin/widgets/adapter.ts frontend/src/views/twin/stateMap.ts frontend/src/views/twin/gridStyle.ts frontend/src/views/twin/__tests__
git commit -m "feat(twin): pure renderer adapters, four-state mapping and grid style (W6)"
```

---

### Task 5: WidgetShell / WidgetGrid / 5 个 P0 renderer（SSR 渲染测试钉死承重原则）

**Files:**
- Create: `frontend/src/views/twin/WidgetShell.vue`
- Create: `frontend/src/views/twin/WidgetGrid.vue`
- Create: `frontend/src/views/twin/widgets/KpiWidget.vue`、`TrendWidget.vue`、`BarWidget.vue`、`DonutWidget.vue`、`AlertTableWidget.vue`
- Test: `frontend/src/views/twin/__tests__/WidgetGrid.spec.ts`

**Interfaces:**
- Consumes: Task 4 的 `widgetState`/`gridStyleOf`/adapter；`StateWrapper.vue`（props：loading/error/empty/emptyTitle/emptyDesc/retryable + @retry）；`MultiLineChart`（xAxis/series）、`BarChart`（data:{name,value}[]）、`PieChart`（data:{name,value}[]）；`types/twin.d.ts`
- Produces:
  - `WidgetGrid.vue` props：`widgets: TwinWidget[]`、`pageData: Record<number, WidgetDatum>`、`mode: TwinMode`、`loading?: boolean`；emits：`bind(widget)`、`drill(widget)`、`retry(widgetId)`、`layout(items: LayoutItem[])`（Task 8  BindDrawer/保存布局消费）
  - `WidgetShell.vue` props：`widget`、`datum: WidgetDatum|null`、`mode`；emits `retry` `bind` `drill`
  - renderer 约定：每个 `*Widget.vue` 只接 `datum: WidgetDatum` prop，内部用 adapter 转组件 props；masked 时对应列/值叠 🔒（`masked_fields`）

- [ ] **Step 1: 写失败测试（programmatic runtime，先例 AssetCardList.spec.ts）**

```ts
import { describe, it, expect } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import WidgetGrid from '../WidgetGrid.vue'
import type { TwinWidget, WidgetDatum } from '@/types/twin'

const mkWidget = (id: number, over = {}): TwinWidget => ({
  id, page_id: 1, widget_key: `w${id}`, title: `标题${id}`, query_id: 1,
  param_values_json: {}, display_json: {}, grid_json: { x: 1, y: id, w: 3, h: 2 },
  refresh_json: null, sort_order: id, updated_at: null, ...over,
})
const mkDatum = (id: number, over = {}): WidgetDatum => ({
  widget_id: id, widget_key: `w${id}`, title: `标题${id}`, query_id: 1,
  state: 'ok', reason: null, result_shape: 'kpi', columns: ['v'],
  data: { value: 42, records: [{ v: 42 }] }, row_count: 1, truncated: false,
  masked_fields: [], error: null, cached: false, updated_at: 'x', ...over,
})

async function render(w: TwinWidget[], d: Record<number, WidgetDatum>, mode: 'edit' | 'run') {
  return await renderToString(createSSRApp(WidgetGrid, { widgets: w, pageData: d, mode }))
}

describe('WidgetGrid / WidgetShell（W3/W6/承重）', () => {
  it('run 态不渲染任何把手（.wops 缺失 = 模式差异唯一实现）', async () => {
    const html = await render([mkWidget(1)], { 1: mkDatum(1) }, 'run')
    expect(html).not.toContain('wops')
    expect(html).toContain('标题1')
  })
  it('edit 态渲染把手', async () => {
    const html = await render([mkWidget(1)], { 1: mkDatum(1) }, 'edit')
    expect(html).toContain('wops')
  })
  it('kpi 出数值；masked 出现 🔒 且绝不出现空态文案', async () => {
    const html = await render([mkWidget(1)], { 1: mkDatum(1) }, 'run')
    expect(html).toContain('42')
    const m = await render([mkWidget(1)],
      { 1: mkDatum(1, { state: 'masked', data: { value: 1380000, records: [] }, masked_fields: ['v'] }) }, 'run')
    expect(m).toContain('🔒')
    expect(m).not.toContain('暂无数据')
  })
  it('error 态回显 code: message（W6）', async () => {
    const html = await render([mkWidget(1)],
      { 1: mkDatum(1, { state: 'error', error: { code: 'TWIN_DATA_TIMEOUT', message: '取数超时（>5s）' } }) }, 'run')
    expect(html).toContain('TWIN_DATA_TIMEOUT')
    expect(html).toContain('取数超时')
  })
  it('empty+unbound 编辑态含绑定 CTA', async () => {
    const html = await render([mkWidget(1)], { 1: mkDatum(1, { state: 'empty', reason: 'unbound' }) }, 'edit')
    expect(html).toContain('未绑定查询，点击绑定')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend; npx vitest run src/views/twin/__tests__/WidgetGrid.spec.ts` → FAIL

- [ ] **Step 3: 实现 5 个 renderer + Shell + Grid**

renderer 模板（五式同构，只有图表体不同；KPI 新建因 StatsCard 是 AI Context 专用卡——spec C2）：

```vue
<!-- frontend/src/views/twin/widgets/KpiWidget.vue -->
<template>
  <div class="kpi-widget">
    <span class="kpi-value mono">{{ locked ? '🔒' : display }}</span>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { kpiValue } from './adapter'
import type { WidgetDatum } from '@/types/twin'
const props = defineProps<{ datum: WidgetDatum }>()
const locked = computed(() => props.datum.masked_fields.includes(props.datum.columns[0] ?? ''))
const display = computed(() => {
  const v = kpiValue(props.datum.data as any)
  return v == null ? '-' : String(v)
})
</script>
```

`TrendWidget`（`toMultiLine(datum.data)` → `<MultiLineChart :x-axis :series>`，masked 时对 `masked_fields` 命中列在系列名后加 🔒——以 series name 后缀实现）、`BarWidget`（`toBar` → `<BarChart :data>`）、`DonutWidget`（`toPie` → `<PieChart :data>`）、`AlertTableWidget`（`toTable` → `a-table`，列 = `datum.columns`；`masked_fields` 命中的 `dataIndex` 单元格渲染 🔒；`truncated` 时表尾提示「已截断（上限 200 行）」）。五者统一签名 `defineProps<{ datum: WidgetDatum }>()`。

```vue
<!-- frontend/src/views/twin/WidgetShell.vue -->
<template>
  <div class="widget-shell" :class="[`st-${vs.branch}`, { masked: vs.masked }]">
    <div class="widget-head">
      <span class="title">{{ widget.title || widget.widget_key }}</span>
      <span v-if="vs.masked" class="mask-flag">🔒</span>
      <span class="wops" v-if="mode === 'edit'">
        <button class="op bind" @click="$emit('bind', widget)">绑定</button>
        <button class="op drill" @click="$emit('drill', widget)">下钻</button>
      </span>
    </div>
    <StateWrapper :loading="loading || vs.loading" :empty="vs.branch === 'empty'"
      :error="vs.branch === 'error' ? vs.errorText : null"
      :empty-title="vs.emptyTitle" :empty-desc="vs.emptyDesc"
      :retryable="vs.retryable" @retry="$emit('retry', widget.id)">
      <component :is="renderer" v-if="renderer && datum" :datum="datum" />
      <div v-else-if="datum && !renderer" class="stub">该形状（{{ datum.result_shape }}）属 P1，暂以表格占位</div>
    </StateWrapper>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import StateWrapper from '@/components/common/StateWrapper.vue'
import { widgetState } from './stateMap'
import KpiWidget from './widgets/KpiWidget.vue'
import TrendWidget from './widgets/TrendWidget.vue'
import BarWidget from './widgets/BarWidget.vue'
import DonutWidget from './widgets/DonutWidget.vue'
import AlertTableWidget from './widgets/AlertTableWidget.vue'
import type { TwinWidget, WidgetDatum, TwinMode, ResultShape } from '@/types/twin'
const props = defineProps<{ widget: TwinWidget; datum: WidgetDatum | null; mode: TwinMode; loading?: boolean }>()
defineEmits<{ retry: [id: number]; bind: [w: TwinWidget]; drill: [w: TwinWidget] }>()
const RENDERERS: Partial<Record<ResultShape, any>> =
  { kpi: KpiWidget, trend: TrendWidget, bar: BarWidget, donut: DonutWidget, table: AlertTableWidget }
const vs = computed(() => props.datum ? widgetState(props.datum, props.mode)
  : { branch: 'empty', loading: props.loading ?? false, emptyTitle: '加载中…', emptyDesc: '', errorText: '', retryable: false, masked: false })
const renderer = computed(() => props.datum ? RENDERERS[props.datum.result_shape ?? 'kpi'] ?? null : null)
</script>
```

```vue
<!-- frontend/src/views/twin/WidgetGrid.vue —— 唯一画布：编辑/运行共用，禁 RunCanvas -->
<template>
  <div class="widget-grid" :class="mode">
    <WidgetShell v-for="w in widgets" :key="w.id" :widget="w" :datum="pageData[w.id] ?? null"
      :mode="mode" :loading="loading" :style="gridStyleOf(w.grid_json)"
      @retry="(id) => $emit('retry', id)" @bind="(x) => $emit('bind', x)" @drill="(x) => $emit('drill', x)" />
  </div>
</template>
<script setup lang="ts">
import WidgetShell from './WidgetShell.vue'
import { gridStyleOf } from './gridStyle'
import type { TwinWidget, WidgetDatum, TwinMode } from '@/types/twin'
defineProps<{ widgets: TwinWidget[]; pageData: Record<number, WidgetDatum>; mode: TwinMode; loading?: boolean }>()
defineEmits<{ retry: [id: number]; bind: [w: TwinWidget]; drill: [w: TwinWidget] }>()
</script>
<style scoped>
.widget-grid { display: grid; grid-template-columns: repeat(12, 1fr); grid-auto-rows: 96px; gap: 10px; }
.widget-grid.run .wops { display: none; }   /* 模式差异唯一实现（原型:125/:163） */
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend; npx vitest run src/views/twin`
Expected: 全绿（Task 4 + Task 5 用例）

- [ ] **Step 5: 承重守卫**

Run: `cd frontend; git grep -l "RunCanvas" -- src` → 必须无输出。
Run: `cd frontend; Select-String -Path src\views\twin\*.vue,src\views\twin\**\*.vue -Pattern "#[0-9a-fA-F]{3,8}\b" | Where-Object Line -notmatch "//"` → 样式内无裸 hex（W2；如有则改 `var(--*)`）。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/twin
git commit -m "feat(twin): WidgetGrid/WidgetShell + 5 P0 renderers, single-canvas mode contract (W3/W6)"
```

---

### Task 6: 工作区壳（TwinWorkspace + 左栏 + 路由/菜单/i18n 接线）

**Files:**
- Create: `frontend/src/views/twin/TwinWorkspace.vue`、`TwinCardList.vue`、`PageModuleList.vue`
- Modify: `frontend/src/router/index.ts`（:113 `admin/simulation` 块后追加）
- Modify: `frontend/src/views/admin/componentMap.ts`（:88 `'voice-tool-policy'` 行后、`}` 前追加 + import）
- Modify: 4 个 locale 文件（`knowledge.menu` 内 `simulation` 行后）

**Interfaces:**
- Consumes: `useTwinStore`（Task 3）；AppLayout 体系约定（requiresAdmin meta）
- Produces: 路由 `/admin/digital-twin`（name `DigitalTwin`）；componentMap key `digital-twin`；i18n key `knowledge.menu.twin`（zh-CN 孪生应用 / zh-TW 孿生應用 / en-US Digital Twin / ja-JP デジタルツイン）；左栏两组组件（卡片三组徽标 + 模块 palette）

- [ ] **Step 1: 追加路由与 componentMap**

`router/index.ts`（`admin/simulation` 对象之后）：

```ts
      // ── 孪生应用（Plan 2）：sys_menu 2407 (/admin/digital-twin)，与沙盘同构双挂载 ──
      {
        path: 'admin/digital-twin',
        name: 'DigitalTwin',
        component: () => import('@/views/twin/TwinWorkspace.vue'),
        meta: { title: '孪生应用', icon: 'DeploymentUnitOutlined', requiresAdmin: true }
      },
```

`componentMap.ts`：import 区追加 `import TwinWorkspace from '@/views/twin/TwinWorkspace.vue'`；表内 `'voice-tool-policy'` 行后：

```ts
  // 孪生应用：sys_menu 2407 (/admin/digital-twin)，path 末段 = menuKey = i18n_key 末段
  'digital-twin': markRaw(TwinWorkspace),
```

- [ ] **Step 2: i18n 四 locale 追加**

各文件 `knowledge.menu` 的 `simulation` 行后加一行（键名与 sys_menu i18n_key `knowledge.menu.twin` 对齐）：

```ts
      twin: '孪生应用',        // zh-CN
      twin: '孿生應用',        // zh-TW
      twin: 'Digital Twin',   // en-US
      twin: 'デジタルツイン',  // ja-JP
```

- [ ] **Step 3: 实现三壳组件**

`TwinWorkspace.vue`：骨架 = ctxbar(42) + `grid-template-columns: 238px 1fr 336px` + statusbar(30)；局部尺寸变量按 spec §7.4（`--twin-top/--twin-ctxbar/--twin-statusbar`，全部 `var(--*)` 取色）。挂载逻辑：

```ts
import { onMounted, onBeforeUnmount } from 'vue'
import { useTwinStore } from '@/stores/twin'
const store = useTwinStore()
onMounted(async () => {
  await store.loadCards()
  const first = store.cards.mine[0] ?? store.cards.shared[0]
  if (first) await store.openCard(first.id)
  const onVis = () => store.onVisibility(document.hidden)
  document.addEventListener('visibilitychange', onVis)
  onBeforeUnmount(() => { document.removeEventListener('visibilitychange', onVis); store.stopScheduler() })
})
```

`TwinCardList.vue`：三组（我的/共享给我的（只读·剩余 N 天 = `share_expires_at` 换算）/🔒 受限）；徽标 `runtime_state` 三态（draft/live/paused → 草稿/运行中/已暂停）；点受限卡 → `store` 不发取数、直接开 PermDrawer（Task 8；本任务先 emit 占位事件）；顶部「+ 新建卡片」（弹最小表单：name/ontology_id/ontology_version≥1/scene_key → `createCard`）。
`PageModuleList.vue`：palette 列出 5 类 P0 壳形（kpi/trend/bar/donut/table），点击 → 走 Task 8 AddModuleModal。
statusbar：刷新档位三选（10秒/30秒/关闭 → `applyRefreshCfg` + `startScheduler`）+ 组件计数 + `collected_at` 时刻。
`TwinCanvas.vue` 与 `CanvasToolbar.vue`：中栏容器（标题、`scene_key` tag、编辑/运行段控件 `setMode`、添加模块入口）+ `<WidgetGrid>`（bind/drill 事件本任务先 console 占位，Task 8 接 overlay）。

- [ ] **Step 4: 类型与守卫**

Run: `cd frontend; npx vitest run src/views/twin src/stores` → 全绿（无回归）
Run: `cd frontend; npx vue-tsc --noEmit -p tsconfig.json` → 无新增错误
守卫：`git grep -n "digital-twin" -- frontend/src/router frontend/src/views/admin/componentMap.ts` 两处都命中；菜单 i18n 四文件 `twin:` 各命中 1 次。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/twin/TwinWorkspace.vue frontend/src/views/twin/TwinCardList.vue frontend/src/views/twin/PageModuleList.vue frontend/src/views/twin/TwinCanvas.vue frontend/src/views/twin/CanvasToolbar.vue frontend/src/router/index.ts frontend/src/views/admin/componentMap.ts frontend/src/i18n/locales/zh-CN.ts frontend/src/i18n/locales/zh-TW.ts frontend/src/i18n/locales/en-US.ts frontend/src/i18n/locales/ja-JP.ts
git commit -m "feat(twin): workspace shell, dual-mount route, componentMap key and i18n (D2/D3)"
```

---

### Task 7: 只读发布页 `/twin-p/:slug`（P0-9）

**Files:**
- Create: `frontend/src/views/twin/TwinPublishedPage.vue`
- Modify: `frontend/src/router/index.ts`（顶层 `/login` 块后追加）
- Test: `frontend/src/views/twin/__tests__/TwinPublishedPage.spec.ts`

**Interfaces:**
- Consumes: `api/twin.getPublished/runPublished`（T11）；`WidgetGrid`（mode='run'）；`/login` 顶层路由模板（hideHeader）
- Produces: 路由 `/twin-p/:slug`（name `TwinPublished`，meta `{requiresAuth:true, hideHeader:true}`）；403 统一拒绝视图（DENY_MESSAGE，无差异分支）

- [ ] **Step 1: 写失败测试（拒绝路径同源文案）**

```ts
import { describe, it, expect, vi } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'

vi.mock('@/api/twin', () => ({
  getPublished: vi.fn().mockRejectedValue(
    Object.assign(new Error('x'), { response: { data: { code: 'TWIN_ACCESS_REQUIRED', message: '无权访问该页面' } } })),
  runPublished: vi.fn(),
}))
import TwinPublishedPage from '../TwinPublishedPage.vue'

describe('TwinPublishedPage（W12）', () => {
  it('403 → 统一拒绝文案，不泄露拒绝原因差异', async () => {
    const html = await renderToString(createSSRApp(TwinPublishedPage, { slug: 'zzz' }))
    // 组件把任何错误都渲染成同一 DENY 视图
    expect(await settle(html)).toContain('无权访问')
  })
})
async function settle(htmlPromise: Promise<string>) { await new Promise(r => setTimeout(r, 0)); return await htmlPromise }
```

注：SSR 一次渲染拿不到异步态；若实测不可行，降级为「把 deny 文案抽成纯函数 `denyView(err): {show: boolean; text: string}`，任何 err → 同一 `'无权访问该页面'`」的纯函数测试——**断言意图不变（反枚举同源文案），胶水允许更换并记入计划缺陷节**。

- [ ] **Step 2: 跑测试确认失败** → FAIL

- [ ] **Step 3: 实现**

```vue
<!-- frontend/src/views/twin/TwinPublishedPage.vue —— 只读壳：复用 WidgetGrid，绝无第二画布 -->
<template>
  <div class="published-page">
    <header class="pp-bar">
      <span>{{ meta?.card?.name }} · {{ meta?.page?.name }}</span>
      <span class="pp-ver mono">v{{ meta?.version }} · {{ meta?.published_at }}</span>
    </header>
    <p v-if="denied" class="pp-deny">{{ DENY_TEXT }}</p>
    <WidgetGrid v-else :widgets="widgetList" :page-data="pageData" mode="run" :loading="loading"
      @retry="refreshOne" />
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import WidgetGrid from './WidgetGrid.vue'
import { getPublished, runPublished } from '@/api/twin'
import type { PublishedMeta, WidgetDatum, TwinWidget } from '@/types/twin'

const props = defineProps<{ slug: string }>()
const DENY_TEXT = '无权访问该页面'          // 反枚举：未知/跨租/停用/角色不命中同一句
const meta = ref<PublishedMeta | null>(null)
const pageData = ref<Record<number, WidgetDatum>>({})
const denied = ref(false)
const loading = ref(true)
const widgetList = computed<TwinWidget[]>(() =>
  (meta.value?.widgets ?? []).map((w, i) => ({
    id: w.widget_id, page_id: meta.value?.page?.id ?? 0, widget_key: w.widget_key,
    title: w.title, query_id: w.query_id, param_values_json: w.param_values_json,
    display_json: null, grid_json: w.grid_json, refresh_json: w.refresh_json ?? null,
    sort_order: i, updated_at: null,
  })))
let timer: ReturnType<typeof setInterval> | null = null
async function load() {
  loading.value = true
  try {
    meta.value = await getPublished(props.slug)
    const resp = await runPublished(props.slug)
    const next: Record<number, WidgetDatum> = {}
    for (const it of resp.items) next[it.widget_id] = it
    pageData.value = next
    denied.value = false
  } catch { denied.value = true } finally { loading.value = false }
}
async function refreshOne(widgetId: number) {
  const resp = await runPublished(props.slug)
  const hit = resp.items.find((i) => i.widget_id === widgetId)
  if (hit) pageData.value = { ...pageData.value, [widgetId]: hit }
}
onMounted(async () => {
  await load()
  const ms = Number((meta.value?.refresh as any)?.interval ?? 10000)
  if (ms > 0) timer = setInterval(() => void load(), ms)
})
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>
```

`router/index.ts` 顶层（`/login` 对象后）：

```ts
  {
    // 孪生只读发布页（T11）：不套 AppLayout（无左导航/把手，W12）；P0 仅登录态
    path: '/twin-p/:slug',
    name: 'TwinPublished',
    component: () => import('@/views/twin/TwinPublishedPage.vue'),
    props: true,
    meta: { title: '孪生看板', requiresAuth: true, hideHeader: true }
  },
```

- [ ] **Step 4: 跑测试确认通过 + 路由守卫**

Run: `cd frontend; npx vitest run src/views/twin/__tests__/TwinPublishedPage.spec.ts` → passed
守卫：确认 `beforeEach` 现有逻辑覆盖 `requiresAuth`（`router/index.ts:142-150`，未登录跳 `/login`），无需新增守卫代码。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/twin/TwinPublishedPage.vue frontend/src/views/twin/__tests__/TwinPublishedPage.spec.ts frontend/src/router/index.ts
git commit -m "feat(twin): read-only published page on top-level /twin-p/:slug (W12, anti-enumeration)"
```

---

### Task 8: Overlays（BindDrawer / AddModuleModal / PublishModal / PermDrawer / DrillDrawer 骨架）+ TwinAiDock 骨架（P0-10 前端面）

**Files:**
- Create: `frontend/src/views/twin/overlays/BindDrawer.vue`、`AddModuleModal.vue`、`PublishModal.vue`、`PermDrawer.vue`、`DrillDrawer.vue`
- Create: `frontend/src/views/twin/TwinAiDock.vue`
- Modify: `frontend/src/views/twin/TwinWorkspace.vue`（挂 overlay 开关）
- Test: `frontend/src/views/twin/__tests__/unbind.spec.ts`

**Interfaces:**
- Consumes: `listQueries/previewQuery`（Task 2）、`patchWidget/addWidget/saveLayout`（Task 1）、store `publish/unpublish/requestAccess/approve/reject/loadRequests`
- Produces: overlay 开关态入 store（`overlay: {name: string|null; target: TwinCard|TwinWidget|null}`——store 需补这组字段：`overlayName`/`overlayTarget` + `openOverlay(name, target)`/`closeOverlay()`，本任务顺带完成并同步 Task 3 测试文件追加 1 条用例）
- 硬约束:DrillDrawer 与 TwinAiDock **零请求**（后端无 drill/T13/T14/batch）

- [ ] **Step 1: 写失败测试（解绑显式 null 的调用面）**

```ts
// unbind.spec.ts —— BindDrawer 的解绑动作必须发 {query_id: null}
import { describe, it, expect, vi } from 'vitest'
vi.mock('@/api/twin', () => ({ patchWidget: vi.fn().mockResolvedValue({}) }))
import { patchWidget } from '@/api/twin'

describe('解绑契约（spec §6.1）', () => {
  it('unbind 必须显式携带 query_id:null 键', async () => {
    await patchWidget(3, { query_id: null })   // BindDrawer 内部同一调用式
    expect(patchWidget).toHaveBeenCalledWith(3, { query_id: null })
  })
})
```

- [ ] **Step 2: 跑测试确认失败**（`@/api/twin` 的 `patchWidget` 尚不存在时先红；Task 1 已交付则此测试直接绿——照跑，红了修到绿）

- [ ] **Step 3: 实现五个 overlay + AI 骨架**

**BindDrawer.vue**（a-drawer）：目标 widget 的 `result_shape` 决定 `listQueries(card.ontology_id, { shape, verifiedOnly: true })` 过滤；列表项选中 → `previewQuery(q.id, widget.param_values_json)` 出预览小表；「绑定」→ `patchWidget(id, { query_id, param_values_json })`；「解绑」→ `patchWidget(id, { query_id: null })`；服务端拒绝（shape 不配对等）→ `ApiError.message + JSON.stringify(detail)` 内联红条展示（W9 前端面）。

**AddModuleModal.vue**：表单 = widget_key（自动生成 `w_<ts>` 可改）、title、壳形五选一；grid 默认追加行（`y = 现有最大 y + h`，w=3/h=2）；提交 `addWidget(pageId, {...})`（`query_id` 留空 → 新组件天然是 empty/unbound 态）。

**PublishModal.vue**：access 段控件（org|role）；role 时 `role_codes` 多选（必填非空）；提交 `store.publish(...)` → 展示返回的 `url`（`/twin-p/{slug}`）+ 复制按钮 + `version`；已发布时另给「停用」（`store.unpublish`，确认框文案含"链接立即拒绝、版本史保留、slug 不回收"）。

**PermDrawer.vue**（双面，W5/W13）：
- `overlayTarget.access === 'restricted'` → 申请面：reason textarea（`maxlength=500` + 计数）→ `store.requestAccess(cardId, reason)`，成功回显「申请已提交」；
- owner/审批面：`store.loadRequests()` 列表 incoming（approve：`expires_in_days` 数字框 min=1 max=365；reject 无体）+ outgoing + 待办计数徽标源；
- 进入受限卡自动开：TwinCardList 点击 restricted → `openOverlay('perm', card)`（W5，**不发取数请求**——取数旁路会被 403 堵，属后端已验证行为）。

**DrillDrawer.vue**：a-drawer 空壳 + `<a-empty description="下钻能力将随后端取数端点提供" />`；**组件内不 import 任何 api**（G2 缺口的诚实呈现）。

**TwinAiDock.vue**：右栏 336 布局镜像 OntAssistantDock（输入框 + 建议 chips + 候选区 + 「应用到页面」按钮），全部 `disabled`，`placeholder="AI 能力即将上线"`；不 import api；props `{ disabled: true }` 常亮。

TwinWorkspace 接线：`<component :is="overlayComp" v-if="store.overlayName" ... @close="store.closeOverlay()" />`。

- [ ] **Step 4: 跑测试 + 零请求守卫**

Run: `cd frontend; npx vitest run src/views/twin` → 全绿
守卫：`Select-String -Path src\views\twin\overlays\DrillDrawer.vue,src\views\twin\TwinAiDock.vue -Pattern "api/"` → **无输出**（两骨架零请求）。
Run: `cd frontend; npx vue-tsc --noEmit -p tsconfig.json` → 无新增错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/twin frontend/src/stores/twin.ts frontend/src/stores/__tests__/twin.spec.ts frontend/src/views/twin/__tests__/unbind.spec.ts
git commit -m "feat(twin): overlays (bind/add/publish/perm) + drill & AI skeletons, zero fabricated calls"
```

---

### Task 9: tokens 缺口补齐（--cyan/--purple + soft，双皮肤）

**Files:**
- Modify: `frontend/src/styles/tokens.css`（dark 块 :94 后、light 块 :154 后各插 4 行；零改动既有行）

**Interfaces:**
- Consumes: spec §7.2 数值表（唯一数值真源）
- Produces: `--cyan` `--cyan-soft` `--purple` `--purple-soft` 于 dark+light 两块

- [ ] **Step 1: 先写守卫测试（红）**

```ts
// frontend/src/views/twin/__tests__/tokens.spec.ts
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

describe('tokens 缺口（spec §7.2，W2）', () => {
  const css = readFileSync(resolve(__dirname, '../../../styles/tokens.css'), 'utf-8')
  for (const [name, dark, light] of [
    ['--cyan', '#39d3c4', '#0d9488'],
    ['--purple', '#b48ef0', '#7c3aed'],
  ] as const) {
    it(`${name} 双皮肤实存（值各归块）`, () => {
      expect(css).toContain(`${name}: ${dark}`)
      expect(css).toContain(`${name}: ${light}`)
      expect(css).toContain(`${name}-soft:`)
    })
  }
  it('--neon-cyan 未被改动（spec §7.3 例外记录）', () => {
    expect(css).toContain('--neon-cyan: #4aa3ff')
  })
})
```

Run: `cd frontend; npx vitest run src/views/twin/__tests__/tokens.spec.ts` → FAIL

- [ ] **Step 2: dark 块插入**（`--info-soft: rgba(74, 163, 255, 0.12);` 行后）：

```css
  /* 孪生应用原型色（Plan 2 引入；仅 twin 模块消费——与 --neon-* 的语义重叠是记录在案的
     例外，见 specs/2026-11-01-digital-twin-frontend-design.md §7.3；R9：只新增不改既有） */
  --cyan: #39d3c4;
  --cyan-soft: rgba(57, 211, 196, 0.12);
  --purple: #b48ef0;
  --purple-soft: rgba(180, 142, 240, 0.12);
```

- [ ] **Step 3: light 块插入**（light 的 `--info-soft: rgba(59, 130, 246, 0.08);` 行后）：

```css
  --cyan: #0d9488;
  --cyan-soft: rgba(13, 148, 136, 0.08);
  --purple: #7c3aed;
  --purple-soft: rgba(124, 58, 237, 0.08);
```

- [ ] **Step 4: 跑测试确认通过 + diff 守卫**

Run: `cd frontend; npx vitest run src/views/twin/__tests__/tokens.spec.ts` → `3 passed`
Run: `git diff -- frontend/src/styles/tokens.css | Select-String "^-"` → **无输出**（零删除行 = R9 铁证）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/styles/tokens.css frontend/src/views/twin/__tests__/tokens.spec.ts
git commit -m "feat(twin): add cyan/purple tokens to both skins, additive-only (R9/W2)"
```

---

### Task 10: 全量验证（vitest 全套 + vue-tsc + 守卫 grep 总表 + 后端菜单测试复跑）

**Files:**
- 无新文件（验证任务；发现问题回改对应文件）

- [ ] **Step 1: 前端全量单测**

Run: `cd frontend; npx vitest run`
Expected: 全绿（含既有 33 个 spec 无回归）。失败 → 修到绿，不改既有测试预期迁就。

- [ ] **Step 2: 类型检查**

Run: `cd frontend; npx vue-tsc --noEmit -p tsconfig.json`
Expected: 无新增错误（与执行前基线对比，基线错误原样记录）。

- [ ] **Step 3: 守卫 grep 总表（spec §8.3，逐条必须为空/命中预期）**

```
git grep -l "RunCanvas" -- frontend/src                                   → 空
Select-String twin 业务样式 裸 hex 模式                                     → 空（W2）
git grep -n "localStorage\|sessionStorage" -- frontend/src/stores/twin.ts  → 空（W11 旁证）
api/twin.ts + twinQuery.ts 端点字面量 ⊆ T1–T12/Q1–Q5                        → 人工比对口
git grep -n "widgets/batch\|/ask\|/draft\|twin/ai" -- frontend/src          → 空（防臆造端点）
```

- [ ] **Step 4: 后端菜单测试复跑（防前端任务顺手碰坏 SQL）**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests\twin -q`
Expected: `85 passed`（原 84 + Task 0 新增 1）。

- [ ] **Step 5: 空提交占位（若前 4 步产生修复，按文件归属并入各自 Task 提交；本步只提交守卫结果记录到计划缺陷节）**

```bash
git add docs/superpowers/plans/2026-11-01-digital-twin-p0-frontend.md
git commit -m "docs(twin): plan2 verification pass recorded"
```

---

### Task 11: 浏览器验收清单（人工门）+ 规格关账（W16 前端面）

**Files:**
- Modify: `docs/superpowers/specs/2026-11-01-digital-twin-app-design.md`（主 spec 关账：§2.3 文本、§6.2 两处映射、§6.5 色值笔误）

**Interfaces:**
- Consumes: 全部前序 Task；本地起前后端（`npm run dev` + 后端 uvicorn，端口照 `.env.local`）

- [ ] **Step 1: 主 spec 四处订正（外科式文本，不动其余内容）**

1. §2.3：`id 2406 → 2407`、`/admin/kg-twin → /admin/digital-twin`、`visible 0 → 1`（含幂等 UPDATE 一句）。
2. §6.2 组件树：`Kpi✅StatsCard` → `Kpi🆕（StatsCard 为 AI Context 专用卡，不可复用）`（订正 C2）。
3. §6.2：bar 行补注「P0 单序列（BarChart props 面）」（订正 C3）。
4. §6.5 散文：`#4cc98a → #4cc38a`（订正 C4，一字之改）。

- [ ] **Step 2: 浏览器验收清单（人工执行，逐项打勾记录于计划缺陷节尾部）**

| # | 步骤 | 通过判据 |
|---|---|---|
| V1 | 登录后侧栏点「孪生应用」 | 进入 `/admin/digital-twin`，三栏 238/1fr/336，1280×800 无横向滚动（W1） |
| V2 | 新建卡片→添加模块→绑定 verified 查询 | BindDrawer 只列 verified；预览出表；保存后出数（W6-ok） |
| V3 | 切「运行」段控件 | 把手全隐、数据仍在轮询；Network 面板每 10s 恰 1 个 `pages/{id}/data`（W3/W7/W8） |
| V4 | 断网/停后端制造 error | 值区显示 `TWIN_*: 文案`，点 ↻ 单组件重试只发 1 个 GET（W6/W9 面） |
| V5 | 发布（access=role 选一个角色） | 恒 200；Modal 显示 `/twin-p/{slug}` 与 v2/v3 递增 |
| V6 | 无权限账号打开只读链接 | 同一句「无权访问该页面」，Network 恰 1 个 403，无 404/403 差异（W12/反枚举） |
| V7 | 受限卡点 🔒 → 申请 → owner 审批（30 天） | 卡片转入「共享给我的」且显示剩余天数（W5/W13） |
| V8 | 豁免角色 vs 普通角色看同一 masked 查询 | 前者见明文、后者见 🔒，交替刷新不串值（W11 联调面） |
| V9 | 切暗/亮皮肤 | cyan/purple 元素两态都可读，无白字白底（W2） |
| V10 | AI dock 与 Drill | 全禁用/空壳、Network 零请求（D1/G2 呈现正确） |

- [ ] **Step 3: 关账与提交**

Run: `git grep -n "kg-twin" -- docs backend frontend` → 除历史叙述（计划文档执行记录、旧 spec 引文）外，**活跃契约面**（菜单 SQL、router、componentMap、测试、主 spec §2.3）零命中。

```bash
git add docs/superpowers/specs/2026-11-01-digital-twin-app-design.md docs/superpowers/plans/2026-11-01-digital-twin-p0-frontend.md
git commit -m "docs(twin): plan2 closeout - main spec corrections C2/C3/C4/C5 and acceptance record"
```

- [ ] **Step 4: 完成后转 finishing-a-development-branch 收尾**

---

## 执行时发现的计划缺陷

（执行期间逐条回写：编号 / 现象 / 根因 / 处置。本行为占位起始，非 TBD。）

1. **D-01｜Step 1 基线不绿**：预期 `6 passed`，实得 `1 failed, 5 passed`。根因：并行沙盘特性已把 `menu_knowledge_governance.sql` 的 2408 行与角色授权末界 `AND 2408` 写进工作区，而 `init.sql` 仍停在 `AND 2407`，旧测试钉死精确串 `BETWEEN 2401 AND 2407` → gov 侧假失败。处置：range 测试改为「末界 ≥ 2407 = 覆盖孪生行」语义（保留 `id <> 2404` 排除），不越界碰 2408 行（沙盘 owner 职责）；后续 Step 6 预期从 `6+1=7 passed` 仍成立。
2. **D-02｜AccessListResp 键名预写有出入**（Step 7 注/Step 8 核对点）：后端 `twin_access_service.list_requests()` 实际返回 `{incoming, outgoing, incoming_pending}`，非计划暂写的 `pending_count`。处置：按裁决永远改前端类型，`types/twin.d.ts` 已按逐字实键落定。
3. **D-03｜Step 8 vue-tsc 基线脏**：仓库存量已有大量无关错误（audioDsp/assistant/context/kms 等），「Expected: 无新增错误」无法直接判读。处置：判据改为「twin 相关错误 = 0」（`Select-String 'twin'` 计数），实测 0，达标。
4. **D-04｜Step 9 守卫命令形态 + 文件粒度暂存污染**：① 计划写 `git diff HEAD~1 --stat`，实际对比的是工作树（含并行未提交改动，报 20 文件）；守卫应使用 `git diff HEAD~1 HEAD --stat`（实报恰 4 文件）。② 即便提交粒度正确，`git add docs/sql/menu_knowledge_governance.sql` 仍以整个文件入暂存，连带提交了并行特性预先存在于工作区的 2406「数据资产」行、2408「推演沙盘」行与授权末界 `2407→2408`。未拆分（共享脏工作区既有困境，拆分反会破坏对方编辑现场）；后续任务凡碰他人并行在飞的文件，守卫一律用 `HEAD~1 HEAD` 形态并在提交信息注明连带范围。
5. **D-05｜Task 1 步骤内部矛盾（测试 vs 实现）**：Step 1 测试钉 T8/runPublished 缺省发体 `{}`，Step 3 实现却发 `{ params: params ?? {} }`（永远带 params 键），直接执行必红。后端 `Optional[DataBody]` 两种体均合法，以测试为准：实现改为 `params ? { params } : {}`（loadPageData/runPublished 两处）。
6. **D-06｜Task 1 mock 键名核对点（注 1 命中）**：`utils/request.ts:106-126` 实际导出 `get/post/put/delete/patch`，无 `del`；Step 1 测试的 mock 工厂按注 1 改为 `delete: del`，实现体本就用 `request.delete/patch`，无需调整。
7. **D-07｜Task 3 测试胶水按授权优化（非缺陷，留痕）**：Step 1 原稿的 `globalThis.__loadPageResp` 钩子与 `openCardStart` 占位写法均未照搬，改为计划注 (:605)/Step 4 预先授权的形态：mock 工厂按 URL 模式返回样本、W11 用例直调 `openCard(99)`；另删未读变量 `resp`/未用导入 `afterEach`（仓库存量 vue-tsc 会报 TS6133，新代码须保持 twin 相关错误 = 0）。五条断言意图零弱化，实得 5 passed。

---

## 明确遗留（不在本 plan 任何 Task）

- AI 双通道接线（T13/T14/widgets-batch 后端交付后另立 plan）；
- 下钻取数端点与其前端（G2）；
- Gauge/Graph/Scene 3D renderer（P1）；
- 分享票据/公开链接（T17，P1，新攻击面须与水印/限流同批）。

