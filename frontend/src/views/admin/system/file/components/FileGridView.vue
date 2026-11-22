<template>
  <div class="file-grid">
    <div
      v-for="file in files"
      :key="file.id"
      class="file-grid__item"
      :class="{ 'file-grid__item--selected': selectedIds.includes(file.id) }"
      @click="$emit('preview', file)"
    >
      <label class="file-grid__check" @click.stop>
        <input type="checkbox" :checked="selectedIds.includes(file.id)" @change="$emit('toggle-select', file.id)" />
      </label>
      <div class="file-grid__thumb">
        <img v-if="isImage(file)" :src="url(file)" :alt="file.name || ''" loading="lazy" />
        <span v-else class="file-grid__ext">{{ ext(file) }}</span>
      </div>
      <div class="file-grid__name" :title="file.name || file.path">{{ file.name || fileName(file) }}</div>
      <div class="file-grid__meta">{{ formatSize(file.size) }} · {{ formatDate(file.createTime) }}</div>
      <div class="file-grid__actions" @click.stop>
        <a-tooltip title="复制链接"><a-button type="text" size="small" @click="$emit('copy-link', file)"><LinkOutlined /></a-button></a-tooltip>
        <a-tooltip title="下载"><a-button type="text" size="small" @click="$emit('download', file)"><DownloadOutlined /></a-button></a-tooltip>
        <a-tooltip title="删除"><a-button type="text" size="small" danger @click="$emit('delete', file)"><DeleteOutlined /></a-button></a-tooltip>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { DownloadOutlined, LinkOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import type { InfraFileVO } from '@/api/file'
import { infraFileApi } from '@/api/file'

defineProps<{ files: InfraFileVO[]; selectedIds: number[] }>()
defineEmits<{
  (e: 'preview', file: InfraFileVO): void
  (e: 'toggle-select', id: number): void
  (e: 'copy-link', file: InfraFileVO): void
  (e: 'download', file: InfraFileVO): void
  (e: 'delete', file: InfraFileVO): void
}>()

function isImage(file: InfraFileVO) { return (file.type || '').startsWith('image/') }
function url(file: InfraFileVO) { return infraFileApi.previewUrl(file) }
function fileName(file: InfraFileVO) { return file.path.split('/').pop() || file.path }
function ext(file: InfraFileVO) { return (fileName(file).split('.').pop() || 'file').slice(0, 5).toUpperCase() }
function formatSize(bytes: number) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)))
  return `${(bytes / Math.pow(1024, i)).toFixed(i ? 1 : 0)} ${units[i]}`
}
function formatDate(v: string | null) { return v ? v.slice(0, 10) : '' }
</script>

<style scoped lang="less">
.file-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px; }
.file-grid__item {
  position: relative; display: flex; flex-direction: column; gap: 8px;
  padding: 12px; border: 1px solid var(--border); border-radius: 10px;
  background: var(--bg-surface); cursor: pointer;
  transition: border-color 160ms ease, transform 160ms ease, box-shadow 160ms ease;
  &:hover { border-color: var(--accent); transform: translateY(-2px); box-shadow: var(--shadow-sm); }
  &--selected { border-color: var(--accent); box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 18%, transparent); }
}
.file-grid__check { position: absolute; top: 18px; left: 18px; z-index: 2; }
.file-grid__thumb { height: 110px; display: grid; place-items: center; background: var(--bg); border-radius: 6px; overflow: hidden; }
.file-grid__thumb img { width: 100%; height: 100%; object-fit: cover; }
.file-grid__ext { font-size: 22px; font-weight: 700; color: var(--accent); letter-spacing: 0.5px; }
.file-grid__name { font-size: 13px; font-weight: 500; color: var(--fg); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-grid__meta { font-size: 11px; color: var(--fg-secondary); }
.file-grid__actions { display: flex; justify-content: flex-end; gap: 2px; }
</style>
