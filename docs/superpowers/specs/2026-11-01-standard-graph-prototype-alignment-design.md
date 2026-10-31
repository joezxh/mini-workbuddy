# 标准中心关系图对齐图谱知识库原型 设计

- 日期：2026-11-01
- 状态：已与用户逐节确认（分色维度 / 渲染方案 / 对齐边界 / NL 命中语义 / 筛选与导出口径 五项决策已裁决）
- 参考原型：`docs/prototypes/kg-knowledge-base-preview.html`（图谱 Tab 的画布与检视面板）
- 原型真实实现：`frontend/src/views/kms/kg/KgGraphView.vue` + `KgInspector.vue` + `kg-tokens.css` + `kgTheme.ts`
- 关联：标准三层语义模型 CDM spec（2026-10-28，其决策 7 被本 spec 取代）、图谱知识库 spec（2026-10-30）

---

## 1. 背景与目标

### 1.1 现状

标准中心的「标准图」页签（`StandardManagement.vue` 的 `graph` Tab）由三个组件承担：

| 组件 | 现状 |
|---|---|
| `standard/StdGraphView.vue` | ECharts 5 `graph` series + 力导向 + tooltip；节点统一色，仅 NL 命中时放大到 64 并加金色描边，命中边加粗到 3；无边颜色语义、无图例、无邻接淡化 |
| `standard/StdInspector.vue` | antd `a-descriptions` + `a-divider` + `a-list`；对象形态给定义/属性/绑定表，关系形态给定义/校验结论 |
| `StandardManagement.vue` | 图区上方只有 `[关系图 | 总览]` 分段 + 新建关系 + 刷新；无筛选、无导出 |

图谱知识库（type=4）一侧已经有一份与原型的**像素级真实实现**：`KgGraphView.vue` 用原生 SVG + Fruchterman-Reingold 静态力导向，节点按实体类型分色、半径随度数、二次贝塞尔边 + 边标签、点选后 1 跳邻居保留其余淡化、左下图例 + 右上提示胶囊 + 点阵底纹；`KgInspector.vue` 用 `kg-kv / kg-sec-t / kg-kvlist / kg-mini / kg-badge / kg-type-tag` 结构，邻接关系行可点击下钻到边。

后端 `StandardQueryService.graph()` 的返回结构当初就是刻意与 kg 侧对齐的（`kg_service.py:547` 注释：「字段与标准中心 `graph()` 对齐……因此前端图组件可与标准中心共用同一套渲染代码」），但前端最终各写了一套，共用意图没有兑现。

### 1.2 目标

1. 标准图的绘制与交互**严格对齐原型**：多色实体背景 + 图例、选中关系线高亮、选中邻接聚焦淡化、右侧详情按原型的显示方式与功能点。
2. 兑现「共用一套渲染代码」：**新增共享画布层**，`kg` 与 `standard` 两个模块都消费它，不留两份渲染实现。
3. 标准图页签补齐原型工具栏能力：对象筛选、关系基数筛选、节点上限、种子子图扩展、导出，**全部前端计算，零后端改动**。

### 1.3 非目标（YAGNI 明确剔除）

- 不给标准图编造原型有而标准中心无的数据：提及数、向量状态、归一化名、权重条、抽取器、抽取依据一律不上面板。
- 不做「隐藏 Chunk 节点」：标准中心不存在切片节点。
- 不做「按类型过滤」档位（见 §6.1 说明）。
- 不改后端模型 / 服务 / 路由 / 迁移；不改左侧目录树、对象表、属性表、绑定表四个页签的既有行为。
- 不改总览视图（`StdOverviewView.vue`）的结构与文案，只保留它向图视图投喂命中码的既有链路。
- 不做图节点标签的逐帧动画或实时物理模拟（与 kg 侧一致：静态一次算完）。

---

## 2. 决策与取代（ADR）

**决策**：标准中心关系图的渲染栈由 **ECharts `graph` series** 改为**原生 SVG 共享画布**。

- **取代**：本 spec 取代 `2026-10-28-standard-cdm-graph-ui-design.md` §11 决策 7 中的「图库 = ECharts graph」，以及 §7 组件树里 `StdGraphView.vue` 的「ECharts graph 力导向」描述。旧 spec 的其余决策（三层 CDM、目录可空、冲突判定收敛等）继续有效。
- **理由**：① 原型（及其已上线实现）的分色 + 度数半径 + 贝塞尔曲率 + 双行标签光晕 + 点选邻接淡化，在 ECharts 上只能逐项逼近，无法「严格对齐」；② 两个模块共用一套渲染代码后，画布缺陷一次修复、视觉天然一致；③ 标准页签本来就要为总览加载 echarts，去掉 graph chart 可少一份图表体积。
- **被否决的替代方案**：(a) 在 `StdGraphView` 内复制一份 SVG 渲染——零跨模块风险，但留下约 400 行重复代码且违背后端注释里的既定意图；(b) 继续用 ECharts 的 `categories` + `blur` + `legend` 仿样式——改动面最小，但边命中、邻接淡化、标签排版的手感差异明显，不满足「严格对齐」。
- **代价与边界**：要重构已上线且**当前无任何自动化测试**的 `KgGraphView.vue`（779 行）。控制手段是把抽取限制在「纯呈现 + 交互」层，数据获取、筛选、导出、检视联动留在原组件，并用 §10 手工回归清单逐项验证不劣化；同时为新的共享层补上缺失的测试（§9.3）。

---

## 3. 共享图谱层（新增边界）

新目录 `frontend/src/components/common/graph/`：

```
components/common/graph/
├─ GraphCanvas.vue      画布：布局 + SVG + 缩放/平移/拖拽 + 点选 + 邻接淡化 + 图例 + 空态
├─ graphTheme.ts        由 views/kms/kg/kgTheme.ts 迁移（同内容，改位置）
└─ graph-tokens.css     由 views/kms/kg/kg-tokens.css 迁移（同内容，改位置 + 头部注释）
```

### 3.1 `GraphCanvas.vue` 接口

只负责呈现与交互，**不含任何 i18n key、不发请求、不做筛选**（文案与数据都由调用方注入，避免 `components/common` 反向依赖 `views/kms`）。

```ts
interface CanvasNode { id: number; name: string; code: string; color: string; typeLabel: string }
interface CanvasEdge { id: number; from: number; to: number; label: string }
interface Selection { kind: 'node' | 'edge'; id: number }

props: {
  nodes: CanvasNode[]
  edges: CanvasEdge[]
  selection: Selection | null
  /** NL/关键字命中集（对象 code / 关系 code）：无选中时作为焦点集 */
  focusNodeCodes?: string[]
  focusEdgeCodes?: string[]
  loading?: boolean
  /** 文案注入（调用方用自己的 i18n 命名空间） */
  hintText: string
  legendSizeText: string
  emptyText: string
}
emits: { (e: 'select', v: Selection | null): void }
expose: { locate(id: number): void }   // 选中 + 平移使该节点进入视野中心
```

从 `KgGraphView` 原样搬入的部分（常量与算法不改值）：`VB_W/VB_H = 790/490`、`MIN/MAX_SCALE`、`LABEL_ALL_MAX = 60`、黄金角撒点 + FR 斥力/引力/向心力 + 位移限幅 + 归一化留白、`r = min(52, 15 + deg * 4.2)`、曲率 0.12 的二次贝塞尔与 `0.25/0.5/0.25` 标签锚点、hover 命中测试、`nodeOpacity`、`showNodeLabel` / `showEdgeLabel`、图例聚合（按节点数降序）、空态与 loading 遮罩。

**焦点判定规则**（写进 canvas，一处生效）：

1. `selection` 非空 → 以选中项为焦点：选中节点的 1 跳邻居保留、其余 `opacity .35`；与该节点相邻的边转 primary 并加粗，命中边本身 `is-on`（标签变蓝加粗）。
2. `selection` 为空但命中集非空 → 以命中集为焦点：命中节点保留并加 `is-hit`（primary 描边），命中边加粗，**其余节点同样淡化 `.35`**。
3. 两者皆空 → 全亮。

`kg` 侧调用后行为不变（它从不传 `focus*`），标准侧因此零特化分支。

### 3.2 `graphTheme.ts` 迁移

`views/kms/kg/kgTheme.ts` 移到 `components/common/graph/graphTheme.ts`，同步改 6 个引用点：`KgGraphView.vue`、`KgInspector.vue`、`KgOverview.vue`、`KgEntityTable.vue`、`KgTripleTable.vue`、`KgProvenance.vue`。不留 `views/kms/kg/kgTheme.ts` 转发壳（避免两套入口）。

标准侧取色规则：`color = typeTone(node.code).color`，`typeLabel = typeLabel(node.code)`。`typeTone` 对未登记 code 按哈希落进同一 5 色板，已登记 CDM 码走语义色——与图谱知识库同码同色。

### 3.3 `graph-tokens.css` 迁移与作用域

文件移到 `components/common/graph/graph-tokens.css`，`KbGraphPane.vue` 的 `<style src>` 路径随之更新。**作用域类名保留 `.kb-graph-pane`**：文件里 100+ 条 `.kb-graph-pane …` 选择器逐条改写（或改 `:is()`）带来的 diff 噪声与回归风险，远大于名字收益。文件头注释补一行说明它是「图谱工作台共用皮肤作用域，标准中心图区亦复用」。

标准中心图区在 `graphView === 'graph'` 时，把 `kb-graph-pane` 类挂到**只包住工具栏 + 画布 + 检视面板**的外层容器（即现有 `.std-mgr__graph-body` 的新父级），**总览视图不挂**——总览的 antd 卡片/统计/表格保持现有主题，避免皮肤越界。

### 3.4 `KgGraphView.vue` 瘦身后保留的内容

工具栏（模式分段 / 实体类型 / 关系类型 / 跳数 / 节点上限 / 隐藏 Chunk）、`/graph/full` 与 `/graph/subgraph` 取数与悬空边过滤、facets（`getLabels` / `getGraphStats`）、种子扩展、导出 Blob、`KgInspector` 联动、`defineExpose` 的三个入口方法。视觉与交互必须逐项不变（§10）。

---

## 4. 标准图画布（`StdGraphView.vue` 重写）

组件从「ECharts option 计算器」改为「画布装配器」：把 `nodes/edges` 映射成 `CanvasNode/CanvasEdge`，把筛选/子图/截断逻辑（§6）套在数据上，渲染交给 `GraphCanvas`。

- **依赖**：删除 `vue-echarts` / `echarts/core` / `GraphChart` / `CanvasRenderer` / `TooltipComponent` 引用与 tooltip 配置（原型无 tooltip，详情走点选）。
- **节点**：填充色 = 对象标准 code 分色；白色 2px 描边、悬停 3px、选中 3.5px（继承 tokens）；半径随度数；下方双行标签——第一行对象名，第二行 code 去 `obj_` 前缀的显示名（着色同色），带白描边光晕。
- **边标签 = 关系标准 `name`**（如「订单属客户」），缺失时回落 `code`。理由：原型的边标签是**语义类型**，而标准中心的 `relation_type` 是基数（`1:1|1:N|N:1|N:N`），把基数画在边上等于丢掉语义；基数改在检视面板的关系形态里给出。
- **图例**：左下角只列当前可见的 code（按对象数降序）+ 「节点大小 = 度数」；右上角「在图上点选对象或关系查看详情」胶囊。
- **画布底**：点阵底纹 + 白卡（tokens 提供）。
- **选中联动**：`selected` 由 `StandardManagement` 持有并经 props 下发（现有 `selected` ref 直接复用，`onNodeClick/onEdgeClick` 收敛为 `@select` 单一入口，点空白 = `null` 取消选中）。
- **NL 命中**：沿用 `highlightCodes` / `highlightRelationCodes` 两个 prop，转发为 `focusNodeCodes` / `focusEdgeCodes`；生效规则见 §3.1 焦点判定第 2 条。用户一旦点选图上对象，切回邻接语义；清空检索（命中集置空）恢复全亮。

## 5. 检视面板（`StdInspector.vue` 重写）

换成原型的 `.insp` 形态（标题条 + `kg-kv` + `kg-sec-t` 分区 + `kg-kvlist` + `kg-mini` + `kg-badge` + `kg-type-tag`），数据源与请求保持现状不变：对象详情 `getObject(id)`、绑定表 `listObjectBindings(id)`、校验结论 `listRelationChecks(id)`，对象/关系基础字段仍从父级 `objects/relations` 池取。

**5.1 对象形态**

- 标题：对象名 + 右侧「编辑」（保留现有 `edit-object` 事件；对象删除继续在对象表页签做，不进面板）。
- `kg-kv`：名称（strong）/ 类型（按 code 上色的 `kg-type-tag` + code 小字）/ 主题域 `domain`（空→`—`）/ 别名（tag 列表，空→`—`）/ 状态（`kg-badge`：`draft`→待发布 warn、`published`→已发布 ok）/ 说明。
- 分区「引用属性」：`kg-kvlist` 行 = 属性名 + `code` 小字，右侧 badge 给必填与密级（沿用现有 `required` / `security_level` 语义）。
- 分区「邻接关系（N）」（**新增功能点**）：从 `props.relations` 全量里按 `from_object_id / to_object_id` 取本对象相关的关系标准，行 = 关系名 tag + 方向箭头（`→` 本对象为源、`←` 本对象为目标）+ 对端对象名 + 基数；点击 = 选中该边并联动图上高亮。取全量而非可见边集：详情反映标准本身，不受视图筛选影响。
- 分区「已绑定物理表」：保留，行换成 `kg-mini`，逐行「下钻」继续 `drill-down` 上抛。
- 分区「操作」：「在图中定位」→ 调 canvas `locate(id)`（若该对象因筛选不可见，先清空筛选再定位）。

**5.2 关系形态**

- 标题：关系名 + 右侧「编辑」「删除」（保留 `edit-relation` / `delete-relation`）。
- `kg-kv`：源对象 / 目标对象（两者均为可点击链接 → 切到对象形态）/ 关系名（`kg-type-tag--rel`）/ code / 关系类型（基数原文）/ 状态 badge / 说明。
- 分区「校验结论」：`kg-kvlist` 行 = `source_id / database` + verdict badge（`hit`→ok、`conflict`→warn、`missing`→err）+ 置信度百分比；无记录时给现有「暂无校验记录」空态。
- 分区「操作」：「在图中定位」（定位到源对象）。

## 6. 标准图工具栏（全部前端计算）

位置：`StandardManagement.vue` 图区上方，与现有 `[关系图 | 总览]` 分段同排；`graphView === 'graph'` 才显示。数据全部来自已加载的 `graph.nodes/edges`（`/standards/graph` 一次返回整个目录子树），**无新增后端参数**。

| 能力 | 实现 |
|---|---|
| 模式分段 | `全图` / `子图`（种子 = 当前选中对象 + 跳数 1–3） |
| 对象筛选 | 下拉：当前可见对象标准 `code`（带计数），选中后只画该对象 + 其 1 跳邻居 |
| 关系基数筛选 | 下拉：`relation_type` 枚举（`1:1/1:N/N:1/N:N`，带计数） |
| 节点上限 | 数字输入（默认 200）：按度数降序截断，截断后丢弃端点缺失的悬空边 |
| 种子子图 | 「以此为种子扩展」：从选中对象做 BFS，深度 = 跳数 |
| 计数 | 右侧「N 对象 · M 关系」 |
| 导出 | `JSON` / `CSV`：序列化**当前可见**子图，前端 `Blob` 下载，文件名 `std-cdm-graph.{json,csv}` |

**砍掉「按类型过滤」档位的理由**（记录以免日后被当成漏实现）：标准中心每个节点本身就是一个类型，按 code 过滤只会剩下一个节点，原型该档位面向的是「多实体共享一个类型」的场景，语义在此不成立；同类诉求由「对象筛选 + 子图」覆盖。目录（场景）维度已由左侧 `StdCatalogTree` 承担，工具栏不重复。

模式切换时清空 `selected`（对齐 kg 侧 `switchMode` 行为），筛选变化不清空选中（若选中项被筛掉，由 `loadGraph` 既有的「选中项可能已被移除」清理逻辑兜底）。

## 7. 纯逻辑抽取与文件清单

`frontend/src/views/data-source/standard/graphViewUtils.ts`（新，纯函数、可脱 DOM 单测）：

```ts
export function toCanvasNodes(nodes, edges): CanvasNode[]      // code→color/label + 度数半径前的 deg
export function toCanvasEdges(edges): CanvasEdge[]             // label = name || code
export function degreeMap(edges): Record<number, number>
export function neighborsOf(id, edges): Set<number>
export function bfsSubgraph(seed, edges, depth): Set<number>   // 种子子图
export function applyNodeLimit(nodes, edges, cap): { nodes, edges }  // 度数降序 + 丢悬空边
export function filterByObject(nodes, edges, code): { nodes, edges }
export function filterByRelationType(edges, relationType): Edge[]
export function buildLegend(nodes): { code, label, color, count }[]
export function serializeGraph(nodes, edges, fmt: 'json' | 'csv'): string
```

`FR 布局`留在 `GraphCanvas` 内部（与渲染强相关，且 kg 侧已验证）；`StandardManagement.vue` 侧只做筛选参数持有与结果透传。

改动文件清单：

- 新增：`components/common/graph/GraphCanvas.vue`、`standard/graphViewUtils.ts`、测试 `graphViewUtils.spec.ts` 与 `GraphCanvas.spec.ts`
- 迁移：`views/kms/kg/kgTheme.ts` → `components/common/graph/graphTheme.ts`；`views/kms/kg/kg-tokens.css` → `components/common/graph/graph-tokens.css`
- 重写：`standard/StdGraphView.vue`、`standard/StdInspector.vue`（含各自 `__tests__` 两份 spec 的同步重写）
- 修改：`StandardManagement.vue`（工具栏 + 皮肤作用域容器 + `@select` 收敛）、`KbGraphPane.vue`（`<style src>` 路径 + 头注释）、`kms/kg/KgGraphView.vue`（瘦身）、6 个 kg 组件的 `kgTheme` import 路径
- 文案：`i18n/locales/zh-CN.ts` / `zh-TW.ts` / `en-US.ts` 三份同步
- 旧 spec：`2026-10-28-standard-cdm-graph-ui-design.md` 决策 7 处加一行「已被 2026-11-01 取代」注记

## 8. i18n

新增 key 全部落 `kbMgmt.graph.*`（标准中心语义命名），**包括通用文案在内一律新增，不引用 `kbMgmt.kg.*`**：那些文案说的是「实体/切片/权重/抽取器」，标准中心对应的是「对象标准/引用属性/基数/校验结论」，混用会把概念讲错，跨命名空间引用也会让 `components/common` 与 `views/kms` 的边界重新模糊。`GraphCanvas` 的三个文案（提示胶囊、图例度数说明、空态）由 props 注入，标准侧传 `kbMgmt.graph.*`，kg 侧继续传 `kbMgmt.kg.*`。

`kbMgmt.graph.` 新增：`modeFull`、`modeSubgraph`、`objectFilter`、`relationFilter`、`nodeLimit`、`expandFromSeed`、`exportGraph`、`exported`、`objectDetail`、`relationDetail`、`adjacentRelations`、`locateInGraph`、`nodeEdgeCount`、`legendNodeSize`、`statusDraft`、`statusPublished`、`verdictHit`、`verdictMissing`、`verdictConflict`、`filterObjectHint`、`filterRelationHint`。

三份 locale 全部补齐；`zh-TW` 走简体→繁体对照翻译，不留英文占位。

## 9. 测试

**9.1 新增 `standard/__tests__/graphViewUtils.spec.ts`**：度数统计、邻居集、BFS 深度边界（0/1/3 与悬空种子）、节点上限截断（同度数稳定性、截断后无悬空边）、对象/基数筛选、图例聚合降序、CSV 转义（名称含逗号/引号/换行）。

**9.2 重写 `standard/__tests__/StdGraphView.spec.ts`**：移除 `vue-echarts` 桩与 `GRAPH_EMPTY_MARKER` 的 option 断言，改为 SSR 断言骨架（画布容器类名、皮肤作用域类、空态文案、无 nodes 时不渲染 svg），分色/淡化/高亮判定通过 §7 纯函数断言覆盖；新增断言：`code` 相同对象同色、边标签取 `name` 而非基数、命中集非空时命中节点 `is-hit`。

**9.3 新增 `components/common/graph/__tests__/GraphCanvas.spec.ts`**：补共享层的结构与焦点判定断言（空节点不画、度数半径单调、`selection` 优先于 `focus`、邻居保留/非邻居 `.35`、边 `is-hl`/`is-on` 判定、图例只列可见 code）。布局用固定输入断言确定性（同输入同坐标），不测动画。

**9.4 重写 `standard/__tests__/StdInspector.spec.ts`**：marker 换成分区（引用属性 / 邻接关系 / 已绑定物理表 / 校验结论），断言邻接行的方向箭头与对端名、点击邻接项 emit 边选中、verdict→badge 三类词表、类型 tag 拿到 code 对应色。

**9.5 回归**：`npm run test`（vitest）全绿 + `vue-tsc` 类型检查通过（迁 `kgTheme` 的漏改会被 TS 直接抓到）。

## 10. 手工回归清单（`kg` 模块，无自动化兜底）

在图谱知识库（type=4）的图谱 Tab 逐项确认与重构前一致：

1. 首屏全库图的布局形态与节点分色、半径、标签光晕无变化；
2. 滚轮缩放（0.6–3.2 钳制）、空白拖拽平移、节点拖动后连线跟随；
3. 点节点 → 邻接聚焦淡化 + 邻边高亮；点边 → 该边高亮；点空白 → 取消选中；
4. 图例只列当前可见类型且按数量降序；超过 60 节点时标签策略（枢纽/选中/邻居）不变；
5. 三个模式分段（全库图/按类型过滤/种子子图）+ 两个下拉 + 跳数 + 上限 + 隐藏 Chunk 的取数与筛选结果不变；
6. 「以此为种子扩展」「导出 JSON/CSV」成功且文件名/内容形制不变；
7. 检视面板实体/关系双形态、邻接下钻、评审接受/驳回、溯源下钻、在图中定位、跳标准中心，逐项可用；
8. 亮色与暗色两套皮肤下画布与面板均无「整块白底」或对比度塌陷。

## 11. 风险与兼容性

- **共享层重构触碰已上线模块**：靠 §9.3 新测试 + §10 清单双兜底；抽取严格限制在呈现/交互层，`kg` 的取数与工具栏逻辑一行不改语义。
- **皮肤作用域外溢**：`kb-graph-pane` 只包图区三件套；总览视图不挂类，`a-card / a-statistic / a-table / BarChart` 的现有观感不受影响。
- **筛选与检视的耦合**：邻接关系列表取全量 `relations`，因此筛选收窄后详情仍完整；「在图中定位」与「点击邻接边」在目标不可见时先放宽筛选，避免点了没反应。
- **向后兼容**：`/standards/graph`、`getObject`、`listObjectBindings`、`listRelationChecks`、`nlQuery` 契约与调用点全部不变；`highlightCodes` / `highlightRelationCodes` prop 名保持，总览→图的联动零改动。
- **确定性**：同码同色 + 固定初值的静态布局，保证同一目录子树每次刷新图形一致（与 kg 侧同源）。

## 12. 分期

| 片 | 交付 | 依赖 |
|---|---|---|
| S1 | 建 `components/common/graph/`：迁 `graphTheme.ts` + `graph-tokens.css`（含 6 处 import 改路径 + `KbGraphPane` style src），`GraphCanvas.vue` 抽出，`KgGraphView` 瘦身接入，§9.3 测试 + §10 清单通过 | — |
| S2 | `graphViewUtils.ts` 纯函数 + §9.1 测试（可先于 S2 之后，但必须早于 S3） | — |
| S3 | `StdGraphView` 接画布（分色/图例/边标签/选中/NL 命中）+ §9.2 测试 | S1, S2 |
| S4 | `StdInspector` 重写为原型形态（含邻接关系下钻）+ §9.4 测试 | S3 |
| S5 | 工具栏（模式/筛选/上限/种子/导出）+ `StandardManagement` 皮肤容器与 `@select` 收敛 + i18n 三份补齐 | S3 |

S1 完成即可独立验证「kg 模块未劣化」，S3–S5 完成标准中心对齐。旧 spec 的取代注记随 S1 一并提交。
