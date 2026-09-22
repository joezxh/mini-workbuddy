<template>
  <!-- 主渲染组件（由 EventRouter 渲染表决定，按序渲染） -->
  <component
    v-for="(entry, i) in activeEntries"
    :key="i"
    :is="entry.component"
    v-bind="entry.props(msg)"
  />
  <!-- 执行产物卡片 -->
  <ArtifactCard
    v-if="spec.showArtifacts && msg.artifacts?.length"
    :artifacts="msg.artifacts"
  />
  <!-- 结果正文回退（thinking 分支不传 expanded / toggle） -->
  <GeneralRenderer
    v-if="spec.showText"
    :parsed="msg.parsed || { rawContent: msg.content, thinking: '' }"
    v-bind="textProps"
  />
</template>

<script setup lang="ts">
/** 消息主渲染视图：消费 EventRouter 的渲染表，替代 ChatContainer 内联 v-if 链。 */
import { computed } from 'vue'
import type { ChatMessage } from './types'
import { resolveRenderKind, RENDER_SPECS, type RenderKind } from './eventRouter'
import ArtifactCard from './renderers/ArtifactCard.vue'
import GeneralRenderer from './renderers/GeneralRenderer.vue'

const props = defineProps<{
  msg: ChatMessage
  /** 当前会话类型（影响 thinking / research-legacy / scheduled 回退判定） */
  sessionType?: string
  /** 思考展开状态（thinkingExpanded[msg.message_id]） */
  thinkingExpanded?: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle-thinking', id: number): void
}>()

const kind = computed<RenderKind>(() =>
  resolveRenderKind(props.msg, { currentSessionType: props.sessionType })
)
const spec = computed(() => RENDER_SPECS[kind.value])
const activeEntries = computed(() =>
  spec.value.primary.filter(entry => !entry.when || entry.when(props.msg))
)

const textProps = computed(() => {
  if (spec.value.textBare) return { sessionType: props.sessionType }
  return {
    expanded: props.thinkingExpanded,
    sessionType: props.sessionType,
    onToggleThinking: () => emit('toggle-thinking', props.msg.message_id),
  }
})
</script>
