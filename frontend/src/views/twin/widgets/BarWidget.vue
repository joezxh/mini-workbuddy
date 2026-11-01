<!-- frontend/src/views/twin/widgets/BarWidget.vue -->
<template>
  <div class="bar-widget">
    <BarChart :data="rows" />
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import BarChart from '@/components/charts/BarChart.vue'
import { toBar } from './adapter'
import type { WidgetDatum } from '@/types/twin'
const props = defineProps<{ datum: WidgetDatum }>()
const rows = computed(() => toBar(props.datum.data as any))
</script>
