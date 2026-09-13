<template>
  <div class="knowledge-management">
    <a-tabs v-model:activeKey="active">
      <a-tab-pane key="kb" :tab="t('wikiMgmt.tabKb')" />
      <a-tab-pane key="category" :tab="t('wikiMgmt.tabCategory')" />
      <a-tab-pane key="article" :tab="t('wikiMgmt.tabArticle')" />
      <a-tab-pane key="rag" :tab="t('wikiMgmt.tabRag')" />
      <a-tab-pane key="version" :tab="t('wikiMgmt.tabVersion')" />
    </a-tabs>
    <div class="tab-body">
      <KnowledgeBaseTab v-if="active === 'kb'" />
      <CategoryTab v-else-if="active === 'category'" />
      <ArticleTab v-else-if="active === 'article'" />
      <RagTestTab v-else-if="active === 'rag'" />
      <VersionTab v-else-if="active === 'version'" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import KnowledgeBaseTab from '@/views/admin/llm-wiki/tabs/KnowledgeBaseTab.vue'
import CategoryTab from '@/views/admin/llm-wiki/tabs/CategoryTab.vue'
import ArticleTab from '@/views/admin/llm-wiki/tabs/ArticleTab.vue'
import RagTestTab from '@/views/admin/llm-wiki/tabs/RagTestTab.vue'
import VersionTab from '@/views/admin/llm-wiki/tabs/VersionTab.vue'

const { t } = useI18n()
const active = ref('kb')
</script>

<style scoped>
.knowledge-management {
  padding: 24px;
}
.tab-body {
  margin-top: 16px;
}
</style>
