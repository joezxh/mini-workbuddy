<template>
  <div class="team-event-block" :class="{ 'is-done': isDone }">
    <div class="team-block-header">
      <span class="team-icon">🏢</span>
      <span class="team-name">{{ teamState.name }}</span>
      <span class="team-status-tag" :class="statusClass">{{ statusText }}</span>
    </div>
    <div class="team-block-meta">
      <span>Agent: {{ teamState.completedAgents }}/{{ teamState.agentsCount }} 完成</span>
      <span v-if="teamState.description"> · {{ teamState.description }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TeamState } from '../types/timeline'

const props = defineProps<{ teamState: TeamState; isDone: boolean }>()
const statusClass = computed(() => `status-${props.teamState.status}`)
const statusText = computed(() => {
  const map: Record<string, string> = { pending: '待启动', running: '执行中', done: '已完成', failed: '失败' }
  return map[props.teamState.status] || props.teamState.status
})
</script>

<style scoped lang="less">
.team-event-block {
  padding: 10px 12px; background: var(--accent-soft); border: 1px solid var(--accent-soft);
  border-radius: 8px; margin-bottom: 8px;
  &.is-done { background: var(--ok-soft); border-color: #b7eb8f; }
}
.team-block-header { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; }
.team-name { color: var(--accent); }
.team-status-tag {
  font-size: 11px; padding: 1px 6px; border-radius: 4px; font-weight: 400;
  &.status-running { background: var(--accent-soft); color: var(--accent); }
  &.status-done { background: var(--ok-soft); color: var(--ok); }
  &.status-failed { background: var(--err-soft); color: var(--err); }
}
.team-block-meta { font-size: 12px; color: var(--fg-secondary); margin-top: 4px; }
</style>
