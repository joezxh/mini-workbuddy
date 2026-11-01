<!-- frontend/src/views/twin/WidgetGrid.vue —— 唯一画布：编辑/运行共用，禁 RunCanvas -->
<template>
  <div class="widget-grid" :class="mode">
    <WidgetShell v-for="w in widgets" :key="w.id" :widget="w" :datum="pageData[w.id] ?? null"
      :mode="mode" :loading="loading" :style="gridStyleOf(w.grid_json)"
      @retry="(id) => $emit('retry', id)" @bind="(x) => $emit('bind', x)" @drill="(x) => $emit('drill', x)" />
  </div>
</template>
<script setup lang="ts">
import WidgetShell from './WidgetShell.vue'
import { gridStyleOf } from './gridStyle'
import type { TwinWidget, WidgetDatum, TwinMode } from '@/types/twin'
defineProps<{ widgets: TwinWidget[]; pageData: Record<number, WidgetDatum>; mode: TwinMode; loading?: boolean }>()
defineEmits<{ retry: [id: number]; bind: [w: TwinWidget]; drill: [w: TwinWidget] }>()
</script>
<style scoped>
.widget-grid { display: grid; grid-template-columns: repeat(12, 1fr); grid-auto-rows: 96px; gap: 10px; }
.widget-grid.run .wops { display: none; }   /* 模式差异唯一实现（原型:125/:163） */
</style>
