<template>
  <div class="agent-section">
    <div class="agent-section-header">
      <component :is="statusIcon" :size="14" :class="iconClass" />
      <span class="agent-name">{{ agent.name }}</span>
      <span v-if="agent.role" class="agent-role">({{ agent.role }})</span>
      <span v-if="elapsed" class="agent-elapsed">{{ elapsed }}</span>
    </div>
    <div class="agent-section-body">
      <slot></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CheckCircle, XCircle, LoaderCircle, Circle } from '@lucide/vue'
import type { AgentState } from '../types/timeline'
import { formatDuration } from './_shared'

const props = defineProps<{ agent: AgentState }>()

const statusIcon = computed(() => {
  const status = props.agent.status as 'done' | 'error' | 'running' | 'pending'
  const map = {
    done: CheckCircle, error: XCircle, running: LoaderCircle, pending: Circle,
  }
  return map[status] || Circle
})
const iconClass = computed(() => {
  const status = props.agent.status as 'done' | 'error' | 'running' | 'pending'
  const map = { done: 'icon-success', error: 'icon-error', running: 'icon-loading', pending: 'icon-pending' }
  return map[status] || 'icon-pending'
})
const elapsed = computed(() => {
  if (!props.agent.startTime) return ''
  const end = props.agent.endTime || Date.now()
  return formatDuration(end - props.agent.startTime)
})
</script>

<style scoped lang="less">
.agent-section { margin-bottom: 12px; }
.agent-section-header {
  display: flex; align-items: center; gap: 6px; padding: 6px 0;
  border-bottom: 1px solid #f0f0f0; margin-bottom: 6px; font-size: 13px;
}
.agent-name { font-weight: 600; color: #333; }
.agent-role { color: #999; font-size: 12px; }
.agent-elapsed { margin-left: auto; font-size: 11px; color: #999; font-variant-numeric: tabular-nums; }
.icon-success { color: #52c41a; }
.icon-error { color: #ff4d4f; }
.icon-loading { color: #1677ff; animation: spin 1s linear infinite; }
.icon-pending { color: #d9d9d9; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.agent-section-body { padding-left: 4px; }
</style>
