<template>
  <div class="think-block" :class="{ thinking, expanded }">
    <div class="think-header" @click="expanded = !expanded">
      <span class="think-icon">
        <span v-if="thinking" class="think-dots">
          <span /><span /><span />
        </span>
        <span v-else class="think-icon-done">💡</span>
      </span>
      <span class="think-label">
        {{ thinking ? '{{ t('apiKeyMgmt.thinkingInProgress') }}' : '已深度思考' }}
      </span>
      <span class="think-toggle">
        <svg
          :style="{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }"
          width="14" height="14" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2.5"
          stroke-linecap="round" stroke-linejoin="round"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </span>
    </div>
    <transition name="think-slide">
      <div v-show="expanded" class="think-body">
        <div class="think-content" v-html="renderMd(content)" />
        <div v-if="thinking" class="think-cursor" />
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { marked } from 'marked'

const props = defineProps<{
  content: string
  thinking: boolean
}>()

// 思考中时自动展开，完成后保持当前状态
const expanded = ref(true)
watch(() => props.thinking, (val) => {
  if (val) expanded.value = true
})

function renderMd(text: string): string {
  if (!text) return ''
  try {
    return marked.parse(text) as string
  } catch {
    return text.replace(/\n/g, '<br/>')
  }
}
</script>

<style lang="less" scoped>
.think-block {
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  background: var(--bg-input);
  transition: border-color 0.2s;

  &.thinking {
    border-color: var(--accent);
    background: var(--accent-soft);
  }
}

.think-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
  font-size: 13px;
  color: var(--fg-secondary);
  transition: background 0.15s;

  &:hover {
    background: rgba(0, 0, 0, 0.03);
  }
}

.think-icon {
  display: flex;
  align-items: center;
  width: 18px;
}

.think-icon-done {
  font-size: 14px;
  line-height: 1;
}

// 三个跳动圆点
.think-dots {
  display: flex;
  gap: 3px;
  align-items: center;

  span {
    display: inline-block;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--accent);
    animation: dot-bounce 1.2s ease-in-out infinite;

    &:nth-child(1) { animation-delay: 0s; }
    &:nth-child(2) { animation-delay: 0.2s; }
    &:nth-child(3) { animation-delay: 0.4s; }
  }
}

@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40%           { transform: scale(1);   opacity: 1; }
}

.think-label {
  flex: 1;
  font-weight: 500;
  color: var(--fg);
  .thinking & { color: var(--accent); }
}

.think-toggle {
  color: var(--fg-secondary);
  display: flex;
  align-items: center;
  transition: color 0.15s;

  svg {
    transition: transform 0.25s ease;
  }
}

.think-body {
  border-top: 1px solid var(--divider);
  padding: 10px 14px 12px;
  .thinking & { border-top-color: var(--accent); }
}

.think-content {
  font-size: 13px;
  line-height: 1.75;
  color: var(--fg-secondary);
  word-break: break-word;
  font-style: italic;

  :deep(p) { margin: 4px 0; }
  :deep(ul), :deep(ol) { padding-left: 18px; margin: 4px 0; }
  :deep(li) { margin: 2px 0; }
  :deep(code) {
    background: rgba(0,0,0,0.06);
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 12px;
    font-style: normal;
  }
  :deep(strong) { color: var(--fg); font-weight: 600; font-style: normal; }
}

.think-cursor {
  display: inline-block;
  width: 2px;
  height: 13px;
  background: var(--accent);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 0.8s step-end infinite;
  margin-top: 4px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}

// 展开/收起动画
.think-slide-enter-active,
.think-slide-leave-active {
  transition: max-height 0.3s ease, opacity 0.3s ease;
  max-height: 800px;
  overflow: hidden;
}

.think-slide-enter-from,
.think-slide-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>
