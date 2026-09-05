/**
 * 多系列折线图组件
 */
<template>
  <v-chart class="chart" :option="chartOption" autoresize />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'

use([
  CanvasRenderer,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

export interface MultiLineSeries {
  name: string
  data: number[]
  color?: string
}

interface Props {
  xAxis: string[]
  series: MultiLineSeries[]
  title?: string
  smooth?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  smooth: true
})

const DEFAULT_COLORS = [
  '#4096ff', '#52c41a', '#faad14', '#f5222d',
  '#722ed1', '#13c2c2', '#fa8c16', '#eb2f96'
]

const chartOption = computed(() => ({
  title: props.title ? {
    text: props.title,
    textStyle: { color: '#333', fontSize: 12 }
  } : undefined,
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(0, 20, 50, 0.9)',
    borderColor: 'rgba(0, 212, 255, 0.4)',
    textStyle: { color: '#e8f4ff', fontSize: 12 }
  },
  legend: {
    show: true,
    top: 0,
    itemWidth: 8,
    itemHeight: 6,
    textStyle: { color: '#555', fontSize: 12 }
  },
  grid: {
    left: '10%',
    right: '5%',
    top: '20%',
    bottom: '15%'
  },
  xAxis: {
    type: 'category',
    data: props.xAxis,
    axisLabel: { color: '#666', fontSize: 12 },
    axisLine: { lineStyle: { color: '#ccc' } },
    axisTick: { show: false }
  },
  yAxis: {
    type: 'value',
    axisLabel: { color: '#666', fontSize: 12 },
    splitLine: { lineStyle: { color: 'rgba(137,195,255,0.5)' } },
    axisLine: { show: false }
  },
  series: props.series.map((s, i) => ({
    name: s.name,
    type: 'line',
    data: s.data,
    smooth: props.smooth,
    symbol: 'none',
    lineStyle: {
      color: s.color ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length],
      width: 2
    },
    itemStyle: {
      color: s.color ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length]
    }
  }))
}))
</script>

<style scoped>
.chart {
  width: 100%;
  height: 100%;
}
</style>
