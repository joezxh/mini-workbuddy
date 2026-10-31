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

/** 画布坐标系（与原型 790×490 一致，实际按容器宽度等比缩放） */
const VB_W = 790
const VB_H = 490
const MIN_SCALE = 0.6
const MAX_SCALE = 3.2
/** 超过该节点数时只给枢纽/选中/邻居画标签，避免文字糊成一团 */
const LABEL_ALL_MAX = 60

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
      r: Math.min(52, 15 + deg * 4.2),
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
    // 二次贝塞尔：控制点沿法线偏移 12%，与原型曲率一致
    const mx = (a.x + b.x) / 2
    const my = (a.y + b.y) / 2
    const dx = b.x - a.x
    const dy = b.y - a.y
    const cx = mx - dy * 0.12
    const cy = my + dx * 0.12
    out.push({
      id: edge.id,
      from: edge.from,
      to: edge.to,
      label: edge.label,
      d: `M${a.x.toFixed(1)},${a.y.toFixed(1)} Q${cx.toFixed(1)},${cy.toFixed(1)} ${b.x.toFixed(1)},${b.y.toFixed(1)}`,
      lx: 0.25 * a.x + 0.5 * cx + 0.25 * b.x,
      ly: 0.25 * a.y + 0.5 * cy + 0.25 * b.y,
    })
  })
  return out
})

const selectedNodeId = computed(() => (props.selection?.kind === 'node' ? props.selection.id : null))
const selectedEdgeId = computed(() => (props.selection?.kind === 'edge' ? props.selection.id : null))

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
  if (visNodes.value.length <= LABEL_ALL_MAX) return true
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
  if (visEdges.value.length <= 40) return true
  const id = selectedNodeId.value
  return id !== null && (edge.from === id || edge.to === id)
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

  const cx = VB_W / 2
  const cy = VB_H / 2
  // 黄金角螺旋撒点：确定性初值，避免对称初始位形导致的不动点
  const pts = nodes.map((node, i) => {
    const angle = i * 2.399963229728653
    const rad = Math.min(VB_W, VB_H) * 0.4 * Math.sqrt((i + 0.5) / n)
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

  const k = Math.sqrt((VB_W * VB_H * 0.55) / n)
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
  const scale = Math.min((VB_W - 112) / spanX, (VB_H - 96) / spanY, n > 1 ? 3 : 1)
  const midX = (minX + maxX) / 2
  const midY = (minY + maxY) / 2

  const next: Record<number, Pt> = {}
  pts.forEach((p) => {
    next[p.id] = {
      x: VB_W / 2 + (p.x - midX) * scale,
      y: VB_H / 2 + (p.y - midY) * scale,
    }
  })
  positions.value = next
}

// ── 指针交互：缩放 / 平移 / 拖节点 / 选中 ──────────────────────────────

type DragState =
  | { kind: 'node'; id: number; moved: boolean; total: number; lastVB: Pt; lastW: Pt }
  | { kind: 'pan'; moved: boolean; total: number; lastVB: Pt }
  | null

let drag: DragState = null

function toViewBox(clientX: number, clientY: number): Pt {
  const el = canvasRef.value
  if (!el) return { x: 0, y: 0 }
  const rect = el.getBoundingClientRect()
  return {
    x: ((clientX - rect.left) / Math.max(1, rect.width)) * VB_W,
    y: ((clientY - rect.top) / Math.max(1, rect.height)) * VB_H,
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
