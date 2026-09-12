<template>
  <div class="kg-panel">
    <div class="kg-panel__header">
      <h2 class="kg-panel__title">{{ t('knowledge.externalKb.title') }}</h2>
    </div>
    <a-tabs v-model:activeKey="active" class="kg-panel__tabs">
      <a-tab-pane key="instance" tab="实例管理"><InstanceManagement /></a-tab-pane>
      <a-tab-pane key="sync" tab="同步任务"><SyncJobs /></a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import InstanceManagement from './external/InstanceManagement.vue'
import SyncJobs from './external/SyncJobs.vue'

const { t } = useI18n()
const active = ref('instance')
</script>

<style lang="less" scoped>
.kg-panel { display: flex; flex-direction: column; height: 100%; }
.kg-panel__header { margin-bottom: 8px; }
.kg-panel__title { margin: 0; font-size: 18px; }
.kg-panel__tabs { flex: 1; min-height: 0; :deep(.ant-tabs-content) { height: 100%; } }
</style>
