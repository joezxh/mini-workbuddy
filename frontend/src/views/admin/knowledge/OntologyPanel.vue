<template>
  <div class="kg-panel">
    <div class="kg-panel__header">
      <h2 class="kg-panel__title">{{ t('knowledge.ontology.title') }}</h2>
    </div>
    <a-tabs v-model:activeKey="active" class="kg-panel__tabs">
      <a-tab-pane key="list" tab="本体列表"><OntologyList /></a-tab-pane>
      <a-tab-pane key="class" tab="类层级"><ClassHierarchy /></a-tab-pane>
      <a-tab-pane key="modeling" tab="建模工作台"><ModelingWorkbench /></a-tab-pane>
      <a-tab-pane key="review" tab="评审与版本"><ReviewVersion /></a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import OntologyList from './ontology/OntologyList.vue'
import ClassHierarchy from './ontology/ClassHierarchy.vue'
import ModelingWorkbench from './ontology/ModelingWorkbench.vue'
import ReviewVersion from './ontology/ReviewVersion.vue'

const { t } = useI18n()
const active = ref('list')
</script>

<style lang="less" scoped>
.kg-panel { display: flex; flex-direction: column; height: 100%; }
.kg-panel__header { margin-bottom: 8px; }
.kg-panel__title { margin: 0; font-size: 18px; }
.kg-panel__tabs { flex: 1; min-height: 0; :deep(.ant-tabs-content) { height: 100%; } }
</style>
