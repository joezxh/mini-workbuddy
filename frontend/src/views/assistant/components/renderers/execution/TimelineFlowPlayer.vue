<!--
  TimelineFlowPlayer.vue — 时间线动态流程图播放器（metaso 风格 · 横向工作流）

  - 主视图：从左到右的横向流程图，串行步骤沿主干依次推进；
    并行批次（服务端 exec_mode=parallel + group_id）渲染为上下分支泳道，
    分支判断/汇聚点（exec_mode=branch）渲染为菱形节点，完整还原服务端 agent 执行形式
  - 控制栏：播放/暂停、重播、进度指示；流式模式自动实时跟随（无需手动播放）
  - 底部事件横轴：刻度与顶层阶段序列一一对应，可点击跳转
  - 步骤/产物按 seq 合并为统一事件序列，状态着色（执行中/完成/失败/提醒）
-->
<template>
  <div class="flow-player" :class="{ 'many-steps': manySteps }">
    <!-- 控制栏 -->
    <div class="fp-controls">
      <template v-if="!streaming">
        <button class="fp-ctrl-btn" :title="playing ? '暂停' : '播放'" @click="togglePlay">
          <PauseOutlined v-if="playing" />
          <CaretRightOutlined v-else />
        </button>
        <button class="fp-ctrl-btn fp-ctrl-replay" title="重播" @click="replay">
          <ReloadOutlined />
        </button>
      </template>
      <span v-else class="fp-live-badge"><LoadingOutlined spin /> 实时同步中</span>
      <span class="fp-progress">{{ litCount }} / {{ stages.length }}</span>
      <span v-if="activeStage" class="fp-active-title" :title="activeStage.title">{{ activeStage.title }}</span>

      <!-- 缩放控制：缩放仅改变横向布局比例，便于纵览长流程或细看分支 -->
      <span class="fp-zoom" title="缩放时间线">
        <button class="fp-zoom-btn" :disabled="zoom <= ZOOM_MIN" title="缩小" @click="zoomOut">−</button>
        <span class="fp-zoom-val">{{ Math.round(zoom * 100) }}%</span>
        <button class="fp-zoom-btn" :disabled="zoom >= ZOOM_MAX" title="放大" @click="zoomIn">＋</button>
        <button class="fp-zoom-btn fp-zoom-reset" title="重置缩放" @click="zoomReset">⤢</button>
      </span>

      <!-- 状态图例 -->
      <span class="fp-legend" title="状态图例">
        <span class="fp-legend-item" v-for="lg in LEGEND" :key="lg.k">
          <i class="fp-legend-dot" :class="`lg-${lg.k}`" />{{ lg.t }}
        </span>
      </span>
    </div>

    <!-- 横向流程图（可缩放内层：zoom 仅放大横向布局，滚动条随之变化）
         支持鼠标滚轮缩放 + 拖拽平移 -->
    <div
      class="fp-flow"
      ref="flowRef"
      @wheel.prevent="onWheel"
      @mousedown="onPanStart"
    >
      <div class="fp-flow-inner" :style="{ zoom }">
      <template v-for="(stage, i) in stages" :key="stage.key">
        <!-- 连接箭头（首节点前不放） -->
        <span
          v-if="i > 0"
          class="fp-arrow"
          :class="{ lit: i < litCount, flowing: playing && i === litCount }"
        >→</span>

        <!-- 并行分支树（深度研究式分叉结构）：分叉起点 → 主干脊线 → 各子分支 → 汇聚点 -->
        <div
          v-if="stage.kind === 'parallel'"
          class="fp-pgroup"
          :class="[stageClass(i), { 'concurrent-active': concurrentActive(i) }]"
          :data-idx="i"
          @click="jumpTo(i)"
        >
          <div class="fp-pgroup-note" v-if="stage.branchNote">{{ stage.branchNote }}</div>
          <div class="fp-pgroup-lane">
            <!-- 分叉起点：主干在此一分为 N -->
            <div class="fp-fork-node fp-fork-split" title="并行分叉起点">
              <svg viewBox="0 0 16 16" class="fp-fork-glyph"><path d="M8 2 V6 M8 6 L4 14 M8 6 L12 14" /></svg>
            </div>
            <!-- 树形连线 + 分支列：SVG 按分支数确定性绘制主干与横向分流短线（无需测量 DOM） -->
            <div class="fp-tree-col">
              <svg class="fp-tree-svg" viewBox="0 0 28 100" preserveAspectRatio="none">
                <line class="fp-spine" x1="14" y1="0" x2="14" y2="100" />
                <line
                  v-for="(m, j) in stage.members"
                  :key="'c-' + m.key"
                  class="fp-branch-line"
                  x1="14"
                  :y1="(j + 0.5) / stage.members.length * 100"
                  x2="28"
                  :y2="(j + 0.5) / stage.members.length * 100"
                />
              </svg>
              <div class="fp-branch-col">
                <div
                  v-for="m in stage.members"
                  :key="m.key"
                  class="fp-branch-node"
                  :class="memberClass(m, stage, i)"
                  @mouseenter="showTip($event, m, stage, i)"
                  @mousemove="moveTip($event)"
                  @mouseleave="hideTip()"
                >
                  <span class="fp-branch-dot" :class="`ic-${memberState(m)}`">
                    <LoadingOutlined v-if="memberState(m) === 'running'" spin />
                    <CheckOutlined v-else-if="memberState(m) === 'done'" />
                    <CloseOutlined v-else-if="memberState(m) === 'failed'" />
                    <ExclamationOutlined v-else-if="memberState(m) === 'warn'" />
                  </span>
                  <span class="fp-branch-label">{{ m.branchLabel || m.title }}</span>
                  <span v-if="m.elapsedMs != null" class="fp-branch-elapsed">{{ formatDuration(m.elapsedMs) }}</span>
                </div>
              </div>
            </div>
            <!-- 汇聚点：各分支在此合并回主干 -->
            <div class="fp-fork-node fp-fork-merge" title="并行汇聚点">
              <svg viewBox="0 0 16 16" class="fp-fork-glyph"><path d="M4 2 L8 10 M12 2 L8 10 M8 10 V14" /></svg>
            </div>
          </div>
          <div class="fp-pgroup-caption" :class="{ 'cap-live': concurrentActive(i) }">
            <span class="fp-cap-dot" v-if="concurrentActive(i)" />
            并行 × {{ stage.members.length }}
            <span v-if="concurrentActive(i)" class="fp-cap-conc">· 并发执行中</span>
            <span v-else class="fp-cap-done">· 已汇聚</span>
          </div>
        </div>

        <!-- 分支判断/汇聚节点（菱形） -->
        <div
          v-else-if="stage.kind === 'branch'"
          class="fp-node fp-diamond"
          :class="stageClass(i)"
          :data-idx="i"
          :title="stage.branchNote || stage.title"
          @click="jumpTo(i)"
          @mouseenter="showTip($event, stage.node, stage, i)"
          @mousemove="moveTip($event)"
          @mouseleave="hideTip()"
        >
          <span class="fp-node-icon" :class="`ic-${stageState(i)}`">
            <LoadingOutlined v-if="stageState(i) === 'running'" spin />
            <CheckOutlined v-else-if="stageState(i) === 'done'" />
            <CloseOutlined v-else-if="stageState(i) === 'failed'" />
            <ExclamationOutlined v-else-if="stageState(i) === 'warn'" />
            <span v-else class="fp-node-seq">{{ i + 1 }}</span>
          </span>
          <span class="fp-node-title">{{ stage.title }}</span>
        </div>

        <!-- 串行节点（竖卡） -->
        <div
          v-else
          class="fp-node fp-card"
          :class="stageClass(i)"
          :data-idx="i"
          @click="jumpTo(i)"
          @mouseenter="showTip($event, stage.node, stage, i)"
          @mousemove="moveTip($event)"
          @mouseleave="hideTip()"
        >
          <span class="fp-node-icon" :class="`ic-${stageState(i)}`">
            <LoadingOutlined v-if="stageState(i) === 'running'" spin />
            <CheckOutlined v-else-if="stageState(i) === 'done'" />
            <CloseOutlined v-else-if="stageState(i) === 'failed'" />
            <ExclamationOutlined v-else-if="stageState(i) === 'warn'" />
            <span v-else class="fp-node-seq">{{ i + 1 }}</span>
          </span>
          <span class="fp-node-phase">{{ stage.phase }}</span>
          <span class="fp-node-title">{{ stage.title }}</span>
          <span v-if="stage.node?.elapsedMs != null" class="fp-node-elapsed" :title="`步骤耗时 ${formatDuration(stage.node.elapsedMs)}`">{{ formatDuration(stage.node.elapsedMs) }}</span>
        </div>
      </template>
      <div v-if="!stages.length" class="fp-empty">暂无时间线记录</div>
      </div><!-- /.fp-flow-inner -->
      </div><!-- /.fp-flow -->

    <!-- 悬停详情浮层：置于缩放层之外，固定定位，避免被 zoom 扭曲 -->
    <div
      v-if="hoverVisible"
      class="fp-tip"
      :class="`tip-${hoverInfo.status}`"
      :style="{ left: tipX + 'px', top: tipY + 'px' }"
    >
      <div class="fp-tip-title">{{ hoverInfo.title }}</div>
      <div class="fp-tip-row"><span class="fp-tip-k">类型</span><span>{{ hoverInfo.kind }}</span></div>
      <div class="fp-tip-row" v-if="hoverInfo.branchLabel"><span class="fp-tip-k">分支</span><span>{{ hoverInfo.branchLabel }}</span></div>
      <div class="fp-tip-row"><span class="fp-tip-k">状态</span><span class="fp-tip-status" :class="`st-${hoverInfo.status}`">{{ hoverInfo.statusText }}</span></div>
      <div class="fp-tip-row" v-if="hoverInfo.elapsed"><span class="fp-tip-k">耗时</span><span>{{ hoverInfo.elapsed }}</span></div>
      <div class="fp-tip-row" v-if="hoverInfo.concurrent"><span class="fp-tip-k">并发</span><span class="fp-tip-conc">{{ hoverInfo.concurrent }}</span></div>
      <div class="fp-tip-detail" v-if="hoverInfo.detail">{{ hoverInfo.detail }}</div>
    </div>

    <!-- 当前聚焦阶段详情条 -->
    <div v-if="activeStage && activeStage.detail" class="fp-detail">{{ activeStage.detail }}</div>

    <!-- 底部事件横轴：刻度与顶层阶段序列一一对应 -->
    <div v-if="stages.length > 1" class="fp-axis">
      <div class="fp-axis-track">
        <div class="fp-axis-fill" :style="{ width: fillPercent }" />
        <span
          v-for="(stage, i) in stages"
          :key="'ax-' + stage.key"
          class="fp-axis-dot"
          :class="[`ax-${stageState(i)}`, { lit: i < litCount, active: i === activeIndex }]"
          :style="{ left: dotPercent(i) }"
          :title="`${i + 1}. ${stage.title}`"
          @click="jumpTo(i)"
        />
      </div>
      <div class="fp-axis-labels"><span>开始</span><span>结束</span></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import {
  CaretRightOutlined, PauseOutlined, ReloadOutlined, LoadingOutlined,
  CheckOutlined, CloseOutlined, ExclamationOutlined,
} from '@ant-design/icons-vue'
import type { UnifiedStep, UnifiedArtifact } from '../../types'

type FlowNode = {
  key: string
  kind: 'step' | 'artifact'
  phase: string
  title: string
  status: string
  detail?: string | null
  seq: number
  /** 步骤耗时（毫秒，来自服务端 StepEvent.elapsed_ms） */
  elapsedMs?: number | null
  /** 工作流执行形式（来自服务端 StepEvent）：serial | parallel | branch */
  execMode: 'serial' | 'parallel' | 'branch'
  /** 并行分组 ID：同组节点聚为同一分支泳道 */
  groupId: string | null
  /** 并行分支显示标签（如 worker 角色名） */
  branchLabel: string | null
  /** 分支判断说明 */
  branchNote: string | null
}

type FlowStage = {
  key: string
  kind: 'serial' | 'parallel' | 'branch'
  /** parallel 泳道的分支成员 */
  members: FlowNode[]
  /** serial / branch 单节点 */
  node: FlowNode | null
  title: string
  phase: string
  detail?: string | null
  branchNote: string | null
  seq: number
}

const props = withDefaults(defineProps<{
  /** 统一时间线步骤 */
  steps?: UnifiedStep[]
  /** 统一时间线产物（合并进事件序列） */
  artifacts?: UnifiedArtifact[]
  /** 流式模式：实时跟随最新事件，自动全部点亮 */
  streaming?: boolean
}>(), {
  steps: () => [],
  artifacts: () => [],
  streaming: false,
})

/** 播放时每个阶段点亮间隔（ms） */
const PLAY_INTERVAL = 700

/** 步骤过多阈值：超过该数量关闭逐步点亮动画，直接全部高亮（无灰度、无闪烁） */
const MANY_STEPS_THRESHOLD = 10

/** 缩放范围与步进：仅放大横向布局比例，便于纵览长流程或细看分支 */
const ZOOM_MIN = 0.3
const ZOOM_MAX = 3
const ZOOM_STEP = 0.2

/** 状态图例：悬停/缩放之外，右下角常驻说明四态含义 */
const LEGEND = [
  { k: 'running', t: '执行中' },
  { k: 'done', t: '完成' },
  { k: 'failed', t: '失败' },
  { k: 'warn', t: '提醒' },
]

const flowRef = ref<HTMLElement>()
/** 动画进度：已点亮阶段数 */
const litStageCount = ref(0)
/** 当前聚焦阶段索引 */
const activeIndex = ref(0)
const playing = ref(false)
let timer: ReturnType<typeof setInterval> | null = null
let autoplayDone = false

/** 缩放比例（作用于 .fp-flow-inner） */
const zoom = ref(1)
function zoomIn() { zoom.value = Math.min(ZOOM_MAX, +(zoom.value + ZOOM_STEP).toFixed(2)) }
function zoomOut() { zoom.value = Math.max(ZOOM_MIN, +(zoom.value - ZOOM_STEP).toFixed(2)) }
function zoomReset() { zoom.value = 1 }

/** 滚轮缩放：向上滚放大、向下滚缩小（仅改变横向布局比例，滚动条随之变化） */
function onWheel(e: WheelEvent) {
  const delta = e.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP
  zoom.value = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, +(zoom.value + delta).toFixed(2)))
}

/** 拖拽平移：在流程容器空白处按下拖动 = 滚动横向/纵向轴，便于纵览长流程 */
let panning = false
const panStart = { x: 0, y: 0, sl: 0, st: 0 }
function onPanStart(e: MouseEvent) {
  const el = flowRef.value
  if (!el || e.button !== 0) return
  // 点在可点击节点/分支上时交给其自身 click，不触发平移
  if ((e.target as HTMLElement).closest('.fp-node, .fp-branch-node, .fp-axis-dot')) return
  panning = true
  panStart.x = e.clientX
  panStart.y = e.clientY
  panStart.sl = el.scrollLeft
  panStart.st = el.scrollTop
  el.classList.add('fp-panning')
  window.addEventListener('mousemove', onPanMove)
  window.addEventListener('mouseup', onPanEnd)
}
function onPanMove(e: MouseEvent) {
  if (!panning) return
  const el = flowRef.value
  if (!el) return
  el.scrollLeft = panStart.sl - (e.clientX - panStart.x)
  el.scrollTop = panStart.st - (e.clientY - panStart.y)
}
function onPanEnd() {
  panning = false
  flowRef.value?.classList.remove('fp-panning')
  window.removeEventListener('mousemove', onPanMove)
  window.removeEventListener('mouseup', onPanEnd)
}

/** 悬停详情浮层状态（固定定位，不随 zoom 缩放） */
const hoverVisible = ref(false)
const tipX = ref(0)
const tipY = ref(0)
const hoverInfo = ref<{
  title: string
  kind: string
  branchLabel?: string | null
  status: string
  statusText: string
  elapsed?: string | null
  concurrent?: string | null
  detail?: string | null
}>({ title: '', kind: '', status: '', statusText: '' })

/** steps + artifacts 按 seq 合并为统一事件序列（保留工作流执行形式字段） */
const nodes = computed<FlowNode[]>(() => {
  const stepNodes: FlowNode[] = (props.steps || []).map(s => ({
    key: `s-${s.seq}-${s.title}`,
    kind: 'step' as const,
    phase: s.phase || '执行',
    title: s.title || '(未命名步骤)',
    status: s.status,
    detail: s.detail,
    seq: s.seq,
    elapsedMs: s.elapsed_ms ?? null,
    execMode: (s.exec_mode === 'parallel' || s.exec_mode === 'branch') ? s.exec_mode : 'serial',
    groupId: s.group_id ?? null,
    branchLabel: s.branch_label ?? null,
    branchNote: s.branch_note ?? null,
  }))
  const artNodes: FlowNode[] = (props.artifacts || []).map(a => ({
    key: `a-${a.artifact_id}`,
    kind: 'artifact' as const,
    phase: '产物',
    title: a.title || '产物',
    status: a.status,
    detail: a.error || a.suggestion || null,
    seq: a.seq,
    execMode: 'serial' as const,
    groupId: null,
    branchLabel: null,
    branchNote: null,
  }))
  return [...stepNodes, ...artNodes].sort((x, y) => x.seq - y.seq)
})

/**
 * 聚合顶层阶段序列：
 * - serial / artifact 节点 → 独立串行阶段
 * - 独立 branch 节点（无关联并行组）→ 菱形判断阶段
 * - 同一 group_id 的所有 parallel 节点 → 合并为「一个」分叉泳道阶段（多分支并列）
 *
 * 关键修复：真实数据中每个并行子问题会伴随一条标题相同的 exec_mode=serial
 * "叙述型"思考步骤，且穿插在并行步骤之间。旧逻辑遇到非 parallel 步骤就闭合分组，
 * 导致每个 group 被拆成大量单成员「大括号」。现改为：先按 group_id 跨整个序列
 * 聚合并行成员为一个多分支组，再在首个成员位置整体输出；同时过滤掉与并行步骤
 * 标题重复的串行噪声，保证分叉结构清晰、各子任务并列呈现。
 */
const stages = computed<FlowStage[]>(() => {
  const ns = nodes.value

  // 1) 收集所有并行步骤的标题，用于过滤与其逐字重复的"叙述型"串行步骤
  const parallelTitles = new Set<string>()
  for (const n of ns) if (n.execMode === 'parallel') parallelTitles.add(n.title)

  // 2) 按 group_id 聚合多分支组（不受中间串行步骤打断）
  type GroupRec = { members: FlowNode[]; firstSeq: number; branchNote: string | null; title: string }
  const groups = new Map<string, GroupRec>()
  const gidOf = (n: FlowNode) => n.groupId || `anon-${n.seq}`
  for (const n of ns) {
    if (n.execMode !== 'parallel') continue
    const gid = gidOf(n)
    const g = groups.get(gid)
    if (g) {
      // 同分支标签的更新事件（如 searching → done）合并为一行：后者状态覆盖前者
      const labelKey = n.branchLabel || n.key
      const idx = g.members.findIndex(m => (m.branchLabel || m.key) === labelKey)
      if (idx >= 0) g.members[idx] = n
      else g.members.push(n)
    } else {
      groups.set(gid, {
        members: [n],
        firstSeq: n.seq,
        branchNote: n.branchNote,
        title: n.title,
      })
    }
  }

  // 3) 按 seq 顺序产出阶段；并行组在其首个成员位置整体输出为分叉泳道
  const out: FlowStage[] = []
  const emittedGroups = new Set<string>()
  for (const n of ns) {
    if (n.execMode === 'parallel') {
      const gid = gidOf(n)
      if (emittedGroups.has(gid)) continue
      emittedGroups.add(gid)
      const g = groups.get(gid)!
      out.push({
        key: `pg-${gid}-${g.firstSeq}`,
        kind: 'parallel',
        members: g.members,
        node: null,
        title: g.title,
        phase: '并发检索',
        detail: g.members[0]?.detail ?? null,
        branchNote: g.branchNote,
        seq: g.firstSeq,
      })
      continue
    }
    if (n.execMode === 'branch') {
      out.push({
        key: n.key, kind: 'branch', members: [], node: n,
        title: n.title, phase: n.phase, detail: n.detail, branchNote: n.branchNote, seq: n.seq,
      })
      continue
    }
    // 串行：跳过与并行步骤逐字重复的"叙述型"步骤，避免噪声、让分叉更清晰
    if (parallelTitles.has(n.title)) continue
    out.push({
      key: n.key, kind: 'serial', members: [], node: n,
      title: n.title, phase: n.phase, detail: n.detail, branchNote: null, seq: n.seq,
    })
  }
  return out
})

const activeStage = computed(() => stages.value[activeIndex.value] || null)

/** 步骤过多：直接全部点亮，关闭逐步动画与灰度 */
const manySteps = computed(() => stages.value.length > MANY_STEPS_THRESHOLD)
/** 实际已点亮阶段数：步骤过多时恒为全部，否则取播放进度 */
const litCount = computed(() => manySteps.value ? stages.value.length : litStageCount.value)

/** 状态归一为四态（running/done/failed/warn）或 pending（未点亮） */
function normStatus(s: string): string {
  if (s === 'generating') return 'running'
  if (s === 'ready') return 'done'
  return ['running', 'done', 'failed', 'warn'].includes(s) ? s : 'pending'
}

/** 毫秒格式化：850ms / 1.2s / 1m05s */
function formatDuration(ms?: number | null): string {
  if (ms == null) return ''
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  const m = Math.floor(ms / 60000)
  const s = Math.round((ms % 60000) / 1000)
  return `${m}m${String(s).padStart(2, '0')}s`
}

function memberState(m: FlowNode): string {
  return normStatus(m.status)
}

/** 阶段状态 = 成员聚合：有失败即失败；有执行中即执行中；全完成即完成 */
function stageState(i: number): string {
  const st = stages.value[i]
  if (!st || i >= litCount.value) return 'pending'
  if (st.kind === 'parallel') {
    const states = st.members.map(memberState)
    if (states.includes('failed')) return 'failed'
    if (states.includes('running')) return 'running'
    if (states.includes('warn')) return 'warn'
    return 'done'
  }
  return normStatus(st.node?.status || 'pending')
}

function stageClass(i: number): Record<string, boolean> {
  const lit = litCount.value
  return {
    lit: i < lit,
    current: !manySteps.value && i === lit - 1 && lit > 0,
    active: i === activeIndex.value,
    pending: i >= lit,
  }
}

function statusText(s: string): string {
  return ({ running: '执行中', done: '完成', failed: '失败', warn: '提醒', pending: '未开始' } as Record<string, string>)[s] || s
}

/**
 * 并发执行窗口判断：并行分支组在"已点亮"且"仍有分支在执行中"时处于并发执行窗口。
 * - 该判定为纯响应式派生，所有并发分支在同一渲染帧内统一得到相同结果 → 同步高亮无延迟/无闪烁；
 * - 当全部分支结束则窗口关闭（caption 转为"已汇聚"）。
 */
function concurrentActive(i: number): boolean {
  const st = stages.value[i]
  if (!st || st.kind !== 'parallel') return false
  if (i >= litCount.value) return false
  return st.members.some(m => memberState(m) === 'running')
}

/**
 * 分支节点状态着色：
 * - nd-<status>：分支自身真实状态（执行中/完成/失败/提醒），与实际执行严格对齐；
 * - nd-glow：仅当整组处于并发执行窗口、且该分支仍在执行时才发光 → 同一时刻所有并发分支一起点亮；
 * - nd-early：当同组仍有分支在跑、而本分支已提前完成/提醒时，相对"收敛"显示，
 *   以视觉对比如实反映"部分分支已结束、其余仍在并发执行"。
 * 失败分支始终保留 failed 高亮，不会被 nd-early 弱化。
 */
function memberClass(m: FlowNode, _stage: FlowStage, stageIdx: number): Record<string, boolean> {
  const s = memberState(m)
  const conc = concurrentActive(stageIdx)
  return {
    [`nd-${s}`]: true,
    'nd-glow': conc && s === 'running',
    'nd-early': conc && (s === 'done' || s === 'warn'),
  }
}

/** 悬停浮层：构建分支/节点详情（含并发上下文），并跟随鼠标定位 */
function showTip(e: MouseEvent, m: FlowNode | null, stage: FlowStage, i: number) {
  if (!m) return
  const s = memberState(m)
  const conc = concurrentActive(i)
  let concurrentText: string | null = null
  if (stage.kind === 'parallel') {
    const running = stage.members.filter(x => memberState(x) === 'running').length
    const total = stage.members.length
    concurrentText = conc
      ? `共 ${total} 个分支，${running === 0 ? '全部已结束' : `${running} 个执行中`}`
      : `共 ${total} 个分支`
  }
  hoverInfo.value = {
    title: m.title,
    kind: m.kind === 'artifact' ? '产物' : (m.branchLabel ? '并行分支' : '步骤'),
    branchLabel: m.branchLabel,
    status: s,
    statusText: statusText(s),
    elapsed: m.elapsedMs != null ? formatDuration(m.elapsedMs) : null,
    concurrent: concurrentText,
    detail: m.detail || (stage.kind === 'parallel' ? stage.branchNote : null),
  }
  hoverVisible.value = true
  moveTip(e)
}
function moveTip(e: MouseEvent) {
  tipX.value = e.clientX + 14
  tipY.value = e.clientY + 14
}
function hideTip() {
  hoverVisible.value = false
}

// ── 播放控制 ────────────────────────────────────────────
function stopTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function play() {
  if (!stages.value.length) return
  // 已播完则从头重播
  if (litStageCount.value >= stages.value.length) {
    litStageCount.value = 0
    activeIndex.value = 0
  }
  playing.value = true
  stopTimer()
  timer = setInterval(() => {
    if (litStageCount.value >= stages.value.length) {
      pause()
      return
    }
    litStageCount.value++
    activeIndex.value = litStageCount.value - 1
    scrollActiveIntoView()
  }, PLAY_INTERVAL)
}

function pause() {
  playing.value = false
  stopTimer()
}

function togglePlay() {
  if (playing.value) pause()
  else play()
}

function replay() {
  litStageCount.value = 0
  activeIndex.value = 0
  play()
}

/** 点击节点/横轴刻度跳转：聚焦该阶段；若尚未播放到该处则推进点亮 */
function jumpTo(i: number) {
  activeIndex.value = i
  if (i >= litStageCount.value) litStageCount.value = i + 1
  if (playing.value && litStageCount.value >= stages.value.length) pause()
  scrollActiveIntoView()
}

/** 流式模式：跟随最新事件，全部点亮并滚动到最右 */
function syncStreaming() {
  const n = stages.value.length
  litStageCount.value = n
  activeIndex.value = Math.max(0, n - 1)
  scrollActiveIntoView()
}

function scrollActiveIntoView() {
  nextTick(() => {
    flowRef.value
      ?.querySelector(`[data-idx="${activeIndex.value}"]`)
      ?.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' })
  })
}

// 流式模式实时同步；回放模式数据首次就绪后自动播放（步骤过多则直接全亮，不逐步播放）
watch(() => stages.value.length, (n) => {
  if (props.streaming) {
    syncStreaming()
    return
  }
  if (manySteps.value) {
    litStageCount.value = n
    autoplayDone = true
    return
  }
  if (!autoplayDone && n > 0) {
    autoplayDone = true
    play()
  }
})

onMounted(() => {
  if (!stages.value.length) return
  if (props.streaming) {
    syncStreaming()
    return
  }
  if (manySteps.value) {
    litStageCount.value = stages.value.length
    autoplayDone = true
    return
  }
  autoplayDone = true
  play()
})

onBeforeUnmount(stopTimer)

// ── 横轴几何 ────────────────────────────────────────────
const fillPercent = computed(() => {
  const n = stages.value.length
  if (n <= 1) return litCount.value > 0 ? '100%' : '0%'
  if (litCount.value <= 1) return '0%'
  return `${((litCount.value - 1) / (n - 1)) * 100}%`
})

function dotPercent(i: number): string {
  const n = stages.value.length
  if (n <= 1) return '50%'
  return `${(i / (n - 1)) * 100}%`
}
</script>

<style scoped>
.flow-player {
  display: flex;
  flex-direction: column;
  height: 300px;
  font-size: 12px;
}

/* ── 控制栏 ── */
.fp-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-bottom: 6px;
  border-bottom: 1px dashed #f0e6ff;
  flex-shrink: 0;
}
.fp-ctrl-btn {
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 50%;
  background: #722ed1;
  color: #fff;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  transition: background 0.2s;
  padding: 0;
}
.fp-ctrl-btn:hover { background: #9254de; }
.fp-live-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #1890ff;
}
.fp-progress {
  font-size: 11px;
  color: #722ed1;
  font-family: monospace;
  background: rgba(114, 46, 209, 0.08);
  border-radius: 8px;
  padding: 1px 8px;
}
.fp-active-title {
  flex: 1;
  min-width: 0;
  text-align: right;
  font-size: 11px;
  color: #8c8c8c;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 缩放控制 */
.fp-zoom {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-left: 4px;
  padding: 1px 4px;
  background: rgba(114, 46, 209, 0.06);
  border-radius: 10px;
}
.fp-zoom-btn {
  width: 18px;
  height: 18px;
  border: none;
  border-radius: 50%;
  background: #722ed1;
  color: #fff;
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}
.fp-zoom-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.fp-zoom-btn:not(:disabled):hover { background: #9254de; }
.fp-zoom-val {
  font-size: 10px;
  color: #722ed1;
  font-family: monospace;
  min-width: 30px;
  text-align: center;
}

/* 状态图例 */
.fp-legend {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-left: 6px;
  font-size: 10px;
  color: #999;
}
.fp-legend-item { display: inline-flex; align-items: center; gap: 3px; }
.fp-legend-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}
.fp-legend-dot.lg-running { background: #1890ff; }
.fp-legend-dot.lg-done { background: #52c41a; }
.fp-legend-dot.lg-failed { background: #f5222d; }
.fp-legend-dot.lg-warn { background: #faad14; }

/* ── 横向流程图 ── */
.fp-flow {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  overflow-x: auto;
  overflow-y: auto;
  padding: 10px 6px;
  gap: 2px;
  cursor: grab;
}
.fp-flow.fp-panning { cursor: grabbing; user-select: none; }
/* 步骤过多：关闭所有过渡动画，整屏同步高亮（无灰度、无逐步、无闪烁） */
.flow-player.many-steps .fp-node,
.flow-player.many-steps .fp-pgroup,
.flow-player.many-steps .fp-branch-node,
.flow-player.many-steps .fp-axis-fill,
.flow-player.many-steps .fp-axis-dot { transition: none !important; }
/* 可缩放内层：zoom 仅放大横向布局，滚动条随之变化 */
.fp-flow-inner {
  display: flex;
  align-items: center;
  gap: 2px;
}
.fp-node {
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s, opacity 0.3s;
  flex-shrink: 0;
}
.fp-node.pending { opacity: 0.4; }
.fp-node.pending:hover { opacity: 0.85; }
.fp-node.active { background: rgba(114, 46, 209, 0.08); }

/* 串行节点竖卡 */
.fp-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  width: 108px;
  padding: 8px 6px;
  border: 1px solid #eee;
  background: #fff;
  text-align: center;
}
.fp-card.lit { border-color: #d3adf7; background: #faf5ff; }

.fp-node-icon {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  background: #fff;
  border: 2px solid #d9d9d9;
  color: #999;
}
.fp-node-icon.ic-running { border-color: #1890ff; color: #1890ff; }
.fp-node-icon.ic-done { border-color: #52c41a; color: #52c41a; }
.fp-node-icon.ic-failed { border-color: #f5222d; color: #f5222d; }
.fp-node-icon.ic-warn { border-color: #faad14; color: #faad14; }
/* 当前推进节点：脉冲光晕 */
.fp-node.current .fp-node-icon {
  border-color: #722ed1;
  color: #722ed1;
  animation: nodePulse 1.4s ease-out infinite;
}
@keyframes nodePulse {
  0% { box-shadow: 0 0 0 0 rgba(114, 46, 209, 0.35); }
  70% { box-shadow: 0 0 0 8px rgba(114, 46, 209, 0); }
  100% { box-shadow: 0 0 0 0 rgba(114, 46, 209, 0); }
}
.fp-node-seq { font-size: 10px; line-height: 1; }
.fp-node-elapsed {
  font-size: 10px;
  color: #999;
  font-family: monospace;
  line-height: 1;
}
.fp-branch-elapsed {
  font-size: 10px;
  color: #999;
  font-family: monospace;
  margin-left: auto;
  flex-shrink: 0;
}
.fp-node-phase {
  font-size: 10px;
  color: #722ed1;
  background: rgba(114, 46, 209, 0.08);
  border-radius: 3px;
  padding: 0 5px;
  line-height: 15px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fp-node-title {
  font-size: 11px;
  color: #333;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-all;
}

/* 分支判断/汇聚节点（菱形） */
.fp-diamond {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  width: 96px;
  padding: 6px;
  text-align: center;
}
.fp-diamond .fp-node-icon {
  transform: rotate(45deg);
  border-radius: 4px;
  width: 20px;
  height: 20px;
}
.fp-diamond .fp-node-icon > * { transform: rotate(-45deg); }

/* 连接箭头 */
.fp-arrow {
  flex-shrink: 0;
  color: #d9d9d9;
  font-size: 13px;
  line-height: 1;
  padding: 0 1px;
}
.fp-arrow.lit { color: #722ed1; }
/* 正在推进的箭头：流动闪烁 */
.fp-arrow.flowing { animation: arrowFlow 0.8s ease-in-out infinite; }
@keyframes arrowFlow {
  0%, 100% { opacity: 0.35; transform: translateX(0); }
  50% { opacity: 1; transform: translateX(2px); }
}

/* ── 并行分支泳道 ── */
.fp-pgroup {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 6px 8px;
  border: 1px dashed #d3adf7;
  border-radius: 8px;
  background: rgba(114, 46, 209, 0.03);
  transition: opacity 0.3s, border-color 0.2s;
}
.fp-pgroup.lit { border-color: #b37feb; background: rgba(114, 46, 209, 0.06); }
.fp-pgroup.pending { opacity: 0.4; }
.fp-pgroup.active { border-color: #722ed1; }
.fp-pgroup-note {
  font-size: 10px;
  color: #722ed1;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fp-pgroup-lane { display: flex; align-items: stretch; gap: 2px; position: relative; }
/* 分叉起点 / 汇聚点：主干在此一分为 N / 合并回主干 */
.fp-fork-node {
  flex-shrink: 0;
  align-self: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid #b37feb;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #722ed1;
  transition: border-color 0.2s, background 0.2s;
}
.fp-fork-glyph {
  width: 12px;
  height: 12px;
  fill: none;
  stroke: #722ed1;
  stroke-width: 1.4;
  stroke-linecap: round;
  stroke-linejoin: round;
  transition: stroke 0.2s;
}
.fp-fork-merge { border-color: #52c41a; }
.fp-fork-merge .fp-fork-glyph { stroke: #389e0d; }
/* 树形连线列：SVG 主干脊线 + 横向分流短线（确定性绘制，无需测量 DOM） */
.fp-tree-col { display: flex; align-items: stretch; position: relative; }
.fp-tree-svg {
  flex-shrink: 0;
  width: 22px;
  align-self: stretch;
  overflow: visible;
}
.fp-spine {
  stroke: #b37feb;
  stroke-width: 1.4;
  stroke-dasharray: 3 3;
  transition: stroke 0.2s, stroke-dasharray 0.2s;
}
.fp-branch-line {
  stroke: #d3adf7;
  stroke-width: 1.4;
  transition: stroke 0.2s;
}
/* 分支列：紧贴 SVG 右侧，横向短线正好接到各分支卡片左缘 */
.fp-branch-col {
  display: flex;
  flex-direction: column;
  justify-content: space-around;
  gap: 4px;
  padding: 4px 6px;
}
/* 并发执行窗口：分叉/汇聚节点与脊线同步发光，强调这些分支正一起运行 */
.fp-pgroup.concurrent-active .fp-fork-node { border-color: #1890ff; }
.fp-pgroup.concurrent-active .fp-fork-glyph { stroke: #1890ff; }
.fp-branch-node {
  position: relative;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 6px;
  border: 1px solid #eee;
  border-radius: 5px;
  background: #fff;
  max-width: 150px;
  cursor: pointer;
  transition: background 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease, opacity 0.25s ease;
}
/* 横向分流短线已交由 SVG 绘制，此处不再用伪元素 */
.fp-branch-node.nd-done { border-color: #b7eb8f; background: #f6ffed; }
.fp-branch-node.nd-running { border-color: #91d5ff; background: #e6f7ff; }
.fp-branch-node.nd-failed { border-color: #ffa39e; background: #fff1f0; }
.fp-branch-node.nd-warn { border-color: #ffe58f; background: #fffbe6; }

/* 同步高亮：并发组内仍执行的分支在同一渲染帧内统一发光（无逐一点亮、无闪烁） */
.fp-branch-node.nd-glow {
  border-color: #1890ff;
  background: #e6f7ff;
  box-shadow: 0 0 0 1px #1890ff, 0 0 10px 1px rgba(24, 144, 255, 0.55);
  animation: branchGlow 1.3s ease-in-out infinite;
}
@keyframes branchGlow {
  0%, 100% { box-shadow: 0 0 0 1px #1890ff, 0 0 8px 0 rgba(24, 144, 255, 0.4); }
  50% { box-shadow: 0 0 0 1px #1890ff, 0 0 14px 3px rgba(24, 144, 255, 0.7); }
}
.fp-branch-node.nd-glow .fp-branch-dot { box-shadow: 0 0 6px rgba(24, 144, 255, 0.8); }
/* 状态一致性：同组仍在跑、本分支已提前完成/提醒 → 相对收敛，与发光同伴形成对比 */
.fp-branch-node.nd-early {
  opacity: 0.78;
  border-style: dashed;
}
.fp-branch-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 8px;
  background: #f5f5f5;
  color: #999;
}
.fp-branch-dot.ic-done { background: #52c41a; color: #fff; }
.fp-branch-dot.ic-running { background: #1890ff; color: #fff; }
.fp-branch-dot.ic-failed { background: #f5222d; color: #fff; }
.fp-branch-dot.ic-warn { background: #faad14; color: #fff; }
.fp-branch-label {
  font-size: 11px;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fp-pgroup-caption {
  font-size: 10px;
  color: #b37feb;
  font-family: monospace;
}
/* 并发执行中：caption 实时点亮脉冲点 */
.fp-pgroup-caption.cap-live { color: #1890ff; }
.fp-cap-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #1890ff;
  margin-right: 2px;
  vertical-align: middle;
  animation: capPulse 1.2s ease-in-out infinite;
}
@keyframes capPulse {
  0%, 100% { opacity: 0.4; box-shadow: 0 0 0 0 rgba(24, 144, 255, 0.5); }
  50% { opacity: 1; box-shadow: 0 0 0 4px rgba(24, 144, 255, 0); }
}
.fp-cap-conc { color: #1890ff; }
.fp-cap-done { color: #b37feb; }

.fp-empty {
  text-align: center;
  color: #bfbfbf;
  padding: 24px 0;
  width: 100%;
}

/* ── 详情条 ── */
.fp-detail {
  flex-shrink: 0;
  font-size: 11px;
  color: #888;
  background: #f7f7f7;
  border-radius: 4px;
  padding: 4px 8px;
  max-height: 44px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* ── 底部事件横轴 ── */
.fp-axis {
  flex-shrink: 0;
  padding-top: 4px;
}
.fp-axis-track {
  position: relative;
  height: 2px;
  border-radius: 1px;
  background: #eee;
  margin: 8px 10px 4px;
}
.fp-axis-fill {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: linear-gradient(90deg, #722ed1, #b37feb);
  border-radius: 1px;
  transition: width 0.35s ease;
}
.fp-axis-dot {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #d9d9d9;
  border: 2px solid #fff;
  box-shadow: 0 0 0 1px #e0e0e0;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s, background 0.2s;
}
.fp-axis-dot:hover { transform: translate(-50%, -50%) scale(1.25); }
.fp-axis-dot.lit { background: #722ed1; box-shadow: 0 0 0 1px #b37feb; }
.fp-axis-dot.ax-failed.lit { background: #f5222d; box-shadow: 0 0 0 1px #ff7875; }
.fp-axis-dot.ax-running.lit { background: #1890ff; box-shadow: 0 0 0 1px #69c0ff; }
.fp-axis-dot.ax-warn.lit { background: #faad14; box-shadow: 0 0 0 1px #ffd666; }
/* 当前聚焦刻度：放大 + 光晕 */
.fp-axis-dot.active {
  background: #722ed1;
  transform: translate(-50%, -50%) scale(1.45);
  box-shadow: 0 0 0 3px rgba(114, 46, 209, 0.22);
}
.fp-axis-labels {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #bbb;
  padding: 0 2px;
}

/* ── 悬停详情浮层 ── */
.fp-tip {
  position: fixed;
  z-index: 1000;
  max-width: 280px;
  padding: 8px 10px;
  background: #1f1f2e;
  color: #fff;
  border-radius: 8px;
  font-size: 11px;
  line-height: 1.5;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
  pointer-events: none;
}
.fp-tip-title { font-size: 12px; font-weight: 600; margin-bottom: 4px; color: #fff; }
.fp-tip-row { display: flex; gap: 6px; margin: 1px 0; }
.fp-tip-k { color: #b0a8c8; flex-shrink: 0; width: 32px; }
.fp-tip-status { font-weight: 600; }
.fp-tip-status.st-running { color: #69c0ff; }
.fp-tip-status.st-done { color: #95de64; }
.fp-tip-status.st-failed { color: #ff7875; }
.fp-tip-status.st-warn { color: #ffd666; }
.fp-tip-conc { color: #69c0ff; }
.fp-tip-detail {
  margin-top: 5px;
  padding-top: 5px;
  border-top: 1px solid rgba(255, 255, 255, 0.15);
  color: #d6d3e0;
  white-space: pre-wrap;
  word-break: break-all;
}
/* 浮层按状态着色左侧指示 */
.fp-tip.tip-failed { background: #2b1620; }
.fp-tip.tip-failed .fp-tip-title { color: #ff9c96; }
.fp-tip.tip-done { background: #16261b; }
.fp-tip.tip-done .fp-tip-title { color: #b7eb8f; }
</style>
