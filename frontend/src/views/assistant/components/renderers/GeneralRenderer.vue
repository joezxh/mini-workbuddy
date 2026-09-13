<template>
  <div class="general-renderer">
    <!-- 思考块 -->
    <div v-if="parsed.thinking" :class="['thinking-block', streaming ? 'streaming' : 'done']">
      <div class="thinking-header" @click="$emit('toggle-thinking')">
        <span class="thinking-icon">🧠</span>
        <span class="thinking-title">{{ streaming ? '正在思考' : '思考过程' }}</span>
        <span v-if="!streaming" class="thinking-toggle-btn">
          {{ expanded ? '收起 ▲' : '展开 ▼' }}
        </span>
        <span v-else class="streaming-dots"><span></span><span></span><span></span></span>
      </div>
      <transition name="collapse">
        <div v-if="streaming || expanded" class="thinking-body">
          <div class="thinking-text" v-html="renderMarkdown(parsed.thinking)"></div>
          <span v-if="streaming" class="typing-cursor">▋</span>
        </div>
      </transition>
    </div>

    <!-- 正文 Markdown -->
    <div v-if="parsed.rawContent" :class="['msg-bubble', 'ai-bubble', { 'streaming-bubble': streaming }]">
      <div class="msg-markdown" v-html="processedContent"></div>
      <span v-if="streaming" class="typing-cursor">▋</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ParsedMsg } from '../types'
import { renderMarkdown } from '../markdown'

const props = defineProps<{
  parsed: ParsedMsg
  streaming?: boolean
  expanded?: boolean
}>()

defineEmits<{
  (e: 'toggle-thinking'): void
}>()

// ── 正文 Markdown 渲染 ─────────────────────────────────────────────────────
const processedContent = computed(() => renderMarkdown(props.parsed.rawContent || ''))
</script>

<style scoped lang="less">
.thinking-block {
  margin-bottom: 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-input);

  &.streaming { border-color: var(--accent-soft); background: var(--accent-soft); }
}
.thinking-header {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 12px; cursor: pointer; user-select: none;
  &:hover { background: var(--bg-hover); }
}
.thinking-icon { font-size: 14px; }
.thinking-title { font-size: 12px; font-weight: 600; color: var(--fg-secondary); }
.thinking-toggle-btn { font-size: 11px; color: var(--fg-muted); margin-left: auto; }
.streaming-dots {
  margin-left: auto; display: flex; gap: 3px;
  span { width: 5px; height: 5px; border-radius: 50%; background: var(--accent); animation: dotBlink 1.2s infinite; }
  span:nth-child(2) { animation-delay: .2s; }
  span:nth-child(3) { animation-delay: .4s; }
}
@keyframes dotBlink { 0%,80%,100% { opacity: .3; } 40% { opacity: 1; } }
.thinking-body { padding: 8px 12px; border-top: 1px solid var(--border); max-height: 300px; overflow-y: auto; }
.thinking-text { font-size: 13px; color: var(--fg-secondary); line-height: 1.6; }
.typing-cursor { animation: blink 1s step-end infinite; color: var(--accent); }
@keyframes blink { 50% { opacity: 0; } }
.msg-bubble { position: relative; }
.streaming-bubble { border-color: var(--accent-soft); }
.collapse-enter-active, .collapse-leave-active { transition: all .2s ease; }
.collapse-enter-from, .collapse-leave-to { max-height: 0; opacity: 0; padding: 0 12px; }






</style>
