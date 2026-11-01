<!-- frontend/src/views/twin/widgets/TrendWidget.vue -->
<template>
  <div class="trend-widget">
    <MultiLineChart :x-axis="view.xAxis" :series="view.series" />
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import MultiLineChart from '@/components/charts/MultiLineChart.vue'
import { toMultiLine } from './adapter'
import type { WidgetDatum } from '@/types/twin'
const props = defineProps<{ datum: WidgetDatum }>()
// masked：命中列在系列名后加 🔒（spec §5，以 series name 后缀实现）
const view = computed(() => {
  const m = toMultiLine(props.datum.data as any)
  return {
    xAxis: m.xAxis,
    series: m.series.map((s) => ({
      ...s,
      name: props.datum.masked_fields.includes(s.name) ? `${s.name} 🔒` : s.name,
    })),
  }
})
</script>
