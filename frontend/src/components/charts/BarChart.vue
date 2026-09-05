/**
 * 柱状图组件
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
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import type { BarChartData } from '@/types/chart'

use([
  CanvasRenderer,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

interface Props {
  data: BarChartData[]
  title?: string
  xAxisKey?: string
  yAxisKey?: string
  color?: string
  barWidth?: number
  xAxisRotate?: number
  showLegend?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  xAxisKey: 'name',
  yAxisKey: 'value',
  color: '#1b6be0',
  barWidth: 20,
  xAxisRotate: 0,
  showLegend: false
})

/** 根据基础色生成从亮到暗的线性渐变（竖向，由上至下） */
function makeGradient(baseColor: string) {
  // 亮色：在 HSL 空间提亮 20%，深色用原色
  return {
    type: 'linear' as const,
    x: 0, y: 0, x2: 0, y2: 1,
    colorStops: [
      { offset: 0, color: lighten(baseColor, 0.3) },
      { offset: 1, color: darken(baseColor, 0.2) }
    ]
  }
}

/** 十六进制颜色提亮：amount 0~1 */
function lighten(hex: string, amount: number): string {
  const { r, g, b } = hexToRgb(hex)
  return rgbToHex(
    Math.min(255, Math.round(r + (255 - r) * amount)),
    Math.min(255, Math.round(g + (255 - g) * amount)),
    Math.min(255, Math.round(b + (255 - b) * amount))
  )
}

/** 十六进制颜色加深：amount 0~1 */
function darken(hex: string, amount: number): string {
  const { r, g, b } = hexToRgb(hex)
  return rgbToHex(
    Math.max(0, Math.round(r * (1 - amount))),
    Math.max(0, Math.round(g * (1 - amount))),
    Math.max(0, Math.round(b * (1 - amount)))
  )
}

function hexToRgb(hex: string) {
  const clean = hex.replace('#', '')
  const full = clean.length === 3
    ? clean.split('').map(c => c + c).join('')
    : clean
  const num = parseInt(full, 16)
  return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 }
}

function rgbToHex(r: number, g: number, b: number) {
  return '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('')
}

const chartOption = computed(() => ({
  title: props.title ? {
    text: props.title,
    textStyle: { color: '#333', fontSize: 14 }
  } : undefined,
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    borderColor: 'rgba(64, 158, 255, 0.5)',
    textStyle: { color: '#fff' },
    confine: true
  },
  legend: props.showLegend ? {
    show: true,
    top: 0,
    itemWidth: 10,
    itemHeight: 12,
    textStyle: { color: '#666', fontSize: 12 }
  } : { show: false },
  grid: {
    left: 20,
    right: 0,
    top: props.showLegend ? 32 : 18,
    bottom: props.xAxisRotate ? 8 : 0,
    containLabel: true
  },
  xAxis: {
    type: 'category',
    data: props.data.map(item => item[props.xAxisKey]),
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
    axisLabel: { color: '#666', fontSize: 12 },
    splitLine: { lineStyle: { color: 'rgba(137,195,255,0.5)' } },
    axisLine: { show: false }
  },
  series: [
    {
      type: 'bar',
      barWidth: props.barWidth,
      data: props.data.map(item => ({
        value: item[props.yAxisKey],
        itemStyle: {
          color: makeGradient(item.color ?? props.color),
          borderRadius: [4, 4, 0, 0]
        }
      })),
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(64, 158, 255, 0.5)'
        }
      }
    }
  ]
}))
</script>

<style scoped>
.chart {
  width: 100%;
  height: 100%;
}
</style>
