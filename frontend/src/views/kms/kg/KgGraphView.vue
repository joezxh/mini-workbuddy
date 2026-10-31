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
          {{ t('kbMgmt.kg.nodeEdgeCount', { nodes: canvasNodes.length, edges: canvasEdges.length }) }}
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
      <!-- 画布：共享 SVG 画布组件（点阵底 / 贝塞尔边 / 半径随度数 / 邻接聚焦），皮肤来自 graph-tokens.css -->
      <GraphCanvas
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
 * 图谱画布宿主：取数 / 筛选 / 导出 / 检视联动（渲染已抽出到 GraphCanvas.vue）。
 *
 * - 取数：全库图走 /graph/full（按度数截断），种子子图走 /graph/subgraph。
 * - 呈现：把 KgGraphNode/Edge 映射成 CanvasNode/CanvasEdge（取色、显示名在此算好）交给画布。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import * as api from '@/api/kg'
import type { KgGraphEdge, KgGraphNode, KgSubgraph } from '@/api/kg'
import { typeLabel as typeName, typeTone } from '@/components/common/graph/graphTheme'
import GraphCanvas from '@/components/common/graph/GraphCanvas.vue'
import type { CanvasEdge, CanvasNode, CanvasSelection } from '@/components/common/graph/graphTypes'
import KgInspector from './KgInspector.vue'

const props = defineProps<{ knowledgeId: number }>()
const emit = defineEmits<{ (e: 'provenance', entityId: number): void }>()

const { t } = useI18n()

type Mode = 'full' | 'type' | 'seed'
const MODES: { value: Mode; label: string }[] = [
  { value: 'full', label: 'kbMgmt.kg.graphModeFull' },
  { value: 'type', label: 'kbMgmt.kg.graphModeType' },
  { value: 'seed', label: 'kbMgmt.kg.graphModeSeed' },
]

const rawNodes = ref<KgGraphNode[]>([])
const rawEdges = ref<KgGraphEdge[]>([])
const loading = ref(false)
const exporting = ref(false)
const selection = ref<CanvasSelection | null>(null)

const mode = ref<Mode>('full')
const typeFilter = ref<string>('')
const relationFilter = ref<string>('')
const depth = ref(2)
const limit = ref(200)
const hideChunk = ref(true)
const seeds = ref<number[]>([])
const typeOptions = ref<{ label: string; value: string }[]>([])
const relationOptions = ref<{ label: string; value: string }[]>([])

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

/** 把 KG 节点映射成画布契约：隐藏 Chunk / 种子类型过滤留在此宿主，取色与显示名也在此算好 */
const canvasNodes = computed<CanvasNode[]>(() =>
  rawNodes.value
    .filter((node) => {
      if (hideChunk.value && isChunkNode(node)) return false
      const code = node.code || node.type_code || ''
      // 种子子图的接口没有类型过滤参数，前端补一道
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

const selectedNodeId = computed(() =>
  selection.value?.kind === 'node' ? selection.value.id : null,
)

function onProvenance(entityId: number) {
  emit('provenance', entityId)
}

async function reload() {
  loading.value = true
  try {
    let res: KgSubgraph | undefined
    if (mode.value === 'seed') {
      if (!seeds.value.length) {
        rawNodes.value = []
        rawEdges.value = []
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
  } catch {
    rawNodes.value = []
    rawEdges.value = []
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
