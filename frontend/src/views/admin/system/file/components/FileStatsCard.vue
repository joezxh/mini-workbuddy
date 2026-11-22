<template>
  <button
    type="button"
    class="stats-card"
    :class="{ 'stats-card--active': selected, 'stats-card--loading': loading }"
    @click="$emit('select', stats.configId)"
  >
    <span class="stats-card__top">
      <span class="stats-card__name">{{ stats.configName }}</span>
      <a-tag :color="storageColor" class="stats-card__tag">{{ storageLabel }}</a-tag>
    </span>
    <span class="stats-card__metric">
      <strong>{{ formatCount(stats.fileCount) }}</strong>
      <span class="stats-card__metric-label">个文件</span>
    </span>
    <span class="stats-card__size">{{ formatSize(stats.totalSize) }}</span>
    <span class="stats-card__bar" aria-hidden="true">
      <span class="stats-card__bar-fill" :style="{ width: percent + '%' }" />
    </span>
    <span class="stats-card__foot">
      <span>占群集容量 {{ percent }}%</span>
      <a-tag v-if="master" color="gold" class="stats-card__master">主</a-tag>
    </span>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FileStatistics } from '@/api/file'
import { FileStorageLabels, FileStorageColorMap } from '@/api/file'

const props = defineProps<{
  stats: FileStatistics
  selected: boolean
  loading?: boolean
  master?: boolean
}>()
defineEmits<{ (e: 'select', id: number): void }>()

const storageLabel = computed(() => FileStorageLabels[props.stats.storageType] || `类型 ${props.stats.storageType}`)
const storageColor = computed(() => FileStorageColorMap[props.stats.storageType] || 'default')
const percent = computed(() => {
  const cap = 10 * 1024 * 1024 * 1024
  return Math.min(100, Math.round((props.stats.totalSize / cap) * 100))
})

function formatCount(n: number) {
  return new Intl.NumberFormat('zh-CN').format(n)
}
function formatSize(bytes: number) {
  if (bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)))
  return `${(bytes / Math.pow(1024, i)).toFixed(i ? 1 : 0)} ${units[i]}`
}
</script>

<style scoped lang="less">
.stats-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 210px;
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-surface);
  text-align: left;
  cursor: pointer;
  transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;

  &:hover {
    border-color: var(--accent);
    transform: translateY(-2px);
    box-shadow: var(--shadow-sm);
  }
  &--active {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 6%, var(--bg-surface));
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 18%, transparent);
  }
  &--loading { opacity: 0.65; pointer-events: none; }
}
.stats-card__top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.stats-card__name { font-size: 14px; font-weight: 600; color: var(--fg); }
.stats-card__tag { margin-inline-end: 0; }
.stats-card__metric { display: flex; align-items: baseline; gap: 6px; }
.stats-card__metric strong { font-size: 26px; font-weight: 700; line-height: 1; color: var(--fg); }
.stats-card__metric-label { font-size: 12px; color: var(--fg-secondary); }
.stats-card__size { font-size: 13px; color: var(--fg-secondary); }
.stats-card__bar { display: block; height: 4px; border-radius: 2px; background: var(--border); overflow: hidden; }
.stats-card__bar-fill { display: block; height: 100%; background: var(--accent); border-radius: 2px; transition: width 400ms ease; }
.stats-card__foot { display: flex; align-items: center; justify-content: space-between; font-size: 11px; color: var(--fg-muted, var(--fg-secondary)); }
.stats-card__master { margin-inline-end: 0; }
</style>
