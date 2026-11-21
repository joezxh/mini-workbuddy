<template>
  <div class="panel event-panel">
    <div class="panel-title">📜 运行时事件流</div>
    <div class="event-log">
      <div v-for="(e, i) in logs" :key="i" class="event-line">
        <span class="ts">{{ e.ts }}</span>
        <span class="evt">{{ e.evt }}</span>
        <span class="msg">{{ e.msg }}</span>
      </div>
      <div v-if="!logs.length" class="event-empty">暂无事件</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { LogEntry } from '../types'

defineProps<{ logs: LogEntry[] }>()
</script>

<style scoped>
.event-panel {
  grid-column: 1 / -1;
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
}
.event-log {
  max-height: 120px;
  overflow-y: auto;
  padding: 8px 14px;
  background: rgba(0, 0, 0, 0.3);
  font-family: monospace;
  font-size: 11px;
}
.event-line {
  padding: 2px 0;
  display: flex;
  gap: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}
.event-line .ts {
  color: #6b7280;
  flex-shrink: 0;
}
.event-line .evt {
  color: #818cf8;
  flex-shrink: 0;
  min-width: 88px;
}
.event-line .msg {
  color: #d1d5db;
}
.event-empty {
  color: #6b7280;
  text-align: center;
  padding: 12px 0;
}
</style>
