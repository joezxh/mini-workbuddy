<template>
  <div class="thinking-card" :class="{ active }">
    <div class="tc-header" @click="$emit('toggle')">
      <span class="tc-icon"><BulbOutlined /></span>
      <span class="tc-title">
        {{ active ? '思考中…' : `已完成思考（${steps.length} 步）` }}
      </span>
      <span v-if="!active && durationText" class="tc-meta">{{ durationText }}</span>
      <CaretDownOutlined v-if="!active" class="tc-caret" :class="{ collapsed: !expanded }" />
    </div>
    <div v-show="active || expanded" class="tc-body">
      <div v-for="s in steps" :key="s.step" class="tc-step">
        <div class="tc-step-head">
          <span class="tc-step-no">{{ s.step }}</span>
          <span class="tc-step-title">{{ s.title }}</span>
          <a-tag v-if="s.confidence != null" color="blue" size="small">置信度 {{ Math.round(s.confidence * 100) }}%</a-tag>
        </div>
        <div class="tc-step-content">{{ s.content }}</div>
      </div>
      <div v-if="!steps.length" class="tc-empty">正在推理…</div>
    </div>
    <div v-if="conclusion" class="tc-conclusion" v-html="renderedConclusion"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { BulbOutlined, CaretDownOutlined } from '@ant-design/icons-vue'
import MarkdownIt from 'markdown-it'
import type { ThinkingStep } from './../types'

const props = defineProps<{
  steps: ThinkingStep[]
  conclusion?: string
  expanded?: boolean
  active?: boolean
  durationMs?: number | null
}>()
defineEmits<{ (e: 'toggle'): void }>()

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
const renderedConclusion = computed(() => (props.conclusion ? md.render(props.conclusion) : ''))
const durationText = computed(() =>
  props.durationMs ? `${(props.durationMs / 1000).toFixed(1)}s` : ''
)
</script>

<style scoped lang="less">
.thinking-card {
  border: 1px solid var(--border); border-radius: 10px; overflow: hidden;
  background: var(--bg-input);
  &.active { border-color: var(--accent-soft); background: var(--accent-soft); }
}
.tc-header {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px;
  cursor: pointer; user-select: none; font-size: 13px; color: var(--fg); font-weight: 600;
}
.tc-icon { color: var(--warn); }
.tc-title { flex: 1; }
.tc-meta { font-size: 12px; color: var(--fg-muted); font-weight: 400; }
.tc-caret { transition: transform .2s; &.collapsed { transform: rotate(-90deg); } }
.tc-body { padding: 0 12px 8px; }
.tc-step { padding: 8px 0; border-top: 1px dashed var(--divider); }
.tc-step:first-child { border-top: none; }
.tc-step-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.tc-step-no {
  width: 20px; height: 20px; border-radius: 50%; background: var(--accent); color: #fff;
  font-size: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.tc-step-title { font-weight: 600; color: var(--fg); font-size: 13px; }
.tc-step-content { font-size: 12.5px; color: var(--fg-secondary); line-height: 1.7; white-space: pre-wrap; }
.tc-empty { font-size: 12px; color: var(--fg-muted); padding: 6px 0; }
.tc-conclusion {
  padding: 12px; border-top: 1px solid var(--border); background: var(--bg-surface); font-size: 14px;
  line-height: 1.7; :deep(p) { margin: 0 0 8px; } :deep(p:last-child) { margin: 0; }
}
</style>
