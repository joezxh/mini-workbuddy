<template>
  <a-card size="small" class="citation-card" hoverable @click="onClick">
    <template #title>
      <span class="ref-badge">[{{ citation.ref }}]</span> {{ citation.title }}
    </template>
    <div class="snippet">{{ citation.snippet }}</div>
  </a-card>
</template>

<script setup lang="ts">
import type { CitationItem } from '../types/wiki'

const props = defineProps<{ citation: CitationItem }>()
const emit = defineEmits<{ (e: 'navigate', slug: string): void }>()

function onClick() {
  emit('navigate', props.citation.slug)
}
</script>

<style scoped>
.citation-card {
  cursor: pointer;
}
.ref-badge {
  color: #1677ff;
  font-weight: 600;
  margin-right: 4px;
}
.snippet {
  color: var(--fg-muted, #666);
  font-size: 12px;
}
</style>
