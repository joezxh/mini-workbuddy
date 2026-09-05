<template>
  <div class="agent-flow-graph">
    <!-- "全部" 按钮 -->
    <button
      class="flow-node flow-node-all"
      :class="{ active: selectedId === null }"
      @click="$emit('select', null)"
    >
      全部
    </button>

    <!-- Agent 节点 -->
    <template v-for="agentId in agentIds" :key="agentId">
      <div class="flow-arrow">→</div>
      <button
        class="flow-node"
        :class="[`status-${agents.get(agentId)?.status || 'pending'}`, { active: selectedId === agentId }]"
        @click="$emit('select', agentId)"
      >
        <component :is="getIcon(agentId)" :size="12" />
        <span class="node-label">{{ agents.get(agentId)?.name || agentId }}</span>
        <span v-if="getElapsed(agentId)" class="node-elapsed">{{ getElapsed(agentId) }}</span>
      </button>
    </template>
  </div>
</template>

<script setup lang="ts">
import { CheckCircle, XCircle, LoaderCircle, Circle } from '@lucide/vue'
import type { AgentState } from '../types/timeline'
import { formatDuration } from './_shared'

const props = defineProps<{
  agents: Map<string, AgentState>
  agentIds: string[]
  selectedId: string | null
}>()

defineEmits<{ (e: 'select', agentId: string | null): void }>()

function getIcon(agentId: string) {
  const status = (props.agents.get(agentId)?.status || 'pending') as 'done' | 'error' | 'running' | 'pending'
  const map = { done: CheckCircle, error: XCircle, running: LoaderCircle, pending: Circle }
  return map[status] || Circle
}

function getElapsed(agentId: string): string {
  const agent = props.agents.get(agentId)
  if (!agent?.startTime) return ''
  const end = agent.endTime || Date.now()
  return formatDuration(end - agent.startTime)
}
</script>

<style scoped lang="less">
.agent-flow-graph {
  display: flex; align-items: center; gap: 4px; padding: 8px 12px;
  overflow-x: auto; background: var(--bg-input); border-radius: 8px;
  border: 1px solid var(--border); margin-bottom: 8px; flex-wrap: wrap;
}
.flow-node {
  display: flex; align-items: center; gap: 4px; padding: 4px 10px;
  border: 1px solid var(--border); border-radius: 16px; font-size: 12px;
  background: var(--bg-surface); cursor: pointer; white-space: nowrap; transition: all 0.2s;
  &:hover { border-color: var(--accent); color: var(--accent); }
  &.active { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); }
  &.status-done { border-color: #b7eb8f; color: var(--ok); }
  &.status-running { border-color: var(--accent-soft); color: var(--accent); }
  &.status-error { border-color: #ffccc7; color: var(--err); }
  &.status-pending { color: var(--fg-muted); }
}
.flow-node-all { font-weight: 600; }
.flow-arrow { color: var(--border); font-size: 14px; flex-shrink: 0; }
.node-label { font-weight: 500; }
.node-elapsed { font-size: 10px; color: var(--fg-muted); margin-left: 2px; }
</style>
