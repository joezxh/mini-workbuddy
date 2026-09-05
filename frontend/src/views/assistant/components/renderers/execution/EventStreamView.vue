<template>
  <div class="event-stream-view">
    <!-- Team 级别事件 -->
    <TeamEventBlock v-if="teamState.id" :team-state="teamState" :is-done="teamState.status === 'done' || teamState.status === 'failed'" />

    <!-- Agent 分组视图 或 单 Agent 视图 -->
    <template v-if="selectedAgentId">
      <!-- 单 Agent 视图 -->
      <AgentSection v-if="agents.get(selectedAgentId)" :agent="agents.get(selectedAgentId)!">
        <template v-for="group in getAgentEventGroups(selectedAgentId)" :key="group.type">
          <ThinkingRow v-if="group.type === 'thinking'" :content="group.content || ''" />
          <TextOutputRow v-else-if="group.type === 'text'" :content="group.content || ''" />
          <ToolCallGroupRow v-else-if="group.type === 'tools'" :pairs="group.pairs || []" />
          <ErrorRow v-else-if="group.type === 'error'" :error="group.error!" />
        </template>
      </AgentSection>
    </template>
    <template v-else>
      <!-- 全部 Agent 分组视图 -->
      <AgentSection v-for="agentId in agentIds" :key="agentId" :agent="agents.get(agentId)!">
        <template v-for="group in getAgentEventGroups(agentId)" :key="group.type">
          <ThinkingRow v-if="group.type === 'thinking'" :content="group.content || ''" />
          <TextOutputRow v-else-if="group.type === 'text'" :content="group.content || ''" />
          <ToolCallGroupRow v-else-if="group.type === 'tools'" :pairs="group.pairs || []" />
          <ErrorRow v-else-if="group.type === 'error'" :error="group.error!" />
        </template>
      </AgentSection>
    </template>

    <!-- 进度追踪（累积显示所有 progress 事件） -->
    <ProgressTracker
      v-for="(p, idx) in progressHistory"
      :key="`${p.stage}-${idx}`"
      :stage="p.stage"
      :progress="p.progress"
      :message="p.message"
    />
  </div>
</template>

<script setup lang="ts">
import type { AgentState, TeamState, ToolCallPair } from '../types/timeline'
import TeamEventBlock from './TeamEventBlock.vue'
import AgentSection from './AgentSection.vue'
import ThinkingRow from './ThinkingRow.vue'
import TextOutputRow from './TextOutputRow.vue'
import ToolCallGroupRow from './ToolCallGroupRow.vue'
import ProgressTracker from './ProgressTracker.vue'

const props = defineProps<{
  teamState: TeamState
  agents: Map<string, AgentState>
  agentIds: string[]
  selectedAgentId: string | null
  progressHistory: Array<{ stage: string; progress: number; message: string }>
}>()

interface EventGroup {
  type: 'thinking' | 'text' | 'tools' | 'error'
  content?: string
  pairs?: ToolCallPair[]
  error?: { message: string; traceback?: string; recovered?: boolean }
}

function getAgentEventGroups(agentId: string): EventGroup[] {
  const agent = props.agents.get(agentId)
  if (!agent) return []

  const groups: EventGroup[] = []

  // 思考内容
  if (agent.thinkingContent) {
    groups.push({ type: 'thinking', content: agent.thinkingContent })
  }

  // 工具调用组（所有 toolPairs 作为一个组）
  if (agent.toolPairs.length > 0) {
    groups.push({ type: 'tools', pairs: agent.toolPairs })
  }

  // 文本输出
  if (agent.textOutput) {
    groups.push({ type: 'text', content: agent.textOutput })
  }

  // 错误
  if (agent.error) {
    groups.push({ type: 'error', error: agent.error })
  }

  return groups
}
</script>

<style scoped lang="less">
.event-stream-view {
  flex: 1; min-width: 0; overflow-y: auto; padding: 8px;
  display: flex; flex-direction: column; gap: 4px;
}
</style>
