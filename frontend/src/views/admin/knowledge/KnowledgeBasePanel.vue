<template>
  <div class="kg-panel">
    <div class="kg-panel__header">
      <h2 class="kg-panel__title">{{ t('knowledge.kb.title') }}</h2>
    </div>
    <a-tabs v-model:activeKey="active" class="kg-panel__tabs">
      <a-tab-pane key="dataset" tab="数据集管理"><DatasetManagement /></a-tab-pane>
      <a-tab-pane key="document" tab="文档管理"><DocumentManagement /></a-tab-pane>
      <a-tab-pane key="search" tab="检索测试"><SearchTester /></a-tab-pane>
      <a-tab-pane key="ingestion" tab="索引状态"><IngestionJobs /></a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import DatasetManagement from './kb/DatasetManagement.vue'
import DocumentManagement from './kb/DocumentManagement.vue'
import SearchTester from './kb/SearchTester.vue'
import IngestionJobs from './kb/IngestionJobs.vue'

const { t } = useI18n()
const active = ref('dataset')
</script>

<style lang="less" scoped>
.kg-panel { display: flex; flex-direction: column; height: 100%; }
.kg-panel__header { margin-bottom: 8px; }
.kg-panel__title { margin: 0; font-size: 18px; }
.kg-panel__tabs { flex: 1; min-height: 0; :deep(.ant-tabs-content) { height: 100%; } }
</style>
