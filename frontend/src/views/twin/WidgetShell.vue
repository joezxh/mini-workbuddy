<!-- frontend/src/views/twin/WidgetShell.vue -->
<template>
  <div class="widget-shell" :class="[`st-${vs.branch}`, { masked: vs.masked }]">
    <div class="widget-head">
      <span class="title">{{ widget.title || widget.widget_key }}</span>
      <span v-if="vs.masked" class="mask-flag">🔒</span>
      <span class="wops" v-if="mode === 'edit'">
        <button class="op bind" @click="$emit('bind', widget)">绑定</button>
        <button class="op drill" @click="$emit('drill', widget)">下钻</button>
      </span>
    </div>
    <StateWrapper :loading="loading || vs.loading" :empty="vs.branch === 'empty'"
      :error="vs.branch === 'error' ? vs.errorText : null"
      :empty-title="vs.emptyTitle" :empty-desc="vs.emptyDesc"
      :retryable="vs.retryable" @retry="$emit('retry', widget.id)">
      <component :is="renderer" v-if="renderer && datum" :datum="datum" />
      <div v-else-if="datum && !renderer" class="stub">该形状（{{ datum.result_shape }}）属 P1，暂以表格占位</div>
    </StateWrapper>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import StateWrapper from '@/components/common/StateWrapper.vue'
import { widgetState } from './stateMap'
import KpiWidget from './widgets/KpiWidget.vue'
import TrendWidget from './widgets/TrendWidget.vue'
import BarWidget from './widgets/BarWidget.vue'
import DonutWidget from './widgets/DonutWidget.vue'
import AlertTableWidget from './widgets/AlertTableWidget.vue'
import type { TwinWidget, WidgetDatum, TwinMode, ResultShape } from '@/types/twin'
const props = defineProps<{ widget: TwinWidget; datum: WidgetDatum | null; mode: TwinMode; loading?: boolean }>()
defineEmits<{ retry: [id: number]; bind: [w: TwinWidget]; drill: [w: TwinWidget] }>()
const RENDERERS: Partial<Record<ResultShape, any>> =
  { kpi: KpiWidget, trend: TrendWidget, bar: BarWidget, donut: DonutWidget, table: AlertTableWidget }
const vs = computed(() => props.datum ? widgetState(props.datum, props.mode)
  : { branch: 'empty', loading: props.loading ?? false, emptyTitle: '加载中…', emptyDesc: '', errorText: '', retryable: false, masked: false })
const renderer = computed(() => props.datum ? RENDERERS[props.datum.result_shape ?? 'kpi'] ?? null : null)
</script>
