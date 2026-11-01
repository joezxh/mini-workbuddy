<!-- frontend/src/views/twin/widgets/AlertTableWidget.vue -->
<template>
  <div class="alert-table-widget">
    <a-table :columns="cols" :data-source="rows" :pagination="false" size="small" row-key="__rowKey" />
    <p v-if="datum.truncated" class="trunc-note">已截断（上限 200 行）</p>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { toTable } from './adapter'
import type { WidgetDatum } from '@/types/twin'
const props = defineProps<{ datum: WidgetDatum }>()
const rows = computed(() => toTable(props.datum.data as any).map((r, i) => ({ ...r, __rowKey: i })))
interface Col { title: string; dataIndex: string; key: string; customRender: (opt: { text: unknown }) => unknown }
// masked_fields 命中的列：值位一律渲染 🔒（spec §5：masked 不进 StateWrapper）
const cols = computed<Col[]>(() => props.datum.columns.map((c) => ({
  title: c, dataIndex: c, key: c,
  customRender: ({ text }: { text: unknown }) => (props.datum.masked_fields.includes(c) ? '🔒' : text),
})))
</script>
