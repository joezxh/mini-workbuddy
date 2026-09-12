<template>
  <div class="kg-panel">
    <div class="kg-panel__header">
      <h2 class="kg-panel__title">{{ t('knowledge.dataSource.title') }}</h2>
    </div>
    <a-tabs v-model:activeKey="active" class="kg-panel__tabs">
      <a-tab-pane key="source" :tab="t('knowledge.common.name') + ' / 数据源'">
        <SourceManagement />
      </a-tab-pane>
      <a-tab-pane key="metadata" tab="元数据浏览">
        <MetadataExplorer />
      </a-tab-pane>
      <a-tab-pane key="standard" tab="元数据标准">
        <StandardManagement />
      </a-tab-pane>
      <a-tab-pane key="binding" tab="字段绑定">
        <BindingWorkbench />
      </a-tab-pane>
      <a-tab-pane key="sql" tab="SQL 工作台">
        <SqlWorkbench />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import SourceManagement from './data-source/SourceManagement.vue'
import MetadataExplorer from './data-source/MetadataExplorer.vue'
import StandardManagement from './data-source/StandardManagement.vue'
import BindingWorkbench from './data-source/BindingWorkbench.vue'
import SqlWorkbench from './data-source/SqlWorkbench.vue'

const { t } = useI18n()
const active = ref('source')
</script>

<style lang="less" scoped>
.kg-panel {
  display: flex;
  flex-direction: column;
  height: 100%;

  &__header {
    margin-bottom: 8px;
  }
  &__title {
    margin: 0;
    font-size: 18px;
  }
  &__tabs {
    flex: 1;
    min-height: 0;
    :deep(.ant-tabs-content) {
      height: 100%;
    }
  }
}
</style>
