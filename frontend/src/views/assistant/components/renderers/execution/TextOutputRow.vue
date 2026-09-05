<template>
  <div class="text-output-row">
    <div class="text-output-content" v-html="renderedContent"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from '../../markdown'

const props = defineProps<{ content: string }>()
const renderedContent = computed(() => renderMarkdown(props.content || ''))
</script>

<style scoped lang="less">
.text-output-row { padding: 4px 10px; font-size: 13px; line-height: 1.7; color: var(--fg); }
.text-output-content {
  :deep(p) { margin: 0 0 8px; }
  :deep(pre) { background: var(--bg-input); padding: 8px; border-radius: 4px; overflow-x: auto; }
}
</style>
