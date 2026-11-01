# 孪生应用前端（Plan 2 / P0-5·6·9·10）设计规格

> **For agentic workers:** 本文件是 spec（设计真源），配套实施计划由 writing-plans 技能产出于
> `docs/superpowers/plans/2026-11-01-digital-twin-p0-frontend.md`。
> 基准文档三件（冲突时按此优先级裁决）：
> 1. 接口契约真源 = `docs/superpowers/plans/2026-11-01-digital-twin-p0-backend-core.md` 已交付实现（`backend/app/routers/twin/twin.py` 等）；
> 2. 交互/视觉基线 = `docs/superpowers/specs/2026-11-01-digital-twin-app-design.md`（下称"主 spec"）；
> 3. 行为真源 = `docs/prototypes/ontology-digital-twin-preview.html`（下称"原型"）。
> **本 spec 与主 spec 散文不一致处，一律以代码事实为准**（见 §9 订正清单）。

**Goal:** 交付孪生应用 P0 前端：编辑工作区（`/admin/digital-twin`）+ 登录态只读发布页（`/twin-p/:slug`），接通已交付的 T1–T12 / Q1–Q5 端点。

**Architecture:** Vue 3 SFC + Pinia 单 store 状态机 + axios 封装（`@/utils/request`）；编辑/运行共用同一 `WidgetGrid`（唯一画布，`mode` prop 分派）；renderer 是"后端归一形状 → 复用组件 props"的薄适配层。

**Tech Stack:** Vite、Pinia、Ant Design Vue、ECharts（复用既有图表组件）、vitest（node 环境，programmatic runtime，**不新增测试依赖**）。

---

## 0. 已裁决决策（brainstorming 期间逐节确认，共 4 项）

| # | 决策 | 内容 |
|---|---|---|
| D1 | AI 双通道范围 | **前端只做 UI 骨架**。后端未交付 T13/T14/widgets-batch（主 spec §6.1 列为 P0 但后端计划只到 T1–T12），`TwinAiDock.vue` 全部禁用态、不发任何请求、不臆造端点；接线留给后继 plan。 |
| D2 | 菜单入口 | path `/admin/kg-twin` → **`/admin/digital-twin`**，`visible 0 → 1` 现在就点亮。Plan 2 附带修正已提交的 2407 行（见 §2）。 |
| D3 | 挂载方式 | 沿用 sandbox 双挂载先例（AppLayout 子路由 + componentMap Tab）；`/twin-p/:slug` 为顶层路由（仿 `/login`），`requiresAuth + hideHeader`。 |
| D4 | 测试依赖 | **不装** `@vue/test-utils` / `happy-dom` / `jsdom`，沿用 `vitest.config.ts:14-16` 既成的 programmatic Vue runtime 模式。 |

---

## 1. 范围

**In scope（P0）**：主计划任务 P0-5（工作区壳+画布）、P0-6（组件与渲染）、P0-9（发布只读页）、P0-10（权限申请闭环前端面）；菜单 2407 修正；tokens 补缺口；W 系列前端可判定项。

**Out of scope（P1，tree 中留位不实现）**：`GaugeWidget`、`GraphWidget`（GraphCanvas 复用）、`SceneWidget`（3D 等距 SVG）、`EntityPopover`、分享票据/公开链接（T17）、AI 真实接线、下钻取数。

---

## 2. 挂载与路由

| 面 | 值 | 落地点 |
|---|---|---|
| sys_menu 2407 | path `/admin/digital-twin`，visible=1 | `docs/sql/menu_knowledge_governance.sql` + `docs/sql/init.sql`（见 §2.1） |
| componentMap | key `digital-twin`（= 菜单 path 末段，`componentMap.ts:3` 硬约定）→ `markRaw(TwinWorkspace)` | `frontend/src/views/admin/componentMap.ts` 追加 |
| 编辑态路由 | `admin/digital-twin`，AppLayout 子路由，`meta.requiresAdmin`，与 `/admin/simulation`（`router/index.ts:108-113`）同构 | `frontend/src/router/index.ts` 追加 |
| 只读运行态 | `/twin-p/:slug` **顶层路由**（不进 AppLayout、无左导航），`meta:{requiresAuth:true, hideHeader:true}`，未登录先跳 `/login` 回来再进 | 仿 `/login`（`router/index.ts:7-11`）；宿主组件 `TwinPublishedPage.vue` |

### 2.1 菜单修正（唯一触碰已交付后端的项）

- **全新安装**：把两份 SQL 中 2407 VALUES 行的 path 改为 `/admin/digital-twin`、visible 改为 `1`。
- **存量安装**：追加一行幂等
  `UPDATE "public"."sys_menu" SET path='/admin/digital-twin', visible=1, updated_at=now() WHERE id=2407;`
- **测试同步**：`backend/tests/twin/test_menu_sql_twin.py` 的 EXPECTED `(path, visible)`、`test_twin_row_inserts_and_is_idempotent` 回读字典更新，并新增"UPDATE 语句存在"断言。
- **文档订正**：主 spec §2.3 陈旧文本（id 2406→**2407**、path→`/admin/digital-twin`、visible→1）。
- 外科式提交纪律照旧：只 add 本任务行，守卫 grep 不得混入他人 2406 数据资产行。

### 2.2 新增前端文件清单

```
src/types/twin.d.ts                        领域类型 + ApiError + 四态字面量
src/api/twin.ts                            T1–T12 + twin-p（BASE=/api/v1/twins, /api/v1/twin-p）
src/api/twinQuery.ts                       Q1–Q5（BASE=/api/v1/dataops）
src/stores/twin.ts                         Pinia 状态机 + 页面级调度器
src/views/twin/TwinWorkspace.vue           壳：ctxbar + grid(238/1fr/336) + statusbar
src/views/twin/TwinCardList.vue            我的/共享/受限 三组 + 徽标 + 模板中心入口
src/views/twin/PageModuleList.vue          左栏 palette（模块类型，非实例）
src/views/twin/TwinCanvas.vue              中栏容器
src/views/twin/CanvasToolbar.vue           标题/场景tag/编辑·运行段控件/自动布局/添加模块
src/views/twin/WidgetGrid.vue              12 列栅格（唯一画布，mode prop）
src/views/twin/WidgetShell.vue             把手 + 四态（StateWrapper 宿主）
src/views/twin/widgets/KpiWidget.vue       🆕 renderer（无通用 KPI 卡，见 §5.2）
src/views/twin/widgets/TrendWidget.vue     ✅ MultiLineChart
src/views/twin/widgets/BarWidget.vue       ✅ BarChart（单序列）
src/views/twin/widgets/DonutWidget.vue     ✅ PieChart
src/views/twin/widgets/AlertTableWidget.vue ✅ a-table + StatusTag
src/views/twin/overlays/BindDrawer.vue
src/views/twin/overlays/AddModuleModal.vue
src/views/twin/overlays/PublishModal.vue
src/views/twin/overlays/DrillDrawer.vue    UI 外壳 only（§6.5）
src/views/twin/overlays/PermDrawer.vue
src/views/twin/TwinAiDock.vue              UI 骨架，禁用态（D1）
src/views/twin/TwinPublishedPage.vue       /twin-p/:slug 只读壳（复用 WidgetGrid mode=run）
i18n                                       knowledge.menu.twin × 4 locales
tokens.css                                 --cyan/--purple + *-soft（dark+light，§7.2）
```

**禁止**出现 `RunCanvas.vue` 或任何平行运行态画布（主 spec §6.3 承重原则；守卫 grep 恒空，§8.3）。

---

## 3. 数据层：stores/twin.ts

服务器态为真相源；`loading`/dirty 由前端本地驱动。

```
cards: {mine[], shared[], restricted[]}    ← T1 list_cards 三组分派
activeCardId / cardDetail                   ← T3 get_card
pages[] / activePageId                      ← T4
widgets[]（当前页）                          ← T5 list_widgets
pageData: Record<widgetId, WidgetDatum>     ← T8 load_page 一次批量填充
mode: 'edit' | 'run'
scheduler: 页面级 10s（refresh_json 覆盖；档位 10秒/30秒/关闭）
accessRequests: {incoming[], outgoing[], pendingCount}   ← T12
aiDraft: []（占位；无端点时"应用到页面"禁用）
```

`WidgetDatum` **逐字对齐后端 `WidgetItem` 15 键**（`twin_data_service.py:138-145`，订正 C1）：

```ts
interface WidgetDatum {
  widget_id: number; widget_key: string; title: string
  query_id: number | null
  state: 'ok' | 'empty' | 'error' | 'masked'
  reason: 'unbound' | 'zero_rows' | null
  result_shape: 'kpi'|'trend'|'bar'|'donut'|'table'|'entity_set'|'graph' | null
  columns: string[]
  data: Record<string, any>      // 后端已按 shape_result 归一；键是 data，不是 rows
  row_count: number
  truncated: boolean
  masked_fields: string[]
  error: { code: string; message: string } | null
  cached: boolean
  updated_at: string
}
```

**actions ↔ endpoints（逐一，无臆造）**：
`loadCards()`T1 · `createCard/patchCard/deleteCard`T2 · `getCard`T3 · `createFromTemplate`T3 ·
`addPage/patchPage/deletePage/reorderPages`T4 · `listWidgets/addWidget`T5 · `patchWidget`T6（**解绑 = 显式 `query_id: null`**，Body 用 `exclude_unset`，省略字段≠解绑）·
`saveLayout(items[])`T7 · `refreshPage(params?)`T8（**整页仅 1 请求 = W8**；端点永远 200）· `retryWidget`T9 ·
`publish/unpublish`T10（**publish 恒回 200 = 版本推进，不得当新资源插入**）· `loadPublished/runPublished`T11（仍登录态）·
`requestAccess/listRequests/approve/reject`T12 · `listQueries(verified_only)`Q2 · `previewQuery`Q3 · `queryBindings`Q5。

**错误契约**：顶层 `ApiError{code,message,detail}`；twin-p 未知/跨租/停用/角色不命中 → **同一 403 `DENY_MESSAGE`（反枚举），前端不得据差异分支**，统一"无权限"文案。`request` 拦截器已有统一 toast；绑定失败按 code 落 BindDrawer 内联提示。

**W11 前端旁证**：缓存键含角色签名属后端已交付能力；前端**不得自建跨角色结果缓存**——Pinia 切卡/切页即弃 `pageData`，且 `pageData` 禁止写入 localStorage/sessionStorage（守卫 §8.3）。

**调度器**：`mode` 两态都可轮询；档位来自页面 `refresh_json`（10s 默认/30s/关闭）；`document.visibilitychange` 隐藏时暂停、回前台**立即刷一次**（W7）；单组件 ↻ 只走 T9。

---

## 4. api 层

- `api/twin.ts`：照 `api/dataops.ts` 惯例（`import request from '@/utils/request'`、`const BASE`、函数命名 `listCards/createCard(...)`）。两个前缀：`/api/v1/twins`、`/api/v1/twin-p`。
- `api/twinQuery.ts`：BASE `/api/v1/dataops`，Q1–Q5 五函数（`createQuery/listQueries/previewQuery/patchQuery/deleteQuery/queryBindings`；Plan 2 只消费 Q2/Q3/Q5，Q1/Q4 留给查询管理页）。
- 请求/响应体字段**逐字来自 `twin.py`/`ontology.py` 的 Body 模型**（`CardCreateBody`、`WidgetCreateBody`、`WidgetPatchBody`、`LayoutBody{items 1-64}`、`DataBody{params}`、`PublishBody{access,role_codes}`、`AccessRequestBody{reason≤500}`、`ApproveBody{expires_in_days 1-365}`、`QueryCreateBody` 等），不新增、不重命名。

---

## 5. 渲染层：WidgetGrid / WidgetShell / renderer

### 5.1 wire 形状 → 组件 props 的薄适配

后端 `shape_result`（`ontology_query_service.py:99-114`）已完成**语义归一**；"不二次整形"指不重定义语义。组件各有 props 契约，故每 renderer 一个**纯函数适配**（字段转置，可单测）：

| result_shape | 后端 `data` | 组件 | 适配 |
|---|---|---|---|
| kpi | `{value, records}` | 🆕 `KpiWidget` | 直接渲染 value + title |
| trend | `{records, t, values}` | `MultiLineChart(xAxis: string[], series[])` | `xAxis=records.map(r=>r[t])`；`series=values.map(v=>({name:v,data:records.map(r=>r[v])}))` |
| bar | `{records, t, values}` | `BarChart(data:{name,value}[])` | `records.map(r=>({name:r[t], value:r[values[0]}))`（**单序列**，订正 C3） |
| donut | `{records, parts}` | `PieChart(data:{name,value}[])` | `records.map(r=>({name:r[parts[0]], value:r[parts[1]]}))` |
| table | `{records}` | `a-table` | columns+dataSource 透传 |
| entity_set/graph | `{records}` | （P1） | P0 占位卡 |

### 5.2 复用映射订正（代码事实，覆盖主 spec §6.2）

- **C2：`Kpi✅StatsCard` 不成立**。`StatsCard.vue` 是 AI Context 专用卡（`stats: ContextStats`，默认标题 `'AI Context Stats'`），全库无通用 KPI 卡。P0 renderer = **3 复用（Bar/Pie/a-table）+ 2 新建（Kpi、AlertTable 状态列外壳）**。
- **C3：BarChart 只画单序列**（`data:{name,value}[]`、单一 color）；多序列 bar 归 P1，不引 StackedBarChart。

### 5.3 四态映射（`StateWrapper` 只有 3 态：loading/error/empty + retryable/@retry）

- `ok` → 透传 slot，renderer 出图；
- `empty` → `empty=true`，文案按 `reason` 分支：`unbound`→"未绑定查询"（编辑态给绑定 CTA）、`zero_rows`→"查询结果为空"；
- `error` → `error = `${error.code}: ${error.message}``（W6 码+人话），`retryable=true`，`@retry`→T9；
- `masked` → **不进 StateWrapper**，数据照常渲染，renderer 按 `masked_fields[]` 在对应**值位**叠 🔒（主 spec §6.4）；误把 masked 当 empty/error 显示即违反验收。

### 5.4 mode 契约（编辑/运行唯一差异）

`WidgetGrid/WidgetShell` 为编辑页与 `TwinPublishedPage` 共用，宿主只传 `mode` + `pageData`：
- 把手显隐**只用 CSS 类**（原型:125 `body.run .edit-only{display:none}`；原型:163 `body.edit .wops{display:flex}`），不在组件内 `v-if` 分叉取数/渲染逻辑；
- `mode` 只影响：`.wops` 把手层是否渲染、双击是否开 BindDrawer/Drill；取数路径、renderer、四态逻辑两态完全相同；
- `WidgetGrid` 绝不感知数据来源（T8/T11 由外层壳注入）。

布局：`grid_json` → CSS Grid `grid-column: span N`（12 列）。

---

## 6. Overlays 与 AI dock（逐一对齐真实端点）

### 6.1 BindDrawer
Q2 `list_queries(verified_only=true, shape=<当前壳形状>)` 列表 → Q3 `preview` 预览 → T6 patch 写回 `{query_id, param_values_json}`；**解绑必须显式带 `query_id: null` 键**。shape 不配对时展示服务端拒绝原因（W9 的后端拒绝在前端 error 面落地）。

### 6.2 PublishModal
T10 publish：`PublishBody{access:'org'|'role', role_codes}`（access=role 时 role_codes 非空必填）；成功回 **200**，就地更新 slug/version 展示，复制只读链接 `/twin-p/{slug}`；unpublish：`DELETE /publish/{id}`，提示"链接立即拒绝但版本史保留、slug 不回收"。

### 6.3 PermDrawer（双面）
- 申请侧（🔒 受限卡）：T12 `POST /cards/{id}/access-request`，`reason ≤ 500` 前端限幅；回 201。受限卡取数被 `_assert_readable` 堵（403 `TWIN_ACCESS_REQUIRED`），PermDrawer 是唯一正当入口。
- 审批侧（owner）：`GET /access-requests`（incoming/outgoing + pendingCount 徽标）；approve 带 `expires_in_days`（1–365 控件限幅）；reject 无 Body。
- 进入受限卡自动弹 PermDrawer（W5）。

### 6.4 AddModuleModal
T5 `POST /pages/{id}/widgets`（`WidgetCreateBody` 七字段整包提交；`grid_json/display_json` 前端组装；`query_id` 可空→未绑定空壳）。

### 6.5 DrillDrawer —— ⚠️ 后端无数据源，P0 仅 UI 外壳
T1–T12 无 drill 端点；T9 只读已存实值不收 `params`。**不接数据、不承诺下钻行为**；真实下钻需后端补"带 params 的组件取数"端点（与 AI 端点同列后补项）。

### 6.6 TwinAiDock —— 仅 UI 骨架（D1）
镜像 `OntAssistantDock.vue` 布局（输入框/指令 chips/候选预览/"应用到页面"按钮），**全部禁用 + "AI 能力即将上线"提示，不发任何请求**。预留 `:disabled/:pending` prop，端点到位后只接线不改结构。即便未来接线：AI 永不落库，应用动作仍走 §6.1/§6.4 既有写端点。

overlay 开关态与目标 id 归 `stores/twin.ts`；表单草稿等临时态留组件本地。

---

## 7. 视觉基线与 tokens

### 7.1 已实存、直接复用（数值以 `tokens.css` 为准）
`--accent #4aa3ff / --accent-hover #7fd0ff / --accent-soft`（:81-83）、`--ok #4cc38a`（:87，订正 C4：主 spec §6.5 散文 `#4cc98a` 为笔误，W2 表格本就写 38a）、`--warn #f2b66d`（:89）、`--err #ff7b72`（:91）、圆角 14/10（:31-32）、过渡 `200ms cubic-bezier(.4,0,.2,1)`（:38）。

### 7.2 缺口补齐（R9：只新增、不改既有行；dark+light 双块）

| 新 token | dark（原型逐字） | light（降饱和同色相） | soft（照相邻家族惯例 .12/.08） |
|---|---|---|---|
| `--cyan` | `#39d3c4` | `#0d9488` | `rgba(57,211,196,.12)` / `rgba(13,148,136,.08)` |
| `--purple` | `#b48ef0` | `#7c3aed` | `rgba(180,142,240,.12)` / `rgba(124,58,237,.08)` |

插入位置：dark 块 `--info-soft`（:94）后、light 块（:154）后。

### 7.3 显式裁决：与 `--neon-cyan` 的语义重叠
`tokens.css:40-48` 既有设计**故意**把 HUD 装饰层的"cyan"吸收为蓝（`--neon-cyan:#4aa3ff`，注释"never introduces a new colour"）。**不动** `--neon-*`（改动波及全站）；新增 `--cyan/--purple` 是有意引入原型色相，**边界 = 仅 twin 模块消费**。此为记录在案的例外。

### 7.4 尺寸基线
top 52 / ctxbar 42 / 三栏 `238px 1fr 336px` / statusbar 30 —— **不进全局 tokens**，以 `TwinWorkspace.vue` scoped 局部自定义属性（`--twin-top: 52px` 等）存放。3D 几何常量（`iso()`、viewBox 900×460）随 P1 Scene renderer 局部存放，本 plan 不实现。

---

## 8. 验收映射与测试策略

### 8.1 W1–W16 前端可判定归属

| W | 归属 | 判定方式 |
|---|---|---|
| W1 | 前端 | 浏览器验收清单：1280×800 无横向滚动；尺寸源 §7.4 |
| W2 | 前端 | 自动化守卫：twin 业务样式无裸 hex；`--cyan/--purple` dark+light 实存 |
| W3 | 前端 | programmatic runtime：`mode='run'` 无把手节点；`RunCanvas` 守卫 grep 恒空；浏览器：切运行后轮询仍可用 |
| W4 | 前端 | store 单测：切页触发一次 load_page + 骨架；「＋」仅编辑态 |
| W5 | 前端 | 单测：restricted 卡进入自动弹 PermDrawer；三态徽标 |
| W6 | 前端 | 纯函数单测主场：四态→渲染分支，error 回显 `code: message`，masked 值位 🔒 |
| W7 | 前端 | fake timers：档位生效；visibilitychange 暂停 + 回前台立即刷（调用计数） |
| W8 | 前端 | mock request：整页刷新 `POST pages/{id}/data` 调用计数 = 1 |
| W9 | 后端已闭环 | 前端仅展示拒绝原因（BindDrawer 内联） |
| W10 | 后端已闭环 | detail 透传约定，无独立前端判定面 |
| W11 | 后端为主 | 前端旁证：切卡即弃 + 无持久化守卫；双角色交替真测进浏览器联调清单 |
| W12 | 前端 | 路由单测：twin-p 不套 AppLayout、mode='run'、403 统一文案；审计属后端 |
| W13 | 前端 | store 流程单测：申请(201)→approve(限幅)→列表转入含过期时间 |
| W14 | **Plan 2 不可判** | D1：只交禁用骨架；完整判据挂账至 AI 端点后继 plan（部分验收，记录于 §9） |
| W15 | 后端 | 已交付；前端无判定面 |
| W16 | 文档 | Plan 2 关账：§2.1 菜单文本 + 主 spec §6.2/§6.5 订正（C2/C3/C4）+ Drill/AI 缺口标注 |

### 8.2 测试分层（D4：不新增依赖）
1. **纯函数层（主力）**：renderer 适配（§5.1）、四态映射（§5.3）、grid→样式映射——node 环境直测；
2. **store 层**：Pinia + `vi.mock('@/utils/request')`，W4/W7/W8/W13 调用计数与时序（fake timers）；
3. **组件层**：programmatic runtime（createApp + h()），W3 类名/节点存在性；
4. **浏览器验收清单**（plan 末任务）：W1/W3 连续性/W7 Network/W11 双角色联调。

### 8.3 守卫 grep（进 plan 验证步骤，恒空）
- `git grep -l "RunCanvas" frontend/src`；
- twin 业务样式内裸 hex（W2）；
- twin store 对 `pageData` 的 localStorage/sessionStorage 持久化（W11）；
- `api/twin*.ts` 端点字面量 ⊆ T1–T12 + Q1–Q5 真实路由表（防臆造接口回归）。

---

## 9. 订正与缺口清单（对主 spec / 后端交付的账）

| # | 类型 | 内容 | 处置 |
|---|---|---|---|
| C1 | 本 spec 内订正 | Section 2 曾写 `pageData{rows,...}`；真实为 `data` + `row_count/reason/error/cached/truncated` 15 键 | §3 已按代码逐字落定 |
| C2 | 主 spec §6.2 订正 | `Kpi✅StatsCard` 映射不成立（域专用卡） | 实施时改主 spec 一行 + 本 spec §5.2 |
| C3 | 主 spec §6.2 订正 | bar 复用暗含多序列能力，实际 BarChart 单序列 | P0 单序列，多序列归 P1 |
| C4 | 主 spec §6.5 订正 | 散文 `#4cc98a` 笔误（代码与 W2 表格均为 `#4cc38a`） | 以代码为准，主 spec 改一字 |
| C5 | 主 spec §2.3 订正 | 2406→2407、path→digital-twin、visible→1 | §2.1 |
| G1 | 缺口（后端） | T13/T14/widgets-batch 未交付（主 spec §6.1 列 P0） | D1 挂账；W14 部分验收 |
| G2 | 缺口（后端） | 无下钻取数端点（T9 不收 params） | DrillDrawer 仅骨架（§6.5） |
