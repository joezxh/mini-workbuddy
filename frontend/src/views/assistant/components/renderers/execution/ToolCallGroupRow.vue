<template>
  <div class="tool-call-group-row">
    <!-- 组摘要行 -->
    <div class="group-summary" :class="{ shimmer: hasRunning }" @click="expanded = !expanded">
      <span class="group-summary-text">
        已调用 {{ pairs.length }} 个工具：{{ summaryText }}
      </span>
      <ChevronRight :size="14" class="group-chevron" :class="{ open: expanded }" />
    </div>

    <!-- 展开态：逐个 ToolCallRow -->
    <transition name="expand">
      <div v-if="expanded" class="group-body">
        <ToolCallRow v-for="pair in pairs" :key="pair.id" :pair="pair" />
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ChevronRight } from '@lucide/vue'
import type { ToolCallPair } from '../types/timeline'
import { summarizeToolGroup } from './_shared'
import ToolCallRow from './ToolCallRow.vue'

const props = defineProps<{ pairs: ToolCallPair[] }>()
const expanded = ref(false)

const hasRunning = computed(() => props.pairs.some(p => p.status === 'calling'))
const summaryText = computed(() => summarizeToolGroup(props.pairs))
</script>

<style scoped lang="less">
.tool-call-group-row {
  margin: 4px 0; border: 1px solid var(--border); border-radius: 6px;
  background: var(--bg-input); overflow: hidden;
}
.group-summary {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 10px; cursor: pointer; font-size: 12px; color: var(--fg-secondary);
  &:hover { background: var(--bg-input); }
  &.shimmer { background: linear-gradient(90deg, var(--bg-input) 25%, var(--border) 50%, var(--bg-input) 75%);
    background-size: 200% 100%; animation: shimmer 1.5s infinite; }
}
.group-summary-text { flex: 1; }
.group-chevron { transition: transform 0.2s; color: var(--fg-muted); &.open { transform: rotate(90deg); } }
.group-body { padding: 4px 8px 8px; display: flex; flex-direction: column; gap: 2px; }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
.expand-enter-active, .expand-leave-active { transition: all 0.2s ease; overflow: hidden; }
.expand-enter-from, .expand-leave-to { opacity: 0; max-height: 0; }
.expand-enter-to, .expand-leave-from { opacity: 1; max-height: 1000px; }
</style>
