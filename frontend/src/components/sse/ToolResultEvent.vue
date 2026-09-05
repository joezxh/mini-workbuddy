<!-- 
  File: frontend/src/components/sse/ToolResultEvent.vue
  
  Description:
    Renders tool execution result with success/failure indicator.
    
  Features:
    - Success/failure visual indicator
    - Result data preview or error message
    - Duration timing if available
-->
<template>
  <div class="tool-result-block" :class="{ success, failure }">
    <a-timeline-item :color="success ? 'green' : 'red'">
      <template #dot>
        <CheckCircleFilled v-if="success" class="success-dot" />
        <CloseCircleFilled v-else class="failure-dot" />
      </template>
      
      <div class="result-header">
        <span class="tool-name">{{ eventData.tool_name }}</span>
        <span class="result-status" :class="{ success, failure }">
          {{ success ? 'Success' : 'Failed' }}
        </span>
      </div>
      
      <!-- Duration -->
      <div v-if="eventData.duration_ms !== undefined" class="duration-info">
        ⏱️ Duration: {{ eventData.duration_ms.toFixed(1) }}ms
      </div>
      
      <!-- Error Message (Failure case) -->
      <div v-if="!success && eventData.error_message" class="error-message">
        <AlertOutlined class="error-icon" />
        {{ eventData.error_message }}
      </div>
      
      <!-- Result Data (Success case) -->
      <div v-if="success && eventData.result" class="result-data">
        <pre>{{ JSON.stringify(eventData.result, null, 2) }}</pre>
      </div>
    </a-timeline-item>
  </div>
</template>

<script setup lang="ts">
import type { SSEEvent } from '@/types/sse'
import { CheckCircleFilled, CloseCircleFilled, AlertOutlined } from '@ant-design/icons-vue'
import { computed } from 'vue'

interface Props {
  eventData: SSEEvent & {
    type: 'tool_result'
    tool_name: string
    success: boolean
    result?: Record<string, unknown>
    error_message?: string
    duration_ms?: number
  }
}

const props = defineProps<Props>()
const success = computed(() => props.eventData.success)
const failure = computed(() => !props.eventData.success)
</script>

<style scoped lang="scss">
.tool-result-block {
  margin-bottom: 16px;
  border-left: 3px solid transparent;
  padding-left: 8px;
  
  &:not(.failure) {
    border-color: #52c41a;
  }
  
  &.failure {
    border-color: #ff4d4f;
  }
  
  :deep(.ant-timeline-item-content) {
    width: 100%;
  }
  
  .result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    
    .tool-name {
      font-weight: 600;
      font-size: 14px;
      color: #333;
    }
    
    .result-status {
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
      
      &.success {
        background: #f6ffed;
        color: #52c41a;
        border: 1px solid #b7eb8f;
      }
      
      &.failure {
        background: #fff1f0;
        color: #ff4d4f;
        border: 1px solid #ffa39e;
      }
    }
  }
  
  .duration-info {
    font-size: 12px;
    color: #666;
    margin-bottom: 8px;
  }
  
  .error-message {
    display: flex;
    gap: 8px;
    padding: 8px;
    background: #fff1f0;
    border: 1px solid #ffa39e;
    border-radius: 4px;
    color: #ff4d4f;
    font-size: 13px;
    
    .error-icon {
      font-size: 16px;
    }
  }
  
  .result-data {
    pre {
      margin: 0;
      padding: 8px;
      background: #f6ffed;
      border: 1px solid #b7eb8f;
      border-radius: 4px;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 12px;
      max-height: 200px;
      overflow-y: auto;
      color: #333;
    }
  }
}

.success-dot {
  color: #52c41a;
  font-size: 20px;
}

.failure-dot {
  color: #ff4d4f;
  font-size: 20px;
}
</style>
