<template>
  <div class="plan-execution-panel">
    <div class="pep-header" @click="expanded = !expanded">
      <span class="pep-title">
        📋 {{ t('assistantChat.plan.title') }}
        <span v-if="streaming" class="pep-streaming-tag">{{ t('assistantChat.plan.running') }}</span>
      </span>
      <span v-if="tasks.length" class="pep-progress-label">
        {{ t('assistantChat.plan.progress', { done: progress.completed, total: progress.total }) }}
      </span>
      <CaretRightOutlined :class="['pep-caret', { expanded }]" />
    </div>

    <div v-show="expanded" class="pep-body">
      <!-- 进度条 -->
      <a-progress
        v-if="tasks.length"
        :percent="progress.percent"
        :show-info="false"
        size="small"
        class="pep-progress-bar"
      />

      <!-- 当前活动（plan_task_activity：正在创建/更新/读取任务…） -->
      <div v-if="activity && streaming" class="pep-activity">
        <LoadingOutlined spin />
        <span>{{ activityLabel }}</span>
      </div>

      <!-- 任务清单卡片：subject/state/blocked_by 依赖、in_progress 高亮 -->
      <div v-if="tasks.length" class="pep-tasks">
        <div
          v-for="task in tasks"
          :key="task.id"
          class="pep-task"
          :class="`state-${task.state}`"
        >
          <span class="pep-task-state">
            <CheckCircleFilled v-if="task.state === 'completed'" class="ok" />
            <LoadingOutlined v-else-if="task.state === 'in_progress'" spin class="running" />
            <MinusCircleOutlined v-else class="pending" />
          </span>
          <div class="pep-task-main">
            <div class="pep-task-subject">
              <span class="pep-task-id">#{{ task.id }}</span>
              {{ task.subject }}
              <a-tag
                :color="stateColor(task.state)"
                class="pep-task-tag"
              >{{ stateLabel(task.state) }}</a-tag>
            </div>
            <div v-if="task.description" class="pep-task-desc">{{ task.description }}</div>
            <div v-if="task.blocked_by?.length" class="pep-task-blocked">
              <LockOutlined />
              {{ t('assistantChat.plan.blockedBy') }}：
              <span
                v-for="dep in task.blocked_by"
                :key="dep"
                class="pep-dep-chip"
                :class="{ done: depState(dep) === 'completed' }"
              >#{{ dep }}</span>
            </div>
          </div>
        </div>
      </div>
      <div v-else-if="streaming" class="pep-empty">
        <LoadingOutlined spin /> {{ t('assistantChat.plan.waiting') }}
      </div>
      <div v-else class="pep-empty">{{ t('assistantChat.plan.noTasks') }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  CaretRightOutlined, CheckCircleFilled, LoadingOutlined, MinusCircleOutlined, LockOutlined,
} from '@ant-design/icons-vue'
import type { PlanTaskSnapshot } from '../../types'

const props = defineProps<{
  /** 任务清单快照（plan_snapshot 事件 / 历史回放 planSnapshot） */
  tasks?: PlanTaskSnapshot[]
  /** 当前任务活动（plan_task_activity 事件，流式中显示） */
  activity?: { tool_name: string; tool_call_id?: string | null; time?: number } | null
  /** 是否流式执行中 */
  streaming?: boolean
}>()

const { t } = useI18n()

const expanded = ref(true)

const tasks = computed<PlanTaskSnapshot[]>(() => props.tasks || [])

const progress = computed(() => {
  const total = tasks.value.length
  const completed = tasks.value.filter(tk => tk.state === 'completed').length
  return { total, completed, percent: total ? Math.round((completed / total) * 100) : 0 }
})

/** plan_task_activity 当前活动文案（TaskCreate/TaskUpdate/TaskGet/TaskList） */
const activityLabel = computed(() => {
  const name = props.activity?.tool_name || ''
  if (name === 'TaskCreate') return t('assistantChat.plan.activityCreate')
  if (name === 'TaskUpdate') return t('assistantChat.plan.activityUpdate')
  if (name === 'TaskGet') return t('assistantChat.plan.activityGet')
  if (name === 'TaskList') return t('assistantChat.plan.activityList')
  return t('assistantChat.plan.activityGeneric')
})

function stateLabel(state: string): string {
  if (state === 'completed') return t('assistantChat.plan.stateCompleted')
  if (state === 'in_progress') return t('assistantChat.plan.stateInProgress')
  return t('assistantChat.plan.statePending')
}
function stateColor(state: string): string {
  if (state === 'completed') return 'success'
  if (state === 'in_progress') return 'processing'
  return 'default'
}
/** 依赖任务状态（用于依赖 chip 高亮已完成） */
function depState(dep: string | number): string {
  return tasks.value.find(tk => String(tk.id) === String(dep))?.state || ''
}
</script>

<style scoped lang="less">
.plan-execution-panel {
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  background: var(--bg-surface);
  padding: 10px 14px;
  margin: 6px 0;
}
.pep-header {
  display: flex; align-items: center; gap: 10px; cursor: pointer; user-select: none;
}
.pep-title { font-weight: 600; color: var(--fg); font-size: 13px; display: inline-flex; align-items: center; gap: 8px; }
.pep-streaming-tag {
  font-size: 11px; font-weight: 400; color: var(--accent);
  background: var(--accent-soft); border-radius: 8px; padding: 1px 8px;
}
.pep-progress-label { font-size: 12px; color: var(--fg-secondary); margin-left: auto; }
.pep-caret { font-size: 10px; color: var(--fg-muted); transition: transform 0.2s; &.expanded { transform: rotate(90deg); } }
.pep-body { margin-top: 8px; }
.pep-progress-bar { margin-bottom: 6px; }
.pep-activity {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--accent); margin-bottom: 8px;
}
.pep-tasks { display: flex; flex-direction: column; gap: 6px; }
.pep-task {
  display: flex; gap: 8px; align-items: flex-start;
  border: 1px solid var(--border-soft); border-radius: 8px;
  padding: 7px 10px; background: var(--bg-subtle);
  // in_progress 高亮（spec T9）
  &.state-in_progress { border-color: var(--accent); background: var(--accent-soft); }
  &.state-completed { opacity: 0.72; }
}
.pep-task-state {
  font-size: 13px; margin-top: 1px;
  .ok { color: var(--ok); }
  .running { color: var(--accent); }
  .pending { color: var(--fg-muted); }
}
.pep-task-main { flex: 1; min-width: 0; }
.pep-task-subject { font-size: 13px; color: var(--fg); display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.pep-task-id { color: var(--fg-muted); font-family: monospace; font-size: 11px; }
.pep-task-tag { margin: 0; font-size: 10px; line-height: 16px; }
.pep-task-desc { font-size: 12px; color: var(--fg-secondary); margin-top: 2px; word-break: break-word; }
.pep-task-blocked {
  font-size: 11px; color: var(--fg-muted); margin-top: 4px;
  display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
}
.pep-dep-chip {
  border: 1px solid var(--border-soft); border-radius: 6px; padding: 0 5px;
  font-family: monospace; background: var(--bg-surface);
  &.done { color: var(--ok); border-color: var(--ok); }
}
.pep-empty {
  font-size: 12px; color: var(--fg-muted);
  display: flex; align-items: center; gap: 6px; padding: 8px 0 2px;
}
</style>
