<!-- 
  File: frontend/src/components/sse/ThinkingEvent.vue
  
  Description:
    Renders AI reasoning/thinking visualization with confidence score and step marker.
    
  Features:
    - Displays thinking content in an expanded box
    - Shows confidence score as progress bar
    - Highlights steps if available
-->
<template>
  <div class="thinking-block">
    <div class="thinking-header">
      <span class="step-badge" v-if="eventData.step !== undefined">
        Step {{ eventData.step }}
      </span>
      <span class="confidence-badge">
        <a-progress
          :percent="calculateConfidence(eventData.confidence)"
          size="small"
          :stroke-color="getConfidenceColor(eventData.confidence)"
          format=""
        />
        {{ eventData.confidence ? `${(eventData.confidence * 100).toFixed(0)}%` : '' }}
      </span>
    </div>
    <div class="thinking-content">
      <p>{{ eventData.content }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SSEEvent } from '@/types/sse'

interface Props {
  eventData: SSEEvent & {
    type: 'thinking'
    content: string
    confidence?: number
    step?: number
  }
}

const props = defineProps<Props>()

// 使用 props 避免未使用警告
void props

function calculateConfidence(confidence: number | undefined): number {
  return Math.round((confidence || 0) * 100)
}

function getConfidenceColor(confidence: number | undefined): string {
  if (!confidence) return '#d9d9d9'
  if (confidence > 0.8) return '#52c41a' // High confidence - green
  if (confidence > 0.5) return '#faad14' // Medium confidence - orange
  return '#ff4d4f' // Low confidence - red
}
</script>

<style scoped lang="scss">
.thinking-block {
  background: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 8px;
  
  .thinking-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }
  
  .step-badge {
    background: #e6f7ff;
    color: #1890ff;
    border: 1px solid #91d5ff;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 600;
  }
  
  .confidence-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: #666;
    
    :deep(.ant-progress) {
      width: 100px;
    }
  }
  
  .thinking-content {
    p {
      margin: 0;
      line-height: 1.6;
      color: #333;
      
      &:first-child::before {
        content: '💭';
        margin-right: 4px;
      }
    }
  }
}
</style>
