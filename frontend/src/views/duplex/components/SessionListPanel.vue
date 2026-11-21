<template>
  <div class="panel side">
    <div class="panel-title">
      📋 会话列表
      <span class="voice-tag">voice 类型</span>
    </div>
    <div class="sess-list">
      <div v-if="loading" class="sess-state">加载中...</div>
      <a-alert
        v-else-if="error"
        type="error"
        :message="error"
        show-icon
        class="sess-error"
      />
      <a-empty v-else-if="!sessions.length" description="暂无会话" :image="simpleImage" />
      <div
        v-for="s in sessions"
        :key="s.session_id"
        class="sess"
        :class="{ active: selectedId === s.session_id }"
        @click="emit('select', s)"
      >
        <div class="sess-head">
          <span class="sess-title">{{ s.session_title || '未命名会话' }}</span>
          <span class="sess-count">{{ s.message_count }} 条</span>
        </div>
        <div class="sess-meta">
          <span>ID: {{ s.session_id }}</span>
          <span>{{ formatDateTime(s.updated_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Empty } from 'ant-design-vue'
import type { SessionItem } from '../types'
import { formatDateTime } from '../types'

defineProps<{
  sessions: SessionItem[]
  loading: boolean
  error: string | null
  selectedId: number | null
}>()

const emit = defineEmits<{ select: [session: SessionItem] }>()
const simpleImage = Empty.PRESENTED_IMAGE_SIMPLE
</script>

<style scoped>
.side {
  display: flex;
  flex-direction: column;
  max-height: 640px;
}
.panel-title {
  padding: 9px 14px;
  font-size: 13px;
  font-weight: 600;
  color: #9ca3af;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #374151;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.voice-tag {
  margin-left: auto;
  font-size: 10px;
  padding: 1px 7px;
  border-radius: 6px;
  background: rgba(59, 130, 246, 0.16);
  color: #93c5fd;
}
.sess-list {
  padding: 10px;
  overflow-y: auto;
}
.sess-state {
  text-align: center;
  color: #9ca3af;
  font-size: 13px;
  padding: 24px 0;
}
.sess-error {
  margin: 4px 0;
}
.sess {
  padding: 9px 11px;
  background: #1f2937;
  border: 1px solid #374151;
  border-radius: 10px;
  margin-bottom: 7px;
  cursor: pointer;
  transition: all 0.2s;
}
.sess:hover {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.07);
}
.sess.active {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.1);
}
.sess-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.sess-title {
  font-weight: 600;
  font-size: 12px;
  color: #e5e7eb;
}
.sess-count {
  font-size: 10px;
  color: #818cf8;
  background: rgba(99, 102, 241, 0.12);
  padding: 1px 8px;
  border-radius: 8px;
  flex-shrink: 0;
}
.sess-meta {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #9ca3af;
  margin-top: 5px;
}
</style>
