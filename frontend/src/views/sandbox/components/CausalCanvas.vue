<template>
  <div class="col">
    <div class="ptabs">
      <button v-for="t in canvasTabs" :key="t.k" class="ptab" :class="{ on: cview === t.k }" @click="emit('set-view', t.k)">{{ t.label }}</button>
    </div>
    <div class="canvas-wrap" @click.self="emit('close-detail')">
      <div class="cbar">
        <button class="btn sm pri" :disabled="!world" @click="emit('open-action')">⚡ 施加行动</button>
        <span class="sep"></span>
        <button class="btn sm" @click="emit('zoom', -1)">－</button>
        <button class="btn sm" @click="emit('zoom', 1)">＋</button>
        <button class="btn sm" @click="emit('fit')">复位</button>
      </div>
      <svg id="canvas" viewBox="0 0 960 460" preserveAspectRatio="xMidYMid meet">
        <defs>
          <marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="rgba(140,192,255,.35)"/></marker>
          <marker id="arh" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="rgba(180,142,240,.9)"/></marker>
        </defs>
        <g :transform="`translate(0,20) scale(${zoomK})`">
          <g v-for="(e, i) in canvasEdges" :key="'e' + i">
            <path :d="e.path" fill="none" :stroke="e.active ? 'rgba(180,142,240,.85)' : 'rgba(140,192,255,.18)'" :stroke-width="e.active ? 2 : 1.1" :marker-end="`url(#${e.active ? 'arh' : 'ar'})`"/>
            <rect :x="e.mx - e.wl / 2" :y="e.my - 20" :width="e.wl" height="13" rx="3.5" fill="rgba(7,17,31,.92)" :stroke="e.active ? 'rgba(180,142,240,.4)' : 'rgba(140,192,255,.14)'"/>
            <text :x="e.mx" :y="e.my - 10" text-anchor="middle" font-size="9.5" :fill="e.active ? '#c9aaff' : '#5a7a9a'">{{ e.label }}</text>
          </g>
          <g v-for="n in canvasNodes" :key="n.entity_code" class="n-box" @click.stop="emit('pick', n.entity_code)" :transform="`translate(${n.x},${n.y})`">
            <polygon v-if="n.isEvent" points="46,0 92,22 46,44 0,22" :fill="'rgba(180,142,240,.16)'" :stroke="selectedEntity === n.entity_code ? '#fff' : '#b48ef0'" :stroke-width="selectedEntity === n.entity_code ? 2.5 : 1.4"/>
            <text v-if="n.isEvent" x="46" y="19" text-anchor="middle" font-size="10.5" font-weight="600" fill="#eadcff">{{ n.name }}</text>
            <text v-if="n.isEvent" x="46" y="31" text-anchor="middle" font-size="8.5" fill="#b48ef0">SimEvent</text>
            <template v-else>
              <rect :width="156" :height="46" rx="10" :fill="n.masked ? 'rgba(123,139,164,.14)' : 'rgba(74,163,255,.12)'" :stroke="selectedEntity === n.entity_code ? '#fff' : (n.masked ? '#7b8ba4' : '#4aa3ff')" :stroke-width="selectedEntity === n.entity_code ? 2.5 : 1.3"/>
              <rect x="0" y="0" width="3.5" :height="46" rx="2" :fill="n.masked ? '#7b8ba4' : '#4aa3ff'"/>
              <text x="12" y="18" font-size="11.5" font-weight="600" fill="#d6e9ff">{{ n.name }}</text>
              <text x="12" y="33" font-size="9" fill="#8fa8c6">{{ n.entity_code }} · {{ n.object_code }}</text>
              <text v-if="n.masked" :x="146" y="18" text-anchor="end" font-size="10" fill="#7b8ba4">🔒 脱敏</text>
              <template v-else>
                <circle :cx="142" cy="15" r="5" :fill="n.riskColor"/>
                <text :x="132" y="18" text-anchor="end" font-size="9.5" :fill="n.riskColor">{{ n.risk.toFixed(2) }}</text>
              </template>
            </template>
          </g>
        </g>
      </svg>
      <div class="legend">
        <span><i style="background:#4aa3ff"></i>实体</span>
        <span><i style="background:#b48ef0"></i>事件/行动</span>
        <span><i style="background:#ff7b72"></i>风险</span>
        <span style="color:var(--fg3)">边随 Tick 逐级点亮因果链</span>
      </div>
      <div class="hint">{{ canvasHint }}</div>
      <div class="loading-veil" :class="{ on: veil }"><div class="spin"></div><span>世界状态重算中…</span></div>
      <div class="ndetail" :class="{ on: !!detail }" v-if="detail">
        <h4><span :style="{ width: '9px', height: '9px', borderRadius: '3px', display: 'inline-block', background: detail.masked ? '#7b8ba4' : (detail.isEvent ? '#b48ef0' : '#4aa3ff') }"></span>{{ detail.name }} <span class="mono" style="font-size:10px;color:var(--fg3)">{{ detail.entity_code }}</span></h4>
        <div class="kvt"><span class="k">类型</span><span class="v">{{ detail.object_code }}</span></div>
        <div class="kvt" v-if="detail.masked"><span class="k">视野/脱敏</span><span class="v" style="color:var(--err)">受限 🔒</span></div>
        <div class="kvt" v-else><span class="k">风险评分</span><span class="v" :style="{ color: detail.riskColor }">{{ detail.risk.toFixed(2) }}</span></div>
        <div class="kvt" v-for="(v, k) in detail.props" :key="k"><span class="k">{{ k }}</span><span class="v">{{ v }}</span></div>
        <div class="kvt"><span class="k">来源</span><span class="v">{{ detail.origin }}</span></div>
        <div class="kvt" v-if="detail.source_ref && !detail.masked">
          <span class="k">数据资产</span>
          <span class="v">{{ sourceRefText(detail.source_ref) }}</span>
        </div>
        <div style="display:flex;gap:6px;margin-top:9px">
          <button class="btn sm" style="flex:1" :disabled="detail.can_act === false" @click="emit('open-action-for', detail.entity_code)">
            {{ detail.can_act === false ? '不可施加' : '施加行动' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CausalEdge, WorldView } from '@/api/sandbox'
import { buildCanvasEdges, buildCanvasLayout, type LayoutNode } from '../sandboxView'

// 推演画布列（col ②）：四视图 Tab + SVG 布局 + 节点详情浮层。
// 布局与边解析全部走 sandboxView 纯函数；游标与详情数据由壳注入。
type CanvasView = 'world' | 'onto' | 'causal' | 'inst'
type DetailNode = LayoutNode & { can_act?: boolean }

const props = withDefaults(defineProps<{
  world: WorldView | null
  tick: number
  cview: CanvasView
  zoomK: number
  selectedEntity: string | null
  detail: DetailNode | null
  veil?: boolean
}>(), { veil: false })

const emit = defineEmits<{
  (e: 'set-view', v: CanvasView): void
  (e: 'zoom', dir: number): void
  (e: 'fit'): void
  (e: 'pick', code: string): void
  (e: 'close-detail'): void
  (e: 'open-action'): void
  (e: 'open-action-for', code: string): void
}>()

const canvasTabs = [
  { k: 'world', label: '世界概览' }, { k: 'onto', label: '本体结构' },
  { k: 'causal', label: '因果传播' }, { k: 'inst', label: '实例探索' },
] as const

const canvasHint = computed(() => ({
  world: '世界概览：克隆自本体建模的完整子图快照',
  onto: '本体结构：对象/关系类型层（非实例）',
  causal: '点击节点查看属性与来源 · 随 Tick 逐级点亮因果链',
  inst: '实例探索：按对象/关系筛选查看具体实例',
}[props.cview]))

const canvasNodes = computed<LayoutNode[]>(() => buildCanvasLayout(props.world?.entities ?? []))

// onto 视图取关系类型层（link_type_code 作边标签），其余视图取因果边
const edgeSource = computed<CausalEdge[]>(() => {
  const w = props.world
  if (!w) return []
  if (props.cview === 'onto') {
    return w.relations.map(r => ({
      code: r.rel_code, label: r.link_type_code,
      from_ref: r.from_entity_code, to_ref: r.to_entity_code, activation_tick: 0,
    }))
  }
  return w.causal_edges
})

const canvasEdges = computed(() => buildCanvasEdges(canvasNodes.value, edgeSource.value, props.tick))

const sourceRefText = (ref: Record<string, any>): string =>
  `${ref.db ?? ''}${ref.db ? '.' : ''}${ref.table ?? ''}${ref.pk != null ? ' · pk=' + ref.pk : ''}` || '—'
</script>
