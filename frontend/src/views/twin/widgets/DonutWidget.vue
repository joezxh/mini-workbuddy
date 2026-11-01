<!-- frontend/src/views/twin/widgets/DonutWidget.vue -->
<template>
  <div class="donut-widget">
    <PieChart :data="rows" />
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import PieChart from '@/components/charts/PieChart.vue'
import { toPie } from './adapter'
import type { WidgetDatum } from '@/types/twin'
const props = defineProps<{ datum: WidgetDatum }>()
const rows = computed(() => toPie(props.datum.data as any))
</script>
