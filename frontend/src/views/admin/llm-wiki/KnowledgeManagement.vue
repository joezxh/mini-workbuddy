<template>
  <div class="knowledge-management">
    <a-tabs v-model:activeKey="active">
      <a-tab-pane key="kb" tab="知识库" />
      <a-tab-pane key="category" tab="分类" />
      <a-tab-pane key="article" tab="文章" />
      <a-tab-pane key="rag" tab="RAG 测试" />
      <a-tab-pane key="version" tab="版本" />
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
import KnowledgeBaseTab from '@/views/admin/llm-wiki/tabs/KnowledgeBaseTab.vue'
import CategoryTab from '@/views/admin/llm-wiki/tabs/CategoryTab.vue'
import ArticleTab from '@/views/admin/llm-wiki/tabs/ArticleTab.vue'
import RagTestTab from '@/views/admin/llm-wiki/tabs/RagTestTab.vue'
import VersionTab from '@/views/admin/llm-wiki/tabs/VersionTab.vue'

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
