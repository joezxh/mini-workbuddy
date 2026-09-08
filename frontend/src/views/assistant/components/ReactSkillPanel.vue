<template>
  <div class="react-skill-panel" v-if="skillName || events.length">
    <div class="rsp-header">
      <ToolOutlined class="rsp-icon" />
      <span class="rsp-title">Skill: {{ skillName || '执行中' }}</span>
      <a-tag :color="skillStatusColor" size="small">{{ skillStatusText }}</a-tag>
    </div>
    <!-- 复用 ReactTimeline 渲染内部步骤 -->
    <ReactTimeline
      v-if="internalEvents.length"
      :events="internalEvents"
      :goal="skillName"
      :plan-status="skillStatus"
      :show-actions="false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ToolOutlined } from '@ant-design/icons-vue'
import ReactTimeline from './ReactTimeline.vue'
import type { ReactEvent } from './ReactTimeline.vue'

const props = defineProps<{
  events: ReactEvent[]
  skillName?: string
}>()

const internalEvents = computed(() => props.events || [])

const skillStatus = computed(() => {
  const hasDone = props.events.some(e => e.type === 'react_skill_done')
  if (hasDone) return 'done'
  const hasStart = props.events.some(e => e.type === 'react_skill_start')
  if (hasStart) return 'executing'
  return 'planning'
})

const skillStatusColor = computed(() => {
  const map: Record<string, string> = { done: 'green', executing: 'processing', planning: 'blue' }
  return map[skillStatus.value] || 'default'
})

const skillStatusText = computed(() => {
  const map: Record<string, string> = { done: '已完成', executing: '执行中', planning: '等待中' }
  return map[skillStatus.value] || skillStatus.value
})
</script>

<style scoped lang="less">
.react-skill-panel {
  margin-top: 6px; padding: 8px 10px;
  background: var(--bg-input); border-radius: 6px;
  border-left: 3px solid var(--accent);
}
.rsp-header {
  display: flex; align-items: center; gap: 6px; margin-bottom: 6px;
}
.rsp-icon { color: var(--accent); font-size: 14px; }
.rsp-title { font-size: 13px; font-weight: 600; color: var(--fg); flex: 1; }
</style>
