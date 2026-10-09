<template>
  <a-list :data-source="items" :loading="loading" size="small" :locale="{ emptyText: t('kmsWiki.noResults') }">
    <template #renderItem="{ item }">
      <a-list-item>
        <a-list-item-meta>
          <template #title>
            <a @click="open(item)">{{ item.title }}</a>
          </template>
          <template #description>
            <div class="snippet">{{ item.snippet }}</div>
            <a-tag v-if="item.score" color="blue" size="small">
              {{ t('kmsWiki.relevance') }} {{ item.score }}
            </a-tag>
          </template>
        </a-list-item-meta>
      </a-list-item>
    </template>
  </a-list>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { SearchItem } from '../types/wiki'
import { openDynamicTab } from '@/utils/shellTab'

defineProps<{ items: SearchItem[]; loading?: boolean }>()
const { t } = useI18n()

function open(item: SearchItem) {
  openDynamicTab(
    { key: `kg-wiki-view:${item.slug}`, component: 'kg-wiki-view', titleKey: 'kmsWiki.articleView', icon: 'ReadOutlined', props: { slug: item.slug } },
    `/wiki/${item.slug}`,
  )
}
</script>

<style scoped>
.snippet {
  color: var(--fg-muted, #666);
  font-size: 13px;
  margin: 4px 0;
}
</style>
