/**
 * 折线图组件
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
import type { LineChartData } from '@/types/chart'

use([
  CanvasRenderer,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

interface Props {
  data: LineChartData[]
  title?: string
  smooth?: boolean
  color?: string | string[]
}

const props = withDefaults(defineProps<Props>(), {
  smooth: true,
  color: '#409eff'
})

const chartOption = computed(() => ({
  title: props.title ? {
    text: props.title,
    textStyle: {
      color: '#fff',
      fontSize: 14
    }
  } : undefined,
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    borderColor: 'rgba(64, 158, 255, 0.5)',
    textStyle: {
      color: '#fff'
    }
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    top: props.title ? '15%' : '3%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    data: props.data.map(item => item.date),
    axisLine: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.3)'
      }
    },
    axisLabel: {
      color: 'rgba(255, 255, 255, 0.7)'
    }
  },
  yAxis: {
    type: 'value',
    axisLine: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.3)'
      }
    },
    axisLabel: {
      color: 'rgba(255, 255, 255, 0.7)'
    },
    splitLine: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.1)'
      }
    }
  },
  series: [
    {
      type: 'line',
      data: props.data.map(item => item.value),
      smooth: props.smooth,
      lineStyle: {
        color: Array.isArray(props.color) ? props.color[0] : props.color,
        width: 2
      },
      itemStyle: {
        color: Array.isArray(props.color) ? props.color[0] : props.color
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            {
              offset: 0,
              color: Array.isArray(props.color) 
                ? `${props.color[0]}80` 
                : `${props.color}80`
            },
            {
              offset: 1,
              color: Array.isArray(props.color) 
                ? `${props.color[0]}00` 
                : `${props.color}00`
            }
          ]
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
  min-height: 300px;
}
</style>

