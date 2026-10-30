<template>
  <div class="kg-graph-view">
    <div class="kg-graph-view__toolbar">
      <a-space wrap>
        <a-select
          v-model:value="depth"
          style="width: 130px"
          :options="depthOptions"
          @change="reload"
        />
        <a-input-number
          v-model:value="limit"
          :min="10" :max="1000" :step="50" style="width: 130px"
          @change="reload"
        />
        <a-button :loading="loading" @click="reload">{{ t('common.refresh') }}</a-button>
        <a-button :disabled="!seedIds.length" @click="expandFromSeed">
          {{ t('kbMgmt.kg.expandFromSeed') }}
        </a-button>
        <a-button :disabled="!hasSelection" @click="clearSelection">
          {{ t('kbMgmt.kg.clearSelection') }}
        </a-button>
      </a-space>
      <a-space>
        <a-tag v-if="selectedInfo" color="blue">{{ selectedInfo }}</a-tag>
        <span class="kg-graph-view__count">
          {{ t('kbMgmt.kg.nodeCount') }}: {{ nodes.length }} /
          {{ t('kbMgmt.kg.edgeCount') }}: {{ edges.length }}
        </span>
      </a-space>
    </div>

    <div v-if="!nodes.length && !loading" class="kg-graph-view__empty">
      <a-empty :description="t('kbMgmt.kg.graphEmpty')" />
    </div>
    <v-chart v-else class="kg-graph-view__chart" :option="option" autoresize @click="onClick" />
  </div>
</template>

<script setup lang="ts">
/**
 * 图谱视图：ECharts 力导向图（复用标准中心 StdGraphView 的按需注册范式）。
 *
 * 节点=实体、边=关系；节点大小按度数映射（凸显枢纽实体），颜色按类型稳定映射。
 * 交互：点击节点/边 -> 抛事件给检视面板；「以此为种子扩展」-> 换种子重查子图。
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { TooltipComponent } from 'echarts/components'
import * as api from '@/api/kg'
import type { KgGraphEdge, KgGraphNode } from '@/api/kg'

use([GraphChart, CanvasRenderer, TooltipComponent])

const props = defineProps<{ knowledgeId: number }>()
const emit = defineEmits<{
  (e: 'inspect-entity', entityId: number): void
  (e: 'inspect-relation', relationId: number): void
}>()

const { t } = useI18n()

const nodes = ref<KgGraphNode[]>([])
const edges = ref<KgGraphEdge[]>([])
const loading = ref(false)
const seedIds = ref<number[]>([])
const depth = ref(1)
const limit = ref(200)
const selectedInfo = ref('')
const hasSelection = ref(false)

const depthOptions = computed(() => [
  { label: `${t('kbMgmt.kg.depth')} 1`, value: 1 },
  { label: `${t('kbMgmt.kg.depth')} 2`, value: 2 },
  { label: `${t('kbMgmt.kg.depth')} 3`, value: 3 },
])

/** 类型 -> 颜色（稳定映射：同类型同色） */
const TYPE_COLORS = ['#722ed1', '#1890ff', '#52c41a', '#fa8c16', '#eb2f96', '#13c2c2']

function colorOf(code: string) {
  if (!code) return '#bfbfbf'
  let h = 0
  for (let i = 0; i < code.length; i += 1) h = (h * 31 + code.charCodeAt(i)) >>> 0
  return TYPE_COLORS[h % TYPE_COLORS.length]
}

/** 度数 -> 节点大小（枢纽实体更大） */
const degreeMap = computed(() => {
  const m: Record<string, number> = {}
  edges.value.forEach((e) => {
    m[String(e.from)] = (m[String(e.from)] || 0) + 1
    m[String(e.to)] = (m[String(e.to)] || 0) + 1
  })
  return m
})

const option = computed(() => ({
  tooltip: { confine: true },
  series: [
    {
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      label: { show: nodes.value.length <= 120, formatter: (p: any) => p.name },
      edgeLabel: { show: nodes.value.length <= 60, formatter: (p: any) => p.data.relation_type },
      force: { repulsion: 260, edgeLength: 130 },
      lineStyle: { color: 'source', curveness: 0.1 },
      emphasis: { focus: 'adjacency' },
      data: nodes.value.map((n) => ({
        id: String(n.id),
        name: n.name,
        code: n.code,
        symbolSize: Math.min(70, 28 + (degreeMap.value[String(n.id)] || 0) * 8),
        itemStyle: { color: colorOf(n.code || '') },
      })),
      links: edges.value.map((e) => ({
        source: String(e.from),
        target: String(e.to),
        relation_type: e.relation_type,
        edgeId: e.id,
      })),
    },
  ],
}))

async function reload() {
  if (!seedIds.value.length) {
    nodes.value = []
    edges.value = []
    return
  }
  loading.value = true
  try {
    const res = await api.getSubgraph(props.knowledgeId, seedIds.value, depth.value, limit.value)
    nodes.value = res?.nodes || []
    edges.value = res?.edges || []
  } catch (e: any) {
    nodes.value = []
    edges.value = []
  } finally {
    loading.value = false
  }
}

async function expandFromSeed() {
  await reload()
}

/** 供父组件调用：以指定实体为种子重新绘图 */
async function focusEntities(ids: number[]) {
  seedIds.value = ids
  await reload()
}

function clearSelection() {
  seedIds.value = []
  nodes.value = []
  edges.value = []
  selectedInfo.value = ''
  hasSelection.value = false
}

function onClick(p: any) {
  if (p.dataType === 'node') {
    const id = Number(p.data.id)
    selectedInfo.value = p.data.name
    hasSelection.value = true
    emit('inspect-entity', id)
  } else if (p.dataType === 'edge') {
    emit('inspect-relation', p.data.edgeId)
  }
}

watch(() => props.knowledgeId, clearSelection)

defineExpose({ focusEntities, clearSelection })
</script>

<style scoped>
.kg-graph-view {
  width: 100%;
}
.kg-graph-view__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.kg-graph-view__chart {
  width: 100%;
  height: 520px;
}
.kg-graph-view__empty {
  padding: 48px 0;
}
.kg-graph-view__count {
  color: #999;
  font-size: 12px;
}
</style>
