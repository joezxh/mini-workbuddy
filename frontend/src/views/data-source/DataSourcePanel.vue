<template>
  <div class="kg-panel">
    <div class="kg-panel__header">
      <h2 class="kg-panel__title">{{ t('kbMgmt.dataSource.title') }}</h2>
    </div>
    <a-tabs v-model:activeKey="active" class="kg-panel__tabs">
      <a-tab-pane key="source" :tab="t('kbMgmt.common.name') + ' / ' + t('kbMgmt.dataSource.tabSource')">
        <SourceManagement />
      </a-tab-pane>
      <a-tab-pane key="metadata" :tab="t('kbMgmt.dataSource.tabMetadata')">
        <MetadataExplorer :focus="metaFocus" />
      </a-tab-pane>
      <a-tab-pane key="standard" :tab="t('kbMgmt.dataSource.tabStandard')">
        <StandardManagement @drill-down="onDrillDown" />
      </a-tab-pane>
      <a-tab-pane key="binding" :tab="t('kbMgmt.dataSource.tabBinding')">
        <BindingWorkbench />
      </a-tab-pane>
      <a-tab-pane key="sql" :tab="t('kbMgmt.dataSource.tabSql')">
        <SqlWorkbench />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import SourceManagement from './SourceManagement.vue'
import MetadataExplorer from './MetadataExplorer.vue'
import StandardManagement from './StandardManagement.vue'
import BindingWorkbench from './BindingWorkbench.vue'
import SqlWorkbench from './SqlWorkbench.vue'

const { t } = useI18n()
const active = ref('source')
/** 标准检视 → 元数据浏览的下钻落点（每次都换新对象，便于子组件 watch 感知） */
const metaFocus = ref<{ source_id: number; db_name?: string; database?: string; table: string } | null>(null)

function onDrillDown(payload: { source_id: number; db_name?: string; database?: string; table: string }) {
  metaFocus.value = { ...payload }
  active.value = 'metadata'
}
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
