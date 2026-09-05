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
  overflow-x: auto; background: #fafafa; border-radius: 8px;
  border: 1px solid #f0f0f0; margin-bottom: 8px; flex-wrap: wrap;
}
.flow-node {
  display: flex; align-items: center; gap: 4px; padding: 4px 10px;
  border: 1px solid #d9d9d9; border-radius: 16px; font-size: 12px;
  background: #fff; cursor: pointer; white-space: nowrap; transition: all 0.2s;
  &:hover { border-color: #1677ff; color: #1677ff; }
  &.active { border-color: #1677ff; background: #e6f7ff; color: #1677ff; }
  &.status-done { border-color: #b7eb8f; color: #52c41a; }
  &.status-running { border-color: #91caff; color: #1677ff; }
  &.status-error { border-color: #ffccc7; color: #ff4d4f; }
  &.status-pending { color: #bbb; }
}
.flow-node-all { font-weight: 600; }
.flow-arrow { color: #d9d9d9; font-size: 14px; flex-shrink: 0; }
.node-label { font-weight: 500; }
.node-elapsed { font-size: 10px; color: #999; margin-left: 2px; }
</style>
