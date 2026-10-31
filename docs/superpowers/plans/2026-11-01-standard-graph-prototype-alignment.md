# 标准中心关系图对齐图谱知识库原型 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让标准中心「标准图」页签的关系图绘制、选中高亮与右侧检视面板严格对齐原型 `kg-knowledge-base-preview.html`，并让图谱知识库与标准中心共用同一套 SVG 画布。

**Architecture:** 从 `views/kms/kg/KgGraphView.vue` 抽出一个纯呈现的共享画布组件 `components/common/graph/GraphCanvas.vue`（力导向布局 + SVG + 缩放平移拖拽 + 点选 + 邻接淡化 + 图例 + 空态），`kg` 与 `standard` 两侧各自负责取数、筛选与检视联动；标准侧的筛选/种子子图/截断/导出全部为前端纯函数（`standard/graphViewUtils.ts`），零后端改动。

**Tech Stack:** Vue 3 `<script setup>` + TypeScript、ant-design-vue、vue-i18n（zh-CN / zh-TW / en-US）、vitest（**node 环境 + `@vue/server-renderer` 字符串断言**，无 jsdom、无 `@vue/test-utils`）、原生 SVG。

**Spec:** `docs/superpowers/specs/2026-11-01-standard-graph-prototype-alignment-design.md`（逐节对应其 §3–§10；分期对应 §12 的 S1–S5）

## Global Constraints

- 工作目录：所有命令在 `d:\projects\MinWorkBuddy\frontend` 下执行。
- 测试环境为 **node**：组件测试一律 `createSSRApp` + `renderToString` + 字符串断言；不得引入 `jsdom` / `happy-dom` / `@vue/test-utils`（本仓未安装）。
- 画布坐标系与原型常量不得改动：`VB_W = 790`、`VB_H = 490`、`MIN_SCALE = 0.6`、`MAX_SCALE = 3.2`、`LABEL_ALL_MAX = 60`、半径 `Math.min(52, 15 + deg * 4.2)`、贝塞尔曲率 `0.12`、标签锚点 `0.25 / 0.5 / 0.25`、黄金角 `2.399963229728653`、向心力 `0.04`、迭代 `n<=60 ? 300 : n<=140 ? 220 : 150`、归一化留白 `112 / 96`、拖拽判定位移阈值 `3`（像素）。
- 皮肤类名保留 **`.kb-graph-pane`**（`graph-tokens.css` 内 100+ 选择器以此为前缀，不重写）。
- 共享层 `components/common/graph/**` **不得出现 `useI18n()` 与 `kbMgmt.*` key**：画布文案由 props 注入。
- 标准中心**不编造**原型有而标准无的字段：提及数、向量状态、归一化名、权重条、抽取器、抽取依据一律不上面板。
- i18n 新 key 全部落 `kbMgmt.graph.*`，三份 locale 同步补齐，不留英文占位、不做跨命名空间引用。
- 后端零改动：不调用新端点，不改 `standard_query_service.py` / `standard_cdm.py` / `api/dataops.ts` 的现有函数签名。
- 提交信息用 conventional commits（`refactor(graph): …` / `feat(standard): …` / `test(standard): …`）。本仓工作区含大量他人的未提交改动：**每次提交必须用 pathspec 限定本任务文件**，禁止 `git add -A` / `git commit -a`。
- 基线：`npx vitest run src/views/data-source/standard/__tests__` 当前 8 文件 48 用例全绿，任何任务结束时不得转红。

---

## 文件结构（本计划锁定）

```
frontend/src/
├─ components/common/graph/            ← 新增共享层
│   ├─ GraphCanvas.vue                 画布：布局+SVG+缩放/平移/拖拽+点选+淡化+图例+空态
│   ├─ graphTypes.ts                   CanvasNode / CanvasEdge / CanvasSelection（`<script setup>` 不能写 ES export，类型单独成文件）
│   ├─ graphTheme.ts                   ← 从 views/kms/kg/kgTheme.ts 迁入
│   ├─ graph-tokens.css                ← 从 views/kms/kg/kg-tokens.css 迁入（+ .is-hit 规则）
│   └─ __tests__/GraphCanvas.spec.ts   ← 新增
├─ views/kms/kg/
│   ├─ KgGraphView.vue                 瘦身：只留工具栏/取数/筛选/导出/检视联动
│   └─ (kgTheme.ts, kg-tokens.css)     删除（迁走）
├─ views/data-source/
│   ├─ StandardManagement.vue          工具栏 + 皮肤容器 + 筛选计算 + select 收敛 + 定位
│   └─ standard/
│       ├─ StdGraphView.vue            重写：映射 canvas 数据 + 渲染 GraphCanvas
│       ├─ StdInspector.vue            重写：kg-insp 形态
│       ├─ graphViewUtils.ts           新增：筛选/BFS/截断/序列化 纯函数
│       └─ __tests__/{StdGraphView,StdInspector,graphViewUtils}.spec.ts
└─ i18n/locales/{zh-CN,zh-TW,en-US}.ts + __tests__/stdGraphKeys.spec.ts（新增）
```

---

## Task 1: 迁移类型配色字典到共享层

**Files:**
- Create: `frontend/src/components/common/graph/graphTheme.ts`（内容 = 现 `frontend/src/views/kms/kg/kgTheme.ts` 全文 109 行）
- Delete: `frontend/src/views/kms/kg/kgTheme.ts`
- Modify（import 路径）: `views/kms/kg/KgGraphView.vue:181`、`views/kms/kg/KgInspector.vue:205`、`views/kms/kg/KgOverview.vue`、`views/kms/kg/KgEntityTable.vue`、`views/kms/kg/KgTripleTable.vue`、`views/kms/kg/KgProvenance.vue`

**Interfaces:**
- Consumes: 无
- Produces: `@/components/common/graph/graphTheme` 导出 `TypeTone` / `TYPE_PALETTE` / `NEUTRAL_TONE` / `typeTone(code)` / `typeLabel(code)` / `weightLevel` / `weightColor` / `propertySummary` / `formatWeight`（签名与现 `kgTheme.ts` 完全一致）

- [ ] **Step 1: 确认 6 个引用点**

Run（在 `frontend` 目录）:

```powershell
Select-String -Path src\views\kms\kg\*.vue -Pattern "from './kgTheme'" | Select-Object Filename, LineNumber, Line
```

Expected: 6 行命中（`KgGraphView.vue:181` 写作 `import { typeLabel as typeName, typeTone } from './kgTheme'`，其余 5 处为 `import { … } from './kgTheme'`）。若命中数不是 6，先停下核对，别继续。

- [ ] **Step 2: 新建共享层文件并搬入内容**

```powershell
New-Item -ItemType Directory -Force -Path src\components\common\graph\__tests__ | Out-Null
git mv src/views/kms/kg/kgTheme.ts src/components/common/graph/graphTheme.ts
```

然后把 `graphTheme.ts` 顶部注释块（第 1–6 行）替换为：

```ts
/**
 * 图谱工作台的视觉字典：节点调色板 / 显示名 / 权重分档 / 属性摘要格式。
 * 原 views/kms/kg/kgTheme.ts，2026-11-01 起供图谱知识库与标准中心共用（spec §3.2）。
 *
 * 原型约定：类型色是语义色（部门蓝、供应商绿、产品橙、仓库紫、客户青），
 * 不随主题变化；未登记的类型按名称哈希落到同一套色板，保证图谱与表格同色。
 */
```

其余内容（含 `KNOWN_TYPES`、`KNOWN_LABELS`、`hashIndex`、分号风格）一字不改。

- [ ] **Step 3: 改 6 处 import**

每个文件只改路径，保留原别名写法。例如 `KgGraphView.vue:181`：

```ts
import { typeLabel as typeName, typeTone } from '@/components/common/graph/graphTheme'
```

`KgInspector.vue:205`：

```ts
import { formatWeight, typeLabel, typeTone, weightColor } from '@/components/common/graph/graphTheme'
```

其余 4 处同法（`KgOverview.vue` / `KgEntityTable.vue` / `KgTripleTable.vue` / `KgProvenance.vue`）。

- [ ] **Step 4: 跑类型检查与基线测试**

```powershell
npx vue-tsc --noEmit -p tsconfig.json
npx vitest run src/views/data-source/standard/__tests__
```

Expected: `vue-tsc` 零错误（漏改会报 `Cannot find module './kgTheme'`）；vitest `8 passed` / `48 passed`。

- [ ] **Step 5: 提交**

```powershell
git commit -m "refactor(graph): move kg type palette to shared common/graph layer" -- src/components/common/graph/graphTheme.ts src/views/kms/kg/kgTheme.ts src/views/kms/kg/KgGraphView.vue src/views/kms/kg/KgInspector.vue src/views/kms/kg/KgOverview.vue src/views/kms/kg/KgEntityTable.vue src/views/kms/kg/KgTripleTable.vue src/views/kms/kg/KgProvenance.vue
```

---

## Task 2: 抽出共享画布 GraphCanvas，KgGraphView 瘦身接入

对应 spec §3（含 §3.1 接口、§3.3 皮肤、§3.4 保留内容）与 §10 手工回归。**本任务结束时 kg 图谱 Tab 观感必须与任务开始时逐项一致。**

**Files:**
- Create: `frontend/src/components/common/graph/graph-tokens.css`（= 现 `kg-tokens.css` 834 行 + 末尾追加 3 条规则）
- Delete: `frontend/src/views/kms/kg/kg-tokens.css`
- Create: `frontend/src/components/common/graph/graphTypes.ts`（`CanvasNode` / `CanvasEdge` / `CanvasSelection` 三个共享类型。单独成文件而非写在画布里：`<script setup>` **不允许出现 ES `export`**（编译报错），而 `graphViewUtils.ts` 与两个宿主组件都要引用这些类型）
- Create: `frontend/src/components/common/graph/GraphCanvas.vue`
- Modify: `views/kms/kg/KbGraphPane.vue:392`（`<style src>` 路径）+ 文件头注释
- Modify: `views/kms/kg/KgGraphView.vue`（删除搬走的模板与脚本，改用 `<GraphCanvas>`）
- Test: `frontend/src/components/common/graph/__tests__/GraphCanvas.spec.ts`

**Interfaces:**
- Consumes: 无（画布不依赖 `graphTheme`：节点颜色与类型显示名已在 props 里；Task 1 的作用是让两个宿主用同一套取色）
- Produces:

```ts
// @/components/common/graph/graphTypes.ts（由 GraphCanvas.vue 与本层调用方共用）
export interface CanvasNode { id: number; name: string; code: string; color: string; typeLabel: string }
export interface CanvasEdge { id: number; from: number; to: number; label: string; code?: string }
export interface CanvasSelection { kind: 'node' | 'edge'; id: number }

props = {
  nodes: CanvasNode[]
  edges: CanvasEdge[]
  selection: CanvasSelection | null
  focusNodeCodes?: string[]     // 命中对象 code：无选中时作为焦点集（spec §3.1 规则 2）
  focusEdgeCodes?: string[]     // 命中关系 code，与 CanvasEdge.code 比对
  loading?: boolean
  hintText: string              // 右上胶囊
  legendSizeText: string        // 图例末尾「节点大小 = 度数」
  emptyTitle: string            // 空态标题
  emptyDesc: string             // 空态说明
  emptyActionText?: string      // 空态按钮文案（不传则不渲染按钮）
}
emits = { (e: 'select', v: CanvasSelection | null): void; (e: 'empty-action'): void }
expose = { locate(id: number): void }   // 平移使该节点位于视野中心（不改 selection，由调用方设置）
```

- [ ] **Step 1: 迁移皮肤文件并追加命中态规则**

```powershell
git mv src/views/kms/kg/kg-tokens.css src/components/common/graph/graph-tokens.css
```

把文件第 1–12 行的头注释替换为：

```css
/**
 * 图谱工作台共用皮肤（2026-11-01 起：图谱知识库 + 标准中心共用）。
 *
 * 原 views/kms/kg/kg-tokens.css。所有规则以 .kb-graph-pane 为作用域前缀：
 * 该前缀同时是「图谱工作台皮肤作用域」的约定名，标准中心图区亦挂它（spec §3.3），
 * 因此不改名 —— 100+ 选择器逐条改写的收益远低于回归风险。
 *
 * 由宿主组件通过 <style src="..."> 引入，非 scoped。
 */
```

在文件**末尾**追加命中态（`is-hit`）规则——标准中心 NL 命中集当焦点时用；kg 侧永不产生 `is-hit`，故 kg 观感不变：

```css
/* 命中焦点集（标准中心 NL 检索）：与 .is-on/.is-hl 同一套 primary 语言 */
.kb-graph-pane .kg-node.is-hit circle {
  stroke: var(--kg-primary);
  stroke-width: 3;
}
.kb-graph-pane .kg-edge.is-hit .kg-edge__line {
  stroke: var(--kg-primary);
  stroke-width: 2.2;
}
.kb-graph-pane .kg-edge.is-hit .kg-edge__label {
  fill: var(--kg-primary);
  font-weight: 600;
}
```

改 `KbGraphPane.vue:392`：

```vue
<style src="@/components/common/graph/graph-tokens.css"></style>
```

- [ ] **Step 2: 写 GraphCanvas 失败测试**

创建 `src/components/common/graph/__tests__/GraphCanvas.spec.ts`：

```ts
import { describe, it, expect } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp, h } from 'vue'
import Antd from 'ant-design-vue'
import GraphCanvas from '../GraphCanvas.vue'
import { typeTone } from '../graphTheme'

const NODES = [
  { id: 1, name: '客户', code: 'OBJ_CUSTOMER', color: typeTone('OBJ_CUSTOMER').color, typeLabel: '客户' },
  { id: 2, name: '订单', code: 'OBJ_ORDER', color: typeTone('OBJ_ORDER').color, typeLabel: 'ORDER' },
  { id: 3, name: '部门', code: 'OBJ_DEPT', color: typeTone('OBJ_DEPT').color, typeLabel: '部门' },
]
const EDGES = [
  { id: 11, from: 2, to: 1, label: '订单属客户', code: 'REL_ORDER_CUSTOMER' },
  { id: 12, from: 3, to: 1, label: '客户服务', code: 'REL_SERVE' },
]

const TEXT = {
  hintText: 'HINT_TEXT',
  legendSizeText: 'LEGEND_SIZE',
  emptyTitle: 'EMPTY_TITLE',
  emptyDesc: 'EMPTY_DESC',
}

function ssr(props: Record<string, unknown> = {}) {
  const app = createSSRApp({
    render: () => h(GraphCanvas, { nodes: [], edges: [], selection: null, ...TEXT, ...props }),
  })
  app.use(Antd)
  return renderToString(app)
}

describe('GraphCanvas', () => {
  it('渲染画布骨架与皮肤作用域类名', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES })
    expect(html).toContain('kg-canvas')
    expect(html).toContain('kg-canvas__svg')
    expect(html).toContain('kg-canvas__hint')
    expect(html).toContain(TEXT.hintText)
  })

  it('同码同色：circle 的 fill 取 props.color', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES })
    expect(html).toContain(`fill="${typeTone('OBJ_CUSTOMER').color}"`)
    expect(html).toContain('kg-node__name');
    expect(html).toContain('客户')
  })

  it('布局确定性：同输入两次渲染坐标一致', async () => {
    const a = await ssr({ nodes: NODES, edges: EDGES })
    const b = await ssr({ nodes: NODES, edges: EDGES })
    const cx = (html: string) => (html.match(/cx="([\d.]+)"/g) || []).join(',')
    expect(cx(a)).toBe(cx(b))
    expect(cx(a)).not.toBe('')
  })

  it('图例：按节点数降序列出可见 code + 度数说明', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES })
    expect(html).toContain('kg-canvas__legend')
    expect(html).toContain(TEXT.legendSizeText)
    // 每个 code 各 1 个节点：三者都出现
    expect(html).toContain('客户')
    expect(html).toContain('部门')
  })

  it('选中节点：该节点 is-on，非邻居淡化，邻边 is-hl', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES, selection: { kind: 'node', id: 2 } })
    expect(html).toContain('kg-node is-on')
    expect(html).toContain('opacity:0.35')
    expect(html).toContain('kg-edge is-hl')
  })

  it('无选中但有命中集：命中节点 is-hit，其余淡化；选中优先于命中集', async () => {
    const html = await ssr({
      nodes: NODES,
      edges: EDGES,
      focusNodeCodes: ['OBJ_ORDER'],
      focusEdgeCodes: ['REL_ORDER_CUSTOMER'],
    })
    expect(html).toContain('is-hit')
    expect(html).toContain('opacity:0.35')

    const both = await ssr({
      nodes: NODES,
      edges: EDGES,
      selection: { kind: 'node', id: 1 },
      focusNodeCodes: ['OBJ_ORDER'],
    })
    // 有选中时走邻接语义：节点 2 是节点 1 的邻居 → 不淡化
    expect(both).not.toContain('opacity:0.35')
  })

  it('空态：标题/说明/按钮，且不渲染任何节点', async () => {
    const html = await ssr({ nodes: [], edges: [], emptyActionText: 'GO_BACK' })
    expect(html).toContain(TEXT.emptyTitle)
    expect(html).toContain(TEXT.emptyDesc)
    expect(html).toContain('GO_BACK')
    expect(html).not.toContain('kg-node"')
  })

  it('loading：遮罩层出现', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES, loading: true })
    expect(html).toContain('kg-canvas__mask')
  })
})
```

- [ ] **Step 3: 跑测试确认失败**

```powershell
npx vitest run src/components/common/graph/__tests__/GraphCanvas.spec.ts
```

Expected: FAIL —— `Failed to resolve import "../GraphCanvas.vue"`（文件还不存在）。

- [ ] **Step 4: 写共享类型与 GraphCanvas.vue**

先创建 `src/components/common/graph/graphTypes.ts`（类型单独成文件：`<script setup>` 不允许 ES `export`）：

```ts
/**
 * 共享图谱画布的数据契约（spec §3.1）。
 * 图谱知识库与标准中心都用它：颜色与显示名在调用方算好，画布只负责呈现。
 */
export interface CanvasNode {
  id: number
  name: string
  /** 类型码（标准侧 = 对象标准 code，kg 侧 = code || type_code）：图例与命中集据此聚合 */
  code: string
  color: string
  typeLabel: string
}

export interface CanvasEdge {
  id: number
  from: number
  to: number
  /** 边上显示的文字（标准侧为关系标准 name，kg 侧为 relation_type/predicate） */
  label: string
  /** 关系码：NL 命中集按 code 比对，无命中时可不传 */
  code?: string
}

export interface CanvasSelection {
  kind: 'node' | 'edge'
  id: number
}
```

然后创建 `src/components/common/graph/GraphCanvas.vue`。**模板**：把 `KgGraphView.vue:71-150`（`<div ref="canvasRef" class="kg-canvas">…</div>` 整块）搬进来，四处按新接口改写：

```vue
<template>
  <div ref="canvasRef" class="kg-canvas">
    <svg
      class="kg-canvas__svg"
      :viewBox="`0 0 ${VB_W} ${VB_H}`"
      @wheel.prevent="onWheel"
      @pointerdown="onCanvasDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointerleave="onPointerUp"
    >
      <g :transform="`translate(${view.tx} ${view.ty}) scale(${view.scale})`">
        <g
          v-for="e in visEdges"
          :key="`e-${e.id}`"
          class="kg-edge"
          :class="{ 'is-hl': isAdjacentEdge(e), 'is-on': e.id === selectedEdgeId, 'is-hit': hitEdgeIds.has(e.id) }"
        >
          <path class="kg-edge__hit" :d="e.d" @click.stop="selectEdge(e.id)" />
          <path class="kg-edge__line" :d="e.d" />
          <text v-if="showEdgeLabel(e)" class="kg-edge__label" :x="e.lx" :y="e.ly" text-anchor="middle">
            {{ e.label }}
          </text>
        </g>

        <g
          v-for="n in visNodes"
          :key="`n-${n.id}`"
          class="kg-node"
          :class="{ 'is-on': n.id === selectedNodeId, 'is-hit': isHitNode(n) }"
          :style="{ opacity: nodeOpacity(n) }"
          @pointerenter="hoverId = n.id"
          @pointerleave="hoverId = null"
          @pointerdown.stop="onNodeDown($event, n)"
        >
          <circle :cx="n.x" :cy="n.y" :r="n.r" :fill="n.color" />
          <template v-if="showNodeLabel(n)">
            <text class="kg-node__name" :x="n.x" :y="n.y + n.r + 21" text-anchor="middle">{{ n.name }}</text>
            <text class="kg-node__type" :x="n.x" :y="n.y + n.r + 33" text-anchor="middle" :style="{ fill: n.color }">
              {{ n.typeLabel }}
            </text>
          </template>
        </g>
      </g>
    </svg>

    <div v-if="loading" class="kg-canvas__mask"><a-spin size="small" /></div>

    <div v-if="!loading && !visNodes.length" class="kg-canvas__empty">
      <div class="kg-canvas__empty-t">{{ emptyTitle }}</div>
      <p>{{ emptyDesc }}</p>
      <a-button v-if="emptyActionText" size="small" @click="emit('empty-action')">
        {{ emptyActionText }}
      </a-button>
    </div>

    <div class="kg-canvas__hint">{{ hintText }}</div>
    <div v-if="legend.length" class="kg-canvas__legend">
      <span v-for="item in legend" :key="item.code"><i :style="{ background: item.color }" />{{ item.label }}</span>
      <span class="kg-muted">{{ legendSizeText }}</span>
    </div>
  </div>
</template>
```

**脚本**：常量与函数从 `KgGraphView.vue` 原样搬入（值与注释都不改），只把 `rawNodes/rawEdges/selection` 换成 props，并新增焦点集判定。逐段对应：

| 搬入内容 | 源行号（KgGraphView.vue） | 改写 |
|---|---|---|
| 常量 `VB_W/VB_H/MIN_SCALE/MAX_SCALE/LABEL_ALL_MAX` | 189–195 | 原样 |
| `VisNode` / `VisEdge` / `Pt` 类型 | 204–229 | `VisNode` 去掉 `code/typeLabel` 之外的推导依赖，保留全部字段 |
| `positions` / `degrees` / `hoverId` / `view` / `canvasRef` | 233–237、247、251 | 原样（`selection` 改用 props） |
| `visNodes` computed | 265–288 | 改为遍历 `props.nodes`，不做 `hideChunk`/`typeFilter`（那两项留在调用方）：`deg = degrees.value[node.id] || 0`、`r = Math.min(52, 15 + deg * 4.2)` |
| `visEdges` computed | 290–316 | 遍历 `props.edges`，去掉 `relationFilter` 分支；贝塞尔与 `lx/ly` 公式原样 |
| `selectedNodeId` / `selectedEdgeId` | 318–323 | 读 `props.selection` |
| `neighborIds` | 325–334 | 原样 |
| `legend` | 336–348 | 原样（`if (!n.code) return` 保留） |
| `nodeOpacity` | 350–354 | 按下面代码改写（加入焦点集分支） |
| `showNodeLabel` / `showEdgeLabel` / `isAdjacentEdge` | 356–376 | 原样（`selection` 改读 props） |
| `runLayout` | 382–511 | 原样，签名改为 `runLayout(nodes, edges)` 并写入 `positions.value` / `degrees.value` |
| 指针交互 `DragState` / `toViewBox` / `toWorld` / `onWheel` / `onCanvasDown` / `onNodeDown` / `onPointerMove` / `onPointerUp` / `updateHover` | 654–760 | 原样，但 `selectNode/selectEdge` 改为 `emit('select', …)` |

脚本骨架（省略「原样搬入」的函数体，实现时逐行照搬源文件）：

```ts
<script setup lang="ts">
/**
 * 共享图谱画布：原生 SVG + Fruchterman-Reingold 静态力导向（零图库依赖）。
 *
 * 纯呈现 + 交互：不发请求、不做筛选、不认 i18n —— 数据与文案由调用方注入。
 * 布局用 immediate watch 在 setup 期算完，因此 SSR 首屏即有坐标（组件测试依赖此行为）。
 */
import { computed, ref, watch } from 'vue'
import type { CanvasEdge, CanvasNode, CanvasSelection } from './graphTypes'

const props = withDefaults(
  defineProps<{
    nodes: CanvasNode[]
    edges: CanvasEdge[]
    selection: CanvasSelection | null
    focusNodeCodes?: string[]
    focusEdgeCodes?: string[]
    loading?: boolean
    hintText: string
    legendSizeText: string
    emptyTitle: string
    emptyDesc: string
    emptyActionText?: string
  }>(),
  { focusNodeCodes: () => [], focusEdgeCodes: () => [], loading: false, emptyActionText: '' },
)

const emit = defineEmits<{
  (e: 'select', v: CanvasSelection | null): void
  (e: 'empty-action'): void
}>()

// …… 常量、类型、positions/degrees/hoverId/view/canvasRef 从 KgGraphView 原样搬入 ……

const selectedNodeId = computed(() => (props.selection?.kind === 'node' ? props.selection.id : null))
const selectedEdgeId = computed(() => (props.selection?.kind === 'edge' ? props.selection.id : null))

/** 命中焦点集：无选中时接管淡化语义（spec §3.1 规则 2） */
const focusNodeIds = computed(() => {
  const codes = new Set(props.focusNodeCodes || [])
  const set = new Set<number>()
  if (!codes.size) return set
  props.nodes.forEach((n) => {
    if (codes.has(n.code)) set.add(n.id)
  })
  return set
})
const hitEdgeIds = computed(() => {
  const codes = new Set(props.focusEdgeCodes || [])
  const set = new Set<number>()
  if (!codes.size || props.selection) return set
  props.edges.forEach((e) => {
    if (e.code && codes.has(e.code)) set.add(e.id)
  })
  return set
})

function isHitNode(node: VisNode) {
  if (props.selection) return false
  return focusNodeIds.value.has(node.id)
}

function nodeOpacity(node: VisNode) {
  const id = selectedNodeId.value
  if (id !== null) {
    if (id === node.id) return 1
    return neighborIds.value.has(node.id) ? 1 : 0.35
  }
  if (focusNodeIds.value.size) return focusNodeIds.value.has(node.id) ? 1 : 0.35
  return 1
}

function showNodeLabel(node: VisNode) {
  if (visNodes.value.length <= LABEL_ALL_MAX) return true
  return (
    node.id === selectedNodeId.value ||
    node.id === hoverId.value ||
    neighborIds.value.has(node.id) ||
    focusNodeIds.value.has(node.id) ||
    node.deg >= 8
  )
}

function selectNode(id: number) {
  emit('select', { kind: 'node', id })
}
function selectEdge(id: number) {
  emit('select', { kind: 'edge', id })
}

/** 平移使该节点位于视野中心；不改动 selection */
function locate(id: number) {
  const pos = positions.value[id]
  if (!pos) return
  view.value = {
    ...view.value,
    tx: VB_W / 2 - pos.x * view.value.scale,
    ty: VB_H / 2 - pos.y * view.value.scale,
  }
}

defineExpose({ locate })

// 布局：props 的节点/边集合变化即重算（immediate → setup 期内完成，SSR 首屏有坐标）
watch(
  () => [props.nodes, props.edges],
  () => runLayout(props.nodes, props.edges),
  { immediate: true },
)
</script>
```

注意：`runLayout` 搬入后入参是 `CanvasNode[]`（有 `id`）与 `CanvasEdge[]`（有 `from`/`to`），函数体里 `rawNodes.value` → `nodes`、`rawEdges.value` → `edges`，其余逐行不变。

- [ ] **Step 5: 跑测试确认通过**

```powershell
npx vitest run src/components/common/graph/__tests__/GraphCanvas.spec.ts
```

Expected: PASS（8 用例）。若 `opacity:0.35` 断言失败，先确认 `:style` 输出的是 `opacity:0.35`（Vue SSR 会输出 `style="opacity:0.35;"`），不要为了过测试去改淡化值。

- [ ] **Step 6: KgGraphView 瘦身接入**

`KgGraphView.vue` 改动：

1. 模板：删除 `71–150` 的 `.kg-canvas` 整块，替换为

```vue
      <GraphCanvas
        ref="canvasRef"
        :nodes="canvasNodes"
        :edges="canvasEdges"
        :selection="selection"
        :loading="loading"
        :hint-text="t('kbMgmt.kg.graphHint')"
        :legend-size-text="t('kbMgmt.kg.legendNodeSize')"
        :empty-title="mode === 'seed' ? t('kbMgmt.kg.noSelectionAny') : t('kbMgmt.kg.noData')"
        :empty-desc="mode === 'seed' ? t('kbMgmt.kg.graphEmpty') : t('kbMgmt.kg.graphNotBuiltDesc')"
        :empty-action-text="mode === 'seed' ? t('kbMgmt.kg.graphModeFull') : ''"
        @select="selection = $event"
        @empty-action="switchMode('full')"
      />
```

2. 脚本：删除 `VB_*`/`MIN_SCALE`/`MAX_SCALE`/`LABEL_ALL_MAX` 常量、`VisNode`/`VisEdge`/`Pt` 类型、`positions`/`degrees`/`hoverId`/`view`/`canvasRef` 的本地状态、`visNodes`/`visEdges`/`selectedEdgeId`/`neighborIds`/`legend`/`nodeOpacity`/`showNodeLabel`/`showEdgeLabel`/`isAdjacentEdge`/`runLayout` 与全部指针交互函数（`DragState`…`updateHover`）。保留 `selectedNodeId`（`expandFromSeed` 仍需要）。新增两个映射 computed：

```ts
const canvasNodes = computed<CanvasNode[]>(() =>
  rawNodes.value
    .filter((node) => {
      if (hideChunk.value && isChunkNode(node)) return false
      const code = node.code || node.type_code || ''
      // 种子子图接口没有类型过滤参数，前端补一道（原 visNodes 行为）
      if (mode.value === 'seed' && typeFilter.value && code !== typeFilter.value) return false
      return true
    })
    .map((node) => {
      const code = node.code || node.type_code || ''
      return {
        id: node.id,
        name: node.name,
        code,
        color: typeTone(code).color,
        typeLabel: typeName(code),
      }
    }),
)

const canvasEdges = computed<CanvasEdge[]>(() =>
  rawEdges.value
    .filter((edge) => !relationFilter.value || edge.relation_type === relationFilter.value)
    .map((edge) => ({
      id: edge.id,
      from: edge.from,
      to: edge.to,
      label: edge.relation_type || edge.predicate || '',
      code: edge.relation_type || edge.predicate || undefined,
    })),
)
```

3. `reload()` 里删除 `view.value = { … }` 与 `runLayout()` 两行（画布自己算），其余保留；`selectNode`/`selectEdge` 保留为 `selection.value = { kind: …, id }`（`KgInspector` 与 `defineExpose` 仍用它们）。
4. import 增：`import GraphCanvas from '@/components/common/graph/GraphCanvas.vue'` 与 `import type { CanvasEdge, CanvasNode } from '@/components/common/graph/graphTypes'`；`typeTone` / `typeName`（来自 `graphTheme`）仍用于上面的 `canvasNodes` 映射，保留。
5. `defineExpose({ selectEntity, selectEdge, focusEntities, reload })` 保持不变。

- [ ] **Step 7: 类型检查 + 全量回归**

```powershell
npx vue-tsc --noEmit -p tsconfig.json
npx vitest run src/components src/views/data-source src/views/kms
```

Expected: `vue-tsc` 零错误；vitest 全绿（`src/views/kms` 目前无测试，0 文件命中属正常）。

- [ ] **Step 8: 手工回归（spec §10，逐项打勾后再提交）**

```powershell
npm run dev
```

浏览器进「知识库管理 → 图谱知识库（type=4）→ 图谱 Tab」，确认 8 项：① 首屏布局/分色/半径/标签光晕无变化；② 滚轮缩放钳制在 0.6–3.2、空白拖拽平移、节点拖动后连线跟随；③ 点节点邻接淡化、点边高亮、点空白取消选中；④ 图例按数量降序且只列可见类型，>60 节点时标签策略不变；⑤ 三个模式分段 + 两个下拉 + 跳数 + 上限 + 隐藏 Chunk 的取数结果不变；⑥ 「以此为种子扩展」「导出 JSON/CSV」可用且文件名不变；⑦ 检视面板双形态与邻接下钻、评审、溯源、定位、跳标准中心均可用；⑧ 亮/暗两套主题下无整块白底。

任一项劣化 → 回到 Step 6 修正，不得带病提交。

- [ ] **Step 9: 提交**

```powershell
git commit -m "refactor(graph): extract shared SVG canvas from KgGraphView" -- src/components/common/graph src/views/kms/kg/kg-tokens.css src/views/kms/kg/KgGraphView.vue src/views/kms/kg/KbGraphPane.vue
```

---

## Task 3: 标准图前端筛选/子图/截断/导出纯函数

对应 spec §6 与 §7。纯逻辑单独成文件的原因：node 环境里指针交互与布局无法被驱动，把判定收敛成函数才能测。

**Files:**
- Create: `frontend/src/views/data-source/standard/graphViewUtils.ts`
- Test: `frontend/src/views/data-source/standard/__tests__/graphViewUtils.spec.ts`

**Interfaces:**
- Consumes: Task 1 的 `typeTone` / `typeLabel`
- Produces（`StandardManagement.vue` 与 `StdGraphView.vue` 依赖这些确切签名）:

```ts
export interface StdGraphNode { id: number; code: string; name: string; domain?: string | null; status?: string }
export interface StdGraphEdge { id: number; code: string; name?: string | null; from: number; to: number; relation_type?: string | null }
export interface StdFilters { mode: 'full' | 'seed'; seedId: number | null; depth: number; objectCode: string; relationType: string; limit: number }
export interface FacetOption { value: string; label: string; count: number }
export function degreeMap(edges: StdGraphEdge[]): Record<number, number>
export function neighborsOf(id: number, edges: StdGraphEdge[]): Set<number>
export function bfsSubgraph(seedId: number | null, edges: StdGraphEdge[], depth: number): Set<number>
export function filterByObjectCode(nodes: StdGraphNode[], edges: StdGraphEdge[], code: string): { nodes: StdGraphNode[]; edges: StdGraphEdge[] }
export function filterByRelationType(nodes: StdGraphNode[], edges: StdGraphEdge[], relationType: string): { nodes: StdGraphNode[]; edges: StdGraphEdge[] }
export function applyNodeLimit(nodes: StdGraphNode[], edges: StdGraphEdge[], cap: number): { nodes: StdGraphNode[]; edges: StdGraphEdge[] }
export function selectVisibleGraph(nodes: StdGraphNode[], edges: StdGraphEdge[], f: StdFilters): { nodes: StdGraphNode[]; edges: StdGraphEdge[] }
export function objectFacets(nodes: StdGraphNode[]): FacetOption[]
export function relationTypeFacets(edges: StdGraphEdge[]): FacetOption[]
export function toCanvasNodes(nodes: StdGraphNode[]): CanvasNode[]
export function toCanvasEdges(edges: StdGraphEdge[]): CanvasEdge[]
export function csvEscape(value: unknown): string
export function serializeGraph(nodes: StdGraphNode[], edges: StdGraphEdge[], fmt: 'json' | 'csv'): string
```

- [ ] **Step 1: 写失败测试**

创建 `src/views/data-source/standard/__tests__/graphViewUtils.spec.ts`：

```ts
import { describe, it, expect } from 'vitest'
import {
  applyNodeLimit,
  bfsSubgraph,
  csvEscape,
  degreeMap,
  filterByObjectCode,
  neighborsOf,
  objectFacets,
  relationTypeFacets,
  selectVisibleGraph,
  serializeGraph,
  toCanvasEdges,
  toCanvasNodes,
} from '../graphViewUtils'

const NODES = [
  { id: 1, code: 'OBJ_CUSTOMER', name: '客户' },
  { id: 2, code: 'OBJ_ORDER', name: '订单' },
  { id: 3, code: 'OBJ_WAREHOUSE', name: '仓库' },
  { id: 4, code: 'OBJ_ORDER', name: '退单' },
]
const EDGES = [
  { id: 11, code: 'REL_A', name: '订单属客户', from: 2, to: 1, relation_type: 'N:1' },
  { id: 12, code: 'REL_B', name: '仓库收订单', from: 3, to: 2, relation_type: '1:N' },
  { id: 13, code: 'REL_C', name: '退单属客户', from: 4, to: 1, relation_type: 'N:1' },
]

describe('graphViewUtils', () => {
  it('degreeMap 按边累计两端', () => {
    expect(degreeMap(EDGES)).toEqual({ 1: 2, 2: 2, 3: 1, 4: 1 })
  })

  it('neighborsOf 无向取 1 跳', () => {
    expect([...neighborsOf(2, EDGES)].sort()).toEqual([1, 3])
  })

  it('bfsSubgraph 深度边界：null/0 给空集，1 跳与 3 跳', () => {
    expect(bfsSubgraph(null, EDGES, 1).size).toBe(0)
    expect(bfsSubgraph(999, EDGES, 3).size).toBe(0)
    expect([...bfsSubgraph(2, EDGES, 1)].sort()).toEqual([1, 2, 3])
    expect([...bfsSubgraph(4, EDGES, 3)].sort()).toEqual([1, 2, 3, 4])
    expect([...bfsSubgraph(4, EDGES, 0)].sort()).toEqual([4])
  })

  it('filterByObjectCode：对象本身 + 关联边 + 对端节点', () => {
    const r = filterByObjectCode(NODES, EDGES, 'OBJ_ORDER')
    expect(r.nodes.map((n) => n.id).sort()).toEqual([1, 2, 3, 4])
    expect(r.edges.map((e) => e.id)).toEqual([11, 12, 13])
  })

  it('filterByObjectCode 未命中 code：只剩该 code 为空集', () => {
    expect(filterByObjectCode(NODES, EDGES, 'NO_SUCH').nodes).toEqual([])
  })

  it('applyNodeLimit：度数降序截断 + 丢弃悬空边', () => {
    const r = applyNodeLimit(NODES, EDGES, 2)
    // 度数 2 的节点优先：1 与 2（同度按 id 升序保证稳定）
    expect(r.nodes.map((n) => n.id)).toEqual([1, 2])
    expect(r.edges.map((e) => e.id)).toEqual([11])
    const ids = new Set(r.nodes.map((n) => n.id))
    expect(r.edges.every((e) => ids.has(e.from) && ids.has(e.to))).toBe(true)
  })

  it('applyNodeLimit 上限不小于节点数时原样返回', () => {
    expect(applyNodeLimit(NODES, EDGES, 99)).toEqual({ nodes: NODES, edges: EDGES })
  })

  it('selectVisibleGraph：种子模式未选种子为空集', () => {
    const r = selectVisibleGraph(NODES, EDGES, {
      mode: 'seed',
      seedId: null,
      depth: 2,
      objectCode: '',
      relationType: '',
      limit: 200,
    })
    expect(r).toEqual({ nodes: [], edges: [] })
  })

  it('selectVisibleGraph：基数筛选先于截断，端点缺失的节点被丢弃', () => {
    const r = selectVisibleGraph(NODES, EDGES, {
      mode: 'full',
      seedId: null,
      depth: 2,
      objectCode: '',
      relationType: '1:N',
      limit: 200,
    })
    expect(r.edges.map((e) => e.id)).toEqual([12])
    expect(r.nodes.map((n) => n.id).sort()).toEqual([2, 3])
  })

  it('facets：按计数降序、同计数按 code 字典序，标签带计数', () => {
    // OBJ_ORDER 两个节点（订单 + 退单）计 2，其余各 1
    expect(objectFacets(NODES).map((f) => f.value)).toEqual(['OBJ_ORDER', 'OBJ_CUSTOMER', 'OBJ_WAREHOUSE'])
    expect(objectFacets(NODES)[0].count).toBe(2)
    expect(objectFacets(NODES).find((f) => f.value === 'OBJ_ORDER')?.label).toBe('ORDER（2）')
    expect(relationTypeFacets(EDGES)[0]).toMatchObject({ value: 'N:1', count: 2 })
  })

  it('toCanvasNodes/toCanvasEdges：分色按 code，边标签取 name 回落 code', () => {
    const cn = toCanvasNodes(NODES)
    const co = toCanvasEdges(EDGES)
    expect(cn.every((n) => !!n.code && !!n.color)).toBe(true)
    // OBJ_CUSTOMER 是 graphTheme 登记过的语义名
    expect(cn.find((n) => n.id === 1)?.typeLabel).toBe('客户')
    expect(cn.find((n) => n.id === 2)?.typeLabel).toBe('ORDER')
    expect(co.find((e) => e.id === 11)?.label).toBe('订单属客户')
    expect(co.find((e) => e.id === 11)?.code).toBe('REL_A')
    // 同码同色
    expect(cn.find((n) => n.id === 4)?.color).toBe(cn.find((n) => n.id === 2)?.color)
  })

  it('边无 name 时回落 code', () => {
    const co = toCanvasEdges([{ id: 1, code: 'REL_X', from: 1, to: 2, relation_type: 'N:1' }])
    expect(co[0].label).toBe('REL_X')
  })

  it('csvEscape：逗号/引号/换行加引号，内部引号翻倍', () => {
    expect(csvEscape('a,b')).toBe('"a,b"')
    expect(csvEscape('say"hi"')).toBe('"say""hi"""')
    expect(csvEscape('l1\nl2')).toBe('"l1\nl2"')
    expect(csvEscape(null)).toBe('')
    expect(csvEscape(12)).toBe('12')
  })

  it('serializeGraph：JSON 保结构，CSV 是边表且解析到两端 code', () => {
    const json = JSON.parse(serializeGraph(NODES, EDGES, 'json'))
    expect(json.nodes).toHaveLength(4)
    expect(json.edges[0].code).toBe('REL_A')
    const csv = serializeGraph(NODES, EDGES, 'csv')
    expect(csv.split('\n')[0]).toBe('edge_id,edge_code,edge_name,from_code,to_code,relation_type')
    expect(csv).toContain('订单属客户,OBJ_ORDER,OBJ_CUSTOMER,N:1')
    expect(csv.trim().split('\n')).toHaveLength(4)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
npx vitest run src/views/data-source/standard/__tests__/graphViewUtils.spec.ts
```

Expected: FAIL —— `Failed to resolve import "../graphViewUtils"`。

- [ ] **Step 3: 实现 graphViewUtils.ts**

创建 `src/views/data-source/standard/graphViewUtils.ts`（完整实现）：

```ts
/**
 * 标准图的前端视图计算（纯函数，便于 node 环境单测）。
 *
 * 口径：现有 /standards/graph 已一次返回所选目录的整个子树，
 * 因此筛选、种子子图、节点上限、导出全部本地算，零后端改动（spec §6）。
 */
import { typeLabel, typeTone } from '@/components/common/graph/graphTheme'
import type { CanvasEdge, CanvasNode } from '@/components/common/graph/graphTypes'

export interface StdGraphNode {
  id: number
  code: string
  name: string
  domain?: string | null
  status?: string
}

export interface StdGraphEdge {
  id: number
  code: string
  name?: string | null
  from: number
  to: number
  relation_type?: string | null
}

export interface StdFilters {
  /** full = 全图；seed = 以选中对象为种子的子图 */
  mode: 'full' | 'seed'
  seedId: number | null
  depth: number
  objectCode: string
  relationType: string
  limit: number
}

export interface FacetOption {
  value: string
  label: string
  count: number
}

export interface StdGraphResult {
  nodes: StdGraphNode[]
  edges: StdGraphEdge[]
}

export function degreeMap(edges: StdGraphEdge[]): Record<number, number> {
  const deg: Record<number, number> = {}
  edges.forEach((e) => {
    deg[e.from] = (deg[e.from] || 0) + 1
    deg[e.to] = (deg[e.to] || 0) + 1
  })
  return deg
}

export function neighborsOf(id: number, edges: StdGraphEdge[]): Set<number> {
  const set = new Set<number>()
  edges.forEach((e) => {
    if (e.from === id) set.add(e.to)
    else if (e.to === id) set.add(e.from)
  })
  return set
}

/** 从种子出发按跳数扩张；种子为空/不在任何边上（不存在或完全孤立）返回空集，depth 0 只保留种子 */
export function bfsSubgraph(seedId: number | null, edges: StdGraphEdge[], depth: number): Set<number> {
  const reached = new Set<number>()
  if (seedId === null || seedId === undefined) return reached
  // 种子必须出现在至少一条边上，否则（id 不存在或完全孤立）无子图可展开
  const incident = edges.some((e) => e.from === seedId || e.to === seedId)
  if (!incident) return reached
  reached.add(seedId)
  let frontier = [seedId]
  const maxDepth = Math.max(0, depth)
  for (let d = 0; d < maxDepth && frontier.length; d += 1) {
    const next: number[] = []
    frontier.forEach((id) => {
      neighborsOf(id, edges).forEach((n) => {
        if (!reached.has(n)) {
          reached.add(n)
          next.push(n)
        }
      })
    })
    frontier = next
  }
  return reached
}

/** 按对象标准过滤：该对象 + 与它直接相连的边与对端 */
export function filterByObjectCode(nodes: StdGraphNode[], edges: StdGraphEdge[], code: string): StdGraphResult {
  if (!code) return { nodes, edges }
  const seeds = nodes.filter((n) => n.code === code)
  if (!seeds.length) return { nodes: [], edges: [] }
  const keep = new Set<number>(seeds.map((n) => n.id))
  const keptEdges = edges.filter((e) => {
    const hit = seeds.some((s) => s.id === e.from || s.id === e.to)
    if (!hit) return false
    keep.add(e.from)
    keep.add(e.to)
    return true
  })
  return { nodes: nodes.filter((n) => keep.has(n.id)), edges: keptEdges }
}

/** 按关系基数过滤：边收窄后，失去所有边的节点一并丢弃 */
export function filterByRelationType(
  nodes: StdGraphNode[],
  edges: StdGraphEdge[],
  relationType: string,
): StdGraphResult {
  if (!relationType) return { nodes, edges }
  const kept = edges.filter((e) => e.relation_type === relationType)
  const alive = new Set<number>()
  kept.forEach((e) => {
    alive.add(e.from)
    alive.add(e.to)
  })
  return { nodes: nodes.filter((n) => alive.has(n.id)), edges: kept }
}

/** 度数降序截断（同度数按 id 升序，保证可复现），再丢弃悬空边 */
export function applyNodeLimit(nodes: StdGraphNode[], edges: StdGraphEdge[], cap: number): StdGraphResult {
  if (!cap || nodes.length <= cap) return { nodes, edges }
  const deg = degreeMap(edges)
  const sorted = [...nodes].sort((a, b) => (deg[b.id] || 0) - (deg[a.id] || 0) || a.id - b.id)
  const kept = sorted.slice(0, cap)
  const ids = new Set(kept.map((n) => n.id))
  return { nodes: kept, edges: edges.filter((e) => ids.has(e.from) && ids.has(e.to)) }
}

/** 视图计算总入口：模式 → 对象 → 基数 → 上限 */
export function selectVisibleGraph(nodes: StdGraphNode[], edges: StdGraphEdge[], f: StdFilters): StdGraphResult {
  let view = { nodes, edges }
  if (f.mode === 'seed') {
    const ids = bfsSubgraph(f.seedId, edges, f.depth)
    view = { nodes: view.nodes.filter((n) => ids.has(n.id)), edges: view.edges.filter((e) => ids.has(e.from) && ids.has(e.to)) }
  }
  view = filterByObjectCode(view.nodes, view.edges, f.objectCode)
  view = filterByRelationType(view.nodes, view.edges, f.relationType)
  return applyNodeLimit(view.nodes, view.edges, f.limit)
}

export function objectFacets(nodes: StdGraphNode[]): FacetOption[] {
  const counts = new Map<string, number>()
  nodes.forEach((n) => counts.set(n.code, (counts.get(n.code) || 0) + 1))
  // 计数降序，同计数按 code 字典序（保证下拉项顺序可复现）
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([value, count]) => ({ value, count, label: `${typeLabel(value) || value}（${count}）` }))
}

export function relationTypeFacets(edges: StdGraphEdge[]): FacetOption[] {
  const counts = new Map<string, number>()
  edges.forEach((e) => {
    if (!e.relation_type) return
    counts.set(e.relation_type, (counts.get(e.relation_type) || 0) + 1)
  })
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([value, count]) => ({ value, count, label: `${value}（${count}）` }))
}

export function toCanvasNodes(nodes: StdGraphNode[]): CanvasNode[] {
  return nodes.map((n) => ({
    id: n.id,
    name: n.name,
    code: n.code,
    color: typeTone(n.code).color,
    typeLabel: typeLabel(n.code) || n.code,
  }))
}

export function toCanvasEdges(edges: StdGraphEdge[]): CanvasEdge[] {
  return edges.map((e) => ({
    id: e.id,
    from: e.from,
    to: e.to,
    // 边标签给语义名（原型口径），基数移到检视面板；无 name 回落 code
    label: e.name || e.code,
    code: e.code,
  }))
}

export function csvEscape(value: unknown): string {
  if (value === null || value === undefined) return ''
  const s = String(value)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

/** 导出当前可见子图：JSON 保结构，CSV 为边表（两端解析为对象 code） */
export function serializeGraph(nodes: StdGraphNode[], edges: StdGraphEdge[], fmt: 'json' | 'csv'): string {
  if (fmt !== 'csv') return JSON.stringify({ nodes, edges }, null, 2)
  const codeOf = new Map(nodes.map((n) => [n.id, n.code]))
  const head = 'edge_id,edge_code,edge_name,from_code,to_code,relation_type'
  const rows = edges.map((e) =>
    [
      e.id,
      csvEscape(e.code),
      csvEscape(e.name),
      csvEscape(codeOf.get(e.from) ?? ''),
      csvEscape(codeOf.get(e.to) ?? ''),
      csvEscape(e.relation_type),
    ].join(','),
  )
  return [head, ...rows].join('\n')
}
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
npx vitest run src/views/data-source/standard/__tests__/graphViewUtils.spec.ts
```

Expected: PASS（14 用例）。

- [ ] **Step 5: 提交**

```powershell
git commit -m "feat(standard): add pure view helpers for standard graph" -- src/views/data-source/standard/graphViewUtils.ts src/views/data-source/standard/__tests__/graphViewUtils.spec.ts
```

---

## Task 4: 标准图新文案 key（三份 locale 同步）

对应 spec §8。先落 key，Task 5–7 才能直接引用；用一个存在性测试把「三语齐全」钉住（本仓没有 i18n parity 测试，这是唯一可机械校验的手段）。

**Files:**
- Modify: `frontend/src/i18n/locales/zh-CN.ts`（`graph` 块末尾，现第 2400 行 `deleted: '关系已删除'` 之后）
- Modify: `frontend/src/i18n/locales/zh-TW.ts`（同结构，现第 2383 行 `deleted: '關係已刪除'` 之后）
- Modify: `frontend/src/i18n/locales/en-US.ts`（同结构，现第 2385 行 `deleted: 'Relation deleted'` 之后）
- Test: `frontend/src/i18n/__tests__/stdGraphKeys.spec.ts`

**Interfaces:**
- Consumes: 无
- Produces: `kbMgmt.graph.{modeFull, modeSubgraph, objectFilterAll, relationFilterAll, depthLabel, nodeLimit, expandFromSeed, seedPickFirst, exportGraph, exported, nodeEdgeCount, legendNodeSize, graphEmptyDesc, objectDetail, relationDetail, adjacentRelations, noAttributes, noAdjacent, noBindings, locateInGraph, statusDraft, statusPublished}` 共 22 个 key（`graph.empty`（空态标题，文案就是「暂无对象标准」，不另起同名 key） / `selectHint` / `boundTables` / `drill` / `checks` / `noChecks` / `required` / `relationType` / `fromTo` / `fromObject` / `toObject` 已存在，直接复用；三态词复用 `kbMgmt.overview.hit/missing/conflict`）

- [ ] **Step 1: 写失败测试**

创建 `src/i18n/__tests__/stdGraphKeys.spec.ts`：

```ts
import { describe, it, expect } from 'vitest'
import zhCN from '../locales/zh-CN'
import zhTW from '../locales/zh-TW'
import enUS from '../locales/en-US'

const NEW_KEYS = [
  'modeFull',
  'modeSubgraph',
  'objectFilterAll',
  'relationFilterAll',
  'depthLabel',
  'nodeLimit',
  'expandFromSeed',
  'seedPickFirst',
  'exportGraph',
  'exported',
  'nodeEdgeCount',
  'legendNodeSize',
  'graphEmptyDesc',
  'objectDetail',
  'relationDetail',
  'adjacentRelations',
  'noAttributes',
  'noAdjacent',
  'noBindings',
  'locateInGraph',
  'statusDraft',
  'statusPublished',
]

const LOCALES: [string, any][] = [
  ['zh-CN', zhCN],
  ['zh-TW', zhTW],
  ['en-US', enUS],
]

describe('kbMgmt.graph 新文案 key', () => {
  it.each(LOCALES)('%s：22 个新 key 齐备且非空', (_name, messages) => {
    const graph = messages?.kbMgmt?.graph || {}
    NEW_KEYS.forEach((key) => {
      expect(graph[key], `${key} 在 ${_name} 缺失`).toBeTypeOf('string')
      expect((graph[key] as string).trim(), `${key} 在 ${_name} 为空`).not.toBe('')
    })
  })

  it('插值占位符三份一致', () => {
    expect(zhCN.kbMgmt.graph.nodeEdgeCount).toContain('{objects}')
    expect(zhTW.kbMgmt.graph.nodeEdgeCount).toContain('{objects}')
    expect(enUS.kbMgmt.graph.nodeEdgeCount).toContain('{objects}')
    expect(enUS.kbMgmt.graph.exported).toContain('{name}')
  })

  it('复用既有 key 未被误删', () => {
    ;['empty', 'selectHint', 'boundTables', 'drill', 'checks', 'noChecks', 'relationType'].forEach((key) => {
      expect(zhCN.kbMgmt.graph[key]).toBeTypeOf('string')
    })
    ;['hit', 'missing', 'conflict'].forEach((key) => {
      expect(zhCN.kbMgmt.overview[key]).toBeTypeOf('string')
    })
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
npx vitest run src/i18n/__tests__/stdGraphKeys.spec.ts
```

Expected: FAIL —— `modeFull 在 zh-CN 缺失`。

- [ ] **Step 3: 三份 locale 追加 key**

`zh-CN.ts`，把 `      deleted: '关系已删除'` 之后补逗号并插入：

```ts
      /* ── 关系图对齐图谱知识库原型（2026-11-01 spec §8）── */
      modeFull: '全图',
      modeSubgraph: '子图',
      objectFilterAll: '对象标准：全部',
      relationFilterAll: '关系基数：全部',
      depthLabel: '跳数',
      nodeLimit: '节点上限',
      expandFromSeed: '以此为种子扩展',
      seedPickFirst: '请先在图上选中一个对象，再以此为种子扩展',
      exportGraph: '导出',
      exported: '已导出 {name}',
      nodeEdgeCount: '{objects} 对象 · {edges} 关系',
      legendNodeSize: '节点大小 = 度数',
      graphEmptyDesc: '在左侧选择目录后新建对象与关系标准，或清空筛选条件重看图。',
      objectDetail: '对象详情',
      relationDetail: '关系详情',
      adjacentRelations: '邻接关系',
      noAttributes: '暂无引用属性',
      noAdjacent: '暂无相邻关系',
      noBindings: '暂无绑定物理表',
      locateInGraph: '在图中定位',
      statusDraft: '待发布',
      statusPublished: '已发布'
```

`zh-TW.ts`（`      deleted: '關係已刪除'` 之后，同位置同缩进）：

```ts
      /* ── 關係圖對齊圖譜知識庫原型（2026-11-01 spec §8）── */
      modeFull: '全圖',
      modeSubgraph: '子圖',
      objectFilterAll: '對象標準：全部',
      relationFilterAll: '關係基數：全部',
      depthLabel: '跳數',
      nodeLimit: '節點上限',
      expandFromSeed: '以此為種子擴展',
      seedPickFirst: '請先在圖上選中一個對象，再以此為種子擴展',
      exportGraph: '導出',
      exported: '已導出 {name}',
      nodeEdgeCount: '{objects} 對象 · {edges} 關係',
      legendNodeSize: '節點大小 = 度數',
      graphEmptyDesc: '在左側選擇目錄後新建對象與關係標準，或清空篩選條件重看圖。',
      objectDetail: '對象詳情',
      relationDetail: '關係詳情',
      adjacentRelations: '鄰接關係',
      noAttributes: '暫無引用屬性',
      noAdjacent: '暫無相鄰關係',
      noBindings: '暫無綁定物理表',
      locateInGraph: '在圖中定位',
      statusDraft: '待發布',
      statusPublished: '已發布'
```

`en-US.ts`（`      deleted: 'Relation deleted'` 之后）：

```ts
      /* ── Standard graph aligned with the KG preview prototype (spec §8) ── */
      modeFull: 'Full graph',
      modeSubgraph: 'Subgraph',
      objectFilterAll: 'Object: all',
      relationFilterAll: 'Cardinality: all',
      depthLabel: 'Depth',
      nodeLimit: 'Node limit',
      expandFromSeed: 'Expand from seed',
      seedPickFirst: 'Select an object on the graph first, then expand from it',
      exportGraph: 'Export',
      exported: 'Exported {name}',
      nodeEdgeCount: '{objects} objects · {edges} relations',
      legendNodeSize: 'Node size = degree',
      graphEmptyDesc: 'Pick a catalog on the left and create object/relation standards, or clear the filters.',
      objectDetail: 'Object detail',
      relationDetail: 'Relation detail',
      adjacentRelations: 'Adjacent relations',
      noAttributes: 'No referenced attributes',
      noAdjacent: 'No adjacent relations',
      noBindings: 'No bound tables',
      locateInGraph: 'Locate in graph',
      statusDraft: 'Draft',
      statusPublished: 'Published'
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
npx vitest run src/i18n/__tests__/stdGraphKeys.spec.ts
npx vue-tsc --noEmit -p tsconfig.json
```

Expected: PASS（3 用例）；`vue-tsc` 零错误。

- [ ] **Step 5: 提交**

```powershell
git commit -m "feat(i18n): add standard graph toolbar and inspector copy for three locales" -- src/i18n/locales/zh-CN.ts src/i18n/locales/zh-TW.ts src/i18n/locales/en-US.ts src/i18n/__tests__/stdGraphKeys.spec.ts
```

---

## Task 5: StdGraphView 改用共享画布

对应 spec §4。删 ECharts，只做「映射 + 渲染」。

**Files:**
- Modify: `frontend/src/views/data-source/standard/StdGraphView.vue`（整文件重写，现 95 行）
- Test: `frontend/src/views/data-source/standard/__tests__/StdGraphView.spec.ts`（整文件重写，现 82 行）

**Interfaces:**
- Consumes: Task 3 的 `toCanvasNodes` / `toCanvasEdges`；Task 2 的 `GraphCanvas.vue`；Task 4 的 `kbMgmt.graph.legendNodeSize` / `graphEmptyDesc` / `modeFull`，以及既有 `graph.selectHint`（提示胶囊）/ `graph.empty`（空态标题）
- Produces:

```ts
props = { nodes: StdGraphNode[]; edges: StdGraphEdge[]; selection: { kind:'node'|'edge'; id:number } | null;
          highlightCodes?: string[]; highlightRelationCodes?: string[]; loading?: boolean }
emits = { (e:'select', v: { kind:'node'|'edge'; id:number } | null): void; (e:'clear-filter'): void }
expose = { locate(id: number): void }   // 透传 GraphCanvas.locate
```

- [ ] **Step 1: 重写测试（先失败）**

把 `src/views/data-source/standard/__tests__/StdGraphView.spec.ts` 全文替换为：

```ts
import { describe, it, expect } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp, h } from 'vue'
import { createI18n } from 'vue-i18n'
import Antd from 'ant-design-vue'
import { typeTone } from '@/components/common/graph/graphTheme'

import StdGraphView from '../StdGraphView.vue'

const EMPTY_TITLE = 'GRAPH_EMPTY_TITLE'
const HINT = 'GRAPH_HINT'

const NODES = [
  { id: 1, code: 'OBJ_CUSTOMER', name: '客户', domain: 'crm', catalog_id: 1, status: 'published' },
  { id: 2, code: 'OBJ_ORDER', name: '订单', domain: 'trade', catalog_id: 1, status: 'published' },
]
const EDGES = [
  { id: 9, code: 'REL_ORDER_CUSTOMER', name: '订单属客户', from: 2, to: 1, relation_type: 'N:1', catalog_id: 1 },
]

function ssr(props: Record<string, unknown> = {}) {
  const app = createSSRApp({
    render: () => h(StdGraphView, { nodes: [], edges: [], selection: null, ...props }),
  })
  app.use(Antd)
  app.use(
    createI18n({
      legacy: false,
      locale: 'zh-CN',
      messages: {
        'zh-CN': {
          kbMgmt: {
            graph: {
              selectHint: HINT,
              legendNodeSize: 'LEGEND_SIZE',
              empty: EMPTY_TITLE,
              graphEmptyDesc: 'EMPTY_DESC',
              modeFull: 'FULL_MODE',
            },
          },
        },
      },
    }),
  )
  return renderToString(app)
}

describe('StdGraphView', () => {
  it('不再依赖 ECharts：渲染的是 SVG 画布', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES })
    expect(html).toContain('kg-canvas__svg')
    expect(html).not.toContain('echarts')
  })

  it('节点按对象标准 code 分色，边标签取关系标准 name', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES })
    expect(html).toContain(`fill="${typeTone('OBJ_CUSTOMER').color}"`)
    expect(html).toContain(`fill="${typeTone('OBJ_ORDER').color}"`)
    expect(html).toContain('订单属客户')
    // 基数不上边（原型边标签是语义名）
    expect(html).not.toContain('N:1')
  })

  it('图例与提示胶囊文案来自 kbMgmt.graph', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES })
    expect(html).toContain(HINT)
    expect(html).toContain('LEGEND_SIZE')
  })

  it('空节点：空态而不是画布节点', async () => {
    const html = await ssr({ nodes: [], edges: [] })
    expect(html).toContain(EMPTY_TITLE)
    expect(html).not.toContain('kg-node"')
  })

  it('选中节点：画布标记 is-on', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES, selection: { kind: 'node', id: 2 } })
    expect(html).toContain('is-on')
  })

  it('NL 命中集当焦点：命中节点 is-hit', async () => {
    const html = await ssr({ nodes: NODES, edges: EDGES, highlightCodes: ['OBJ_ORDER'] })
    expect(html).toContain('is-hit')
  })
})
```

```powershell
npx vitest run src/views/data-source/standard/__tests__/StdGraphView.spec.ts
```

Expected: FAIL —— 现组件仍走 `vue-echarts`，`kg-canvas__svg` 断言不成立。

- [ ] **Step 2: 重写 StdGraphView.vue**

全文替换：

```vue
<template>
  <GraphCanvas
    ref="canvasRef"
    :nodes="canvasNodes"
    :edges="canvasEdges"
    :selection="selection"
    :focus-node-codes="highlightCodes || []"
    :focus-edge-codes="highlightRelationCodes || []"
    :loading="loading"
    :hint-text="t('kbMgmt.graph.selectHint')"
    :legend-size-text="t('kbMgmt.graph.legendNodeSize')"
    :empty-title="t('kbMgmt.graph.empty')"
    :empty-desc="t('kbMgmt.graph.graphEmptyDesc')"
    :empty-action-text="canvasNodes.length ? '' : t('kbMgmt.graph.modeFull')"
    @select="emit('select', $event)"
    @empty-action="emit('clear-filter')"
  />
</template>

<script setup lang="ts">
/**
 * 标准图：对象标准 = 节点（按 code 分色），关系标准 = 边（标签用语义名）。
 *
 * 渲染与交互全在共享画布里（GraphCanvas，对齐原型 kg-knowledge-base-preview.html）；
 * 本组件只做「后端 graph 契约 -> 画布数据」的映射，筛选与截断由父级算好后传进来。
 * 边标签取 name 而非 relation_type：后者的 1:1|1:N 是基数，画在边上等于丢掉语义（spec §4）。
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import GraphCanvas from '@/components/common/graph/GraphCanvas.vue'
import type { CanvasEdge, CanvasNode } from '@/components/common/graph/graphTypes'
import { toCanvasEdges, toCanvasNodes, type StdGraphEdge, type StdGraphNode } from './graphViewUtils'

const props = defineProps<{
  nodes: StdGraphNode[]
  edges: StdGraphEdge[]
  selection: { kind: 'node' | 'edge'; id: number } | null
  /** 命中对象标准 code（NL / 关键字检索）：无选中时作为焦点集 */
  highlightCodes?: string[]
  /** 命中关系标准 code */
  highlightRelationCodes?: string[]
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'select', v: { kind: 'node' | 'edge'; id: number } | null): void
  (e: 'clear-filter'): void
}>()

const { t } = useI18n()
const canvasRef = ref<InstanceType<typeof GraphCanvas> | null>(null)

const canvasNodes = computed<CanvasNode[]>(() => toCanvasNodes(props.nodes || []))
const canvasEdges = computed<CanvasEdge[]>(() => toCanvasEdges(props.edges || []))

/** 供父级调用：把某对象平移到视野中心（selection 由父级自己维护） */
function locate(id: number) {
  canvasRef.value?.locate(id)
}

defineExpose({ locate })
</script>
```

- [ ] **Step 3: 跑测试确认通过**

```powershell
npx vitest run src/views/data-source/standard/__tests__/StdGraphView.spec.ts
```

Expected: PASS（6 用例）。若 `N:1` 断言失败，检查是否把基数又塞回了边标签。

- [ ] **Step 4: 提交**

此时 `StandardManagement.vue` 还在用旧的 `@node-click` / `:selected` 契约（Task 7 收口），所以本步只提交组件与其测试；类型检查会报父级 props 不匹配 —— 因此**先改父级最小适配**再提交：

`StandardManagement.vue:106-116` 的 `<StdGraphView …>` 改为

```vue
                <StdGraphView
                  v-if="graphView === 'graph'"
                  ref="stdGraphRef"
                  :nodes="graph.nodes"
                  :edges="graph.edges"
                  :selection="selected"
                  :highlight-codes="highlightCodes"
                  :highlight-relation-codes="highlightRelationCodes"
                  :loading="statsLoading"
                  @select="selected = $event"
                  @clear-filter="resetGraphFilters"
                />
```

并在脚本区（现 `onNodeClick` 附近，第 570–575 行）把 `onNodeClick` / `onEdgeClick` 替换为：

```ts
const stdGraphRef = ref<{ locate(id: number): void } | null>(null)
/** 筛选态：全图 / 种子子图 + 对象 + 基数 + 上限（spec §6，全部前端计算） */
const graphMode = ref<'full' | 'seed'>('full')
const graphDepth = ref(2)
const graphObjectCode = ref('')
const graphRelationType = ref('')
const graphLimit = ref(200)

function resetGraphFilters() {
  graphMode.value = 'full'
  graphObjectCode.value = ''
  graphRelationType.value = ''
  graphLimit.value = 200
}
```

（`graphMode` 等状态在 Task 7 才被工具栏消费，本步先落地是为了让类型检查与运行期一致。）

```powershell
npx vue-tsc --noEmit -p tsconfig.json
npx vitest run src/views/data-source/standard/__tests__
git commit -m "feat(standard): render standard graph on the shared SVG canvas" -- src/views/data-source/standard/StdGraphView.vue src/views/data-source/standard/__tests__/StdGraphView.spec.ts src/views/data-source/StandardManagement.vue
```

Expected: `vue-tsc` 零错误，standard 目录测试全绿。

---

## Task 6: StdInspector 重写为原型检视形态

对应 spec §5。结构与 `KgInspector.vue` 同构（`kg-insp` / `kg-kv` / `kg-sec-t` / `kg-kvlist` / `kg-mini` / `kg-badge` / `kg-type-tag`），数据源与请求保持不变。

**Files:**
- Create: `frontend/src/views/data-source/standard/inspectorFormat.ts`（状态/三态 的文案 key 与 badge 类名——纯函数；抽出来的理由与仓内 `attrDict.ts` / `nlFocus.ts` 一致：node 环境下的 SSR 拿不到 `await` 后的数据，badge 映射必须在组件外单独可测）
- Modify: `frontend/src/views/data-source/standard/StdInspector.vue`（整文件重写，现 206 行）
- Test: `frontend/src/views/data-source/standard/__tests__/StdInspector.spec.ts`（整文件重写，现 89 行）
- Test: `frontend/src/views/data-source/standard/__tests__/inspectorFormat.spec.ts`（新增）

**Interfaces:**
- Consumes: `@/components/common/graph/graphTheme` 的 `typeTone` / `typeLabel`；`kbMgmt.graph.*`（Task 4）；现有 `api.getObject` / `api.listObjectBindings` / `api.listRelationChecks`
- Produces:

```ts
// @/views/data-source/standard/inspectorFormat
export function statusTextKey(status?: string | null): string | null
export function statusBadgeClass(status?: string | null): string
export function verdictTextKey(verdict?: string | null): string | null
export function verdictBadgeClass(verdict?: string | null): string
export function bindingTitle(row: any): string

// StdInspector.vue
props = { selected: { kind:'node'|'edge'; id:number } | null; objects: any[]; relations: any[] }
emits = { (e:'edit-object',id), (e:'edit-relation',id), (e:'delete-relation',id),
          (e:'drill-down', { source_id:number; db_name?:string; database?:string; table:string }),
          (e:'inspect-entity', id: number), (e:'inspect-relation', id: number), (e:'locate', id: number) }
```

- [ ] **Step 1: 写失败测试（先纯函数，再组件）**

创建 `src/views/data-source/standard/__tests__/inspectorFormat.spec.ts`：

```ts
import { describe, it, expect } from 'vitest'
import {
  bindingTitle,
  statusBadgeClass,
  statusTextKey,
  verdictBadgeClass,
  verdictTextKey,
} from '../inspectorFormat'

describe('inspectorFormat', () => {
  it('对象/关系状态 -> 文案 key 与 badge 类', () => {
    expect(statusTextKey('published')).toBe('kbMgmt.graph.statusPublished')
    expect(statusTextKey('draft')).toBe('kbMgmt.graph.statusDraft')
    expect(statusBadgeClass('published')).toBe('kg-badge--ok')
    expect(statusBadgeClass('draft')).toBe('kg-badge--warn')
    expect(statusBadgeClass('deprecated')).toBe('kg-badge--err')
    // 未知状态不编造文案：key 为 null，组件回落原值
    expect(statusTextKey('weird')).toBeNull()
    expect(statusBadgeClass('weird')).toBe('')
    expect(statusTextKey(null)).toBeNull()
  })

  it('校验三态 -> overview.* 复用 + badge 三色', () => {
    expect(verdictTextKey('hit')).toBe('kbMgmt.overview.hit')
    expect(verdictTextKey('missing')).toBe('kbMgmt.overview.missing')
    expect(verdictTextKey('conflict')).toBe('kbMgmt.overview.conflict')
    expect(verdictBadgeClass('hit')).toBe('kg-badge--ok')
    expect(verdictBadgeClass('conflict')).toBe('kg-badge--warn')
    expect(verdictBadgeClass('missing')).toBe('kg-badge--err')
    expect(verdictBadgeClass(undefined)).toBe('')
  })

  it('绑定表标题：db 层级按需拼接，缺字段不出现孤点', () => {
    expect(bindingTitle({ db_name: 'dw', database: 'ods', table_name: 't_c' })).toBe('dw.ods.t_c')
    expect(bindingTitle({ table_name: 't_c' })).toBe('t_c')
    expect(bindingTitle({ database: 'ods', table_name: 't_c' })).toBe('ods.t_c')
    expect(bindingTitle({})).toBe('')
  })
})
```

全文替换 `src/views/data-source/standard/__tests__/StdInspector.spec.ts`：

```ts
import { describe, it, expect, vi } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp, h } from 'vue'
import { createI18n } from 'vue-i18n'
import Antd from 'ant-design-vue'
import { typeTone } from '@/components/common/graph/graphTheme'

vi.mock('@/api/dataops', () => ({
  getObject: vi.fn(() => Promise.resolve({ attributes: [{ id: 5, code: 'attr_id', name: '客户编号', required: true, security_level: 'L2' }] })),
  listObjectBindings: vi.fn(() => Promise.resolve([{ source_id: 3, db_name: 'dw', database: 'ods', table_name: 't_customer', status: 'accepted' }])),
  listRelationChecks: vi.fn(() => Promise.resolve([{ source_id: 3, database: 'ods', verdict: 'hit', confidence: 0.91 }])),
}))

import StdInspector from '../StdInspector.vue'

const M = {
  hint: 'SELECT_HINT_MARKER',
  attrs: 'ATTR_SECTION_MARKER',
  adjacent: 'ADJACENT_SECTION_MARKER',
  bound: 'BOUND_TABLES_MARKER',
  checks: 'CHECKS_SECTION_MARKER',
  action: 'ACTION_SECTION_MARKER',
}

const OBJECTS = [
  { id: 1, code: 'OBJ_CUSTOMER', name: '客户', domain: 'crm', aliases: ['customer'], status: 'published' },
]
const RELATIONS = [
  { id: 9, code: 'REL_ORDER_CUSTOMER', name: '订单属客户', from_object_id: 2, to_object_id: 1, relation_type: 'N:1', status: 'published', description: '' },
  { id: 10, code: 'REL_SERVE', name: '客户服务', from_object_id: 1, to_object_id: 3, relation_type: '1:N', status: 'draft', description: '' },
]

function ssr(props: Record<string, unknown> = {}) {
  const app = createSSRApp({
    render: () => h(StdInspector, { selected: null, objects: [], relations: [], ...props }),
  })
  app.use(Antd)
  app.use(
    createI18n({
      legacy: false,
      locale: 'zh-CN',
      messages: {
        'zh-CN': {
          kbMgmt: {
            graph: {
              selectHint: M.hint,
              required: 'REQ',
              boundTables: M.bound,
              drill: 'DRILL',
              checks: M.checks,
              noChecks: 'NO_CHECKS',
              relationType: 'CARD',
              fromObject: 'SRC',
              toObject: 'TGT',
              objectDetail: 'OBJ_DETAIL',
              relationDetail: 'REL_DETAIL',
              adjacentRelations: M.adjacent,
              locateInGraph: 'LOCATE',
              statusDraft: 'DRAFT',
              statusPublished: 'PUBLISHED',
              noAttributes: 'NO_ATTRS',
              noAdjacent: 'NO_ADJ',
              noBindings: 'NO_BINDINGS',
            },
            catalog: { description: 'DESC', attributes: M.attrs },
            overview: { hit: 'HIT', missing: 'MISSING', conflict: 'CONFLICT' },
            meta: { domain: 'DOMAIN' },
            std: { aliases: 'ALIAS' },
            common: { name: 'NAME', type: 'TYPE', edit: 'EDIT', delete: 'DEL', deleteConfirm: 'CONFIRM', status: 'STATUS', actions: M.action },
          },
        },
      },
    }),
  )
  return renderToString(app)
}

// SSR 只渲染一次，且发生在 load() 里的 await 之前：因此接口桩的数据
// （引用属性列表 / 绑定行 / 校验行）不会出现在 HTML 里。组件测试只断言
// 「分区标题 + 骨架 + 从 props 池同步取到的字段」；badge 与文案映射下沉到
// inspectorFormat.spec（Step 1 已覆盖）。

describe('StdInspector', () => {
  it('未选中：kg-insp 骨架 + 点选提示', async () => {
    const html = await ssr()
    expect(html).toContain('kg-insp')
    expect(html).toContain(M.hint)
  })

  it('选中对象：类型 tag 按 code 上色，属性/邻接/绑定/操作四分区齐备', async () => {
    const html = await ssr({ selected: { kind: 'node', id: 1 }, objects: OBJECTS, relations: RELATIONS })
    expect(html).toContain('kg-type-tag')
    expect(html).toContain(typeTone('OBJ_CUSTOMER').bg)
    expect(html).toContain('OBJ_CUSTOMER')
    expect(html).toContain(M.attrs)
    expect(html).toContain(M.adjacent)
    expect(html).toContain(M.bound)
    expect(html).toContain(M.action)
    // SSR 阶段属性/绑定为空集 → 各自的空态文案而非行项目
    expect(html).toContain('NO_ATTRS')
    expect(html).toContain('NO_BINDINGS')
    expect(html).not.toContain(M.checks)
  })

  it('选中对象：邻接关系行给方向与对端名（数据同步来自 props.relations 池）', async () => {
    const html = await ssr({ selected: { kind: 'node', id: 1 }, objects: OBJECTS, relations: RELATIONS })
    expect(html).toContain('订单属客户')
    expect(html).toContain('←')
    expect(html).toContain('→')
    expect(html).toContain('kg-mini')
  })

  it('选中关系：两端链接 + 基数 + 校验分区', async () => {
    const html = await ssr({ selected: { kind: 'edge', id: 9 }, objects: OBJECTS, relations: RELATIONS })
    expect(html).toContain('订单属客户')
    expect(html).toContain('N:1')
    expect(html).toContain(M.checks)
    expect(html).toContain('kg-insp__link')
    // 校验行要 await 后才出现，SSR 下为空态文案
    expect(html).toContain('NO_CHECKS')
  })

  it('状态徽标从对象/关系池同步取到：published 绿、draft 橙', async () => {
    const pub = await ssr({
      selected: { kind: 'node', id: 1 },
      objects: [{ id: 1, code: 'OBJ_CUSTOMER', name: '客户', status: 'published' }],
      relations: [],
    })
    expect(pub).toContain('kg-badge--ok')
    const draft = await ssr({ selected: { kind: 'edge', id: 10 }, objects: OBJECTS, relations: RELATIONS })
    expect(draft).toContain('kg-badge--warn')
  })

  it('操作分区：在图中定位', async () => {
    const html = await ssr({ selected: { kind: 'node', id: 1 }, objects: OBJECTS, relations: RELATIONS })
    expect(html).toContain('LOCATE')
  })
})
```

```powershell
npx vitest run src/views/data-source/standard/__tests__/inspectorFormat.spec.ts src/views/data-source/standard/__tests__/StdInspector.spec.ts
```

Expected: 两份都 FAIL —— `inspectorFormat` 报 `Failed to resolve import "../inspectorFormat"`；`StdInspector` 报 `kg-insp` 断言不成立（现组件根类名是 `std-inspector`）。

- [ ] **Step 2: 实现 inspectorFormat.ts**

创建 `src/views/data-source/standard/inspectorFormat.ts`：

```ts
/**
 * 检视面板的展示映射（纯函数）：状态 / 校验三态 / 绑定表标题。
 *
 * 抽成独立文件与仓内 `attrDict.ts`、`nlFocus.ts` 同一理由：node 环境下的 SSR
 * 拿不到 `await` 后的数据，badge 与文案 key 的映射必须在组件外单独可测。
 * 未知值一律回落（key 返回 null → 组件直接显原值），不编造中文词表。
 */

const STATUS_KEY: Record<string, string> = {
  draft: 'kbMgmt.graph.statusDraft',
  published: 'kbMgmt.graph.statusPublished',
  accepted: 'kbMgmt.graph.statusPublished',
}

export function statusTextKey(status?: string | null): string | null {
  return STATUS_KEY[status || ''] || null
}

export function statusBadgeClass(status?: string | null): string {
  if (status === 'published' || status === 'accepted' || status === 'active') return 'kg-badge--ok'
  if (status === 'draft' || status === 'suggested') return 'kg-badge--warn'
  if (status === 'deprecated' || status === 'rejected') return 'kg-badge--err'
  return ''
}

/** 三态词复用 kbMgmt.overview.hit/missing/conflict（同一套业务词汇，不另起 key） */
const VERDICT_KEY: Record<string, string> = {
  hit: 'kbMgmt.overview.hit',
  missing: 'kbMgmt.overview.missing',
  conflict: 'kbMgmt.overview.conflict',
}

export function verdictTextKey(verdict?: string | null): string | null {
  return VERDICT_KEY[verdict || ''] || null
}

export function verdictBadgeClass(verdict?: string | null): string {
  if (verdict === 'hit') return 'kg-badge--ok'
  if (verdict === 'conflict') return 'kg-badge--warn'
  if (verdict === 'missing') return 'kg-badge--err'
  return ''
}

export function bindingTitle(row: any): string {
  return [row?.db_name, row?.database, row?.table_name].filter(Boolean).join('.')
}
```

- [ ] **Step 3: 重写 StdInspector.vue**

全文替换：

```vue
<template>
  <section class="kg-insp">
    <header class="kg-insp__hd">
      <span>{{ isEdge ? t('kbMgmt.graph.relationDetail') : t('kbMgmt.graph.objectDetail') }}</span>
      <span v-if="selected" class="kg-insp__hd-ops">
        <template v-if="isEdge">
          <a-button size="small" @click="emit('edit-relation', selected.id)">
            {{ t('kbMgmt.common.edit') }}
          </a-button>
          <a-popconfirm :title="t('kbMgmt.common.deleteConfirm')" @confirm="emit('delete-relation', selected.id)">
            <a-button size="small" danger>{{ t('kbMgmt.common.delete') }}</a-button>
          </a-popconfirm>
        </template>
        <a-button v-else size="small" @click="emit('edit-object', selected.id)">
          {{ t('kbMgmt.common.edit') }}
        </a-button>
      </span>
    </header>

    <div class="kg-insp__bd">
      <a-spin :spinning="loading">
        <div v-if="!selected" class="kg-insp__empty">
          <div class="kg-insp__empty-icon">🔍</div>
          <div class="kg-insp__empty-t">{{ t('kbMgmt.graph.selectHint') }}</div>
        </div>

        <!-- 形态一：对象标准（定义 + 引用属性 + 邻接关系 + 绑定表） -->
        <template v-else-if="!isEdge">
          <dl class="kg-kv">
            <dt>{{ t('kbMgmt.common.name') }}</dt>
            <dd class="is-strong">{{ object?.name || '—' }}</dd>
            <dt>{{ t('kbMgmt.common.type') }}</dt>
            <dd>
              <span v-if="object?.code" class="kg-type-tag" :style="typeTagStyle(object.code)">
                {{ typeLabel(object.code) || object.code }}
              </span>
              <code v-if="object?.code" class="kg-code">{{ object.code }}</code>
              <span v-else class="kg-muted">—</span>
            </dd>
            <dt>{{ t('kbMgmt.meta.domain') }}</dt>
            <dd>{{ object?.domain || '—' }}</dd>
            <dt>{{ t('kbMgmt.std.aliases') }}</dt>
            <dd>
              <template v-if="object?.aliases?.length">
                <span v-for="alias in object.aliases" :key="alias" class="kg-insp__alias">{{ alias }}</span>
              </template>
              <span v-else class="kg-muted">—</span>
            </dd>
            <dt>{{ t('kbMgmt.common.status') }}</dt>
            <dd>
              <span class="kg-badge" :class="statusBadgeClass(object?.status)">{{ statusText(object?.status) }}</span>
            </dd>
            <dt>{{ t('kbMgmt.catalog.description') }}</dt>
            <dd>{{ object?.description || '—' }}</dd>
          </dl>

          <div class="kg-sec-t">{{ t('kbMgmt.catalog.attributes') }}</div>
          <div class="kg-kvlist">
            <div v-if="!attributes.length" class="kg-kvrow">
              <span class="k kg-muted">{{ t('kbMgmt.graph.noAttributes') }}</span>
            </div>
            <div v-for="row in attributes" :key="row.id || row.code" class="kg-kvrow">
              <span class="k">
                {{ row.name }} <code class="kg-code">{{ row.code }}</code>
              </span>
              <span class="v">
                <span v-if="row.required" class="kg-badge kg-badge--ok">{{ t('kbMgmt.graph.required') }}</span>
                <span v-if="row.security_level" class="kg-badge kg-badge--err">{{ row.security_level }}</span>
                <span v-if="!row.required && !row.security_level" class="kg-muted">—</span>
              </span>
            </div>
          </div>

          <div class="kg-sec-t">
            {{ t('kbMgmt.graph.adjacentRelations') }}（{{ adjacent.length }}）
          </div>
          <div v-if="!adjacent.length" class="kg-muted">{{ t('kbMgmt.graph.noAdjacent') }}</div>
          <div v-else>
            <div
              v-for="row in adjacent"
              :key="`adj-${row.id}`"
              class="kg-mini"
              @click="emit('inspect-relation', row.id)"
            >
              <span class="kg-type-tag kg-type-tag--rel">{{ row.name }}</span>
              <span class="kg-insp__dir">{{ row.dir }}</span>
              <span class="kg-insp__strong">{{ row.otherName }}</span>
              <span class="kg-mini__tail">{{ row.relation_type || '—' }}</span>
            </div>
          </div>

          <div class="kg-sec-t">{{ t('kbMgmt.graph.boundTables') }}</div>
          <div v-if="!bindings.length" class="kg-muted">{{ t('kbMgmt.graph.noBindings') }}</div>
          <div v-else>
            <div v-for="(row, i) in bindings" :key="`bind-${i}`" class="kg-mini">
              <span class="kg-insp__strong">{{ bindingTitle(row) }}</span>
              <span class="kg-badge" :class="row.status === 'accepted' ? 'kg-badge--ok' : 'kg-badge--warn'">
                {{ row.status || '—' }}
              </span>
              <span class="kg-mini__tail" @click.stop="drill(row)">{{ t('kbMgmt.graph.drill') }}</span>
            </div>
          </div>

          <div class="kg-sec-t">{{ t('kbMgmt.common.actions') }}</div>
          <div class="kg-insp__ops">
            <a-button size="small" @click="emit('locate', selected.id)">
              {{ t('kbMgmt.graph.locateInGraph') }}
            </a-button>
          </div>
        </template>

        <!-- 形态二：关系标准（两端 + 基数 + 校验三态） -->
        <template v-else>
          <dl class="kg-kv">
            <dt>{{ t('kbMgmt.graph.fromObject') }}</dt>
            <dd class="is-strong">
              <a class="kg-insp__link" @click="emit('inspect-entity', relation?.from_object_id)">
                {{ objectName(relation?.from_object_id) }}
              </a>
            </dd>
            <dt>{{ t('kbMgmt.graph.toObject') }}</dt>
            <dd class="is-strong">
              <a class="kg-insp__link" @click="emit('inspect-entity', relation?.to_object_id)">
                {{ objectName(relation?.to_object_id) }}
              </a>
            </dd>
            <dt>{{ t('kbMgmt.common.name') }}</dt>
            <dd>
              <span class="kg-type-tag kg-type-tag--rel">{{ relation?.name || '—' }}</span>
              <code v-if="relation?.code" class="kg-code">{{ relation.code }}</code>
            </dd>
            <dt>{{ t('kbMgmt.graph.relationType') }}</dt>
            <dd>{{ relation?.relation_type || '—' }}</dd>
            <dt>{{ t('kbMgmt.common.status') }}</dt>
            <dd>
              <span class="kg-badge" :class="statusBadgeClass(relation?.status)">
                {{ statusText(relation?.status) }}
              </span>
            </dd>
            <dt>{{ t('kbMgmt.catalog.description') }}</dt>
            <dd>{{ relation?.description || '—' }}</dd>
          </dl>

          <div class="kg-sec-t">{{ t('kbMgmt.graph.checks') }}</div>
          <div v-if="!checks.length" class="kg-muted">{{ t('kbMgmt.graph.noChecks') }}</div>
          <div v-else class="kg-kvlist">
            <div v-for="(row, i) in checks" :key="`chk-${i}`" class="kg-kvrow">
              <span class="k">{{ row.source_id }} / {{ row.database || '—' }}</span>
              <span class="v">
                <span class="kg-badge" :class="verdictBadgeClass(row.verdict)">{{ verdictText(row.verdict) }}</span>
                <span v-if="row.confidence != null"> {{ Math.round(row.confidence * 100) }}%</span>
              </span>
            </div>
          </div>

          <div class="kg-sec-t">{{ t('kbMgmt.common.actions') }}</div>
          <div class="kg-insp__ops">
            <a-button size="small" @click="emit('locate', relation?.from_object_id)">
              {{ t('kbMgmt.graph.locateInGraph') }}
            </a-button>
          </div>
        </template>
      </a-spin>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * 标准中心检视面板：对齐原型 .insp 形态（原 a-descriptions/a-list 版式替换）。
 *
 * 与 KgInspector 同构（同一套 kg-* 皮肤），但字段只出标准中心真实存在的：
 * 没有提及数、向量状态、归一化名、权重与抽取依据 —— 不编造原型有而标准无的数据（spec §5）。
 * 邻接关系取全量 relations 而非当前可见边集：详情反映标准本身，不受视图筛选影响。
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import * as api from '@/api/dataops'
import { typeLabel, typeTone } from '@/components/common/graph/graphTheme'
import {
  bindingTitle,
  statusBadgeClass,
  statusTextKey,
  verdictBadgeClass,
  verdictTextKey,
} from './inspectorFormat'

const props = defineProps<{
  selected: { kind: 'node' | 'edge'; id: number } | null
  objects: any[]
  relations: any[]
}>()

const emit = defineEmits<{
  (e: 'edit-object', id: number): void
  (e: 'edit-relation', id: number): void
  (e: 'delete-relation', id: number): void
  (e: 'drill-down', payload: { source_id: number; db_name?: string; database?: string; table: string }): void
  (e: 'inspect-entity', id: number): void
  (e: 'inspect-relation', id: number): void
  (e: 'locate', id: number): void
}>()

const { t } = useI18n()
const loading = ref(false)
const object = ref<any>(null)
const relation = ref<any>(null)
const attributes = ref<any[]>([])
const bindings = ref<any[]>([])
const checks = ref<any[]>([])

const isEdge = computed(() => props.selected?.kind === 'edge')

function typeTagStyle(code: string) {
  const tone = typeTone(code)
  return { color: tone.fg, background: tone.bg, borderColor: tone.border }
}

function objectName(id?: number | null) {
  if (!id) return '—'
  return props.objects.find((o) => o.id === id)?.name || `#${id}`
}

/** 邻接关系：方向箭头 + 对端名 + 基数，按 id 稳定排序 */
const adjacent = computed(() => {
  const id = props.selected?.kind === 'node' ? props.selected.id : null
  if (id === null) return []
  return props.relations
    .filter((r: any) => r.from_object_id === id || r.to_object_id === id)
    .map((r: any) => ({
      id: r.id,
      name: r.name || r.code,
      relation_type: r.relation_type,
      dir: r.from_object_id === id ? '→' : '←',
      otherName: objectName(r.from_object_id === id ? r.to_object_id : r.from_object_id),
    }))
    .sort((a, b) => a.id - b.id)
})

/**
 * 组件层只把 key 变成文案；映射本身在 inspectorFormat（可在组件外单测）。
 * 模板里直接用导入的 statusBadgeClass / verdictBadgeClass / bindingTitle。
 */
function statusText(status?: string | null) {
  const key = statusTextKey(status)
  return key ? t(key) : String(status || '—')
}

function verdictText(verdict?: string | null) {
  const key = verdictTextKey(verdict)
  return key ? t(key) : String(verdict || '—')
}

function drill(row: any) {
  emit('drill-down', {
    source_id: row.source_id,
    db_name: row.db_name || undefined,
    database: row.database || undefined,
    table: row.table_name,
  })
}

async function load(payload: { kind: 'node' | 'edge'; id: number } | null) {
  if (!payload) {
    object.value = null
    relation.value = null
    attributes.value = []
    bindings.value = []
    checks.value = []
    return
  }
  loading.value = true
  attributes.value = []
  bindings.value = []
  checks.value = []
  try {
    if (payload.kind === 'node') {
      relation.value = null
      object.value = props.objects.find((o) => o.id === payload.id) || null
      const detail: any = await api.getObject(payload.id)
      const data = detail.data || detail
      object.value = { ...(object.value || {}), ...data }
      attributes.value = data.attributes || []
      const b: any = await api.listObjectBindings(payload.id)
      bindings.value = b.data || b || []
    } else {
      object.value = null
      relation.value = props.relations.find((r) => r.id === payload.id) || null
      const c: any = await api.listRelationChecks(payload.id)
      checks.value = c.data || c || []
    }
  } finally {
    loading.value = false
  }
}

watch(() => [props.selected?.kind, props.selected?.id], () => load(props.selected), { immediate: true })
</script>
```

删除原 `<style scoped>` 整块（版式全由 `graph-tokens.css` 的 `.kb-graph-pane .kg-*` 提供；`std-inspector__*` 类已无引用）。

- [ ] **Step 4: 跑测试确认通过**

```powershell
npx vitest run src/views/data-source/standard/__tests__/inspectorFormat.spec.ts src/views/data-source/standard/__tests__/StdInspector.spec.ts
```

Expected: PASS（`inspectorFormat` 3 用例 + `StdInspector` 6 用例）。若组件用例报 `i18n::message does not exist`，是测内 stub 缺 key，补齐 stub 即可；不要为了过测试给 `load()` 加同步预取。

- [ ] **Step 5: 提交**

```powershell
npx vue-tsc --noEmit -p tsconfig.json
git commit -m "feat(standard): restyle inspector panel to the KG prototype form" -- src/views/data-source/standard/StdInspector.vue src/views/data-source/standard/inspectorFormat.ts src/views/data-source/standard/__tests__/StdInspector.spec.ts src/views/data-source/standard/__tests__/inspectorFormat.spec.ts
```

---

## Task 7: 工具栏（模式 / 筛选 / 上限 / 种子 / 导出）与皮肤容器

对应 spec §3.3、§6、§11 的「定位与筛选放宽」。

**Files:**
- Modify: `frontend/src/views/data-source/StandardManagement.vue`（graph Tab 模板 96–145；脚本 506–512、570–575 附近）
- Test: 复用已有测试 + 手工核对（父级无 SSR 测试，见 Step 5）

**Interfaces:**
- Consumes: Task 3 `selectVisibleGraph` / `objectFacets` / `relationTypeFacets` / `serializeGraph`；Task 5 `StdGraphView` 的 `locate` 与 `@select` / `@clear-filter`；Task 6 `StdInspector` 的 `@inspect-entity` / `@inspect-relation` / `@locate`；Task 4 文案 key
- Produces: 无对外接口（页面级组件）

- [ ] **Step 1: graph Tab 模板换成皮肤容器 + kg-toolbar + kg-wrap**

把 `StandardManagement.vue:96-145` 的 `a-tab-pane key="graph"` 内容替换为：

```vue
          <a-tab-pane key="graph" :tab="t('kbMgmt.graph.tab')">
            <div class="std-mgr__toolbar">
              <a-segmented v-model:value="graphView" :options="graphViewOptions" size="small" />
              <span class="std-mgr__spacer" />
              <a-button type="primary" @click="openRelationForm()">
                <PlusOutlined /> {{ t('kbMgmt.graph.createRelation') }}
              </a-button>
              <a-button @click="loadGraph"><ReloadOutlined /> {{ t('kbMgmt.common.refresh') }}</a-button>
            </div>

            <!-- 关系图：挂 kb-graph-pane 复用图谱工作台皮肤（仅图模式，总览不挂，spec §3.3） -->
            <div v-if="graphView === 'graph'" class="kb-graph-pane">
              <div class="kg-toolbar">
                <div class="kg-toolbar__l">
                  <div class="kg-seg">
                    <span
                      class="kg-seg__item"
                      :class="{ 'kg-seg__item--on': graphMode === 'full' }"
                      @click="switchGraphMode('full')"
                    >{{ t('kbMgmt.graph.modeFull') }}</span>
                    <span
                      class="kg-seg__item"
                      :class="{ 'kg-seg__item--on': graphMode === 'seed' }"
                      @click="switchGraphMode('seed')"
                    >{{ t('kbMgmt.graph.modeSubgraph') }}</span>
                  </div>
                  <a-select v-model:value="graphObjectCode" size="small" style="width: 168px" :options="objectOptions" @change="onFilterChange" />
                  <a-select v-model:value="graphRelationType" size="small" style="width: 150px" :options="relationOptions" @change="onFilterChange" />
                  <a-select v-model:value="graphDepth" size="small" style="width: 92px" :options="depthOptions" :disabled="graphMode !== 'seed'" @change="onFilterChange" />
                  <a-input-number v-model:value="graphLimit" size="small" style="width: 92px" :min="20" :max="2000" :step="50" @change="onFilterChange" />
                </div>
                <div class="kg-toolbar__r">
                  <span class="kg-muted">
                    {{ t('kbMgmt.graph.nodeEdgeCount', { objects: visibleGraph.nodes.length, edges: visibleGraph.edges.length }) }}
                  </span>
                  <a-button size="small" :disabled="!selectedNodeAvailable" @click="expandFromSeed">
                    {{ t('kbMgmt.graph.expandFromSeed') }}
                  </a-button>
                  <a-dropdown :trigger="['click']">
                    <a-button size="small">{{ t('kbMgmt.graph.exportGraph') }}</a-button>
                    <template #overlay>
                      <a-menu @click="onExport">
                        <a-menu-item key="json">JSON</a-menu-item>
                        <a-menu-item key="csv">CSV</a-menu-item>
                      </a-menu>
                    </template>
                  </a-dropdown>
                </div>
              </div>

              <div class="kg-wrap">
                <StdGraphView
                  ref="stdGraphRef"
                  :nodes="visibleGraph.nodes"
                  :edges="visibleGraph.edges"
                  :selection="selected"
                  :highlight-codes="highlightCodes"
                  :highlight-relation-codes="highlightRelationCodes"
                  :loading="statsLoading"
                  @select="onGraphSelect"
                  @clear-filter="resetGraphFilters"
                />
                <StdInspector
                  :selected="selected"
                  :objects="graph.nodes"
                  :relations="relations"
                  @edit-object="editObjectById"
                  @edit-relation="editRelationById"
                  @delete-relation="removeRelation"
                  @drill-down="onDrillDown"
                  @inspect-entity="selectObject"
                  @inspect-relation="selectRelation"
                  @locate="locateInGraph"
                />
              </div>
            </div>

            <div v-else class="std-mgr__graph-body">
              <div class="std-mgr__graph std-mgr__graph--overview">
                <StdGuidTour class="std-mgr__tour" :current="tourStep" />
                <StdOverviewView
                  :stats="stats"
                  :loading="statsLoading"
                  :summary="nlSummary"
                  :degraded="nlDegraded"
                  :degraded-reason="nlDegradedReason"
                  :hits="nlHits"
                  :search-empty="nlSearchEmpty"
                  :searching="nlSearching"
                  @search="onNlSearch"
                  @view-in-graph="graphView = 'graph'"
                />
              </div>
            </div>
          </a-tab-pane>
```

> 原 `<div class="std-mgr__graph">` 的边框与 `calc(100vh - 280px)` 高度对图模式不再需要：画布自带边框，SVG 按 790×490 等比自适应，容器只负责 `kg-wrap` 的两列栅格。

- [ ] **Step 2: 脚本补筛选状态与可见子图计算**

在脚本区（Task 5 已加入 `graphMode` / `graphDepth` / `graphObjectCode` / `graphRelationType` / `graphLimit` / `stdGraphRef` / `resetGraphFilters`）之后追加：

```ts
const visibleGraph = computed(() =>
  selectVisibleGraph(graph.value.nodes, graph.value.edges, {
    mode: graphMode.value,
    seedId: graphMode.value === 'seed' ? seedId.value : null,
    depth: graphDepth.value,
    objectCode: graphObjectCode.value,
    relationType: graphRelationType.value,
    limit: graphLimit.value,
  }),
)

const objectOptions = computed(() => [
  { value: '', label: t('kbMgmt.graph.objectFilterAll'), count: graph.value.nodes.length },
  ...objectFacets(graph.value.nodes).map((f) => ({ value: f.value, label: f.label, count: f.count })),
])

const relationOptions = computed(() => [
  { value: '', label: t('kbMgmt.graph.relationFilterAll'), count: graph.value.edges.length },
  ...relationTypeFacets(graph.value.edges).map((f) => ({ value: f.value, label: f.label, count: f.count })),
])

const depthOptions = computed(() =>
  [1, 2, 3].map((d) => ({ value: d, label: `${t('kbMgmt.graph.depthLabel')} ${d}` })),
)

const selectedNodeAvailable = computed(() => selected.value?.kind === 'node')

/** 种子：优先当前选中对象，其次上一个选中对象（切模式不清种子，避免子图直接空掉） */
const seedId = ref<number | null>(null)

function switchGraphMode(next: 'full' | 'seed') {
  if (graphMode.value === next) return
  if (next === 'seed' && !seedId.value) {
    message.warning(t('kbMgmt.graph.seedPickFirst'))
    return
  }
  graphMode.value = next
}

function onFilterChange() {
  // 选中项被筛掉时清掉，避免面板与图不一致（沿用 loadGraph 里的同款兜底）
  if (selected.value) {
    const pool = selected.value.kind === 'node' ? visibleGraph.value.nodes : visibleGraph.value.edges
    if (!pool.some((x: any) => x.id === selected.value!.id)) selected.value = null
  }
}

function onGraphSelect(v: { kind: 'node' | 'edge'; id: number } | null) {
  selected.value = v
  if (v?.kind === 'node') seedId.value = v.id
}

function selectObject(id: number) {
  seedId.value = id
  selected.value = { kind: 'node', id }
}

function selectRelation(id: number) {
  // 该边可能已被筛选排除：先放宽筛选再选中，点了才有反应（spec §11）
  if (!visibleGraph.value.edges.some((e) => e.id === id)) {
    graphMode.value = 'full'
    graphObjectCode.value = ''
    graphRelationType.value = ''
  }
  selected.value = { kind: 'edge', id }
}

/** 在图中定位对象：不在可见集则清空筛选，随后平移到视野中心 */
async function locateInGraph(id?: number | null) {
  if (!id) return
  if (!visibleGraph.value.nodes.some((n) => n.id === id)) {
    graphMode.value = 'full'
    graphObjectCode.value = ''
    graphRelationType.value = ''
    graphLimit.value = 2000
  }
  selectObject(id)
  await nextTick()
  stdGraphRef.value?.locate(id)
}

function expandFromSeed() {
  const id = selected.value?.kind === 'node' ? selected.value.id : seedId.value
  if (!id) {
    message.warning(t('kbMgmt.graph.seedPickFirst'))
    return
  }
  seedId.value = id
  graphMode.value = 'seed'
}

const exportFilename = 'std-cdm-graph'

function onExport(info: { key: string }) {
  const fmt = info.key === 'csv' ? 'csv' : 'json'
  const content = serializeGraph(visibleGraph.value.nodes, visibleGraph.value.edges, fmt)
  const name = `${exportFilename}.${fmt}`
  const blob = new Blob([content], {
    type: fmt === 'csv' ? 'text/csv;charset=utf-8' : 'application/json;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  message.success(t('kbMgmt.graph.exported', { name }))
}
```

`loadGraph()` 尾部（现第 564–568 行的「选中项可能已被移除」兜底之后）补一行，保证刷新后种子仍有效：

```ts
  if (seedId.value && !graph.value.nodes.some((n: any) => n.id === seedId.value)) seedId.value = null
```

import 增（现有 import 块内）：

```ts
import { nextTick } from 'vue'
import {
  objectFacets,
  relationTypeFacets,
  selectVisibleGraph,
  serializeGraph,
} from './standard/graphViewUtils'
```

并删除不再使用的 `onNodeClick` / `onEdgeClick`（现第 570–575 行）。

- [ ] **Step 3: 类型检查与全量测试**

```powershell
npx vue-tsc --noEmit -p tsconfig.json
npx vitest run src
```

Expected: `vue-tsc` 零错误；vitest 全绿。测试文件总计 10 份：既有 6 份（`StdOverviewView` / `keywordSearch` / `nlFocus` / `attrDict` / `viaOptions` / `StdCatalogTree`）、本计划新增 4 份（`GraphCanvas.spec` / `graphViewUtils.spec` / `stdGraphKeys.spec` / `inspectorFormat.spec`）、重写 2 份（`StdGraphView.spec` / `StdInspector.spec`）。

- [ ] **Step 4: 手工核对标准图页签**

```powershell
npm run dev
```

进「数据源管理 → 标准管理 → 标准图」，逐项确认：① 节点按对象 code 分色、半径随度数、左下图例 + 右上胶囊、点阵底；② 边标签是关系名（不是 `N:1`）；③ 点节点邻接淡化 + 邻边 primary，点边高亮，点空白取消；④ 「子图」分段在未选对象时给警告且不切换；⑤ 对象/基数下拉带计数、切换后「N 对象 · M 关系」跟着变；⑥ 上限调到 20 后只留高度数节点且无悬空边；⑦ 导出 JSON/CSV 各一次，CSV 表头为 `edge_id,edge_code,edge_name,from_code,to_code,relation_type`；⑧ 检视面板双形态、邻接点击可切边、绑定下钻仍跳数据源、在图中定位会把目标移到中心；⑨ 总览页签观感不变（没被皮肤污染）；⑩ NL 检索命中后切到关系图：命中节点 `is-hit`、其余淡化，点任一节点后切回邻接语义，清空检索恢复全亮。

- [ ] **Step 5: 提交**

```powershell
git commit -m "feat(standard): add graph toolbar with client-side filters and export" -- src/views/data-source/StandardManagement.vue
```

---

## Task 8: 收尾回归与文档同步

**Files:**
- Modify: `docs/superpowers/specs/2026-11-01-standard-graph-prototype-alignment-design.md`（状态行）
- 无代码改动

- [ ] **Step 1: 全量验证**

```powershell
npx vue-tsc --noEmit -p tsconfig.json
npx vitest run src
npx eslint src/components/common/graph src/views/data-source/standard src/views/data-source/StandardManagement.vue src/views/kms/kg --ext .ts,.vue
```

Expected: 三者零错误（eslint 仅报告本次改动文件；既有历史告警按 `.gitignore`/ignore 处理，不新增）。

- [ ] **Step 2: 确认旧文件已消失且无残留引用**

```powershell
Test-Path src/views/kms/kg/kgTheme.ts, src/views/kms/kg/kg-tokens.css
Select-String -Path src -Pattern "kgTheme|kg-tokens|vue-echarts" -Include *.vue,*.ts -Recurse | Where-Object { $_.Path -notlike '*__tests__*' }
```

Expected: `Test-Path` 两项都 `False`；`Select-String` 对 `kgTheme` / `kg-tokens` 零命中。`vue-echarts` **允许**在总览的 `BarChart` 相关代码里命中（那是另一条链路，本计划不动它），但 `standard/StdGraphView.vue` 不得命中。

- [ ] **Step 3: spec 状态回填**

把 spec 第 4 行 `- 状态：已与用户逐节确认（…）` 改为：

```markdown
- 状态：已实施（2026-11-01，实施计划 `docs/superpowers/plans/2026-11-01-standard-graph-prototype-alignment.md`，Task 1–8）
```

- [ ] **Step 4: 提交**

```powershell
git commit -m "docs(standard): mark graph prototype alignment spec as implemented" -- docs/superpowers/specs/2026-11-01-standard-graph-prototype-alignment-design.md
```

---

## 自审对照（spec → task）

| spec 小节 | 落在哪个 Task |
|---|---|
| §3.1 GraphCanvas 接口 + 焦点判定三规则 | T2 Step 1–5（`nodeOpacity` / `isHitNode` / `hitEdgeIds`）、T2 Step 6（kg 接入） |
| §3.2 graphTheme 迁移 + 6 处 import | T1 |
| §3.3 graph-tokens.css + `.kb-graph-pane` 作用域 + 仅图模式挂载 | T2 Step 1、T7 Step 1 |
| §4 分色/图例/边标签用 name/淡化/NL 命中/无 tooltip | T3（`toCanvasEdges`）、T5（组件重写 + 测试断言）、T8 Step 2（ECharts 残留清零） |
| §5 检视面板双形态 + 邻接下钻 + 定位 + 不编造字段 | T6 |
| §6 工具栏（模式/筛选/上限/种子/导出/砍掉按类型过滤） | T3（纯函数）、T7 Step 1–2 |
| §7 纯逻辑文件与函数清单 | T3 |
| §8 i18n 新 key + 三份同步 | T4 |
| §9 测试（新增 4 份 spec + 重写 2 份） | T2 Step 2（GraphCanvas）、T3 Step 1（graphViewUtils）、T4 Step 1（stdGraphKeys）、T5 Step 1（StdGraphView 重写）、T6 Step 1（inspectorFormat + StdInspector 重写） |
| §10 kg 手工回归 8 项 | T2 Step 8 |
| §11 风险（定位与筛选放宽 / 皮肤外溢 / 确定性） | T7 Step 2（`locateInGraph` / `selectRelation` / 仅图模式挂类）、T3（确定性排序） |
| §12 分期 S1–S5 | S1=T1+T2，S2=T3，S3=T5，S4=T6，S5=T4+T7（i18n 前置以免 T5/T7 引用不存在的 key） |
