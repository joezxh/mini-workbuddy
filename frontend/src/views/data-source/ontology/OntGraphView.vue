<template>
  <div class="ont-graph">
    <div class="ont-graph__bar">
      <a-radio-group v-model:value="view" button-style="solid" size="small" @change="reload">
        <a-radio-button value="workflow">{{ t2('工作流视图（表→对象）') }}</a-radio-button>
        <a-radio-button value="architecture">{{ t2('架构视图（对象↔关系）') }}</a-radio-button>
      </a-radio-group>
      <a-tag v-if="stage" :color="stage === 'published' ? 'green' : 'blue'">{{ stage }}</a-tag>
      <span class="ont-graph__counts">{{ countsText }}</span>
    </div>
    <div class="ont-graph__canvas">
      <a-spin :spinning="loading" wrapper-class-name="ont-graph__spin">
        <v-chart v-if="nodes.length" class="ont-graph__chart" :option="option" autoresize @click="onClick" />
        <a-empty v-else :description="t2('暂无已采纳元素——请先在审阅台采纳对象与关系')" />
      </a-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * schema 图（E16，双视图 §6.6/AF-12）：workflow 分层拓扑 / architecture 力导向，共用一套数据与组件。
 * 点击对象节点向外抛 {kind, code}，容器跳检视页签定位（对齐 StdGraphView 事件风格）。
 */
import { computed, onMounted, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { TooltipComponent } from 'echarts/components'
import { ontologyGraph } from '@/api/dataops'
import { t2 } from './ontologyText'

use([GraphChart, CanvasRenderer, TooltipComponent])

const props = defineProps<{ ontologyId: number | null }>()
const emit = defineEmits<{ (e: 'node-click', payload: { kind: string; code: string }): void }>()

const view = ref<'workflow' | 'architecture'>('workflow')
const nodes = ref<any[]>([])
const edges = ref<any[]>([])
const stage = ref('')
const counts = ref<Record<string, number>>({})
const loading = ref(false)

const TYPE_COLOR: Record<string, string> = { object: '#3371fc', table: '#52c41a' }

const countsText = computed(() =>
  Object.entries(counts.value).map(([k, v]) => `${k}:${v}`).join(' · '),
)

const option = computed(() => ({
  tooltip: { confine: true, formatter: (p: any) => (p.dataType === 'edge' ? p.data.name : p.data.label) },
  series: [
    {
      type: 'graph',
      layout: view.value === 'architecture' ? 'force' : 'none',
      roam: true,
      draggable: true,
      categories: [
        { name: 'object', itemStyle: { color: TYPE_COLOR.object } },
        { name: 'table', itemStyle: { color: TYPE_COLOR.table } },
      ],
      label: { show: true, formatter: (p: any) => p.data.label, fontSize: 11 },
      edgeLabel: { show: true, formatter: (p: any) => p.data.name, fontSize: 10 },
      force: { repulsion: 260, edgeLength: 130 },
      lineStyle: { color: 'source', curveness: 0.12 },
      emphasis: { focus: 'adjacency' },
      data: nodes.value.map((n) => ({
        id: n.id,
        name: n.label,
        label: n.label,
        code: n.code,
        type: n.type,
        x: n._x,
        y: n._y,
        symbolSize: n.type === 'object' ? 46 : 36,
        category: n.type === 'table' ? 1 : 0,
      })),
      links: edges.value.map((e) => ({
        source: e.source,
        target: e.target,
        name: e.relation_type || e.label,
      })),
    },
  ],
}))

async function reload() {
  if (!props.ontologyId) return
  loading.value = true
  try {
    const resp: any = await ontologyGraph(props.ontologyId, view.value)
    stage.value = resp?.stage || ''
    counts.value = resp?.counts || {}
    // workflow 简易分层：table 节点在左（x 小），object 在右；architecture 交由力导向
    const list = resp?.nodes || []
    nodes.value = list.map((n: any, i: number) => {
      if (view.value === 'workflow') {
        return { ...n, _x: n.type === 'table' ? 100 : 480, _y: 60 + i * 70 }
      }
      return n
    })
    edges.value = resp?.edges || []
  } finally {
    loading.value = false
  }
}

function onClick(p: any) {
  if (p.dataType === 'node' && p.data.type === 'object') {
    emit('node-click', { kind: 'object', code: p.data.code })
  }
}

watch(() => props.ontologyId, reload)
onMounted(reload)
defineExpose({ reload })
</script>

<style lang="less" scoped>
.ont-graph {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 420px;
  &__bar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
  }
  &__counts {
    color: var(--fg-mute, #999);
    font-size: 12px;
  }
  &__canvas {
    flex: 1;
    min-height: 0;
  }
  &__spin {
    width: 100%;
    height: 100%;
  }
  &__chart {
    width: 100%;
    height: 100%;
    min-height: 420px;
  }
}
</style>
