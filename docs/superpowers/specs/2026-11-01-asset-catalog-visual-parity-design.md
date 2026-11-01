# 数据资产目录 · 全视觉对齐原型 · 设计规格

> 状态：已批准（brainstorming 收敛）
> 关联：`docs/superpowers/specs/2026-10-31-ontology-capability-design.md`（§4.7 §6.5）·
> `docs/superpowers/plans/2026-11-01-asset-catalog-alignment.md`（AF-01~AF-08 一期，已执行完毕）·
> 目标原型：`docs/prototypes/ontology-asset-catalog-preview.html`
> 裁决沿用：`external_type` 物化列（Q1=B）；可见性引擎（§10 Q1 裁决 A）本期仍不做。

## 0. 目标与范围

把 `/admin/data-asset`（`AssetPickerPanel` 及其子组件 + 后端 `search`/`tree`）的**交互与视觉形态**逐项对齐到原型 `ontology-asset-catalog-preview.html`，覆盖 AF-01~AF-08 全部能力点。范围档位 = **全视觉奇偶对齐**（含右侧「送数预览」契约 dock、送数后跳转构建页、树分组徽标/计数药丸、卡片标签 chip 点击筛选）。

一期计划已落地的能力（探活三态、编辑弹窗、批量打标/探活/重分级、跨源拦截、draft_scope 回显、三段得分徽章、排序/类型下拉、状态点）为本次基线，不重做。

### 0.1 已锁定的三项取舍
- **AF-05 PII 红字依据**：后端权威 `meta_column.pii_level`，`pii ∈ {L2,L3}` 的列标红（与卡片右上 PII 徽章同源）；不复刻原型关键词启发式正则。
- **送数后行为**：`送入本体建模` 成功 → 跳转本体工作台构建页签（`OntologyWorkspace` 读 route query 预选本体 + 切 build）。
- **Dock 控件归属**：目标本体下拉移入右侧 dock；底部 send bar 保留 计数/打标签/批量探活/重新分级/清空/送入。

### 0.2 两项默认（可后被否决）
- dock 中 `status=stopped` 的本体项**禁用并标注**（产品安全）；`ONTOLOGY_STOPPED` 仍由后端兜底拦截。
- CJK「检索降级」**只出徽标**，不每次搜索弹 toast（降噪）。

## 1. 现状核对结论（AF × 落地态）

| 能力 | 判定 | 缺口 |
|---|---|---|
| AF-01 分组树 | 基本对齐 | 缺分组字母徽标（RL/TS…）+ 计数药丸（现内联 `[n]`） |
| AF-02 检索+三段打分 | 基本对齐 | 缺 CJK「检索降级」徽标 |
| AF-03 标签体系 | 基本对齐 | 卡片 tag chip 不可点→按标签筛选（现只读 `a-tag`） |
| AF-05 字段内联摘要 | **实质缺口** | 现扁平 `column_digest` 整串；缺逐列结构化渲染 + PII 红字 + 摘要内关键词高亮 |
| AF-06 卡片操作 | 对齐 | 无（可见性按裁决 A 正确不做） |
| AF-07 分页 | 部分 | 缺「前往 N 页」quick-jumper + 富化总数文案 |
| AF-08 勾选送数 | 部分 | 缺右侧契约 dock；本体下拉未显示状态/未禁用 stopped；未跳转构建页 |

## 2. 后端契约变更

文件：`backend/app/services/ontology/ontology_asset_service.py`

### 2.1 `_card(t, score, q)` — 增结构化列
- **复用**现第 147–155 行已加载的 `cols`（原本仅拼 `column_digest`），新增：
  ```python
  "columns": [
      {"name": c.column_name, "type": c.data_type or "",
       "comment": (c.column_comment or c.biz_name or ""), "pii": c.pii_level or "L0"}
      for c in cols
  ]
  ```
- 保留 `column_digest`（扁平串）：向后兼容 + 前端 `columns` 为空时回退 + title tooltip。
- 不新增 SQL；`_COLUMN_DIGEST_LIMIT` 上限不变。
- `pii_max_level`（现有 `func.max`）保持不变，与逐列 `pii` 同源。

### 2.2 `_tags_for(table_id)` — 增 `id`
- select 增 `MetaAssetTag.id`；返回 `{"id","code","name","color"}`。供 AF-03 chip 点击按 `tag.id` 回填筛选。

### 2.3 路由/参数
- `GET /assets/search`、`GET /assets/tree` 请求签名不变；仅响应卡片体增加 `columns` 与 `tags[].id`。
- docstring 更新（说明卡片含逐列结构化摘要）。

### 2.4 边界与错误
- 无新增错误码。送数侧 `ONTOLOGY_STOPPED` / `DRAFT_SCOPE_EMPTY` / `BUILD_SCOPE_SINGLE_SOURCE` 沿用现有实现。

## 3. 前端组件架构

### 3.1 布局：2 栏 → 3 栏（`AssetPickerPanel.vue`）
- `asset-picker__body` 由 `tree｜main` 扩展为 `tree｜main｜dock(372px)` grid。
- 响应式：`@media (max-width:1420px)` 隐藏 dock（复刻原型）；`max-width:1020px` 隐树（沿用原型口径可选）。
- 目标本体 `a-select` 从底部 send bar 移入 dock；send bar 保留 计数 + 打标签/批量探活/重新分级/清空/送入本体建模。

### 3.2 新组件 `AssetSendDock.vue`
- Props：`selected: any[]`、`targetId`（`v-model`）、`ontologies`/`ontOptions`（带 `status`/`current_version`）、`loadingOnt`。
- 渲染：
  1. 标题「送数预览」+「契约实时对齐 §6.5」徽标。
  2. 目标本体下拉：option label = `name` + `status` 标签（`statusColor`）+ `v{current_version}`；`stopped` 项 `disabled` + 标注「已停止」。
  3. 实时请求体 JSON 预览（`<pre class="json">`，着色由 `formatPayloadJson`）。
  4. 静态「相关度得分规则」：3=表名/库名/表注释，2=字段名，1=仅字段注释；同分按 table_name 字典序。
  5. 静态「关键约束」列表（不写结构表 / 跨源 BUILD_SCOPE_SINGLE_SOURCE / 空清单 DRAFT_SCOPE_EMPTY / 幂等键含解析后 tables / asset_id 故意不建外键 / 强制 page-size 默认50上限200）。
- 无独立网络：全部读父级传入的 `selected` + 共享 `targetId`。

### 3.3 单一数据源：payload 构造（`assetSend.ts` 新纯函数）
- `buildSendPreviewPayload(selected, targetId, meta)` → 与 `doSend` **完全同构**的请求体：
  ```ts
  { mode:'tables', source_id, db_name, database, tables: [table_name...], tag_ids:[], catalog_ids:[], origin:'asset_picker' }
  ```
  - 空选择 → `tables: []`（预览显示空态；doSend 侧仍被 `DRAFT_SCOPE_EMPTY` 兜底）。
- `doSend` 改为调用同一函数（消除 dock 预览与实际发送的漂移）。
- `formatPayloadJson(obj)`：移植原型 `jsonColor`，输出已转义 + key/string/number 着色的 HTML 串（供 `v-html`）。

### 3.4 卡片（`AssetCardList.vue` + `assetText.ts`）
- **摘要逐列渲染**（AF-05）：`columns` 非空时按原型 `dg` 口径渲染
  `名 类型 COMMENT '注'`，`· ` 分隔；`hl(name,kw)` / `hl(comment,kw)` 高亮；`col.pii ∈ {L2,L3}` → 红字（`.cc-pii`）。折叠/渐隐展开沿用现 `.exp`。`columns` 空 → 回落 `column_digest`。
  - 新纯函数 `renderColumnDigest(cols, kw)`（`assetText.ts`，移植原型，含 PII 着色 + 高亮 + 转义）。
- **标签 chip 可点**（AF-03）：`a-tag` → 可点 chip（携带 `tg.id`），`emit('filter-tag', tg.id)`；父级把该 tag 并入检索条 `tag_ids` 并重查。
- **分页**（AF-07）：`a-pagination` 增 `show-quick-jumper`；`show-total` 改 `共 N 条 / Y 页 · size Z`（`Y=Math.ceil(total/size)`）。**不加** `show-size-changer`。

### 3.5 检索条降级徽标（`AssetSearchBar.vue` + `assetSearch.ts`）
- 新纯函数 `isCjkQuery(kw)`（`/[\u4e00-\u9fa5]/`）。
- `kw` 命中 CJK 时，bar 内实时渲染 `<a-tag color="orange">检索降级</a-tag>`（title 提示：走 `LIKE '%kw%' + gin_trgm_ops`，未用 `similarity()`）。纯前端，不改后端。

### 3.6 树分组徽标 + 计数药丸（`AssetTypeTree.vue` + `assetTree.ts`）
- `buildAssetTree` 节点输出增字段：`label`（纯名）、`count`（数值）、`badge`（组字母码）；组节点渲染 `.ic` 徽标 + `label（count）`，源节点渲染 `dotk` 状态点 + `label` + `.cnt` 药丸（替代内联 `[n]`）。
- 新纯函数 `groupBadge(code)`：`rdbms→RL, tsdb→TS, warehouse→WH, graph→GR, kv→KV, vector→VC, search→SE, file→FS, saas→AP`；未知码回落取前两位大写。
- 状态点 `.dotk`（已实现）保留；空组「暂无连接」占位保留。

### 3.7 送数后跳转构建页（`OntologyWorkspace.vue`）
- `doSend` 成功（`putDraftScope` 200）→ `router.push({ path:'/admin', query:{ tab:'kg-ontology', ontology:String(targetId), ot:'build' } })`。
- `OntologyWorkspace`：`onMounted` + `watch(() => route.query)`：
  - `query.ontology` → 载入后设 `currentId = Number(query.ontology)`；
  - `query.ot`（如 `build`）→ 设 `tab = query.ot`（仅当匹配现有 tab key）。
- 跳转后仍执行既有清空/成功提示；跳转放在成功分支 `finally` 前。

### 3.8 i18n
- 新短语经 `t2`：送数预览 / 契约实时对齐 / 目标本体 / 相关度得分规则 / 关键约束 / 前往 / 页 / 共 / 条 / 检索降级 / 已停止 / 构建 / 送入本体建模 → 补 `ontologyLocale.ts` en/ja 映射（zh-TW/zh-CN 走既有中文回落）。

## 4. 数据流与契约一致性

- 预览即所发：dock JSON、`doSend` body 均来自 `buildSendPreviewPayload`，同源。
- 跨源约束：`selected` 锁 `source_id`（卡片层拦截不变）；`payload.source_id` 取 `selected[0].source_id`。
- draft_scope 回显：`syncDraftScope`/`applyRestore` 逻辑不变；目标切换仍在 `watch(targetId)`。
- stopped 本体：dock 禁用不可选；若竞态仍发到 stopped，`putDraftScope` 抛 `ONTOLOGY_STOPPED` → 拦截器提示。

## 5. 测试策略

约束：node 测试环境无 `@vue/test-utils` / `jsdom`；沿用「抽纯函数 + `vi.mock ontologyText`（`t2=s=>s`）+ `@vue/server-renderer` `renderToString`」。

### 5.1 后端（`pytest tests/ontology`）
- 扩展资产检索卡片测试：断言 `items[].columns[]` 结构（`name/type/comment/pii`）与 `pii` 对 `L2/L3` 的透传；断言 `tags[].id` 存在。
- 保持一期既有 172 passed/10 skipped 基线不回退。

### 5.2 前端纯函数（新增/扩展 spec）
- `renderColumnDigest`：PII 红字（L2/L3）、关键词 `<mark>` 高亮、`·` 分隔、空列回退、转义。
- `isCjkQuery`：CJK true / ASCII false / 空 false。
- `groupBadge`：9 组映射 + 未知码回落。
- `buildSendPreviewPayload`：同源 `source_id`/`db_name`/`tables`（table_name 集合）、空选择 → `tables:[]`。
- `formatPayloadJson`：着色 HTML + 转义（无注入）。
- `buildAssetTree`（扩展）：`label`/`count`/`badge` 字段与药丸/徽标数据。
- 组件级 `renderToString`：dock 预览 JSON 渲染、卡片摘要着色/高亮冒烟。

### 5.3 回归门槛
- `vitest run src/views/data-source`（含 i18n）全绿；`vue-tsc`（在 `frontend/` 运行）触及文件零错误。

## 6. 触及文件清单（约 13）

后端：
1. `backend/app/services/ontology/ontology_asset_service.py`（`_card` 增 `columns`、`_tags_for` 增 `id`、docstring）
2. `backend/tests/ontology/…`（卡片结构断言）

前端：
3. `frontend/src/views/data-source/asset/AssetSendDock.vue`（**新**）
4. `frontend/src/views/data-source/asset/AssetPickerPanel.vue`（3 栏 + dock 编排 + 跳转 + payload 共用）
5. `frontend/src/views/data-source/asset/AssetCardList.vue`（逐列摘要 + chip 点击 + pager）
6. `frontend/src/views/data-source/asset/AssetSearchBar.vue`（降级徽标）
7. `frontend/src/views/data-source/asset/AssetTypeTree.vue`（徽标 + 药丸）
8. `frontend/src/views/data-source/asset/assetText.ts`（`renderColumnDigest`）
9. `frontend/src/views/data-source/asset/assetSearch.ts`（`isCjkQuery`）
10. `frontend/src/views/data-source/asset/assetTree.ts`（`groupBadge` + label/count/badge）
11. `frontend/src/views/data-source/asset/assetSend.ts`（`buildSendPreviewPayload` + `formatPayloadJson`）
12. `frontend/src/views/data-source/ontology/OntologyWorkspace.vue`（读 query 预选 + 切 build）
13. `frontend/src/i18n/ontologyLocale.ts`（新短语 en/ja）
14. 相关 `__tests__/*.spec.ts`（纯函数扩展）

## 7. 全局约束（不变）

1. 检索禁 `pg_trgm.similarity()`（对 CJK 恒 0），GIN 仅加速 `LIKE`。
2. 送数不写任何结构表，只覆盖 `draft_scope_json`。
3. 一个建模作用域仅单一 `source_id`。
4. 同分排序恒按 `table_name` 字典序（可复现）。
5. `asset_tag_binding.asset_id` 不建外键（重扫连带删人工标签风险）。
6. 清单强制 `page/size`（默认 50，上限 200）。

## 8. 非目标（本期不做）

- 资产可见性开关/引擎（§10 Q1 裁决 A）。
- 卡片操作/标签/探活/编辑的后端新接口（一期已具备，本次仅复用）。
- 树按「标签」根节点的第二套分组（原型仅 external_type 分组 + 连接叶）。
