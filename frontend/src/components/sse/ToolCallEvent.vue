<!-- 
  File: frontend/src/components/sse/ToolCallEvent.vue
  
  Description:
    Renders external tool invocation visualization with parameters preview.
    
  Features:
    - Shows tool name and parameters
    - Collapsible details for long parameter lists
    - Timeout indicator if available
-->
<template>
  <div class="tool-call-block">
    <a-timeline-item color="blue">
      <template #dot>
        <CloudOutlined class="custom-dot" />
      </template>
      <div class="tool-header">
        <span class="tool-name">{{ eventData.tool_name }}</span>
        <span v-if="eventData.timeout_seconds" class="timeout-warning">
          Expected timeout: {{ eventData.timeout_seconds }}s
        </span>
      </div>
      
      <!-- Parameters Preview -->
      <div class="parameters-preview">
        <pre>{{ JSON.stringify(eventData.parameters, null, 2) }}</pre>
      </div>
    </a-timeline-item>
  </div>
</template>

<script setup lang="ts">
import type { SSEEvent } from '@/types/sse'
import { CloudOutlined } from '@ant-design/icons-vue'

interface Props {
  eventData: SSEEvent & {
    type: 'tool_call'
    tool_name: string
    parameters: Record<string, unknown>
    tool_description?: string
    timeout_seconds?: number
  }
}

defineProps<Props>()
</script>

<style scoped lang="scss">
.tool-call-block {
  margin-bottom: 16px;
  
  :deep(.ant-timeline-item-content) {
    width: 100%;
  }
  
  .tool-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    
    .tool-name {
      font-weight: 600;
      font-size: 14px;
      color: #333;
    }
    
    .timeout-warning {
      background: #fff7e6;
      border: 1px solid #ffe58f;
      color: #faad14;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 12px;
    }
  }
  
  .parameters-preview {
    pre {
      margin: 0;
      padding: 8px;
      background: #f5f5f5;
      border-radius: 4px;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 12px;
      max-height: 200px;
      overflow-y: auto;
      color: #555;
    }
  }
}

.custom-dot {
  font-size: 20px;
  color: #1890ff;
}
</style>
