/**
 * 堆积柱状图组件
 */
<template>
  <v-chart class="chart" :option="chartOption" autoresize />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent
} from 'echarts/components'

use([
  CanvasRenderer,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent
])

interface StatusItem {
  code: string
  label: string
  color: string
}

interface DataItem {
  eventTypeName: string
  color?: string
  statusBreakdown?: StatusItem[]
  [key: string]: any
}

interface Props {
  data: DataItem[]
  statusItems?: StatusItem[]
  stacked?: boolean
  barWidth?: number
  xAxisRotate?: number
  showLegend?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  stacked: true,
  barWidth: 20,
  xAxisRotate: 0,
  showLegend: true
})

const DEFAULT_COLORS = [
  '#5470c6',
  '#91cc75',
  '#fac858',
  '#ee6666',
  '#73c0de',
  '#3ba272',
  '#fc8452',
  '#9a60b4',
  '#ea7ccc',
  '#1890ff',
  '#36cfc9',
  '#73d13d',
  '#ff4d4f',
  '#faad14',
  '#722ed1'
]

const chartOption = computed(() => {
  if (!props.data || props.data.length === 0) {
    return {}
  }

  // 从 data 中提取分类名称
  const categoryNames = props.data.map(item => item.eventTypeName)

  // 从 data[0].statusBreakdown 或 props.statusItems 获取状态配置
  const statusItems = props.statusItems || props.data[0]?.statusBreakdown || []

  // 构建 series（每个状态一个系列）
  const series = statusItems.map((status, idx) => ({
    name: status.label,
    type: 'bar' as const,
    stack: props.stacked ? 'total' : undefined,
    barWidth: props.barWidth,
    data: props.data.map(item => item[status.code] ?? 0),
    itemStyle: {
      color: status.color || DEFAULT_COLORS[idx % DEFAULT_COLORS.length]
    }
  }))

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      borderColor: 'rgba(64, 158, 255, 0.5)',
      textStyle: {
        color: '#fff'
      },
      axisPointer: { type: 'shadow' },
      confine: true
    },
    grid: {
      left: 20,
      right: 0,
      top: props.showLegend ? 28 : 8,
      bottom: 0,
      containLabel: true
    },
    legend: props.showLegend ? {
      show: true,
      top: 0,
      itemWidth: 10,
      itemHeight: 12,
      textStyle: { color: '#666', fontSize: 12 },
      data: statusItems.map(s => s.label)
    } : { show: false },
    xAxis: {
      type: 'category',
      data: categoryNames,
      axisLabel: {
        color: '#666',
        fontSize: 12,
        interval: 0,
        rotate: props.xAxisRotate
      },
      axisLine: { lineStyle: { color: 'rgba(137,195,255,0.5)' } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#666', fontSize:12 },
      splitLine: { lineStyle: { color: 'rgba(137,195,255,0.5)' } },
      axisLine: { show: false }
    },
    series
  }
})
</script>

<style scoped>
.chart {
  width: 100%;
  height: 100%;
}
</style>

