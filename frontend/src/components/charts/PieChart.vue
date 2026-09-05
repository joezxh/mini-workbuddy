/**
 * 饼图组件
 */
<template>
  <v-chart class="chart" :option="chartOption" autoresize />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GraphicComponent
} from 'echarts/components'
import type { PieChartData } from '@/types/chart'

use([
  CanvasRenderer,
  PieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GraphicComponent
])

interface Props {
  data: PieChartData[]
  title?: string
  radius?: [string, string]
  center?: [string, string]
  showLegend?: boolean
  showTotal?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  radius: () => ['40%', '60%'],
  center: () => ['50%', '50%'],
  showLegend: true,
  showTotal: false
})

// 默认色板，数据项未指定颜色时按顺序分配
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
]

const coloredData = computed(() =>
  props.data.map((item, index) => ({
    ...item,
    itemStyle: {
      ...item.itemStyle,
      color: item.itemStyle?.color ?? DEFAULT_COLORS[index % DEFAULT_COLORS.length]
    }
  }))
)

const total = computed(() => props.data.reduce((sum, item) => sum + (item.value || 0), 0))

const chartOption = computed(() => {
  const dataTotal = total.value

  return {
  title: props.title ? {
    text: props.title,
    textStyle: {
      color: '#fff',
      fontSize: 14
    }
  } : undefined,
  tooltip: {
    trigger: 'item',
    confine: true,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    borderColor: 'rgba(64, 158, 255, 0.5)',
    textStyle: {
      color: '#fff'
    },
    formatter: '{b}: {c} ({d}%)'
  },
  legend: props.showLegend ? {
    orient: 'vertical',
    right: '0',
    top: 'center',
    icon: 'circle',
    itemWidth: 8,
    itemHeight: 8,
    textStyle: {
      color: '#333'
    },
    formatter: (name: string) => {
      const item = coloredData.value.find(d => d.name === name)
      if (!item || dataTotal === 0) return name
      const pct = ((item.value / dataTotal) * 100).toFixed(1)
      return `${name}  ${item.value}  ${pct}%`
    }
  } : { show: false },
  graphic: [],
  series: [
    {
      type: 'pie',
      radius: props.radius,
      center: props.center,
      data: coloredData.value,
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(64, 158, 255, 0.5)'
        }
      },
      label: props.showTotal ? {
        show: true,
        position: 'center',
        formatter: () => `{total|${total.value}}\n{label|总数}`,
        rich: {
          total: {
            fontSize: 24,
            fontWeight: 'bold',
            color: '#1677ff',
            lineHeight: 28
          },
          label: {
            fontSize: 16,
            color: '#333',
            lineHeight: 20
          }
        }
      } : { show: false },
      labelLine: {
        show: false
      }
    }
  ]
  }
})
</script>

<style scoped>
.chart {
  width: 100%;
  height: 100%;
}
</style>
