<template>
  <div class="task-panel" v-if="tasks.length > 0">
    <div class="task-panel-header" @click="collapsed = !collapsed">
      <span class="task-panel-title">任务进度</span>
      <span class="task-panel-count">{{ completedCount }}/{{ tasks.length }}</span>
      <ChevronRight :size="14" class="task-panel-chevron" :class="{ open: !collapsed }" />
    </div>
    <transition name="expand">
      <div v-if="!collapsed" class="task-panel-body">
        <div v-for="task in tasks" :key="task.id" class="task-item" :class="`task-${task.status}`">
          <component
            :is="getTaskIcon(task.status)"
            :size="14"
            class="task-icon"
            :class="{ 'task-icon-done': task.status === 'done' }"
          />
          <div class="task-info">
            <div class="task-name">{{ task.name }}</div>
            <div class="task-message">{{ task.message }}</div>
          </div>
          <a-progress
            v-if="task.status === 'running' || task.status === 'done'"
            :percent="task.progress" :show-info="false" size="small"
            :status="task.status === 'done' ? 'success' : 'active'"
            style="width: 80px; flex-shrink: 0;"
          />
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Clock, LoaderCircle, CircleCheckBig, XCircle, ChevronRight } from '@lucide/vue'
import type { TaskItem } from '../types/timeline'

const props = defineProps<{ tasks: TaskItem[] }>()
const collapsed = ref(false)

const completedCount = computed(() => props.tasks.filter(t => t.status === 'done').length)

function getTaskIcon(status: string) {
  // 完成状态使用带勾的大图标（CircleCheckBig），更明确地表达“已完成”
  const map: Record<string, any> = {
    pending: Clock, running: LoaderCircle, done: CircleCheckBig, error: XCircle,
  }
  return map[status] || Clock
}
</script>

<style scoped lang="less">
.task-panel {
  border: 1px solid #f0f0f0; border-radius: 8px; background: #fafafa;
  min-width: 200px; max-width: 260px;
}
.task-panel-header {
  display: flex; align-items: center; gap: 6px; padding: 8px 12px;
  cursor: pointer; font-size: 13px; font-weight: 600; color: #333;
  &:hover { background: #f5f5f5; }
}
.task-panel-title { flex: 1; }
.task-panel-count { font-size: 11px; color: #999; font-weight: 400; }
.task-panel-chevron { transition: transform 0.2s; color: #bbb; &.open { transform: rotate(90deg); } }
.task-panel-body { padding: 4px 8px 8px; display: flex; flex-direction: column; gap: 6px; }
.task-item {
  display: flex; align-items: center; gap: 6px; padding: 4px 0; font-size: 12px;
  &.task-done .task-name { color: #52c41a; }
  &.task-error .task-name { color: #ff4d4f; }
  &.task-running .task-name { color: #1677ff; }
}
.task-icon { flex-shrink: 0; }
.task-icon-done { color: #52c41a; }
.task-info { flex: 1; min-width: 0; }
.task-name { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.task-message { font-size: 11px; color: #999; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.expand-enter-active, .expand-leave-active { transition: all 0.2s ease; overflow: hidden; }
.expand-enter-from, .expand-leave-to { opacity: 0; max-height: 0; }
.expand-enter-to, .expand-leave-from { opacity: 1; max-height: 600px; }
</style>
