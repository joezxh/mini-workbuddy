<template>
  <div class="agent-event-stream">
    <!-- 仅当当前执行出现 HITL 暂停且未处理时，渲染确认面板 -->
    <HitlConfirmPanel
      v-if="renderedPause"
      :execution-id="executionId"
      :pause="renderedPause"
      @resolved="onResolved"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { storeToRefs } from 'pinia'
import { useAgentEventsStore } from '@/stores/agentEvents'
import HitlConfirmPanel from './HitlConfirmPanel.vue'
import type { EventEnvelope } from '@/types/agentEvents'

const props = defineProps<{
  executionId: string
}>()

const store = useAgentEventsStore()
const { hitlPause, connected, error } = storeToRefs(store)

const renderedPause = computed<EventEnvelope | null>(() => {
  const p = hitlPause.value
  if (p && p.execution_id === props.executionId) return p
  return null
})

function ensureConnected() {
  if (!props.executionId) return
  if (!connected.value || (hitlPause.value && hitlPause.value.execution_id !== props.executionId)) {
    store.connect(props.executionId)
  }
}

function onResolved() {
  store.clearHitl()
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
