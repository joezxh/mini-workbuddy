<template>
  <div class="execution-panel" :class="{ 'is-expanded': panelExpanded }">
    <!-- 折叠态：摘要栏 -->
    <div class="panel-summary" @click="togglePanel">
      <div class="summary-left">
        <component :is="statusIconComponent" :size="16" :class="statusIconClass" />
        <span class="summary-text">{{ summaryText }}</span>
      </div>
      <div class="summary-right">
        <span v-if="elapsed > 0" class="summary-elapsed">{{ formatDuration(elapsed) }}</span>
        <ChevronRight :size="14" class="summary-chevron" :class="{ open: panelExpanded }" />
      </div>
    </div>

    <!-- 展开态：完整内容 -->
    <transition name="panel-expand">
      <div v-if="panelExpanded" class="panel-content">
        <!-- Agent 流程图导航 -->
        <AgentFlowGraph
          :agents="agentGroups"
          :agent-ids="agentOrder"
          :selected-id="selectedAgentId"
          @select="selectedAgentId = $event"
        />

        <!-- 运行态拓扑可视化（§13.6）+ v2.1 调度计划批次泳道（spec §9.2） -->
        <TeamTopology
          :agents="agentGroups"
          :agent-ids="agentOrder"
          :plan="plan"
          @select="selectedAgentId = $event"
        />

        <!-- 主体区域：事件流 + 任务面板 -->
        <div class="panel-main">
          <EventStreamView
            :team-state="teamState"
            :agents="agentGroups"
            :agent-ids="agentOrder"
            :selected-agent-id="selectedAgentId"
            :progress-history="progressHistory"
          />
          <TaskPanel v-if="tasks.length > 0" :tasks="tasks" />
        </div>

        <!-- 错误恢复 -->
        <div v-if="hasError" class="panel-error">
          <a-alert type="error" show-icon>
            <template #message>
              {{ errorMessage }}
              <a-button size="small" type="primary" ghost @click="retry">重新连接</a-button>
            </template>
          </a-alert>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { CheckCircle, XCircle, LoaderCircle, ChevronRight } from '@lucide/vue'
import type { ExecutionPanelProps, ExecutionPhase } from '../types/timeline'
import { useExecutionState } from './useExecutionState'
import { formatDuration } from './_shared'
import AgentFlowGraph from './AgentFlowGraph.vue'
import TeamTopology from './TeamTopology.vue'
import EventStreamView from './EventStreamView.vue'
import TaskPanel from './TaskPanel.vue'

const props = withDefaults(defineProps<ExecutionPanelProps>(), {
  status: 'pending',
  streaming: false,
})

// 判断是否为外部传入 composable 状态模式
const isExternalMode = computed(() => !!props.agentGroups)

// 内部 composable（仅在历史回放模式下使用）
const internal = isExternalMode.value
  ? null
  : useExecutionState(props)

// 统一访问器：优先使用外部 props，否则使用内部 composable
const agentGroups = computed(() =>
  isExternalMode.value ? (props.agentGroups || new Map()) : internal!.agentGroups.value
)
const agentOrder = computed(() =>
  isExternalMode.value ? (props.agentOrder || []) : internal!.agentOrder.value
)
const teamState = computed(() =>
  isExternalMode.value
    ? (props.teamState || { id: '', name: '', status: 'pending' as const, agentsCount: 0, completedAgents: 0 })
    : internal!.teamState.value
)
const tasks = computed(() =>
  isExternalMode.value ? (props.tasks || []) : internal!.tasks.value
)
const progressHistory = computed(() =>
  isExternalMode.value
    ? (props.progressHistory || [])
    : internal!.progressHistory.value
)
// v2.1 调度计划状态（dispatch_plan 事件驱动，spec §9.2）
const plan = computed(() =>
  isExternalMode.value ? (props.plan ?? null) : internal!.planState.value
)
const phase = computed<ExecutionPhase>(() => {
  if (isExternalMode.value) {
    if (props.phase) return props.phase
    // 将 status ('pending'|'running'|'completed'|'failed') 映射为 ExecutionPhase
    const s = props.status
    if (s === 'completed' || s === 'failed') return s
    if (s === 'running') return 'streaming'
    return 'idle'
  }
  return internal!.phase.value
})
const hasError = computed(() =>
  isExternalMode.value ? false : internal!.hasError.value
)
const errorMessage = computed(() =>
  isExternalMode.value ? '' : internal!.errorMessage.value
)
const selectedAgentId = ref<string | null>(null)

// 耗时计算（外部模式下从 teamState 推算）
const elapsed = computed(() => {
  if (isExternalMode.value) return 0
  return internal!.elapsed.value
})

// 用户手动展开标记：历史/已完成消息默认折叠（事件过程收起），
// 用户点击摘要栏可手动展开查看完整的 Agent 事件过程
const userExpanded = ref(false)

// 展开状态由 phase 直接驱动（computed）：
// - 流式执行中（streaming）始终展开，实时展示 Agent 事件
// - 历史/已完成的技能消息默认折叠，仅当用户手动点击展开时才显示
const panelExpanded = computed(() => {
  const ph = phase.value
  if (ph === 'streaming' || props.streaming) return true
  // 历史/已完成消息默认折叠，仅当用户手动展开时展示事件过程
  return userExpanded.value
})

// 用户手动切换折叠/展开
function togglePanel() {
  userExpanded.value = !userExpanded.value
}

const summaryText = computed(() => {
  const ts = teamState.value
  if (ts.name) {
    const done = ts.completedAgents
    const total = ts.agentsCount
    if (phase.value === 'streaming') return `${ts.name} - ${done}/${total} Agent 执行中`
    if (phase.value === 'completed') return `${ts.name} - ${total} 个 Agent 执行完成`
    if (phase.value === 'failed') return `${ts.name} - 执行失败`
    return ts.name
  }
  if (phase.value === 'streaming') return '执行中...'
  if (phase.value === 'completed') return '执行完成'
  if (phase.value === 'failed') return '执行失败'
  return '等待执行'
})

const statusIconComponent = computed(() => {
  if (phase.value === 'completed') return CheckCircle
  if (phase.value === 'failed') return XCircle
  if (phase.value === 'streaming') return LoaderCircle
  return CheckCircle
})

const statusIconClass = computed(() => {
  if (phase.value === 'completed') return 'status-icon status-success'
  if (phase.value === 'failed') return 'status-icon status-error'
  if (phase.value === 'streaming') return 'status-icon status-loading'
  return 'status-icon status-pending'
})

onMounted(() => {
  if (!isExternalMode.value) {
    internal!.init()
  }
})

function retry() {
  if (!isExternalMode.value) {
    internal!.retry()
  }
}

defineExpose({ retry })
</script>

<style scoped lang="less">
.execution-panel {
  border: 1px solid var(--border); border-radius: 10px; overflow: hidden;
  background: var(--bg-surface); transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.panel-summary {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; cursor: pointer; background: var(--bg-input);
  &:hover { background: var(--bg-input); }
}
.summary-left { display: flex; align-items: center; gap: 8px; }
.summary-text { font-size: 13px; font-weight: 500; color: var(--fg); }
.summary-right { display: flex; align-items: center; gap: 8px; }
.summary-elapsed { font-size: 11px; color: var(--fg-muted); font-variant-numeric: tabular-nums; }
.summary-chevron { transition: transform 0.2s; color: var(--fg-muted); &.open { transform: rotate(90deg); } }
.panel-content { border-top: 1px solid var(--border); }
.panel-main {
  display: flex; gap: 8px; padding: 0 8px 8px;
  @media (max-width: 640px) { flex-direction: column; }
}
.panel-error { padding: 8px; }

.status-icon {
  &.status-success { color: var(--ok); }
  &.status-error { color: var(--err); }
  &.status-loading { color: var(--accent); animation: spin 1s linear infinite; }
  &.status-pending { color: var(--border); }
}
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.panel-expand-enter-active, .panel-expand-leave-active { transition: all 0.3s ease; overflow: hidden; }
.panel-expand-enter-from, .panel-expand-leave-to { opacity: 0; max-height: 0; }
.panel-expand-enter-to, .panel-expand-leave-from { opacity: 1; max-height: 2000px; }
</style>
