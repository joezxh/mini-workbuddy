<!-- frontend/src/views/admin/workflow/components/WorkflowDashboard.vue -->
<template>
  <div>
    <a-row :gutter="16">
      <a-col :span="6">
        <a-card title="总工作流数" size="small"><a-statistic :value="stats.totalFlows" /></a-card>
      </a-col>
      <a-col :span="6">
        <a-card title="今日执行" size="small"><a-statistic :value="stats.todayExecutions" /></a-card>
      </a-col>
      <a-col :span="6">
        <a-card title="成功率" size="small"><a-statistic :value="stats.successRate" suffix="%" /></a-card>
      </a-col>
      <a-col :span="6">
        <a-card title="平均延迟" size="small"><a-statistic :value="stats.avgLatency" suffix="ms" /></a-card>
      </a-col>
    </a-row>
    <a-card title="执行趋势" style="margin-top: 16px">
      <div style="height: 300px; display: flex; align-items: center; justify-content: center; color: #999">
        ECharts 图表区域（待接入 ECharts）
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { listFlows, listExecutions } from '@/api/workflow'

const stats = reactive({ totalFlows: 0, todayExecutions: 0, successRate: 0, avgLatency: 0 })

onMounted(async () => {
  try {
    const flowRes = await listFlows({ page: 1, page_size: 1 })
    stats.totalFlows = flowRes.data.total
    const execRes = await listExecutions({ page: 1, page_size: 100 })
    const items = execRes.data.items || []
    stats.todayExecutions = items.length
    const successCount = items.filter((i: any) => i.status === 'success').length
    stats.successRate = items.length ? Math.round(successCount / items.length * 100) : 0
    const latencies = items.filter((i: any) => i.latency_ms).map((i: any) => i.latency_ms)
    stats.avgLatency = latencies.length ? Math.round(latencies.reduce((a: number, b: number) => a + b, 0) / latencies.length) : 0
  } catch { /* ignore */ }
})
</script>
