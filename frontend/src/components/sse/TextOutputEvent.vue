<!-- 
  File: frontend/src/components/sse/TextOutputEvent.vue
  
  Description:
    Renders text output chunks with progressive streaming effect.
    
  Features:
    - Streaming text display with typewriter effect
    - Final message distinction
    - Auto-expand on new content
-->
<template>
  <div class="text-output-block">
    <a-timeline-item>
      <template #dot>
        <MessageOutlined class="text-dot" />
      </template>
      
      <div class="text-content" ref="textContainer">
        <!-- Typewriter animation for streaming -->
        <transition name="fade">
          <p v-html="renderedContent" class="output-text"></p>
        </transition>
        
        <!-- Final marker -->
        <span v-if="isFinal" class="final-marker">✅ 完成</span>
      </div>
    </a-timeline-item>
  </div>
</template>

<script setup lang="ts">
import type { SSEEvent } from '@/types/sse'
import { MessageOutlined } from '@ant-design/icons-vue'
import { ref, computed, watch } from 'vue'

interface Props {
  eventData: SSEEvent & {
    type: 'text_chunk' | 'text_final'
    content: string
  }
}

const props = defineProps<Props>()
const textContainer = ref<HTMLDivElement>()

// Computed properties
const isFinal = computed(() => props.eventData.type === 'text_final')
const renderedContent = computed(() => {
  // Escape HTML and add line breaks
  return escapeHtml(props.eventData.content)
    .replace(/\n/g, '<br>')
})

// Methods
function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// Auto-scroll to bottom when new content arrives
watch([isFinal], () => {
  if (textContainer.value) {
    textContainer.value.scrollTop = textContainer.value.scrollHeight
  }
})
</script>

<style scoped lang="scss">
.text-output-block {
  :deep(.ant-timeline-item-content) {
    width: 100%;
  }
  
  .text-content {
    padding: 8px;
    background: #fafafa;
    border-radius: 4px;
    
    .output-text {
      margin: 0;
      padding: 8px;
      font-family: inherit;
      font-size: 14px;
      line-height: 1.6;
      color: #333;
      white-space: pre-wrap;
      word-break: break-word;
    }
    
    .final-marker {
      display: inline-block;
      margin-top: 8px;
      font-size: 12px;
      color: #52c41a;
      font-weight: 600;
    }
  }
}

.text-dot {
  color: #722ed1;
  font-size: 20px;
}

/* Fade animation for new text */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
