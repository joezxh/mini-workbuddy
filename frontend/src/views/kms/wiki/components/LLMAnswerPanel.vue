<template>
  <div class="llm-answer-panel">
    <div class="markdown-body" v-html="renderedAnswer"></div>
    <a-divider v-if="citations.length" orientation="left">{{ t('kmsWiki.citations') }}</a-divider>
    <div class="citation-list" v-if="citations.length">
      <CitationCard
        v-for="c in citations"
        :key="c.ref"
        :citation="c"
        @navigate="navigate"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import CitationCard from './CitationCard.vue'
import type { CitationItem } from '../types/wiki'
import { openDynamicTab } from '@/utils/shellTab'

const props = defineProps<{ answer: string; citations: CitationItem[] }>()
const { t } = useI18n()
const md = new MarkdownIt({ html: false, linkify: true, typographer: true })

const renderedAnswer = computed(() =>
  props.answer ? DOMPurify.sanitize(md.render(props.answer)) : ''
)

function navigate(slug: string) {
  openDynamicTab(
    { key: `kg-wiki-view:${slug}`, component: 'kg-wiki-view', titleKey: 'kmsWiki.articleView', icon: 'ReadOutlined', props: { slug } },
    `/wiki/${slug}`,
  )
}
</script>

<style scoped>
.llm-answer-panel {
  line-height: 1.8;
}
.markdown-body {
  font-size: 15px;
}
.citation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
