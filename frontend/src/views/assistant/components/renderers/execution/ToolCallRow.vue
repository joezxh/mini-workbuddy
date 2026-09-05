<template>
  <div class="tool-call-row" :class="{ 'is-error': pair.status === 'error', 'is-calling': pair.status === 'calling' }">
    <!-- 触发行 -->
    <div
      class="tool-call-row-header"
      :class="{ clickable: hasBody }"
      @click="hasBody && (expanded = !expanded)"
    >
      <!-- 左侧：渲染器提供的 header 内容 -->
      <div class="tool-call-row-content">
        <component :is="headerContent" v-if="typeof headerContent === 'object'" />
        <template v-else>{{ headerContent }}</template>
      </div>

      <!-- 右侧：状态图标 + 耗时 + chevron -->
      <div class="tool-call-row-right">
        <component :is="stateIconComponent" />
        <span v-if="pair.durationMs" class="tool-call-duration">
          {{ formatDuration(pair.durationMs) }}
        </span>
        <component :is="ChevronRight" v-if="hasBody" :size="14"
          class="tool-call-chevron" :class="{ 'chevron-open': expanded }" />
      </div>
    </div>

    <!-- 展开内容 -->
    <transition name="expand">
      <div v-if="expanded && hasBody" class="tool-call-row-body">
        <component :is="bodyContent" v-if="typeof bodyContent === 'object'" />
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, h } from 'vue'
import { CheckCircle, XCircle, LoaderCircle, ChevronRight } from '@lucide/vue'
import type { ToolCallPair } from '../types/timeline'
import { renderHeader, renderBody } from './toolRegistry'
import { formatDuration } from './_shared'

const props = defineProps<{ pair: ToolCallPair }>()

const expanded = ref(false)

const headerContent = computed(() => renderHeader(props.pair))
const bodyContent = computed(() => renderBody(props.pair))
const hasBody = computed(() => bodyContent.value != null)

// 状态图标组件
const stateIconComponent = computed(() => {
  if (props.pair.status === 'success') {
    return { render: () => h(CheckCircle, { size: 14, class: 'tool-state-icon tool-state-success' }) }
  }
  if (props.pair.status === 'error') {
    return { render: () => h(XCircle, { size: 14, class: 'tool-state-icon tool-state-error' }) }
  }
  return { render: () => h(LoaderCircle, { size: 14, class: 'tool-state-icon tool-state-loading' }) }
})
</script>

<style scoped lang="less">
.tool-call-row {
  border-left: 2px solid var(--border);
  transition: border-color 0.2s;
  &.is-error { border-left-color: var(--err); }
  &.is-calling { border-left-color: var(--accent); }
}
.tool-call-row-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 10px; gap: 8px; min-height: 32px;
  &.clickable { cursor: pointer; &:hover { background: var(--bg-input); } }
}
.tool-call-row-content {
  flex: 1; min-width: 0; display: flex; align-items: center; gap: 6px;
  font-size: 13px; color: var(--fg); overflow: hidden;
}
.tool-call-row-right {
  display: flex; align-items: center; gap: 6px; flex-shrink: 0;
}
.tool-call-duration {
  font-size: 11px; color: var(--fg-muted); font-variant-numeric: tabular-nums;
}
.tool-call-chevron {
  transition: transform 0.2s; color: var(--fg-muted);
  &.chevron-open { transform: rotate(90deg); }
}
.tool-call-row-body {
  padding: 4px 10px 10px; border-top: 1px solid var(--border);
}
.tool-state-icon {
  &.tool-state-success { color: var(--ok); }
  &.tool-state-error { color: var(--err); }
  &.tool-state-loading { color: var(--accent); animation: spin 1s linear infinite; }
}
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.expand-enter-active, .expand-leave-active { transition: all 0.2s ease; overflow: hidden; }
.expand-enter-from, .expand-leave-to { opacity: 0; max-height: 0; }
.expand-enter-to, .expand-leave-from { opacity: 1; max-height: 500px; }
</style>
