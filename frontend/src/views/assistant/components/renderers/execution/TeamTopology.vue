<script setup lang="ts">
import { computed } from 'vue'
import type { DispatchPlanState } from '../types/timeline'
/**
 * TeamTopology —— 运行态拓扑可视化（设计文档 §13.6）
 *
 * 根据 useExecutionState 提供的 agentGroups / agentOrder，实时渲染团队成员状态：
 *   - pending / running / done / error 状态药丸
 *   - TeamSay 通道标识（@提及 单点追问）
 *   - 运行态干预暂停标记（paused）
 * 数据由 SSE 事件流（AGENT_START / AGENT_COMPLETE / AGENT_ERROR）驱动，无需额外接口。
 * v2.1（spec §9.2）：plan prop 驱动调度计划批次泳道（dispatch_plan 事件）。
 */
interface AgentStateLike {
  id: string
  name: string
  role?: string
  status: 'pending' | 'running' | 'done' | 'error'
  channel?: 'leader' | 'teamsay'
  nodeKey?: string
  paused?: boolean
  startTime?: number
  endTime?: number
}

const props = defineProps<{
  agents: Map<string, AgentStateLike>
  agentIds: string[]
  plan?: DispatchPlanState | null
}>()

const emit = defineEmits<{ (e: 'select', id: string): void }>()

const STATUS_LABEL: Record<string, string> = {
  pending: '待命',
  running: '执行中',
  done: '已完成',
  error: '出错',
}

const BATCH_STATUS_LABEL: Record<string, string> = {
  pending: '待执行',
  running: '执行中',
  done: '已完成',
}

const ordered = computed(() => {
  const ids = props.agentIds?.length ? props.agentIds : Array.from(props.agents.keys())
  return ids
    .map((id) => props.agents.get(id))
    .filter((a): a is AgentStateLike => !!a)
})

const activeCount = computed(
  () => ordered.value.filter((a) => a.status === 'running').length
)
const doneCount = computed(
  () => ordered.value.filter((a) => a.status === 'done').length
)

const memberStatus = (name: string): AgentStateLike['status'] =>
  props.agents.get(name)?.status || 'pending'

const batchSummary = computed(() => {
  if (!props.plan?.batches?.length) return null
  const done = props.plan.batches.filter((b) => b.status === 'done').length
  return `${done}/${props.plan.batches.length} 批次完成`
})
</script>

<template>
  <div class="team-topology">
    <div class="tt-header">
      <span class="tt-title">运行态拓扑</span>
      <span class="tt-summary">
        <template v-if="batchSummary">{{ batchSummary }} · </template>
        {{ doneCount }}/{{ ordered.length }} 成员完成 · {{ activeCount }} 执行中
      </span>
    </div>
    <!-- v2.1 调度计划批次泳道（spec §9.2）：Leader 生成的动态拓扑 -->
    <div v-if="plan?.batches?.length" class="tt-batches">
      <div
        v-for="batch in plan.batches"
        :key="batch.batch_no"
        class="tt-batch"
        :class="`is-${batch.status}`"
      >
        <span class="tt-batch-no">批{{ batch.batch_no }}</span>
        <button
          v-for="mem in batch.members"
          :key="mem.role_name"
          class="tt-node tt-batch-member"
          :class="`is-${memberStatus(mem.role_name)}`"
          @click="emit('select', mem.role_name)"
        >
          <span class="tt-dot" />
          <span class="tt-name">{{ mem.role_name }}</span>
        </button>
        <span class="tt-batch-status">{{ BATCH_STATUS_LABEL[batch.status] || batch.status }}</span>
      </div>
      <div v-if="plan.planReason" class="tt-plan-reason">编排理由：{{ plan.planReason }}</div>
    </div>
    <div class="tt-grid">
      <button
        v-for="a in ordered"
        :key="a.id"
        class="tt-node"
        :class="[`is-${a.status}`, { 'is-teamsay': a.channel === 'teamsay', 'is-paused': a.paused }]"
        @click="emit('select', a.id)"
      >
        <span class="tt-dot" />
        <span class="tt-name">{{ a.name }}</span>
        <span v-if="a.channel === 'teamsay'" class="tt-badge tt-badge-say">@</span>
        <span v-if="a.paused" class="tt-badge tt-badge-pause">暂停</span>
        <span class="tt-status">{{ STATUS_LABEL[a.status] }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.team-topology {
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--panel-bg, var(--bg-input));
  margin-bottom: 10px;
}
.tt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.tt-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--text-strong, #111827);
}
.tt-summary {
  font-size: 12px;
  color: var(--text-muted, #6b7280);
}
.tt-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.tt-node {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid var(--border-color, #e5e7eb);
  background: var(--bg-surface);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s ease;
}
.tt-node:hover {
  border-color: #6366f1;
}
.tt-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #9ca3af;
}
.tt-node.is-running .tt-dot { background: #3b82f6; animation: tt-pulse 1.2s infinite; }
.tt-node.is-done .tt-dot { background: #22c55e; }
.tt-node.is-error .tt-dot { background: #ef4444; }
.tt-node.is-pending .tt-dot { background: #9ca3af; }
.tt-name { font-weight: 500; }
.tt-status { color: var(--text-muted, #6b7280); }
.tt-badge {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 600;
}
.tt-badge-say { background: #ede9fe; color: #7c3aed; }
.tt-badge-pause { background: #fef3c7; color: #b45309; }
/* v2.1 调度计划批次泳道 */
.tt-batches { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
.tt-batch {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  padding: 6px 8px; border-radius: 6px;
  border: 1px dashed var(--border-color, #e5e7eb);
}
.tt-batch.is-running { border-color: #3b82f6; background: rgba(59, 130, 246, 0.06); }
.tt-batch.is-done { opacity: 0.65; }
.tt-batch-no { font-size: 11px; font-weight: 600; color: var(--text-muted, #6b7280); min-width: 34px; }
.tt-batch-status { font-size: 11px; color: var(--text-muted, #6b7280); margin-left: auto; }
.tt-plan-reason { font-size: 11px; color: var(--text-muted, #6b7280); margin-top: 2px; }
@keyframes tt-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
