/**
 * 图表相关类型定义
 */

import type { EChartsOption } from 'echarts'

// 图表类型
export type ChartType = 'line' | 'bar' | 'pie' | 'scatter' | 'radar' | 'funnel' | 'gauge'

// 图表配置
export interface ChartConfig {
  type: ChartType
  title?: string
  data: any[]
  options?: Partial<EChartsOption>
}

// 柱状图数据
export interface BarChartData {
  name: string
  value: number
  [key: string]: any
}

// 折线图数据
export interface LineChartData {
  date: string
  value: number
  series?: string
  [key: string]: any
}

// 饼图数据
export interface PieChartData {
  name: string
  value: number
  percentage?: number
  [key: string]: any
}

// 雷达图数据
export interface RadarChartData {
  name: string
  values: number[]
  max?: number[]
  indicators?: string[]
}

// 漏斗图数据
export interface FunnelChartData {
  name: string
  value: number
  percentage?: number
}

