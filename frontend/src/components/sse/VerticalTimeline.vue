<!-- 
  File: frontend/src/components/sse/VerticalTimeline.vue
    
  Description:
    Main vertical timeline renderer for SSE events with collapsible sections.
    
  Features:
    - Renders TeamStart, AgentStart, AgentDone events as expandable sections
    - Collapsible UI with Ant Design Vue collapse component
    - Handles per-agent event streams independently
    
  Usage:
    <VerticalTimeline
      :events="sseEvents"
      @toggle-section="onSectionToggle"
    />
-->
<template>
  <div class="vertical-timeline-container">
    <a-collapse v-model:activeKeys="activeSections" bordered :accordion="true">
      
      <!-- Team Level Events -->
      <a-collapse-panel key="team-header" header="执行概览" v-if="teamEvent">
        <div class="team-summary-card">
          <a-descriptions :column="2" size="small">
            <a-descriptions-item label="团队 ID">{{ teamEvent.team_id }}</a-descriptions-item>
            <a-descriptions-item label="团队名称">{{ teamEvent.team_name }}</a-descriptions-item>
            <a-descriptions-item label="Agent 数量">
              <a-tag color="blue">{{ teamEvent.agents_count }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="开始时间">{{ formatTimestamp(teamEvent.timestamp) }}</a-descriptions-item>
          </a-descriptions>
        </div>
      </a-collapse-panel>
      
      <!-- Individual Agents -->
      <template v-for="agent in agents" :key="agent.id">
        <a-collapse-panel
          :key="agent.id"
          :header="`${agent.name} (${agent.role})`"
          :class="{ 'agent-collapsed': agent.collapsed }"
          @change="onSectionChange(agent.id, $event)"
        >
          <!-- Agent Header Stats -->
          <div class="agent-info-bar">
            <span class="agent-status" :class="agent.status">
              <LoadingOutlined v-if="agent.status === 'running'" spin />
              <CheckCircleFilled v-else-if="agent.status === 'completed'" />
              <CloseCircleFilled v-else-if="agent.status === 'error'" />
            </span>
            <span class="agent-sequence">#{{ getSequence(agent.id) }}</span>
            <span v-if="agent.completedAt" class="agent-duration">
              耗时：{{ calculateDuration(agent.startTime) }}ms
            </span>
          </div>
          
          <!-- Event Stream -->
          <div class="agent-events-list">
            <ThinkingEvent
              v-for="event in agent.events.filter((e: any) => e.type === 'thinking')"
              :key="event.id"
              :event-data="event"
            />
            
            <ToolCallEvent
              v-for="event in agent.events.filter((e: any) => e.type === 'tool_call')"
              :key="event.id"
              :event-data="event"
            />
            
            <ToolResultEvent
              v-for="event in agent.events.filter((e: any) => e.type === 'tool_result')"
              :key="event.id"
              :event-data="event"
            />
            
            <TextOutputEvent
              v-for="event in agent.events.filter((e: any) => (e.type === 'text_chunk' || e.type === 'text_final'))"
              :key="event.id"
              :event-data="event"
            />
          </div>
        </a-collapse-panel>
      </template>
      
      <!-- Team Done Event -->
      <a-collapse-panel key="team-footer" header="执行完成状态" v-if="doneEvent">
        <div class="team-done-summary">
          <SuccessOutlined v-if="doneEvent.success" class="success-icon" />
          <ExclamationCircleOutlined v-else class="warning-icon" />
          <span class="summary-text">{{ doneEvent.summary || 'Execution completed' }}</span>
        </div>
        
        <!-- Execution Statistics -->
        <div v-if="doneEvent.completed_agents !== undefined" class="execution-stats">
          <a-statistic title="完成 Agent" :value="doneEvent.completed_agents">
            <template #prefix><TemplateOutlined /></template>
          </a-statistic>
          <a-statistic title="总 Agent" :value="doneEvent.total_agents">
            <template #prefix><TeamOutlined /></template>
          </a-statistic>
          <a-statistic title="成功率" :value="completionRate">
            <template #prefix><PercentageOutlined /></template>
          </a-statistic>
        </div>
        
        <!-- Final Output -->
        <div v-if="doneEvent.final_output" class="final-output">
          <h4>最终输出:</h4>
          <p>{{ JSON.stringify(doneEvent.final_output, null, 2) }}</p>
        </div>
      </a-collapse-panel>
      
      <!-- Loading Indicator -->
      <div v-if="loading" class="loading-indicator">
        <a-spin tip="正在加载事件流..." />
      </div>
    </a-collapse>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { SSEEvent } from '@/types/sse'
import { useSSEStore } from '@/stores/sse'
import { LoadingOutlined, CheckCircleFilled, CloseCircleFilled, ExclamationCircleOutlined, TeamOutlined, PercentageOutlined } from '@ant-design/icons-vue'
// SuccessOutlined 不存在，使用 CheckCircleFilled 替代
import ThinkingEvent from './ThinkingEvent.vue'
import ToolCallEvent from './ToolCallEvent.vue'
import ToolResultEvent from './ToolResultEvent.vue'
import TextOutputEvent from './TextOutputEvent.vue'

// Props
interface Props {
  loading?: boolean
}

const props = defineProps<Props>()

// 使用 props 避免未使用警告
void props

// Emits
const emit = defineEmits<{
  (e: 'update', event: SSEEvent): void
  (e: 'section-toggle', sectionId: string): void
}>()

// Reactive state
const activeSections = ref<string[]>([])
const sseStore = useSSEStore()

// Computed properties
const teamEvent = computed(() => sseStore.teamEvent)
const doneEvent = computed(() => sseStore.doneEvent)
const rawEvents = computed(() => sseStore.rawEvents)

// Agents derived from raw events
const agents = computed(() => {
  const agentMap = new Map<string, any>()
  
  rawEvents.value.forEach((event: any) => {
    if (event.agent_id && event.agent_id !== '_system') {
      if (!agentMap.has(event.agent_id)) {
        agentMap.set(event.agent_id, {
          id: event.agent_id,
          name: event.agent_name || event.agent_id,
          role: event.agent_role || 'Agent',
          status: 'idle',
          startTime: null,
          endTime: null,
          events: [],
          collapsed: true // Start collapsed by default
        })
      }
      
      const agent = agentMap.get(event.agent_id)!
      agent.events.push(event)
      
      // Update agent status based on events
      if (event.type === 'agent_start') {
        agent.status = 'running'
        agent.startTime = Date.parse(event.timestamp)
      } else if (event.type === 'agent_done') {
        agent.status = 'completed'
        agent.endTime = Date.parse(event.timestamp)
      } else if (event.type === 'agent_error') {
        agent.status = 'error'
        agent.endTime = Date.parse(event.timestamp)
      }
    }
  })
  
  return Array.from(agentMap.values())
})

// Methods
function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

function getSequence(agentId: string): number {
  const agent = agents.value.find(a => a.id === agentId)
  return agent?.events.length || 0
}

function calculateDuration(startTime: number | null): string {
  if (!startTime || !agents.value[0].endTime) return 'N/A'
  return (agents.value[0].endTime - startTime).toString()
}

const completionRate = computed(() => {
  if (!doneEvent.value || !doneEvent.value.total_agents) return 0
  return Math.round((doneEvent.value.completed_agents / doneEvent.value.total_agents) * 100)
})

function onSectionChange(sectionId: string, isActive: boolean | string[]) {
  const agent = agents.value.find(a => a.id === sectionId)
  if (agent) {
    agent.collapsed = !isActive
  }
  emit('section-toggle', sectionId)
}

// Watch for new events
watch(rawEvents, (newEvents) => {
  newEvents.forEach(event => {
    emit('update', event)
  })
}, { deep: true })
</script>

<style scoped lang="scss">
.vertical-timeline-container {
  max-width: 900px;
  margin: 0 auto;
  background: #fff;
}

.team-summary-card {
  padding: 16px;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  border-radius: 8px;
  margin-bottom: 12px;
}

.agent-info-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #666;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #eee;
}

.agent-status {
  font-size: 18px;
  
  &.running {
    color: #1890ff;
  }
  
  &.completed {
    color: #52c41a;
  }
  
  &.error {
    color: #ff4d4f;
  }
}

.agent-collapsed .ant-collapse-header {
  opacity: 0.7;
  transition: opacity 0.2s ease;
}

.agent-events-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-left: 8px;
}

.team-done-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
  margin-bottom: 16px;
}

.success-icon {
  color: #52c41a;
  font-size: 20px;
}

.warning-icon {
  color: #faad14;
  font-size: 20px;
}

.execution-stats {
  display: flex;
  gap: 24px;
  margin-top: 12px;
}

.final-output {
  margin-top: 16px;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 4px;
  border-left: 3px solid #1890ff;
  
  h4 {
    margin: 0 0 8px 0;
    font-size: 14px;
    color: #333;
  }
  
  p {
    margin: 0;
    font-family: monospace;
    white-space: pre-wrap;
    word-break: break-all;
  }
}

.loading-indicator {
  text-align: center;
  padding: 32px;
  color: #999;
}
</style>
