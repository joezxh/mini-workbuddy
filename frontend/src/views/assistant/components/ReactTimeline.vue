<template>
  <div class="react-timeline" v-if="goal || steps.length">
    <!-- 目标标题 -->
    <div class="rt-header">
      <span class="rt-goal-icon"><NodeIndexOutlined /></span>
      <span class="rt-goal-text">{{ goal || 'ReAct 计划执行' }}</span>
      <a-tag :color="statusColor" size="small">{{ statusText }}</a-tag>
    </div>

    <!-- 步骤列表 -->
    <div class="rt-steps" v-if="steps.length">
      <div
        v-for="step in steps"
        :key="step.id"
        class="rt-step"
        :class="[`depth-${step.depth}`, step.status]"
      >
        <!-- 连接线 + 图标 -->
        <div class="rt-step-indicator">
          <div class="rt-step-line" />
          <span class="rt-step-icon" :class="step.status">
            <LoadingOutlined v-if="step.status === 'running'" spin />
            <CheckCircleFilled v-else-if="step.status === 'done'" />
            <CloseCircleFilled v-else-if="step.status === 'failed'" />
            <MinusCircleFilled v-else-if="step.status === 'skipped'" />
            <ClockCircleOutlined v-else />
          </span>
        </div>
        <!-- 内容 -->
        <div class="rt-step-body" @click="toggleExpand(step.id)">
          <div class="rt-step-header">
            <span class="rt-step-title">{{ step.title }}</span>
            <a-tag :color="stepStatusColor(step.status)" size="small">
              {{ stepStatusText(step.status) }}
            </a-tag>
            <span class="rt-step-expand-icon">
              <DownOutlined v-if="!expanded.has(step.id)" />
              <UpOutlined v-else />
            </span>
          </div>
          <!-- 展开详情 -->
          <div v-if="expanded.has(step.id)" class="rt-step-detail">
            <div v-if="step.description" class="rt-step-desc">{{ step.description }}</div>
            <div v-if="step.result" class="rt-step-result">
              <pre>{{ step.result }}</pre>
            </div>
            <!-- 工具调用记录 -->
            <div v-if="step.tool_calls?.length" class="rt-step-tools">
              <div v-for="(tc, i) in step.tool_calls" :key="i" class="rt-tool-call">
                <span class="rt-tool-name">{{ tc.name }}</span>
                <span class="rt-tool-status" :class="tc.status">{{ tc.status }}</span>
              </div>
            </div>
            <!-- 嵌套 Skill 子面板 -->
            <ReactSkillPanel v-if="step.depth > 0 && skillEvents(step.id).length" :events="skillEvents(step.id)" />
          </div>
        </div>
      </div>
    </div>

    <!-- 进度条 -->
    <div class="rt-progress" v-if="planStatus === 'executing'">
      <a-progress :percent="progressPercent" :show-info="false" size="small" status="active" />
    </div>

    <!-- 操作按钮 -->
    <div class="rt-actions" v-if="showActions">
      <a-button size="small" @click="$emit('pause')">
        <PauseOutlined /> {{ $t('react.pause') }}
      </a-button>
      <a-button size="small" danger @click="$emit('cancel')">
        <CloseOutlined /> {{ $t('react.cancel') }}
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  NodeIndexOutlined, LoadingOutlined, CheckCircleFilled,
  CloseCircleFilled, MinusCircleFilled, ClockCircleOutlined,
  DownOutlined, UpOutlined, PauseOutlined, CloseOutlined,
} from '@ant-design/icons-vue'
import ReactSkillPanel from './ReactSkillPanel.vue'

export interface ReactPlanStep {
  id: string
  title: string
  description: string
  status: 'pending' | 'running' | 'done' | 'failed' | 'skipped'
  result: string
  tool_calls: Array<{ name: string; status: string }>
  depth: number
}

export interface ReactEvent {
  type: string
  [key: string]: any
}

const props = withDefaults(defineProps<{
  events: ReactEvent[]
  goal?: string
  planStatus?: string
  showActions?: boolean
}>(), {
  goal: '',
  planStatus: 'planning',
  showActions: true,
})

defineEmits<{
  (e: 'pause'): void
  (e: 'cancel'): void
}>()

const steps = ref<ReactPlanStep[]>([])
const expanded = ref<Set<string>>(new Set())

// 监听事件列表变化，更新步骤状态
watch(() => props.events, (events) => {
  for (const event of events) {
    handleEvent(event)
  }
}, { deep: true, immediate: true })

function handleEvent(event: ReactEvent) {
  switch (event.type) {
    case 'react_plan':
      if (event.steps) {
        steps.value = event.steps.map((s: any, i: number) => ({
          id: s.id || `step-${i}`,
          title: s.title || `步骤 ${i + 1}`,
          description: s.description || '',
          status: s.status || 'pending',
          result: s.result || '',
          tool_calls: s.tool_calls || [],
          depth: s.depth || 0,
        }))
      }
      break
    case 'react_step_start':
      updateStep(event.step_id, { status: 'running' })
      break
    case 'react_step_done':
      updateStep(event.step_id, { status: 'done', result: event.result || '' })
      break
    case 'react_step_failed':
      updateStep(event.step_id, { status: 'failed', result: event.error || '' })
      break
    case 'react_step_skipped':
      updateStep(event.step_id, { status: 'skipped' })
      break
    case 'react_tool_call':
      addToolCall(event.step_id, { name: event.tool_name, status: 'running' })
      break
    case 'react_tool_result':
      updateToolCall(event.step_id, event.tool_name, { status: 'done' })
      break
  }
}

function updateStep(stepId: string, patch: Partial<ReactPlanStep>) {
  const step = steps.value.find(s => s.id === stepId)
  if (step) Object.assign(step, patch)
}

function addToolCall(stepId: string, tc: { name: string; status: string }) {
  const step = steps.value.find(s => s.id === stepId)
  if (step) step.tool_calls.push(tc)
}

function updateToolCall(stepId: string, toolName: string, patch: Partial<{ name: string; status: string }>) {
  const step = steps.value.find(s => s.id === stepId)
  if (!step) return
  const tc = step.tool_calls.find(t => t.name === toolName)
  if (tc) Object.assign(tc, patch)
}

function toggleExpand(stepId: string) {
  if (expanded.value.has(stepId)) {
    expanded.value.delete(stepId)
  } else {
    expanded.value.add(stepId)
  }
}

function skillEvents(stepId: string): ReactEvent[] {
  return props.events.filter(e => e.step_id === stepId && e.type?.startsWith('react_skill_'))
}

const progressPercent = computed(() => {
  if (!steps.value.length) return 0
  const done = steps.value.filter(s => s.status === 'done' || s.status === 'skipped').length
  return Math.round((done / steps.value.length) * 100)
})

const statusColor = computed(() => {
  const map: Record<string, string> = {
    planning: 'blue', executing: 'processing', done: 'green',
    cancelled: 'default', failed: 'red', reflecting: 'orange',
  }
  return map[props.planStatus] || 'default'
})

const statusText = computed(() => {
  const map: Record<string, string> = {
    planning: '规划中', executing: '执行中', done: '已完成',
    cancelled: '已取消', failed: '执行失败', reflecting: '反思中',
  }
  return map[props.planStatus] || props.planStatus
})

function stepStatusColor(status: string): string {
  const map: Record<string, string> = {
    pending: 'default', running: 'processing', done: 'success',
    failed: 'error', skipped: 'warning',
  }
  return map[status] || 'default'
}

function stepStatusText(status: string): string {
  const map: Record<string, string> = {
    pending: '待执行', running: '执行中', done: '已完成',
    failed: '失败', skipped: '已跳过',
  }
  return map[status] || status
}
</script>

<style scoped lang="less">
.react-timeline {
  border: 1px solid var(--border); border-radius: 10px;
  background: var(--bg-surface); padding: 12px 16px; margin: 4px 0;
}
.rt-header {
  display: flex; align-items: center; gap: 8px; margin-bottom: 12px;
  padding-bottom: 8px; border-bottom: 1px solid var(--border);
}
.rt-goal-icon { font-size: 16px; color: var(--accent); }
.rt-goal-text { font-size: 14px; font-weight: 600; color: var(--fg); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.rt-steps { display: flex; flex-direction: column; gap: 0; }
.rt-step {
  display: flex; gap: 0; position: relative;
  &.depth-1 { padding-left: 24px; }
  &.depth-2 { padding-left: 48px; }
}
.rt-step-indicator {
  display: flex; flex-direction: column; align-items: center; width: 28px; flex-shrink: 0; position: relative;
}
.rt-step-line {
  position: absolute; left: 50%; top: 0; bottom: 0; width: 2px;
  background: var(--border); transform: translateX(-50%);
}
.rt-step:last-child .rt-step-line { display: none; }
.rt-step-icon {
  position: relative; z-index: 1; font-size: 16px; margin-top: 2px;
  &.pending { color: var(--fg-muted); }
  &.running { color: var(--accent); }
  &.done { color: var(--ok); }
  &.failed { color: var(--err); }
  &.skipped { color: var(--warn); }
}
.rt-step-body {
  flex: 1; min-width: 0; padding: 4px 0 12px 8px; cursor: pointer;
}
.rt-step-header {
  display: flex; align-items: center; gap: 8px;
}
.rt-step-title { font-size: 13px; color: var(--fg); flex: 1; min-width: 0; }
.rt-step-expand-icon { font-size: 10px; color: var(--fg-muted); }
.rt-step-detail {
  margin-top: 6px; padding: 8px 10px; background: var(--bg-input);
  border-radius: 6px; font-size: 12px;
}
.rt-step-desc { color: var(--fg-secondary); margin-bottom: 6px; }
.rt-step-result {
  pre { margin: 0; white-space: pre-wrap; word-break: break-all; max-height: 120px; overflow: auto; font-size: 11px; color: var(--fg); }
}
.rt-step-tools { margin-top: 6px; display: flex; flex-direction: column; gap: 4px; }
.rt-tool-call {
  display: flex; align-items: center; gap: 6px; font-size: 11px;
  padding: 2px 6px; background: var(--bg-surface); border-radius: 4px;
}
.rt-tool-name { color: var(--accent); font-family: monospace; }
.rt-tool-status { margin-left: auto; &.done { color: var(--ok); } &.running { color: var(--accent); } }

.rt-progress { margin-top: 8px; }
.rt-actions {
  display: flex; gap: 8px; margin-top: 10px; padding-top: 8px;
  border-top: 1px solid var(--border);
}
</style>
