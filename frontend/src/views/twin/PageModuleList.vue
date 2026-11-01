<!-- frontend/src/views/twin/PageModuleList.vue —— 左下模块 palette：5 类 P0 壳形（点击走 Task 8 AddModuleModal） -->
<template>
  <div class="module-palette">
    <div class="mp-title">页面模块</div>
    <div class="mp-grid">
      <button v-for="m in MODULES" :key="m.shape" class="mp-item" :disabled="!store.activePageId"
        @click="$emit('add', m.shape)">
        <span class="mp-icon">{{ m.icon }}</span><span class="mp-label">{{ m.label }}</span>
      </button>
    </div>
  </div>
</template>
<script setup lang="ts">
import type { ResultShape } from '@/types/twin'
import { useTwinStore } from '@/stores/twin'
defineEmits<{ add: [shape: ResultShape] }>()
const store = useTwinStore()
// 仅 5 类 P0 壳形；entity_set/graph 属 P1，不列入 palette
const MODULES: { shape: ResultShape; label: string; icon: string }[] = [
  { shape: 'kpi', label: '核心指标', icon: '📊' },
  { shape: 'trend', label: '趋势折线', icon: '📈' },
  { shape: 'bar', label: '柱状对比', icon: '📶' },
  { shape: 'donut', label: '环形占比', icon: '🍩' },
  { shape: 'table', label: '明细表格', icon: '📋' },
]
</script>
<style scoped>
.module-palette { display: flex; flex-direction: column; gap: 8px; padding: 10px; border-top: 1px solid var(--border); flex: none; }
.mp-title { font-size: 12px; color: var(--fg-secondary); font-weight: 600; }
.mp-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; }
.mp-item { display: flex; align-items: center; gap: 6px; padding: 8px; font-size: 12px; color: var(--fg); background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px; cursor: pointer; text-align: left; }
.mp-item:disabled { opacity: .4; cursor: not-allowed; }
.mp-item:hover:not(:disabled) { border-color: var(--border-strong); }
.mp-icon { font-size: 14px; }
</style>
