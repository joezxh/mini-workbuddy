<template>
  <div class="thinking-row">
    <div class="thinking-row-header" @click="expanded = !expanded">
      <Brain :size="14" class="thinking-icon" />
      <span class="thinking-label">思考</span>
      <span v-if="preview" class="thinking-preview">{{ preview }}</span>
      <ChevronRight :size="14" class="thinking-chevron" :class="{ open: expanded }" />
    </div>
    <transition name="expand">
      <div v-if="expanded" class="thinking-content">
        <div class="thinking-text" v-html="renderedContent"></div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Brain, ChevronRight } from '@lucide/vue'
import { renderMarkdown } from '../../markdown'

const props = defineProps<{ content: string }>()
const expanded = ref(false)
const preview = computed(() => props.content?.slice(0, 60) || '')
const renderedContent = computed(() => renderMarkdown(props.content || ''))
</script>

<style scoped lang="less">
.thinking-row { font-size: 13px; }
.thinking-row-header {
  display: flex; align-items: center; gap: 6px; padding: 6px 10px;
  cursor: pointer; color: var(--fg-secondary); &:hover { background: var(--bg-input); }
}
.thinking-icon { color: #8b5cf6; }
.thinking-label { font-weight: 500; color: #8b5cf6; }
.thinking-preview { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--fg-muted); font-size: 12px; }
.thinking-chevron { transition: transform 0.2s; color: var(--fg-muted); &.open { transform: rotate(90deg); } }
.thinking-content { padding: 8px 10px 8px 30px; border-top: 1px solid var(--border); }
.thinking-text { color: var(--fg-secondary); line-height: 1.6; font-size: 12px; white-space: pre-wrap; }
.expand-enter-active, .expand-leave-active { transition: all 0.2s ease; overflow: hidden; }
.expand-enter-from, .expand-leave-to { opacity: 0; max-height: 0; }
.expand-enter-to, .expand-leave-from { opacity: 1; max-height: 500px; }
</style>
