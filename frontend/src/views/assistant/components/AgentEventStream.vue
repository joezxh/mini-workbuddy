<template>
  <div class="agent-event-stream">
    <!-- 当前执行出现 HITL 暂停时渲染确认面板（多轮队列语义：resolve 后保持可见等待下一轮） -->
    <HitlConfirmPanel
      v-if="renderedPause"
      :execution-id="executionId"
      :pause="renderedPause"
      :round="store.hitlRound"
      :history="store.pauseHistory"
      :resolved="store.hitlResolved"
      @resolved="onResolved"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useAgentEventsStore } from '@/stores/agentEvents'
import HitlConfirmPanel from './HitlConfirmPanel.vue'
import type { EventEnvelope } from '@/types/agentEvents'

const props = defineProps<{
  executionId: string
}>()

const store = useAgentEventsStore()

const renderedPause = computed<EventEnvelope | null>(() => {
  const p = store.hitlPause
  if (p && p.execution_id === props.executionId) return p
  return null
})

function ensureConnected() {
  if (!props.executionId) return
  if (!store.connected || (store.hitlPause && store.hitlPause.execution_id !== props.executionId)) {
    store.connect(props.executionId)
  }
}

/** resolve 后仅记录轮次并等待下一轮 hitl_pause，不断开订阅、不隐藏面板 */
function onResolved(action: string) {
  store.resolveCurrentPause(action)
}

onMounted(ensureConnected)
watch(() => props.executionId, ensureConnected)
onBeforeUnmount(() => store.disconnect())
</script>

<style scoped lang="less">
.agent-event-stream {
  width: 100%;
}
</style>
