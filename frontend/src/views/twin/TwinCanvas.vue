<!-- frontend/src/views/twin/TwinCanvas.vue —— 中栏画布容器：承载唯一 WidgetGrid（编辑/运行共用） -->
<template>
  <div class="twin-canvas">
    <WidgetGrid :widgets="store.widgets" :page-data="store.pageData" :mode="store.mode"
      :loading="store.loadingPage" @retry="onRetry" @bind="onBind" @drill="onDrill" />
  </div>
</template>
<script setup lang="ts">
import WidgetGrid from './WidgetGrid.vue'
import { useTwinStore } from '@/stores/twin'
import type { TwinWidget } from '@/types/twin'
const store = useTwinStore()
function onRetry(id: number) { void store.retryWidget(id) }
// bind/drill 本任务先占位；Task 8 接 BindDrawer / DrillOverlay
function onBind(w: TwinWidget) { console.log('[twin] bind →', w.id) }
function onDrill(w: TwinWidget) { console.log('[twin] drill →', w.id) }
</script>
<style scoped>
.twin-canvas { flex: 1; min-height: 0; overflow: auto; padding: 12px; background: var(--bg-base); }
</style>
