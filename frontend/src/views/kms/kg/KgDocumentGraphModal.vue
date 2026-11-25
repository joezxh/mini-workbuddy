<template>
  <a-modal
    :open="open"
    :title="title"
    width="1100px"
    :footer="null"
    destroy-on-close
    wrap-class-name="kg-doc-graph-modal kb-graph-pane"
    @cancel="close"
  >
    <a-spin :spinning="loading">
      <div class="kg-doc-graph__body">
        <a-tabs v-model:activeKey="activeTab" size="small">
          <!-- Tab 1：图谱可视化（与实体/关系 Tab 同源数据，切换不重取） -->
          <a-tab-pane key="graph" :tab="t('kbMgmt.kg.tabDocGraph')">
            <div class="kg-doc-graph__bar">
              <span class="kg-muted kg-doc-graph__counts">
                {{ t('kbMgmt.kg.docGraphEntityCount', { count: graphEntities.length }) }}
                ·
                {{ t('kbMgmt.kg.docGraphRelationCount', { count: docRelations.length }) }}
              </span>
              <div class="kg-seg kg-doc-graph__layout-seg">
                <span
                  v-for="l in LAYOUTS"
                  :key="l.value"
                  class="kg-seg__item"
                  :class="{ 'kg-seg__item--on': layout === l.value }"
                  @click="layout = l.value"
                >
                  {{ t(l.label) }}
                </span>
              </div>
            </div>
            <GraphCanvas
              class="kg-doc-graph__canvas"
              spread
              :layout="layout"
              :zoom-labels="{ in: t('kbMgmt.kg.zoomIn'), out: t('kbMgmt.kg.zoomOut'), reset: t('kbMgmt.kg.zoomReset') }"
              :nodes="canvasNodes"
              :edges="canvasEdges"
              :selection="selection"
              :loading="loading"
              :hint-text="t('kbMgmt.kg.graphHint')"
              :legend-size-text="t('kbMgmt.kg.legendNodeSize')"
              :empty-title="t('kbMgmt.kg.docGraphEmptyTitle')"
              :empty-desc="t('kbMgmt.kg.docGraphEmptyDesc')"
              @select="selection = $event"
            />
          </a-tab-pane>

          <!-- Tab 2：实体清单（只读） -->
          <a-tab-pane key="entities" :tab="t('kbMgmt.kg.tabDocEntities')">
            <div class="kg-doc-graph__counts kg-muted">
              {{ t('kbMgmt.kg.docGraphEntityCount', { count: docEntities.length }) }}
            </div>
            <a-table
              v-if="docEntities.length"
              :columns="entityColumns"
              :data-source="docEntities"
              :loading="loading"
              row-key="id"
              size="small"
              :pagination="{ pageSize: 10, size: 'small', showSizeChanger: false, hideOnSinglePage: true }"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'name'">
                  <div class="kg-ent-name">{{ record.name }}</div>
                  <div class="kg-ent-key">{{ record.entity_key }}</div>
                </template>
                <template v-else-if="column.key === 'type'">
                  <span
                    v-if="record.type_code"
                    class="kg-type-tag"
                    :style="typeTagStyle(record.type_code)"
                  >{{ typeLabel(record.type_code) }}</span>
                  <span v-else class="kg-muted">{{ t('kbMgmt.kg.unclassified') }}</span>
                </template>
                <template v-else-if="column.key === 'aliases'">
                  <a-tag v-for="a in record.aliases" :key="a" class="kg-alias-tag">{{ a }}</a-tag>
                  <span v-if="!record.aliases?.length" class="kg-muted">—</span>
                </template>
                <template v-else-if="column.key === 'mention_count'">
                  {{ record.mention_count ?? 0 }}
                </template>
                <template v-else-if="column.key === 'status'">
                  <span class="kg-status" :class="`kg-status--${record.status}`">
                    {{ entityStatusText(record.status) }}
                  </span>
                </template>
                <template v-else-if="column.key === 'locate'">
                  <a-button size="small" type="link" @click="selectNode(record.id)">
                    {{ t('kbMgmt.kg.provLocateGraph') }}
                  </a-button>
                </template>
              </template>
            </a-table>
            <a-empty v-else-if="!loading" :description="t('kbMgmt.kg.docGraphNoEntities')" />
          </a-tab-pane>

          <!-- Tab 3：关系明细（只读） -->
          <a-tab-pane key="relations" :tab="t('kbMgmt.kg.tabDocRelations')">
            <div class="kg-doc-graph__counts kg-muted">
              {{ t('kbMgmt.kg.docGraphRelationCount', { count: docRelations.length }) }}
            </div>
            <a-table
              v-if="docRelations.length"
              :columns="relationColumns"
              :data-source="docRelations"
              :loading="loading"
              row-key="id"
              size="small"
              :pagination="{ pageSize: 10, size: 'small', showSizeChanger: false, hideOnSinglePage: true }"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'from'">
                  <a
                    class="kg-rel-link"
                    :title="entityKeyOf(record.from_entity_id)"
                    @click="selectNode(record.from_entity_id)"
                  >
                    {{ record.from_entity_name || `#${record.from_entity_id}` }}
                  </a>
                </template>
                <template v-else-if="column.key === 'relation'">
                  <a-tag v-if="record.relation_code" color="purple">{{ record.relation_code }}</a-tag>
                  <span v-else class="kg-muted">{{ t('kbMgmt.kg.freePredicate') }}</span>
                  <div v-if="record.predicate" class="kg-muted kg-rel-pred">{{ record.predicate }}</div>
                </template>
                <template v-else-if="column.key === 'to'">
                  <a
                    class="kg-rel-link"
                    :title="entityKeyOf(record.to_entity_id)"
                    @click="selectNode(record.to_entity_id)"
                  >
                    {{ record.to_entity_name || `#${record.to_entity_id}` }}
                  </a>
                </template>
                <template v-else-if="column.key === 'weight'">
                  {{ formatWeight(record.weight) }}
                </template>
                <template v-else-if="column.key === 'status'">
                  <span class="kg-status" :class="`kg-status--${record.status}`">
                    {{ relationStatusText(record.status) }}
                  </span>
                </template>
                <template v-else-if="column.key === 'locate'">
                  <a-button size="small" type="link" @click="selectEdge(record.id)">
                    {{ t('kbMgmt.kg.provLocateGraph') }}
                  </a-button>
                </template>
              </template>
            </a-table>
            <a-empty v-else-if="!loading" :description="t('kbMgmt.kg.docGraphNoRelations')" />
          </a-tab-pane>
        </a-tabs>
      </div>
    </a-spin>
  </a-modal>
</template>

<script setup lang="ts">
/**
 * 单文档实体与关系弹窗：图谱 Tab（GraphCanvas 可视化）+ 实体 Tab + 关系 Tab。
 *
 * 数据一致性：弹窗打开时一次性拉取该知识库的实体与关系（各上限 500 条），
 * 前端按 source_document_ids 过滤出本文档的实体/关系；三个 Tab 共用同一份
 * docEntities/docRelations（computed 派生），切换 Tab 不重取。
 *
 * 连线完整性（2026-11-25 修复）：GraphCanvas 只绘制「两端节点都在节点集」的
 * 边。旧实现节点集仅取本文档实体，而关系的端点实体可能是在其他文档中首次
 * 创建（其 source_document_ids 不含本文档）——该端点不在节点集，连线被静默
 * 丢弃。现节点集改为「本文档实体 ∪ 本文档关系的端点实体」并集，保证每条
 * 关系两端必有节点，图与关系 Tab 一一对应。
 *
 * 空状态：文档未抽取（无实体且无关系）时，图谱 Tab 与两个列表 Tab 都给明确提示。
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import * as kgApi from '@/api/kg'
import type { KgEntity, KgRelation } from '@/api/kg'
import { formatWeight, typeLabel, typeTone } from '@/components/common/graph/graphTheme'
import GraphCanvas from '@/components/common/graph/GraphCanvas.vue'
import type { CanvasEdge, CanvasNode, CanvasSelection } from '@/components/common/graph/graphTypes'

const props = defineProps<{
  open: boolean
  knowledgeId: number
  documentId: string
  documentName?: string
}>()

const emit = defineEmits<{
  (e: 'update:open', v: boolean): void
}>()

const { t } = useI18n()

const loading = ref(false)
const activeTab = ref<'graph' | 'entities' | 'relations'>('graph')
const selection = ref<CanvasSelection | null>(null)
/** 布局算法：默认 Sugiyama 定向分层（流程图风格），可切回力导向 */
const layout = ref<'layered' | 'force'>('layered')
const LAYOUTS: { value: 'layered' | 'force'; label: string }[] = [
  { value: 'layered', label: 'kbMgmt.kg.layoutLayered' },
  { value: 'force', label: 'kbMgmt.kg.layoutForce' },
]

/** 原始数据（每次打开重取，destroy-on-close 保证弹窗销毁后无残留状态） */
const entities = ref<KgEntity[]>([])
const relations = ref<KgRelation[]>([])

const title = computed(() =>
  t('kbMgmt.kg.docGraphTitle', { name: props.documentName || props.documentId }),
)

/** 本文档贡献的实体（source_document_ids 包含当前文档） */
const docEntities = computed<KgEntity[]>(() =>
  entities.value.filter((e) => (e.source_document_ids || []).includes(props.documentId)),
)

/** 本文档抽取出的关系：接口按 jsonb 精确查询返回（与文档列表计数同口径，无截断） */
const docRelations = computed<KgRelation[]>(() => relations.value)

/** 实体 id → 实体行（图谱节点集与列表联动的统一字典） */
const entityMap = computed(() => {
  const map = new Map<number, KgEntity>()
  entities.value.forEach((e) => map.set(e.id, e))
  return map
})

/** 图谱节点集 = 本文档实体 ∪ 本文档关系的端点实体。
 *  端点实体即使不是本文档首次创建（如跨文档共享实体），也必须入图，
 *  否则 GraphCanvas 会因端点缺失而丢弃连线（连线缺失的根因）。 */
const graphEntities = computed<KgEntity[]>(() => {
  const seen = new Set<number>()
  const out: KgEntity[] = []
  const push = (id: number) => {
    if (seen.has(id)) return
    const row = entityMap.value.get(id)
    if (row) {
      seen.add(id)
      out.push(row)
    }
  }
  docEntities.value.forEach((e) => push(e.id))
  docRelations.value.forEach((r) => {
    push(r.from_entity_id)
    push(r.to_entity_id)
  })
  return out
})

const graphEntityIds = computed(() => new Set(graphEntities.value.map((e) => e.id)))

/* ── 图谱 Tab：与实体/关系 Tab 同源的画布契约 ─────────────────────────── */
const canvasNodes = computed<CanvasNode[]>(() =>
  graphEntities.value.map((e) => ({
    id: e.id,
    name: e.name,
    code: e.type_code || '',
    color: typeTone(e.type_code || '').color,
    typeLabel: typeLabel(e.type_code),
  })),
)

const canvasEdges = computed<CanvasEdge[]>(() =>
  docRelations.value
    .filter((r) => graphEntityIds.value.has(r.from_entity_id) && graphEntityIds.value.has(r.to_entity_id))
    .map((r) => ({
      id: r.id,
      from: r.from_entity_id,
      to: r.to_entity_id,
      label: r.relation_code || r.predicate || '',
      code: r.relation_code || r.predicate || undefined,
    })),
)

/* ── 实体 / 关系 Tab：只读表格 ───────────────────────────────────────── */
const entityColumns = computed(() => [
  { title: t('kbMgmt.kg.colEntity'), key: 'name', width: 240 },
  { title: t('kbMgmt.kg.colType'), key: 'type', width: 120 },
  { title: t('kbMgmt.kg.aliases'), key: 'aliases', width: 180 },
  { title: t('kbMgmt.kg.colMentions'), key: 'mention_count', width: 76 },
  { title: t('kbMgmt.kg.status'), key: 'status', width: 96 },
  { title: t('kbMgmt.kg.colActions'), key: 'locate', width: 100 },
])

const relationColumns = computed(() => [
  { title: t('kbMgmt.kg.colSource'), key: 'from', width: 200, ellipsis: true },
  { title: t('kbMgmt.kg.relationType'), key: 'relation', width: 160, ellipsis: true },
  { title: t('kbMgmt.kg.colTarget'), key: 'to', width: 200, ellipsis: true },
  { title: t('kbMgmt.kg.colWeight'), key: 'weight', width: 90 },
  { title: t('kbMgmt.kg.status'), key: 'status', width: 96 },
  { title: t('kbMgmt.kg.colActions'), key: 'locate', width: 100 },
])

function typeTagStyle(code: string) {
  const tone = typeTone(code)
  return { color: tone.fg, background: tone.bg, borderColor: tone.border }
}

function entityStatusText(s: string) {
  if (s === 'active') return t('kbMgmt.kg.statusActive')
  if (s === 'deprecated') return t('kbMgmt.kg.statusDeprecated')
  return t('kbMgmt.kg.statusSuggested')
}

function relationStatusText(s: string) {
  if (s === 'accepted') return t('kbMgmt.kg.statusAccepted')
  if (s === 'rejected') return t('kbMgmt.kg.statusRejected')
  return t('kbMgmt.kg.statusSuggested')
}

function entityKeyOf(entityId: number) {
  return entityMap.value.get(entityId)?.entity_key || ''
}

/** 列表 → 图谱联动：切到图谱 Tab 并选中该节点 */
function selectNode(entityId: number) {
  if (!graphEntityIds.value.has(entityId)) return
  selection.value = { kind: 'node', id: entityId }
  activeTab.value = 'graph'
}

/** 关系 Tab → 图谱联动：切到图谱 Tab 并选中该边 */
function selectEdge(relationId: number) {
  selection.value = { kind: 'edge', id: relationId }
  activeTab.value = 'graph'
}

function close() {
  emit('update:open', false)
}

async function load() {
  if (!props.open || !props.knowledgeId) return
  loading.value = true
  activeTab.value = 'graph'
  selection.value = null
  try {
    // 专用接口：jsonb 精确查询本文档的实体/关系（旧实现 listEntities/
    // listRelations limit=500 客户端过滤——大库被截断导致列表计数与弹窗不一致）
    const res = await kgApi.getDocumentGraph(props.knowledgeId, props.documentId)
    entities.value = res?.entities || []
    relations.value = res?.relations || []
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.docGraphLoadFailed'))
    entities.value = []
    relations.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.knowledgeId, props.documentId],
  ([open]) => {
    if (open) void load()
  },
  { immediate: true },
)
</script>

<style scoped>
/* 弹窗整体加高：内容区占满视口剩余高度并内部滚动，避免溢出遮挡 */
.kg-doc-graph__body {
  max-height: calc(100vh - 200px);
  overflow-y: auto;
}
/* Tab 栏：拉开间距、激活态主色 + 加粗、hover 提示色（默认挤在一起无区分度） */
.kg-doc-graph__body :deep(.ant-tabs-tab) {
  padding: 8px 4px;
  margin-right: 28px;
  font-size: 13px;
  color: var(--kg-text-2, #8f959e);
}
.kg-doc-graph__body :deep(.ant-tabs-tab:last-child) {
  margin-right: 0;
}
.kg-doc-graph__body :deep(.ant-tabs-tab:hover) {
  color: var(--kg-primary, #1677ff);
}
.kg-doc-graph__body :deep(.ant-tabs-tab.ant-tabs-tab-active .ant-tabs-tab-btn) {
  color: var(--kg-primary, #1677ff);
  font-weight: 600;
}
.kg-doc-graph__body :deep(.ant-tabs-ink-bar) {
  background: var(--kg-primary, #1677ff);
}
.kg-doc-graph__counts {
  margin-bottom: 8px;
  font-size: 11.5px;
  font-variant-numeric: tabular-nums;
}
/* 图谱 Tab 头部：计数与布局切换同行（两端对齐，不换行） */
.kg-doc-graph__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.kg-doc-graph__bar .kg-doc-graph__counts {
  margin-bottom: 0;
  white-space: nowrap;
}
.kg-doc-graph__layout-seg {
  flex: none;
}
.kg-doc-graph__canvas {
  height: 560px;
}
.kg-ent-name {
  font-size: 12.5px;
  color: var(--kg-text);
  line-height: 1.35;
}
.kg-ent-key {
  margin-top: 1px;
  padding: 0 3px;
  display: inline-block;
  border-radius: 3px;
  background: var(--kg-subtle);
  color: var(--kg-code-fg);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 10.5px;
  line-height: 15px;
}
.kg-type-tag {
  display: inline-block;
  padding: 0 7px;
  border: 1px solid transparent;
  border-radius: var(--kg-r-xs);
  font-size: 11px;
  line-height: 18px;
}
.kg-alias-tag {
  background: var(--kg-subtle);
  border-color: var(--kg-border);
  color: var(--kg-text-2);
}
.kg-status {
  display: inline-flex;
  align-items: center;
  height: 19px;
  padding: 0 6px;
  border: 1px solid var(--kg-border);
  border-radius: var(--kg-r-xs);
  background: var(--kg-subtle);
  color: var(--kg-text-2);
  font-size: 11px;
  line-height: 1;
}
.kg-status--active,
.kg-status--accepted {
  border-color: var(--kg-ok-border);
  background: var(--kg-ok-bg);
  color: var(--kg-ok-fg);
}
.kg-status--suggested {
  border-color: var(--kg-warn-border);
  background: var(--kg-warn-bg);
  color: var(--kg-warn-fg);
}
.kg-status--deprecated,
.kg-status--rejected {
  color: var(--kg-text-3);
}
.kg-rel-link {
  color: var(--kg-text);
  cursor: pointer;
}
.kg-rel-link:hover {
  color: var(--kg-primary, #1677ff);
}
.kg-rel-pred {
  margin-top: 2px;
  font-size: 11px;
}
</style>
