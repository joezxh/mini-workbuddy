<template>
  <div class="std-graph-wrap">
    <v-chart v-if="nodes.length" class="std-graph" :option="option" autoresize @click="onClick" />
    <a-empty v-else :description="t('kbMgmt.graph.empty')" />
  </div>
</template>

<script setup lang="ts">
/**
 * 标准关系图（对象=节点，关系=边）：力导向布局，点击节点/边向外抛事件。
 * 只注册用到的 ECharts 模块，避免把整包 echarts 打进首屏。
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { TooltipComponent } from 'echarts/components'

use([GraphChart, CanvasRenderer, TooltipComponent])

const props = defineProps<{
  nodes: any[]
  edges: any[]
  /** 高亮对象标准 code（NL 检索 / 下钻联动） */
  highlightCodes?: string[]
}>()

const emit = defineEmits<{
  (e: 'node-click', id: number): void
  (e: 'edge-click', id: number): void
}>()

const { t } = useI18n()

const highlighted = computed(() => new Set(props.highlightCodes || []))

const option = computed(() => ({
  tooltip: { confine: true },
  series: [
    {
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      label: { show: true, formatter: (p: any) => p.name },
      edgeLabel: { show: true, formatter: (p: any) => p.data.relation_type },
      force: { repulsion: 240, edgeLength: 120 },
      lineStyle: { color: 'source', curveness: 0.1 },
      emphasis: { focus: 'adjacency' },
      data: props.nodes.map((n) => ({
        id: String(n.id),
        name: n.name,
        code: n.code,
        symbolSize: highlighted.value.has(n.code) ? 64 : 48,
        itemStyle: highlighted.value.has(n.code)
          ? { borderColor: '#faad14', borderWidth: 3 }
          : undefined,
      })),
      links: props.edges.map((e) => ({
        source: String(e.from),
        target: String(e.to),
        relation_type: e.relation_type,
        edgeId: e.id,
      })),
    },
  ],
}))

function onClick(p: any) {
  if (p.dataType === 'node') emit('node-click', Number(p.data.id))
  else if (p.dataType === 'edge') emit('edge-click', p.data.edgeId)
}
</script>

<style scoped>
.std-graph-wrap {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.std-graph {
  width: 100%;
  height: 100%;
}
</style>
