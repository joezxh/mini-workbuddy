<template>
  <div ref="canvasRef" class="kg-canvas" :class="{ 'kg-canvas--spread': spread }">
    <div class="kg-canvas__scroll">
    <svg
      ref="svgRef"
      class="kg-canvas__svg"
      :viewBox="`0 0 ${vbW} ${vbH}`"
      :style="svgSizeStyle"
      @wheel.prevent="onWheel"
      @pointerdown="onCanvasDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointerleave="onPointerUp"
    >
      <g :transform="`translate(${view.tx} ${view.ty}) scale(${view.scale})`">
        <!-- 关系方向箭头模板：两条边（常规 / 高亮）共用同一几何，只是填色不同 -->
        <defs>
          <marker
            id="kg-arrow"
            class="kg-arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="8"
            markerHeight="8"
            markerUnits="userSpaceOnUse"
            orient="auto"
          >
            <path d="M0,0 L10,5 L0,10 Z" />
          </marker>
          <marker
            id="kg-arrow-hl"
            class="kg-arrow kg-arrow--hl"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="8"
            markerHeight="8"
            markerUnits="userSpaceOnUse"
            orient="auto"
          >
            <path d="M0,0 L10,5 L0,10 Z" />
          </marker>
        </defs>

        <g
          v-for="e in visEdges"
          :key="`e-${e.id}`"
          class="kg-edge"
          :class="{ 'is-hl': isAdjacentEdge(e), 'is-on': e.id === selectedEdgeId, 'is-hit': hitEdgeIds.has(e.id) }"
        >
          <path class="kg-edge__hit" :d="e.d" @click.stop="selectEdge(e.id)" />
          <path class="kg-edge__line" :d="e.d" :marker-end="edgeMarker(e)" />
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
    </div>

    <div v-if="loading" class="kg-canvas__mask"><a-spin size="small" /></div>

    <div v-if="!loading && !visNodes.length" class="kg-canvas__empty">
      <div class="kg-canvas__empty-t">{{ emptyTitle }}</div>
      <p>{{ emptyDesc }}</p>
      <a-button v-if="emptyActionText" size="small" @click="emit('empty-action')">
        {{ emptyActionText }}
      </a-button>
    </div>

    <div class="kg-canvas__hint">{{ hintText }}</div>
    <!-- 视口控制：＋/− 缩放（围绕视口中心，与滚轮同一数学）、复位 -->
    <div class="kg-canvas__zoom">
      <button type="button" :title="zoomLabels.in" @click="zoomBy(1.2)">＋</button>
      <button type="button" :title="zoomLabels.out" @click="zoomBy(1 / 1.2)">−</button>
      <button type="button" :title="zoomLabels.reset" @click="resetViewport()">⟲</button>
    </div>
    <div v-if="legend.length" class="kg-canvas__legend">
      <span v-for="item in legend" :key="item.code"><i :style="{ background: item.color }" />{{ item.label }}</span>
      <span class="kg-muted">{{ legendSizeText }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 共享图谱画布：原生 SVG + Fruchterman-Reingold 静态力导向（零图库依赖）。
 *
 * 纯呈现 + 交互：不发请求、不做筛选、不认 i18n —— 数据与文案由调用方注入。
 * 布局用 immediate watch 在 setup 期算完，因此 SSR 首屏即有坐标（组件测试依赖此行为）。
 */
import { computed, ref, watch } from 'vue'
import type { CanvasEdge, CanvasNode, CanvasSelection } from './graphTypes'
import { sugiyamaLayout } from './sugiyamaLayout'

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
    /** 铺开模式：节点不互相覆盖地铺开；内容超出画布时不缩小适配，
     *  由容器出现滚动条浏览（原型交互语义）。默认关闭保持既有适配行为。 */
    spread?: boolean
    /** 布局算法：'force' Fruchterman-Reingold 力导向（默认，StdGraphView 不变）；
     *  'layered' Sugiyama 定向分层（自上而下流程图风格，见 sugiyamaLayout.ts） */
    layout?: 'force' | 'layered'
    /** 缩放按钮 title 文案（由宿主传 i18n；组件本身不依赖 i18n 注入，SSR 可裸跑） */
    zoomLabels?: { in: string; out: string; reset: string }
  }>(),
  {
    focusNodeCodes: () => [], focusEdgeCodes: () => [], loading: false,
    emptyActionText: '', spread: false, layout: 'force',
    zoomLabels: () => ({ in: '放大', out: '缩小', reset: '复位视口' }),
  },
)

const emit = defineEmits<{
  (e: 'select', v: CanvasSelection | null): void
  (e: 'empty-action'): void
}>()

/** 画布设计坐标系（与原型 790×490 一致）；spread 模式下按内容外扩（滚动条浏览） */
const DESIGN_W = 790
const DESIGN_H = 490
const vbW = ref(DESIGN_W)
const vbH = ref(DESIGN_H)
/** spread 模式：SVG 用显式像素尺寸撑开滚动区；普通模式跟随容器宽度 */
const svgSizeStyle = computed(() =>
  props.spread ? { width: `${vbW.value}px`, height: `${vbH.value}px` } : undefined,
)
const MIN_SCALE = 0.6
const MAX_SCALE = 3.2
/** 超过该节点数时只给枢纽/选中/邻居画标签，避免文字糊成一团 */
const LABEL_ALL_MAX = 120
/** 超过该边数时同理，只给选中/邻边画关系标签 */
const EDGE_LABEL_MAX = 120
/** 放大到该倍数视为「凑近看」：标签一律画出来，不再按数量抑制 */
const ZOOM_REVEAL = 1.6
/** 箭头尖端离节点边缘的留白（用户单位，与缩放同步） */
const ARROW_GAP = 3

/** 节点半径（2026-11-25 调小：大图节点圆盘互相覆盖，半径随度数缓增保留枢纽语义） */
function nodeRadius(deg: number) {
  return Math.min(34, 12 + deg * 2.2)
}

interface VisNode {
  id: number
  name: string
  code: string
  typeLabel: string
  color: string
  x: number
  y: number
  r: number
  deg: number
}

interface VisEdge {
  id: number
  from: number
  to: number
  label: string
  d: string
  lx: number
  ly: number
}

interface Pt {
  x: number
  y: number
}

const positions = ref<Record<number, Pt>>({})
const degrees = ref<Record<number, number>>({})
const hoverId = ref<number | null>(null)
const view = ref({ scale: 1, tx: 0, ty: 0 })
const canvasRef = ref<HTMLElement | null>(null)
const svgRef = ref<SVGElement | null>(null)

const visNodes = computed<VisNode[]>(() => {
  const out: VisNode[] = []
  props.nodes.forEach((node) => {
    const pos = positions.value[node.id]
    if (!pos) return
    const deg = degrees.value[node.id] || 0
    out.push({
      id: node.id,
      name: node.name,
      code: node.code,
      typeLabel: node.typeLabel,
      color: node.color,
      x: pos.x,
      y: pos.y,
      r: nodeRadius(deg),
      deg,
    })
  })
  return out
})

const visEdges = computed<VisEdge[]>(() => {
  const map = new Map(visNodes.value.map((n) => [n.id, n]))
  const out: VisEdge[] = []
  props.edges.forEach((edge) => {
    const a = map.get(edge.from)
    const b = map.get(edge.to)
    if (!a || !b) return
    // 端点沿各自半径外推：路径若画到圆心，箭头与线头都埋在圆盘底下，关系就「看不见方向」
    const vx = b.x - a.x
    const vy = b.y - a.y
    const dist = Math.hypot(vx, vy)
    if (dist < 0.01) return // 重合到分不清方向，宁可不画
    const ux = vx / dist
    const uy = vy / dist
    const tail = Math.min(dist * 0.45, a.r + 1)
    const head = Math.min(dist * 0.45, b.r + ARROW_GAP)
    const ax = a.x + ux * tail
    const ay = a.y + uy * tail
    const bx = b.x - ux * head
    const by = b.y - uy * head
    // 二次贝塞尔：控制点沿法线偏移 12%，与原型曲率一致
    const mx = (ax + bx) / 2
    const my = (ay + by) / 2
    const dx = bx - ax
    const dy = by - ay
    const cx = mx - dy * 0.12
    const cy = my + dx * 0.12
    out.push({
      id: edge.id,
      from: edge.from,
      to: edge.to,
      label: edge.label,
      d: `M${ax.toFixed(1)},${ay.toFixed(1)} Q${cx.toFixed(1)},${cy.toFixed(1)} ${bx.toFixed(1)},${by.toFixed(1)}`,
      lx: 0.25 * ax + 0.5 * cx + 0.25 * bx,
      ly: 0.25 * ay + 0.5 * cy + 0.25 * by,
    })
  })
  return out
})

const selectedNodeId = computed(() => (props.selection?.kind === 'node' ? props.selection.id : null))
const selectedEdgeId = computed(() => (props.selection?.kind === 'edge' ? props.selection.id : null))
/** 用户放大即视为要读文字：标签不再按数量抑制 */
const zoomReveal = computed(() => view.value.scale >= ZOOM_REVEAL)

const neighborIds = computed(() => {
  const id = selectedNodeId.value
  const set = new Set<number>()
  if (id === null) return set
  visEdges.value.forEach((e) => {
    if (e.from === id) set.add(e.to)
    else if (e.to === id) set.add(e.from)
  })
  return set
})

/** 图例：只列当前视图里出现的类型，按节点数降序 */
const legend = computed(() => {
  const counts = new Map<string, { label: string; color: string; count: number }>()
  visNodes.value.forEach((n) => {
    if (!n.code) return
    const item = counts.get(n.code)
    if (item) item.count += 1
    else counts.set(n.code, { label: n.typeLabel || n.code, color: n.color, count: 1 })
  })
  return Array.from(counts.entries())
    .sort((a, b) => b[1].count - a[1].count)
    .map(([code, item]) => ({ code, label: item.label, color: item.color }))
})

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
  if (visNodes.value.length <= LABEL_ALL_MAX || zoomReveal.value) return true
  return (
    node.id === selectedNodeId.value ||
    node.id === hoverId.value ||
    neighborIds.value.has(node.id) ||
    focusNodeIds.value.has(node.id) ||
    node.deg >= 8
  )
}

function showEdgeLabel(edge: VisEdge) {
  if (edge.id === selectedEdgeId.value) return true
  if (visEdges.value.length <= EDGE_LABEL_MAX || zoomReveal.value) return true
  const id = selectedNodeId.value
  return id !== null && (edge.from === id || edge.to === id)
}

/** 箭头跟线走同一套强调语言：选中/邻接/命中的边用主色箭头 */
function edgeMarker(edge: VisEdge) {
  const hl =
    edge.id === selectedEdgeId.value ||
    isAdjacentEdge(edge) ||
    hitEdgeIds.value.has(edge.id)
  return hl ? 'url(#kg-arrow-hl)' : 'url(#kg-arrow)'
}

function isAdjacentEdge(edge: VisEdge) {
  const id = selectedNodeId.value
  return id !== null && (edge.from === id || edge.to === id)
}

/**
 * 静态力导向布局（Fruchterman-Reingold）+ 归一化。
 * 结果写回 positions/degrees，只触发一次渲染，不做逐帧动画。
 */
function runLayout(nodes: CanvasNode[], edges: CanvasEdge[]) {
  const n = nodes.length
  const idSet = new Set(nodes.map((x) => x.id))
  const links = edges.filter((e) => idSet.has(e.from) && idSet.has(e.to))

  const deg: Record<number, number> = {}
  links.forEach((e) => {
    deg[e.from] = (deg[e.from] || 0) + 1
    deg[e.to] = (deg[e.to] || 0) + 1
  })
  degrees.value = deg
  if (!n) {
    positions.value = {}
    return
  }

  // 分层布局（Sugiyama，自上而下流程图风格）：纯函数四阶段流水线
  //（环消除→最长路分层→重心法交叉优化→槽位坐标），零随机、同输入可复现；
  // 输出 x 以 0 为中轴、y 自 0 起，由 finishLayout 统一接管画布尺寸与居中
  if (props.layout === 'layered') {
    const radii: Record<number, number> = {}
    nodes.forEach((nd) => {
      radii[nd.id] = nodeRadius(deg[nd.id] || 0)
    })
    const raw = sugiyamaLayout(nodes, edges, (id) => radii[id] || 15)
    const next: Record<number, Pt> = {}
    for (const key of Object.keys(raw)) {
      next[Number(key)] = { ...raw[Number(key)] }
    }
    // 兜底碰撞消解：槽位坐标理论无重叠（槽宽 ≥ 半径和 + 间距），空转一轮即退出
    resolveOverlaps(next, radii, null)
    finishLayout(next, radii)
    return
  }

  const cx = DESIGN_W / 2
  const cy = DESIGN_H / 2
  // 黄金角螺旋撒点：确定性初值，避免对称初始位形导致的不动点
  const pts = nodes.map((node, i) => {
    const angle = i * 2.399963229728653
    const rad = Math.min(DESIGN_W, DESIGN_H) * 0.4 * Math.sqrt((i + 0.5) / n)
    return {
      id: node.id,
      x: cx + Math.cos(angle) * rad,
      y: cy + Math.sin(angle) * rad,
      dx: 0,
      dy: 0,
    }
  })
  const index = new Map<number, number>()
  pts.forEach((p, i) => index.set(p.id, i))

  // 理想边距 k：spread 模式整体拉长 1.6x——关系线段更长、节点更分散
  //（配合小半径 + 碰撞消解，全库图不再挤成一团）
  const k = Math.sqrt((DESIGN_W * DESIGN_H * 0.55) / n) * (props.spread ? 1.6 : 1)
  const iters = n <= 60 ? 300 : n <= 140 ? 220 : 150

  for (let iter = 0; iter < iters; iter += 1) {
    const temp = Math.max(0.6, k * 0.55 * (1 - iter / iters))
    pts.forEach((p) => {
      p.dx = 0
      p.dy = 0
    })

    // 斥力：k²/d
    for (let a = 0; a < n; a += 1) {
      const pa = pts[a]
      for (let b = a + 1; b < n; b += 1) {
        const pb = pts[b]
        let vx = pa.x - pb.x
        let vy = pa.y - pb.y
        let d = Math.sqrt(vx * vx + vy * vy)
        if (d < 0.01) {
          // 完全重合时给一个确定性的伪随机方向，保证可复现
          vx = ((a * 37 + b * 11) % 100) / 100 - 0.5
          vy = ((a * 17 + b * 29) % 100) / 100 - 0.5
          d = Math.sqrt(vx * vx + vy * vy) || 1
        }
        const f = (k * k) / d
        const ux = vx / d
        const uy = vy / d
        pa.dx += ux * f
        pa.dy += uy * f
        pb.dx -= ux * f
        pb.dy -= uy * f
      }
    }

    // 引力：d²/k（只沿边）
    links.forEach((e) => {
      const ai = index.get(e.from)
      const bi = index.get(e.to)
      if (ai === undefined || bi === undefined) return
      const pa = pts[ai]
      const pb = pts[bi]
      const vx = pa.x - pb.x
      const vy = pa.y - pb.y
      const d = Math.max(0.5, Math.sqrt(vx * vx + vy * vy))
      const f = (d * d) / k
      const ux = vx / d
      const uy = vy / d
      pa.dx -= ux * f
      pa.dy -= uy * f
      pb.dx += ux * f
      pb.dy += uy * f
    })

    // 向心力（连通分量不外飘）+ 位移限幅
    pts.forEach((p) => {
      p.dx += (cx - p.x) * 0.04
      p.dy += (cy - p.y) * 0.04
      const len = Math.sqrt(p.dx * p.dx + p.dy * p.dy)
      if (len > 0.0001) {
        const step = Math.min(len, temp)
        p.x += (p.dx / len) * step
        p.y += (p.dy / len) * step
      }
    })
  }

  // 归一化：等比缩放并居中，留出节点标签的边距
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  pts.forEach((p) => {
    minX = Math.min(minX, p.x)
    maxX = Math.max(maxX, p.x)
    minY = Math.min(minY, p.y)
    maxY = Math.max(maxY, p.y)
  })
  const spanX = Math.max(1, maxX - minX)
  const spanY = Math.max(1, maxY - minY)
  const fitScale = Math.min((DESIGN_W - 112) / spanX, (DESIGN_H - 96) / spanY, n > 1 ? 3 : 1)
  // spread 模式不缩小适配（scale 下限 1）：图比视口大时保持 1:1，
  // 由容器滚动条呈现超出部分；普通模式维持「压缩塞进视口」的既有行为
  const scale = props.spread ? Math.max(1, fitScale) : fitScale
  const midX = (minX + maxX) / 2
  const midY = (minY + maxY) / 2

  const next: Record<number, Pt> = {}
  pts.forEach((p) => {
    next[p.id] = {
      x: DESIGN_W / 2 + (p.x - midX) * scale,
      y: DESIGN_H / 2 + (p.y - midY) * scale,
    }
  })

  // 碰撞消解（2026-11-25）：FR 收敛后相邻节点仍可能重叠（半径随度数增大，
  // 大图还被归一化压缩）。按最终渲染半径把重叠对推开，保证实体不互相覆盖。
  const radii: Record<number, number> = {}
  nodes.forEach((nd) => {
    radii[nd.id] = nodeRadius(deg[nd.id] || 0)
  })
  finishLayout(next, radii)
}

/**
 * 布局收尾（force / layered 两条路径共用）：碰撞消解 + 画布尺寸 + 内容居中。
 * spread：按内容外扩 viewBox（含半径 + 节点下方两行标签高度），超出部分滚动条；
 * 非 spread：内容收在视口内，边界作墙参与碰撞消解。
 */
function finishLayout(next: Record<number, Pt>, radii: Record<number, number>) {
  if (props.spread) {
    resolveOverlaps(next, radii, null)
    let cMinX = Infinity
    let cMaxX = -Infinity
    let cMinY = Infinity
    let cMaxY = -Infinity
    Object.entries(next).forEach(([idStr, p]) => {
      const r = radii[Number(idStr)] || 15
      cMinX = Math.min(cMinX, p.x - r - 6)
      cMaxX = Math.max(cMaxX, p.x + r + 6)
      cMinY = Math.min(cMinY, p.y - r - 6)
      cMaxY = Math.max(cMaxY, p.y + r + 44)
    })
    const pad = 40
    vbW.value = Math.max(DESIGN_W, Math.ceil(cMaxX - cMinX + pad * 2))
    vbH.value = Math.max(DESIGN_H, Math.ceil(cMaxY - cMinY + pad * 2))
    const shiftX = vbW.value / 2 - (cMinX + cMaxX) / 2
    const shiftY = vbH.value / 2 - (cMinY + cMaxY) / 2
    Object.values(next).forEach((p) => {
      p.x += shiftX
      p.y += shiftY
    })
  } else {
    // 适配模式：内容收在视口内，边界作墙参与碰撞消解
    resolveOverlaps(
      next, radii,
      { minX: 60, maxX: DESIGN_W - 60, minY: 60, maxY: DESIGN_H - 44 },
    )
    vbW.value = DESIGN_W
    vbH.value = DESIGN_H
  }
  positions.value = next
}

/**
 * 成对推开重叠节点（确定性：固定遍历序 + 相同迭代轮数语义）。
 * bounds 非空时每轮把越界节点拉回（视口边界当墙）；null = 无边界自由铺开。
 */
function resolveOverlaps(
  pts: Record<number, Pt>,
  radii: Record<number, number>,
  bounds: { minX: number; maxX: number; minY: number; maxY: number } | null,
) {
  const ids = Object.keys(pts).map(Number)
  const passes = ids.length <= 120 ? 60 : 20
  for (let pass = 0; pass < passes; pass += 1) {
    let moved = false
    for (let a = 0; a < ids.length; a += 1) {
      const pa = pts[ids[a]]
      const ra = radii[ids[a]] || 15
      for (let b = a + 1; b < ids.length; b += 1) {
        const pb = pts[ids[b]]
        const rb = radii[ids[b]] || 15
        let vx = pb.x - pa.x
        let vy = pb.y - pa.y
        let d = Math.sqrt(vx * vx + vy * vy)
        const minD = ra + rb + 8
        if (d >= minD) continue
        if (d < 0.01) {
          // 完全重合给确定性伪随机方向，保证可复现
          vx = ((ids[a] * 37 + ids[b] * 11) % 100) / 100 - 0.5
          vy = ((ids[a] * 17 + ids[b] * 29) % 100) / 100 - 0.5
          d = Math.sqrt(vx * vx + vy * vy) || 1
        }
        const push = (minD - d) / 2
        const ux = vx / d
        const uy = vy / d
        pa.x -= ux * push
        pa.y -= uy * push
        pb.x += ux * push
        pb.y += uy * push
        moved = true
      }
    }
    if (bounds) {
      Object.values(pts).forEach((p) => {
        const nx = Math.max(bounds.minX, Math.min(bounds.maxX, p.x))
        const ny = Math.max(bounds.minY, Math.min(bounds.maxY, p.y))
        if (nx !== p.x || ny !== p.y) moved = true
        p.x = nx
        p.y = ny
      })
    }
    if (!moved) break
  }
}

// ── 指针交互：缩放 / 平移 / 拖节点 / 选中 ──────────────────────────────

type DragState =
  | { kind: 'node'; id: number; moved: boolean; total: number; lastVB: Pt; lastW: Pt }
  | { kind: 'pan'; moved: boolean; total: number; lastVB: Pt }
  | null

let drag: DragState = null

function toViewBox(clientX: number, clientY: number): Pt {
  const el = svgRef.value
  if (!el) return { x: 0, y: 0 }
  const rect = el.getBoundingClientRect()
  return {
    x: ((clientX - rect.left) / Math.max(1, rect.width)) * vbW.value,
    y: ((clientY - rect.top) / Math.max(1, rect.height)) * vbH.value,
  }
}

function toWorld(p: Pt): Pt {
  return {
    x: (p.x - view.value.tx) / view.value.scale,
    y: (p.y - view.value.ty) / view.value.scale,
  }
}

function onWheel(e: WheelEvent) {
  const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12
  const next = Math.min(MAX_SCALE, Math.max(MIN_SCALE, view.value.scale * factor))
  const current = view.value.scale
  if (Math.abs(next - current) < 0.0001) return
  const p = toViewBox(e.clientX, e.clientY)
  view.value = {
    scale: next,
    tx: p.x - ((p.x - view.value.tx) * next) / current,
    ty: p.y - ((p.y - view.value.ty) * next) / current,
  }
}

function onCanvasDown(e: PointerEvent) {
  if ((e.target as Element)?.tagName !== 'svg') return
  drag = { kind: 'pan', moved: false, total: 0, lastVB: toViewBox(e.clientX, e.clientY) }
}

function onNodeDown(e: PointerEvent, node: VisNode) {
  const vb = toViewBox(e.clientX, e.clientY)
  drag = {
    kind: 'node',
    id: node.id,
    moved: false,
    total: 0,
    lastVB: vb,
    lastW: toWorld(vb),
  }
}

function onPointerMove(e: PointerEvent) {
  if (!drag) {
    updateHover(e)
    return
  }
  const vb = toViewBox(e.clientX, e.clientY)
  if (drag.kind === 'node') {
    const world = toWorld(vb)
    const pos = positions.value[drag.id]
    if (pos) {
      const dx = world.x - drag.lastW.x
      const dy = world.y - drag.lastW.y
      drag.total += Math.hypot(dx * view.value.scale, dy * view.value.scale)
      if (drag.total > 3) drag.moved = true
      pos.x += dx
      pos.y += dy
    }
    drag.lastW = world
  } else {
    const dx = vb.x - drag.lastVB.x
    const dy = vb.y - drag.lastVB.y
    drag.total += Math.hypot(dx, dy)
    if (drag.total > 3) drag.moved = true
    view.value = { ...view.value, tx: view.value.tx + dx, ty: view.value.ty + dy }
  }
  drag.lastVB = vb
}

function onPointerUp() {
  if (!drag) return
  const state = drag
  drag = null
  if (state.kind === 'node') {
    if (!state.moved) selectNode(state.id)
    return
  }
  // 空白处点一下 = 取消选中（原型行为）
  if (!state.moved) emit('select', null)
}

function updateHover(e: PointerEvent) {
  const world = toWorld(toViewBox(e.clientX, e.clientY))
  let hit: number | null = null
  for (const node of visNodes.value) {
    if (Math.hypot(world.x - node.x, world.y - node.y) <= node.r + 2) {
      hit = node.id
      break
    }
  }
  hoverId.value = hit
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
    tx: vbW.value / 2 - pos.x * view.value.scale,
    ty: vbH.value / 2 - pos.y * view.value.scale,
  }
}

/** 按钮缩放：围绕视口中心（与 onWheel 围绕光标同一套数学） */
function zoomBy(factor: number) {
  const current = view.value.scale
  const next = Math.min(MAX_SCALE, Math.max(MIN_SCALE, current * factor))
  if (Math.abs(next - current) < 0.0001) return
  const cx = vbW.value / 2
  const cy = vbH.value / 2
  view.value = {
    scale: next,
    tx: cx - ((cx - view.value.tx) * next) / current,
    ty: cy - ((cy - view.value.ty) * next) / current,
  }
}

/** 复位视口：scale=1、平移归零 */
function resetViewport() {
  view.value = { scale: 1, tx: 0, ty: 0 }
}

defineExpose({ locate, zoomBy, resetViewport })

// 布局：props 的节点/边集合/布局算法变化即重算（immediate → setup 期内完成，SSR 首屏有坐标）
watch(
  () => [props.nodes, props.edges, props.layout],
  () => runLayout(props.nodes, props.edges),
  { immediate: true },
)
</script>

<style scoped>
/* 画布基础样式（graph-tokens.css 里同名规则作用于 .kb-graph-pane 作用域，
   此处自带一份等价定义，使弹窗等无该作用域的宿主也正确呈现） */
.kg-canvas {
  position: relative;
  overflow: hidden;
}
.kg-canvas__scroll {
  width: 100%;
  height: 100%;
}
.kg-canvas--spread .kg-canvas__scroll {
  overflow: auto;
}
/* 铺开模式：画布本体是固定视口，内部滚动区随内容外扩（超出出滚动条） */
.kg-canvas--spread {
  height: 560px;
}
.kg-canvas__svg {
  display: block;
  width: 100%;
  height: auto;
  touch-action: none;
}
/* 视口控制按钮组：右上角覆盖，与 hint 胶囊同风格的小型描边按钮 */
.kg-canvas__zoom {
  position: absolute;
  top: 10px;
  right: 10px;
  display: flex;
  gap: 4px;
  z-index: 3;
}
.kg-canvas__zoom button {
  width: 26px;
  height: 24px;
  padding: 0;
  border: 1px solid var(--kg-border);
  border-radius: var(--kg-r-xs);
  background: #fff;
  color: var(--kg-text-2);
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
}
.kg-canvas__zoom button:hover {
  color: var(--kg-text);
  background: var(--kg-subtle);
}
</style>
