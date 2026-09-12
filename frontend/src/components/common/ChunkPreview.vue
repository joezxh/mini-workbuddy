<template>
  <div class="chunk-preview">
    <a-empty v-if="!chunks || chunks.length === 0" :description="t('knowledge.common.empty')" />
    <div v-for="(c, i) in chunks" :key="c.index ?? i" class="chunk-preview__item">
      <div class="chunk-preview__head">
        <span class="chunk-preview__idx">#{{ c.index ?? i + 1 }}</span>
        <span v-if="c.token_count != null" class="chunk-preview__token">
          {{ c.token_count }} tokens
        </span>
      </div>
      <div class="chunk-preview__body">{{ c.content }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

interface Chunk {
  index?: number
  content: string
  token_count?: number
}

defineProps<{ chunks?: Chunk[] }>()
const { t } = useI18n()
</script>

<style lang="less" scoped>
.chunk-preview {
  display: flex;
  flex-direction: column;
  gap: 10px;

  &__item {
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    overflow: hidden;
    background: var(--bg-surface);
  }

  &__head {
    display: flex;
    justify-content: space-between;
    padding: 6px 10px;
    background: var(--bg-hover);
    border-bottom: 1px solid var(--border);
    font-size: 12px;
  }

  &__idx {
    font-weight: 600;
    color: var(--accent);
  }

  &__token {
    color: var(--fg-muted);
  }

  &__body {
    padding: 10px;
    font-size: 13px;
    line-height: 1.7;
    color: var(--fg);
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 260px;
    overflow: auto;
  }
}
</style>
