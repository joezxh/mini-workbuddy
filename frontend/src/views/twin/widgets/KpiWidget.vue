<!-- frontend/src/views/twin/widgets/KpiWidget.vue -->
<template>
  <div class="kpi-widget">
    <span class="kpi-value mono">{{ locked ? '🔒' : display }}</span>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { kpiValue } from './adapter'
import type { WidgetDatum } from '@/types/twin'
const props = defineProps<{ datum: WidgetDatum }>()
const locked = computed(() => props.datum.masked_fields.includes(props.datum.columns[0] ?? ''))
const display = computed(() => {
  const v = kpiValue(props.datum.data as any)
  return v == null ? '-' : String(v)
})
</script>
