<!--
  ContextHistoryList.vue
  PR-3 Task 14: 通用跨模式历史条目列表组件

  Props:
    - entries: ContextEntry[]    必填,来自 POST /api/v1/ai/context/entries

  用于 ModeContextCard / CrossModeStatsPage 点击"查看历史"后展示
  单模式条目流:source_mode tag + 时间 + 跨模式可读标记 + context_data 预览 + tags。
-->
<template>
  <div class="context-history-list">
    <a-empty v-if="!entries.length" description="暂无历史记录" />
    <div
      v-for="entry in entries"
      :key="entry.id"
      class="history-item"
    >
      <div class="history-header">
        <a-tag color="blue">{{ entry.source_mode }}</a-tag>
        <span class="history-time">{{ formatTime(entry.created_at) }}</span>
        <a-tag v-if="entry.is_cross_mode_accessible" color="green" size="small">
          跨模式可读
        </a-tag>
      </div>
      <div class="history-body">
        <pre class="context-data">{{ formatData(entry.context_data) }}</pre>
        <div v-if="entry.context_tags.length" class="tags">
          <a-tag v-for="t in entry.context_tags" :key="t" size="small">{{ t }}</a-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ContextEntry } from '@/api/aiContext.types'

defineProps<{ entries: ContextEntry[] }>()

function formatTime(iso: string): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

function formatData(data: Record<string, any> | null | undefined): string {
  if (!data) return ''
  try {
    const json = JSON.stringify(data, null, 2)
    return json.length > 500 ? json.slice(0, 500) + '\n...' : json
  } catch {
    return String(data)
  }
}
</script>

<style scoped>
.context-history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.history-item {
  padding: 12px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  background: #fafafa;
}
.history-header {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.history-time {
  color: #999;
  font-size: 12px;
}
.context-data {
  margin: 0;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}
.tags {
  margin-top: 8px;
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
</style>
