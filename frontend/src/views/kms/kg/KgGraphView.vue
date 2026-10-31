<template>
  <div class="kg-graph-view">
    <!-- 工具栏：模式分段 + 类型/关系筛选 + 跳数 + 节点上限 + 隐藏 Chunk -->
    <div class="kg-toolbar">
      <div class="kg-toolbar__l">
        <div class="kg-seg">
          <span
            v-for="m in MODES"
            :key="m.value"
            class="kg-seg__item"
            :class="{ 'kg-seg__item--on': mode === m.value }"
            @click="switchMode(m.value)"
          >
            {{ t(m.label) }}
          </span>
        </div>
        <a-select
          v-model:value="typeFilter"
          size="small"
          style="width: 156px"
          :options="typeOptions"
          @change="reload"
        />
        <a-select
          v-model:value="relationFilter"
          size="small"
          style="width: 168px"
          :options="relationOptions"
          @change="reload"
        />
        <a-select
          v-model:value="depth"
          size="small"
          style="width: 92px"
          :options="depthOptions"
          :disabled="mode !== 'seed'"
          @change="reload"
        />
        <a-input-number
          v-model:value="limit"
          :min="20"
          :max="1000"
          :step="50"
          size="small"
          style="width: 92px"
          @change="reload"
        />
        <a-checkbox v-model:checked="hideChunk">{{ t('kbMgmt.kg.hideChunk') }}</a-checkbox>
      </div>
      <div class="kg-toolbar__r">
        <span class="kg-muted">
          {{ t('kbMgmt.kg.nodeEdgeCount', { nodes: visNodes.length, edges: visEdges.length }) }}
        </span>
        <a-button size="small" :disabled="selectedNodeId === null" @click="expandFromSeed">
          {{ t('kbMgmt.kg.expandFromSeed') }}
        </a-button>
        <a-dropdown :trigger="['click']">
          <a-button size="small" :loading="exporting">{{ t('kbMgmt.kg.exportGraph') }}</a-button>
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
      <!-- 画布：点阵底 + 原生 SVG（贝塞尔边 / 半径随度数 / 邻接聚焦） -->
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
              :class="{ 'is-hl': isAdjacentEdge(e), 'is-on': e.id === selectedEdgeId }"
            >
              <path class="kg-edge__hit" :d="e.d" @click.stop="selectEdge(e.id)" />
              <path class="kg-edge__line" :d="e.d" />
              <text
                v-if="showEdgeLabel(e)"
                class="kg-edge__label"
                :x="e.lx"
                :y="e.ly"
                text-anchor="middle"
              >
                {{ e.label }}
              </text>
            </g>

            <g
              v-for="n in visNodes"
              :key="`n-${n.id}`"
              class="kg-node"
              :class="{ 'is-on': n.id === selectedNodeId }"
              :style="{ opacity: nodeOpacity(n) }"
              @pointerenter="hoverId = n.id"
              @pointerleave="hoverId = null"
              @pointerdown.stop="onNodeDown($event, n)"
            >
              <circle :cx="n.x" :cy="n.y" :r="n.r" :fill="n.color" />
              <template v-if="showNodeLabel(n)">
                <text class="kg-node__name" :x="n.x" :y="n.y + n.r + 21" text-anchor="middle">
                  {{ n.name }}
                </text>
                <text
                  class="kg-node__type"
                  :x="n.x"
                  :y="n.y + n.r + 33"
                  text-anchor="middle"
                  :style="{ fill: n.color }"
                >
                  {{ n.typeLabel }}
                </text>
              </template>
            </g>
          </g>
        </svg>

        <div v-if="loading" class="kg-canvas__mask"><a-spin size="small" /></div>

        <!-- 空态：种子模式未选种子 / 当前筛选无节点 -->
        <div v-if="!loading && !visNodes.length" class="kg-canvas__empty">
          <div class="kg-canvas__empty-t">
            {{ mode === 'seed' ? t('kbMgmt.kg.noSelectionAny') : t('kbMgmt.kg.noData') }}
          </div>
          <p>{{ mode === 'seed' ? t('kbMgmt.kg.graphEmpty') : t('kbMgmt.kg.graphNotBuiltDesc') }}</p>
          <a-button v-if="mode === 'seed'" size="small" @click="switchMode('full')">
            {{ t('kbMgmt.kg.graphModeFull') }}
          </a-button>
        </div>

        <div class="kg-canvas__hint">{{ t('kbMgmt.kg.graphHint') }}</div>
        <div v-if="legend.length" class="kg-canvas__legend">
          <span v-for="item in legend" :key="item.code">
            <i :style="{ background: item.color }" />{{ item.label }}
          </span>
          <span class="kg-muted">{{ t('kbMgmt.kg.legendNodeSize') }}</span>
        </div>
      </div>

      <!-- 306px 内联检视面板（实体 / 关系双形态） -->
      <KgInspector
        :knowledge-id="knowledgeId"
        :selection="selection"
        @inspect-entity="selectEntity"
        @inspect-relation="selectEdge"
        @locate="selectEntity"
        @provenance="onProvenance"
        @reviewed="reload"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 图谱画布：原生 SVG 静态力导向（零图库依赖，对齐原型 kg-knowledge-base-preview.html）。
 *
 * - 布局：Fruchterman-Reingold，黄金角撒点做确定性初值，布局后整体归一到画布内；
 * - 视觉：节点半径随度数放大、边为二次贝塞尔（曲率 0.12）+ 边标签；
 * - 交互：点节点/边 -> 右侧检视面板；选中节点后 1 跳邻居保留、其余淡化；
 *         滚轮缩放、空白处拖拽平移、节点可拖动。
 * - 取数：全库图走 /graph/full（按度数截断），种子子图走 /graph/subgraph。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import * as api from '@/api/kg'
import type { KgGraphEdge, KgGraphNode, KgSubgraph } from '@/api/kg'
import { typeLabel as typeName, typeTone } from '@/components/common/graph/graphTheme'
import KgInspector from './KgInspector.vue'

const props = defineProps<{ knowledgeId: number }>()
const emit = defineEmits<{ (e: 'provenance', entityId: number): void }>()

const { t } = useI18n()

/** 画布坐标系（与原型 790×490 一致，实际按容器宽度等比缩放） */
const VB_W = 790
const VB_H = 490
const MIN_SCALE = 0.6
const MAX_SCALE = 3.2
/** 超过该节点数时只给枢纽/选中/邻居画标签，避免文字糊成一团 */
const LABEL_ALL_MAX = 60

type Mode = 'full' | 'type' | 'seed'
const MODES: { value: Mode; label: string }[] = [
  { value: 'full', label: 'kbMgmt.kg.graphModeFull' },
  { value: 'type', label: 'kbMgmt.kg.graphModeType' },
  { value: 'seed', label: 'kbMgmt.kg.graphModeSeed' },
]

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

const rawNodes = ref<KgGraphNode[]>([])
const rawEdges = ref<KgGraphEdge[]>([])
const positions = ref<Record<number, Pt>>({})
const degrees = ref<Record<number, number>>({})
const loading = ref(false)
const exporting = ref(false)
const hoverId = ref<number | null>(null)
const selection = ref<{ kind: 'node' | 'edge'; id: number } | null>(null)

const mode = ref<Mode>('full')
const typeFilter = ref<string>('')
const relationFilter = ref<string>('')
const depth = ref(2)
const limit = ref(200)
const hideChunk = ref(true)
const seeds = ref<number[]>([])
const view = ref({ scale: 1, tx: 0, ty: 0 })
const typeOptions = ref<{ label: string; value: string }[]>([])
const relationOptions = ref<{ label: string; value: string }[]>([])

const canvasRef = ref<HTMLElement | null>(null)

const depthOptions = computed(() => [
  { label: `${t('kbMgmt.kg.depthLabel')} 1`, value: 1 },
  { label: `${t('kbMgmt.kg.depthLabel')} 2`, value: 2 },
  { label: `${t('kbMgmt.kg.depthLabel')} 3`, value: 3 },
])

/** Chunk / 切片节点：图谱里通常是噪音，默认隐藏 */
function isChunkNode(node: KgGraphNode) {
  const code = (node.code || node.type_code || '').toUpperCase()
  return code.includes('CHUNK') || code.includes('SEGMENT')
}

const visNodes = computed<VisNode[]>(() => {
  const out: VisNode[] = []
  rawNodes.value.forEach((node) => {
    const pos = positions.value[node.id]
    if (!pos) return
    if (hideChunk.value && isChunkNode(node)) return
    const code = node.code || node.type_code || ''
    // 种子子图的接口没有类型过滤参数，前端补一道
    if (mode.value === 'seed' && typeFilter.value && code !== typeFilter.value) return
    const deg = degrees.value[node.id] || 0
    out.push({
      id: node.id,
      name: node.name,
      code,
      typeLabel: typeName(code),
      color: typeTone(code).color,
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
  rawEdges.value.forEach((edge) => {
    const a = map.get(edge.from)
    const b = map.get(edge.to)
    if (!a || !b) return
    if (relationFilter.value && edge.relation_type !== relationFilter.value) return
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
      label: edge.relation_type || edge.predicate || '',
      d: `M${a.x.toFixed(1)},${a.y.toFixed(1)} Q${cx.toFixed(1)},${cy.toFixed(1)} ${b.x.toFixed(1)},${b.y.toFixed(1)}`,
      lx: 0.25 * a.x + 0.5 * cx + 0.25 * b.x,
      ly: 0.25 * a.y + 0.5 * cy + 0.25 * b.y,
    })
  })
  return out
})

const selectedNodeId = computed(() =>
  selection.value?.kind === 'node' ? selection.value.id : null,
)
const selectedEdgeId = computed(() =>
  selection.value?.kind === 'edge' ? selection.value.id : null,
)

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

function nodeOpacity(node: VisNode) {
  const id = selectedNodeId.value
  if (id === null || id === node.id) return 1
  return neighborIds.value.has(node.id) ? 1 : 0.35
}

function showNodeLabel(node: VisNode) {
  if (visNodes.value.length <= LABEL_ALL_MAX) return true
  return (
    node.id === selectedNodeId.value ||
    node.id === hoverId.value ||
    neighborIds.value.has(node.id) ||
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

function onProvenance(entityId: number) {
  emit('provenance', entityId)
}

/**
 * 静态力导向布局（Fruchterman-Reingold）+ 归一化。
 * 结果写回 positions/degrees，只触发一次渲染，不做逐帧动画。
 */
function runLayout() {
  const nodes = rawNodes.value
  const n = nodes.length
  const idSet = new Set(nodes.map((x) => x.id))
  const links = rawEdges.value.filter((e) => idSet.has(e.from) && idSet.has(e.to))

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

async function reload() {
  loading.value = true
  try {
    let res: KgSubgraph | undefined
    if (mode.value === 'seed') {
      if (!seeds.value.length) {
        rawNodes.value = []
        rawEdges.value = []
        positions.value = {}
        degrees.value = {}
        return
      }
      res = await api.getSubgraph(props.knowledgeId, seeds.value, depth.value, limit.value)
    } else {
      res = await api.getFullGraph(props.knowledgeId, {
        limit: limit.value,
        typeCode: typeFilter.value,
        relationCode: relationFilter.value,
      })
    }
    rawNodes.value = res?.nodes || []
    rawEdges.value = res?.edges || []
    // 悬空边（端点不在节点集里）直接丢弃，避免力导向出现虚点
    const keep = new Set(rawNodes.value.map((x) => x.id))
    rawEdges.value = rawEdges.value.filter((e) => keep.has(e.from) && keep.has(e.to))
    view.value = { scale: 1, tx: 0, ty: 0 }
    runLayout()
  } catch {
    rawNodes.value = []
    rawEdges.value = []
    positions.value = {}
    degrees.value = {}
  } finally {
    loading.value = false
  }
}

async function loadFacets() {
  const [labelsRes, statsRes] = await Promise.allSettled([
    api.getLabels(props.knowledgeId),
    api.getGraphStats(props.knowledgeId),
  ])
  if (labelsRes.status === 'fulfilled') {
    const items = labelsRes.value?.items || []
    typeOptions.value = [
      { label: t('kbMgmt.kg.entityTypeAll'), value: '' },
      ...items
        .filter((i) => !!i.code)
        .sort((a, b) => b.count - a.count)
        .map((i) => ({ label: `${typeName(i.code) || i.code}（${i.count}）`, value: i.code })),
    ]
  }
  if (statsRes.status === 'fulfilled') {
    const byRelation = statsRes.value?.by_relation || {}
    relationOptions.value = [
      { label: t('kbMgmt.kg.relationTypeAll'), value: '' },
      ...Object.entries(byRelation)
        .filter(([key]) => !!key)
        .sort((a, b) => b[1] - a[1])
        .map(([key, count]) => ({ label: `${key}（${count}）`, value: key })),
    ]
  }
}

function switchMode(next: Mode) {
  if (mode.value === next) return
  mode.value = next
  selection.value = null
  // 「按类型过滤」要求先有类型：未选时自动落到第一个出现的类型
  if (next === 'type' && !typeFilter.value) {
    const first = typeOptions.value.find((o) => !!o.value)
    if (first) typeFilter.value = first.value
  }
  void reload()
}

function selectNode(id: number) {
  selection.value = { kind: 'node', id }
}

function selectEdge(id: number) {
  selection.value = { kind: 'edge', id }
}

/** 供父组件调用：在图谱中定位并选中实体（不在当前视图则改用种子子图） */
async function selectEntity(id: number) {
  if (!rawNodes.value.some((n) => n.id === id)) {
    seeds.value = [id]
    mode.value = 'seed'
    await reload()
  }
  selection.value = { kind: 'node', id }
}

/** 供父组件调用：以若干实体为种子重画 */
async function focusEntities(ids: number[]) {
  if (!ids.length) return
  seeds.value = [...ids]
  mode.value = 'seed'
  await reload()
  selection.value = { kind: 'node', id: ids[0] }
}

function expandFromSeed() {
  const id = selectedNodeId.value
  if (id === null) {
    message.warning(t('kbMgmt.kg.seedPickFirst'))
    return
  }
  seeds.value = [id]
  mode.value = 'seed'
  void reload()
}

async function onExport(info: { key: string }) {
  const fmt = info.key === 'csv' ? 'csv' : 'json'
  exporting.value = true
  try {
    const payload: any = await api.exportGraph(props.knowledgeId, fmt)
    const content =
      fmt === 'csv' ? String(payload?.content || '') : JSON.stringify(payload ?? {}, null, 2)
    const name = `kb-${props.knowledgeId}-graph.${fmt}`
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
    message.success(t('kbMgmt.kg.exported', { name }))
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.actionFailed'))
  } finally {
    exporting.value = false
  }
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
  if (!state.moved) selection.value = null
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

watch(
  () => props.knowledgeId,
  () => {
    selection.value = null
    seeds.value = []
    void loadFacets()
    void reload()
  },
)

onMounted(() => {
  void loadFacets()
  void reload()
})

defineExpose({ selectEntity, selectEdge, focusEntities, reload })
</script>
