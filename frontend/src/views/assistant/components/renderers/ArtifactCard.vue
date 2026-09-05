<template>
  <div class="artifact-card" v-if="artifacts.length">
    <div class="artifact-header">
      <PaperClipOutlined :size="14" />
      <span>产物文件 ({{ artifacts.length }})</span>
    </div>
    <div class="artifact-list">
      <div v-for="art in artifacts" :key="art.file_id" class="artifact-item">
        <component :is="iconFor(art.mime_type)" class="artifact-icon" />
        <div class="artifact-info">
          <span class="artifact-name" :title="art.filename">{{ art.filename }}</span>
          <span class="artifact-size">{{ formatSize(art.size_bytes) }}</span>
        </div>
        <a-button size="small" type="link" @click="handleDownload(art)">
          <DownloadOutlined /> 下载
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  FileTextOutlined,
  FileWordOutlined,
  FileExcelOutlined,
  PaperClipOutlined,
  DownloadOutlined,
} from '@ant-design/icons-vue'
import { artifactDownloadUrl, type ArtifactItem } from '@/api/skill'
import { getToken } from '@/utils/auth'

defineProps<{ artifacts: ArtifactItem[] }>()

function iconFor(mime: string) {
  if (mime.includes('pdf')) return FileTextOutlined
  if (mime.includes('sheet') || mime.includes('excel')) return FileExcelOutlined
  if (mime.includes('word') || mime.includes('document')) return FileWordOutlined
  return FileTextOutlined
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function handleDownload(art: ArtifactItem) {
  const url = artifactDownloadUrl(art.file_id)
  // token 统一从 @/utils/auth 读取（键名 miniworkbuddy_token），
  // 直接读 localStorage['token'] 会取到空值，导致下载请求 401。
  const token = getToken()
  fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    .then(r => r.blob())
    .then(blob => {
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = art.filename
      a.click()
      URL.revokeObjectURL(a.href)
    })
}
</script>

<style scoped>
.artifact-card {
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  padding: 10px 12px;
  margin: 8px 0;
  background: #fafafa;
}
.artifact-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}
.artifact-list { display: flex; flex-direction: column; gap: 6px; }
.artifact-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px;
  border-radius: 4px;
  background: #fff;
  border: 1px solid #f0f0f0;
}
.artifact-icon { color: #1890ff; flex-shrink: 0; }
.artifact-info { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.artifact-name {
  font-size: 13px; color: #333;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.artifact-size { font-size: 11px; color: #999; }
</style>
