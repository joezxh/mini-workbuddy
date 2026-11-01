<!-- frontend/src/views/twin/TwinPublishedPage.vue —— 只读发布壳：复用 WidgetGrid（mode=run），绝无第二画布 -->
<script lang="ts">
// 反枚举同源文案（W12）：未知 slug / 跨租 / 已停用 / 角色不命中 → 同一句，任何 err 走 denyView 单出口
export function denyView(err: unknown): { show: boolean; text: string } {
  return err ? { show: true, text: '无权访问该页面' } : { show: false, text: '' }
}
</script>
<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import WidgetGrid from './WidgetGrid.vue'
import { getPublished, runPublished } from '@/api/twin'
import type { PublishedMeta, WidgetDatum, TwinWidget } from '@/types/twin'

const props = defineProps<{ slug: string }>()
const meta = ref<PublishedMeta | null>(null)
const pageData = ref<Record<number, WidgetDatum>>({})
const loadError = ref<unknown>(null)
const deny = computed(() => denyView(loadError.value))
const loading = ref(true)
const widgetList = computed<TwinWidget[]>(() =>
  (meta.value?.widgets ?? []).map((w, i) => ({
    id: w.widget_id, page_id: meta.value?.page?.id ?? 0, widget_key: w.widget_key,
    title: w.title, query_id: w.query_id, param_values_json: w.param_values_json,
    display_json: null, grid_json: w.grid_json, refresh_json: w.refresh_json ?? null,
    sort_order: i, updated_at: null,
  })))
let timer: ReturnType<typeof setInterval> | null = null
async function load() {
  loading.value = true
  try {
    meta.value = await getPublished(props.slug)
    const resp = await runPublished(props.slug)
    const next: Record<number, WidgetDatum> = {}
    for (const it of resp.items) next[it.widget_id] = it
    pageData.value = next
    loadError.value = null
  } catch (e) { loadError.value = e } finally { loading.value = false }
}
async function refreshOne(widgetId: number) {
  const resp = await runPublished(props.slug)
  const hit = resp.items.find((i) => i.widget_id === widgetId)
  if (hit) pageData.value = { ...pageData.value, [widgetId]: hit }
}
onMounted(async () => {
  await load()
  const ms = Number((meta.value?.refresh as any)?.interval ?? 10000)
  if (ms > 0) timer = setInterval(() => void load(), ms)
})
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>
<template>
  <div class="published-page">
    <header class="pp-bar">
      <span>{{ meta?.card?.name }} · {{ meta?.page?.name }}</span>
      <span class="pp-ver mono">v{{ meta?.version }} · {{ meta?.published_at }}</span>
    </header>
    <p v-if="deny.show" class="pp-deny">{{ deny.text }}</p>
    <WidgetGrid v-else :widgets="widgetList" :page-data="pageData" mode="run" :loading="loading"
      @retry="refreshOne" />
  </div>
</template>
<style scoped>
.published-page { display: flex; flex-direction: column; min-height: 100vh; background: var(--bg-base); color: var(--fg); }
.pp-bar { display: flex; align-items: center; justify-content: space-between; height: 46px; padding: 0 16px; background: var(--bg-page); border-bottom: 1px solid var(--border); font-size: 13px; }
.pp-ver { font-size: 11px; color: var(--fg-muted); }
.pp-deny { padding: 48px 16px; text-align: center; font-size: 14px; color: var(--fg-secondary); }
</style>
