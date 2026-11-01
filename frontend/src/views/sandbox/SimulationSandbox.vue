<template>
  <div class="sandbox-root">
    <ContextBar
      :source-label="sourceLabel" :clone-scope-label="cloneScopeLabel"
      :tick="tick" :max-tick="maxTick" :exec-mode="execMode"
      :checkpoint-count="checkpointCount" :has-scene="!!currentScene"
      @save-checkpoint="saveCheckpoint" @refresh="refreshState" @open-kpi="openKPI"
      @open-create="openCreate" @open-delete="show.del = true" @exec-mode="onExecModeChange" />

    <TickBar
      :tick="tick" :max-tick="maxTick" :scrub-ticks="scrubTicks" :cp-ticks="cpTicks"
      :can-advance="canAdvance" :auto-on="!!autoTimer" :health="health" :controllability="controllability"
      :goal-count="goalCount" :risk-top3="riskTop3View"
      @toggle-auto="toggleAuto" @step="stepAdvance" @jump="jumpTick" />

    <div class="main">
      <ScenePanel
        :scenes="scenes" :current-scene-id="currentScene?.scene_id ?? null" :timeline="timeline"
        :branches="branches" :selected-branch-id="branchId" :compare-set="compareSet" :tick="tick"
        @select-scene="selectScene" @open-create="openCreate" @jump="jumpTick"
        @pick-branch="pickBranch" @toggle-compare="toggleCompare" @do-compare="doCompare" />

      <CausalCanvas
        :world="world" :tick="tick" :cview="cview" :zoom-k="zoomK"
        :selected-entity="selectedEntity" :detail="detailEntity" :veil="veil"
        @set-view="cview = $event" @zoom="zoom" @fit="fit" @pick="pick"
        @close-detail="closeDetail" @open-action="openAction" @open-action-for="openActionFor" />

      <TracePanel
        :tview="tview" :goal-elements="goalElements" :rule-elements="ruleElements"
        :trace-obs="traceObs" :future-items="futureItems" :entity-count="entityCount"
        :relation-count="relationCount" :tick="tick" @set-view="tview = $event" />

      <AdvisorPanel
        :aview="aview" :chat="chat" :chat-input="chatInput" :asking="asking"
        :action-logs="actionLogs" :recommendations="recommendations" :has-scene="!!currentScene"
        @set-view="aview = $event" @ask="askPreset" @send="sendChat"
        @update:chat-input="chatInput = $event" />
    </div>

    <ActionModal
      :show="show.action" :entities="actableEntities" :templates="actionTemplates"
      :target="actForm.target" :template="actForm.template" :param-fields="actParamFields"
      :params="actForm.params" :note="actNote" :note-lock="actTargetMasked"
      @cancel="show.action = false" @submit="submitAction"
      @update:target="onActTarget" @update:template="onActTemplate" @update:params="onActParams" />

    <CompareView :show="show.compare" :summary="compareSummary" @close="show.compare = false" />

    <KpiModal
      :show="show.kpi" :scene-name="currentScene?.name || ''" :tick="tick"
      :health="health" :controllability="controllability" :entity-count="entityCount"
      :branch-name="currentBranch?.name || ''" :observation-count="traceObs.length" :max-tick="maxTick"
      @close="show.kpi = false" />

    <NewSceneModal :show="show.create" :ontologies="publishedOntologies" :busy="creating"
      @cancel="show.create = false" @create="submitCreate" />

    <DeleteConfirmModal
      :show="show.del" :scene-name="currentScene?.name || ''"
      :checkpoint-count="checkpointCount" :branch-count="branches.length"
      @cancel="show.del = false" @confirm="confirmDelete" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import * as sb from '@/api/sandbox'
import type {
  ActionLog, ActionTemplate, BranchSummary, Checkpoint, Element, KpiPoint, Observation,
  SandboxBranch, SandboxScene, WorldEntity, WorldView,
} from '@/api/sandbox'
import { listOntologies } from '@/api/dataops'
import { useSandboxStore } from '@/stores/sandbox'
import './sandbox.css'
import ContextBar from './components/ContextBar.vue'
import TickBar from './components/TickBar.vue'
import ScenePanel from './components/ScenePanel.vue'
import CausalCanvas from './components/CausalCanvas.vue'
import TracePanel from './components/TracePanel.vue'
import AdvisorPanel from './components/AdvisorPanel.vue'
import ActionModal from './components/ActionModal.vue'
import CompareView from './components/CompareView.vue'
import KpiModal from './components/KpiModal.vue'
import NewSceneModal from './components/NewSceneModal.vue'
import DeleteConfirmModal from './components/DeleteConfirmModal.vue'
import {
  buildCanvasLayout, deriveControllability, deriveHealth, deriveRiskTop3,
  entityDisplayName, selectLatestKpi, timelineItems, traceObservations,
} from './sandboxView'
import { escapeHtml } from './sandboxFormat'

// 编排壳：游标（场景/分支/Tick/执行模式）进 Pinia，世界快照数据留在本组件 ref。
// 画布布局、KPI 派生、格式化全部走 sandboxView / sandboxFormat 纯函数。
const store = useSandboxStore()

// ── 世界数据（真源在后端沙箱表，这里只缓存当前游标下的快照）─────
const scenes = ref<SandboxScene[]>([])
const currentScene = ref<SandboxScene | null>(null)
const branches = ref<SandboxBranch[]>([])
const world = ref<WorldView | null>(null)
const checkpoints = ref<Checkpoint[]>([])
const observations = ref<Observation[]>([])
const futureItems = ref<Observation[]>([])
const kpis = ref<KpiPoint[]>([])
const elements = ref<Element[]>([])
const actionTemplates = ref<ActionTemplate[]>([])
const actionLogs = ref<ActionLog[]>([])
const compareSet = ref<Set<number>>(new Set())
const compareSummary = ref<BranchSummary[]>([])

// ── UI 态 ────────────────────────────────────────────────────
const zoomK = ref(1)
const veil = ref(false)
const selectedEntity = ref<string | null>(null)
const detailData = ref<(WorldEntity & { origin: string; can_act: boolean }) | null>(null)
const cview = ref<'world' | 'onto' | 'causal' | 'inst'>('causal')
const tview = ref<'goal' | 'trace' | 'future' | 'rule'>('trace')
const aview = ref<'chat' | 'audit' | 'rec'>('chat')
const autoTimer = ref<ReturnType<typeof setInterval> | null>(null)
const show = reactive({ action: false, del: false, kpi: false, create: false, compare: false })
const creating = ref(false)

type ChatMsg = { who: 'u' | 'a'; time: string; html: string; run?: boolean; evidence?: number[]; degraded?: boolean }
const chat = ref<ChatMsg[]>([])
const chatInput = ref('')
const asking = ref(false)

const publishedOntologies = ref<{ id: number; code: string; name: string; current_version: number }[]>([])
const actForm = reactive<{ target: string; template: string; params: Record<string, any> }>({ target: '', template: '', params: {} })

const recommendations = [
  '当前场景中风险最高的实体是什么？',
  '推进 3 个 Tick 后总体态势会如何变化？',
  '哪条因果边对世界状态影响最大？',
  '解释因果传播路径与关键传导点',
]

// ── 游标（store 单一来源）──────────────────────────────────────
const tick = computed(() => store.tick)
const branchId = computed(() => store.branchId)
const execMode = computed(() => store.execMode)
const maxTick = computed(() => currentScene.value?.tick_max ?? 12)

// ── 派生展示值 ───────────────────────────────────────────────
const currentBranch = computed(() => branches.value.find(b => b.id === branchId.value) || null)
const canAdvance = computed(() => !!currentScene.value && currentScene.value.status === 'running' && execMode.value !== 'replay')
const scrubTicks = computed(() => Array.from({ length: maxTick.value + 1 }, (_, i) => i))
const cpTicks = computed(() => new Set(checkpoints.value.map(c => c.tick)))
const sourceLabel = computed(() => currentScene.value ? `${currentScene.value.name} · v${currentScene.value.ontology_version}` : '未选择场景')
const cloneScopeLabel = computed(() => {
  const n = world.value?.entities.length ?? currentScene.value?.clone_stats?.entities ?? 0
  const r = world.value?.relations.length ?? currentScene.value?.clone_stats?.relations ?? 0
  return `${n} 实体 / ${r} 关系`
})
const checkpointCount = computed(() => checkpoints.value.length)
const entityCount = computed(() => world.value?.entities.length ?? 0)
const relationCount = computed(() => world.value?.relations.length ?? 0)
const goalElements = computed(() => elements.value.filter(e => e.kind === 'goal'))
const ruleElements = computed(() => elements.value.filter(e => e.kind === 'rule'))
const goalCount = computed(() => goalElements.value.length)
const timeline = computed(() => timelineItems(observations.value))
const traceObs = computed(() => traceObservations(observations.value, tick.value))
const latestKpi = computed(() => selectLatestKpi(kpis.value, tick.value, 'kpi_point'))
const health = computed(() => deriveHealth(latestKpi.value))
const controllability = computed(() => deriveControllability(latestKpi.value))
const riskTop3View = computed(() => deriveRiskTop3(kpis.value, tick.value)
  .map(r => ({ ...r, name: entityDisplayName(world.value?.entities ?? [], r.entity_code) })))

const canvasNodes = computed(() => buildCanvasLayout(world.value?.entities ?? []))

// 详情浮层：画布布局节点（名称/风险/坐标）+ getEntity 回来的 can_act / source_ref
const detailEntity = computed(() => {
  const node = canvasNodes.value.find(n => n.entity_code === selectedEntity.value)
  if (!node) return null
  return { ...node, can_act: detailData.value?.can_act, source_ref: detailData.value?.source_ref ?? node.source_ref }
})

const actableEntities = computed(() => (world.value?.entities || []).filter(e => e.origin !== 'derived'))
const actTargetMasked = computed(() => (world.value?.entities || []).find(e => e.entity_code === actForm.target)?.masked ?? false)
const actNote = computed(() => {
  const e = (world.value?.entities || []).find(x => x.entity_code === actForm.target)
  if (!e) return '选择目标实体'
  if (e.masked) return '🔒 该实体命中脱敏策略，当前角色无明文视野，行动将被门禁拒绝'
  return `来源：${e.origin} · 本体映射 ${e.object_code}`
})
const actParamFields = computed(() => {
  const tp = actionTemplates.value.find(t => t.code === actForm.template)
  const props = (tp?.param_schema_json?.properties) || {}
  return Object.keys(props).map(k => ({ key: k, label: props[k].description || props[k].title || k, hint: props[k].type || '值' }))
})

// ── 数据加载 ─────────────────────────────────────────────────
async function loadScenes() {
  scenes.value = await sb.listScenes()
  if (!currentScene.value && scenes.value.length) await selectScene(scenes.value[0].scene_id)
}
async function selectScene(id: number) {
  const s = await sb.getScene(id)
  currentScene.value = s
  store.setCursor({ sceneId: id, execMode: s.exec_mode })
  branches.value = s.branches || []
  store.setCursor({ branchId: branches.value.length ? branches.value[0].id : null })
  compareSet.value = new Set(branches.value.length ? [branches.value[0].id] : [])
  await loadBranchData()
}
async function loadBranchData() {
  if (!currentScene.value || branchId.value == null) { world.value = null; return }
  const sid = currentScene.value.scene_id, bid = branchId.value
  veil.value = true
  try {
    const [w, cp, obs, future, k, el, logs] = await Promise.all([
      sb.getWorld(sid, { branch_id: bid }),
      sb.listCheckpoints(sid, { branch_id: bid }),
      sb.listObservations(sid, { branch_id: bid }),
      sb.listObservations(sid, { branch_id: bid, kind: 'future' }),
      sb.listKpis(sid, { branch_id: bid }),
      sb.listElements(sid),
      sb.listActions(sid, { branch_id: bid }),
    ])
    world.value = w
    checkpoints.value = cp
    observations.value = obs
    futureItems.value = future
    kpis.value = k
    elements.value = el
    actionLogs.value = logs
    store.setCursor({ tick: w.tick })
    const fresh = await sb.getScene(sid)
    currentScene.value = fresh
    branches.value = fresh.branches || branches.value
  } finally {
    veil.value = false
  }
}
function pickBranch(id: number) {
  if (branchId.value === id) return
  store.setCursor({ branchId: id })
  loadBranchData()
}
function toggleCompare(id: number) {
  const set = new Set(compareSet.value)
  set.has(id) ? set.delete(id) : set.add(id)
  compareSet.value = set
}

// ── 时钟控制 ─────────────────────────────────────────────────
function withVeil(fn: () => Promise<void>) {
  veil.value = true
  fn().finally(() => { veil.value = false })
}
async function stepAdvance(n: number) {
  if (!currentScene.value || branchId.value == null) return
  if (!canAdvance.value) { message.warning('当前模式或状态不可推进'); return }
  const sid = currentScene.value.scene_id, bid = branchId.value
  await withVeil(async () => {
    const res = await sb.advance(sid, bid, n)
    store.setCursor({ tick: res.tick_after })
    await loadBranchData()
    message.success(n === 1 ? `推进至 Tick ${res.tick_after}` : `批量推进 → Tick ${res.tick_after}`, 2)
  })
}
async function jumpTick(t: number) {
  if (!currentScene.value || branchId.value == null) return
  if (t === tick.value) return
  const sid = currentScene.value.scene_id, bid = branchId.value
  await withVeil(async () => {
    if (t < tick.value) { await sb.replay(sid, bid, t) }
    else { const diff = t - tick.value; if (canAdvance.value) await sb.advance(sid, bid, diff) }
    await loadBranchData()
  })
}
function toggleAuto() {
  if (autoTimer.value) { clearInterval(autoTimer.value); autoTimer.value = null; return }
  autoTimer.value = setInterval(async () => {
    if (!currentScene.value || branchId.value == null) return
    if (tick.value >= maxTick.value || !canAdvance.value) { toggleAuto(); return }
    await stepAdvance(1)
  }, 1200)
}
async function refreshState() { await loadBranchData(); message.success('已刷新世界状态', 1.5) }
async function saveCheckpoint() {
  if (!currentScene.value || branchId.value == null) return
  if (checkpointCount.value >= 5) { message.error('检查点已达上限 5/5'); return }
  await sb.saveCheckpoint(currentScene.value.scene_id, branchId.value, `T${tick.value} 快照`)
  await loadBranchData()
  message.success('已保存检查点 @ Tick ' + tick.value, 1.5)
}
async function doCompare() {
  if (!currentScene.value) return
  const ids = [...compareSet.value]
  if (ids.length < 2) { message.warning('请至少选择 2 个分支进行对比'); return }
  const cmp = await sb.compare(currentScene.value.scene_id, ids)
  compareSummary.value = cmp.branch_summary ?? []
  show.compare = true
}
async function onExecModeChange(mode: string) {
  if (!currentScene.value) return
  store.setCursor({ execMode: mode })
  await sb.patchScene(currentScene.value.scene_id, { exec_mode: mode })
  if (currentScene.value) currentScene.value.exec_mode = mode
  message.success('执行模式：' + { auto: '自动执行', stepwise: '逐步确认', replay: '只读回放' }[mode as 'auto'], 1.5)
}

// ── 画布交互 ─────────────────────────────────────────────────
function zoom(d: number) { zoomK.value = Math.max(0.6, Math.min(1.5, zoomK.value + d * 0.12)) }
function fit() { zoomK.value = 1 }
async function pick(code: string) {
  selectedEntity.value = code
  detailData.value = null
  if (!currentScene.value || branchId.value == null) return
  try { detailData.value = await sb.getEntity(currentScene.value.scene_id, code, { branch_id: branchId.value }) } catch { /* 拦截器已提示 */ }
}
function closeDetail() { selectedEntity.value = null; detailData.value = null }

// ── 行动 ─────────────────────────────────────────────────────
async function loadTemplates() {
  if (!currentScene.value) return
  actionTemplates.value = await sb.listActionTemplates(currentScene.value.scene_id)
}
function openAction() {
  if (!world.value) return
  show.action = true
  if (!actionTemplates.value.length) loadTemplates()
  actForm.target = canvasNodes.value.find(n => !n.masked)?.entity_code || ''
  actForm.params = {}
}
function openActionFor(id: string) {
  actForm.target = id
  show.action = true
  if (!actionTemplates.value.length) loadTemplates()
  actForm.params = {}
}
function onActTarget(v: string) { actForm.target = v; actForm.params = {} }
function onActTemplate(v: string) {
  actForm.template = v
  actForm.params = {}
  actParamFields.value.forEach(p => { actForm.params[p.key] = '' })
}
function onActParams(v: Record<string, any>) { actForm.params = v }
async function submitAction() {
  if (!currentScene.value || branchId.value == null) return
  const sid = currentScene.value.scene_id, bid = branchId.value
  const params: Record<string, any> = {}
  actParamFields.value.forEach(p => { if (actForm.params[p.key] !== '' && actForm.params[p.key] != null) params[p.key] = Number.isNaN(Number(actForm.params[p.key])) ? actForm.params[p.key] : Number(actForm.params[p.key]) })
  const res = await sb.applyAction(sid, bid, { template_code: actForm.template, target_entity_code: actForm.target, params })
  show.action = false
  if (res.gate_result === 'denied') { message.error('门禁拒绝：' + (res.reason || '目标受限'), 3); await loadBranchData(); return }
  if (res.gate_result === 'pending') {
    message.warning('逐步确认模式：行动待确认，请在 5 分钟内确认', 3)
    try { await sb.confirmAction(sid, res.action_id, res.confirm_token || ''); message.success('已自动确认并生效', 2) } catch { /* 拦截器已提示 */ }
    await loadBranchData(); return
  }
  if (res.tick_after != null) store.setCursor({ tick: res.tick_after })
  await loadBranchData()
  message.success(`已施加「${actionTemplates.value.find(t => t.code === actForm.template)?.name || actForm.template}」并推进至 Tick ${tick.value}`, 2)
}

// ── AI 顾问 ──────────────────────────────────────────────────
function now() { return new Date().toTimeString().slice(0, 8) }
function askPreset(q: string) { chatInput.value = q; sendChat() }
async function sendChat() {
  const v = chatInput.value.trim()
  if (!v || !currentScene.value || branchId.value == null) return
  chat.value.push({ who: 'u', time: now(), html: escapeHtml(v) })
  chatInput.value = ''
  asking.value = true
  const ph: ChatMsg = { who: 'a', time: now(), html: '正在读取世界快照并按因果链推演…', run: true }
  chat.value.push(ph)
  try {
    const res = await sb.ask(currentScene.value.scene_id, { branch_id: branchId.value, question: v })
    ph.run = false
    ph.html = escapeHtml(res.answer)
    ph.evidence = res.cited_evidence
    ph.degraded = res.degraded
    if (res.degraded) message.warning('顾问降级：LLM 不可用，返回确定性证据摘要', 2)
  } catch {
    ph.run = false; ph.html = '（提问失败，请检查登录状态与场景）'
  } finally {
    asking.value = false
  }
}

// ── 场景创建 / 删除 ──────────────────────────────────────────
async function loadOntologies() {
  const res: any = await listOntologies({ status: 'published' })
  const list = res?.data ?? res ?? []
  publishedOntologies.value = (Array.isArray(list) ? list : []).filter((o: any) => o.status === 'published' && (o.current_version || 0) > 0)
}
function openKPI() { if (currentScene.value) show.kpi = true }
function openCreate() { show.create = true; if (!publishedOntologies.value.length) loadOntologies() }
// 克隆是后台任务：轮询到 running / failed 再刷新列表，避免停在空世界上
async function pollSceneReady(sid: number) {
  for (let i = 0; i < 30; i++) {
    const s = await sb.getScene(sid)
    if (s.status === 'running' || s.status === 'failed') return s
    await new Promise(r => setTimeout(r, 600))
  }
  return null
}
async function submitCreate(payload: { ontology_id: number; name: string; tick_max: number }) {
  creating.value = true
  try {
    const res = await sb.createScene(payload)
    show.create = false
    message.success('场景已创建，克隆进行中…', 2)
    const sid = (res as any).scene_id
    if (sid) await pollSceneReady(sid)
    await loadScenes()
    if (sid) await selectScene(sid)
  } finally {
    creating.value = false
  }
}
async function confirmDelete() {
  if (!currentScene.value) return
  await sb.deleteScene(currentScene.value.scene_id)
  show.del = false
  currentScene.value = null
  world.value = null
  branches.value = []
  store.reset()
  message.success('已删除推演沙盘', 2)
  await loadScenes()
}

onMounted(async () => {
  await loadScenes()
  if (currentScene.value) await loadTemplates()
  chat.value.push({ who: 'a', time: now(), html: '推演沙盘已就绪：世界克隆自已发布本体。选择场景、推进 Tick 或施加行动观察因果传播。' })
})
onUnmounted(() => { if (autoTimer.value) clearInterval(autoTimer.value) })
</script>
