<template>
  <div class="ext-sync">
    <div class="ext-sync__toolbar">
      <a-select v-model:value="instanceId" :placeholder="t('kbMgmt.ext.filterByInstance')" allow-clear style="width: 220px" @change="load">
        <a-select-option v-for="i in instances" :key="i.id" :value="i.id">{{ i.name }}</a-select-option>
      </a-select>
      <a-button @click="load"><ReloadOutlined /> {{ t('kbMgmt.common.refresh') }}</a-button>
    </div>
    <DataTable :columns="columns" :data-source="jobs" :loading="loading" row-key="id" :page-visible="false">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'success' ? 'success' : record.status === 'failed' ? 'error' : 'processing'">{{ record.status }}</a-tag>
        </template>
        <template v-if="column.key === 'error' && record.error_detail">
          <span class="err">{{ record.error_detail }}</span>
        </template>
      </template>
    </DataTable>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import DataTable from '@/components/common/DataTable/index.vue'
import * as api from '@/api/externalKb'

const { t } = useI18n()
const instances = ref<any[]>([])
const instanceId = ref<number>()
const jobs = ref<any[]>([])
const loading = ref(false)

const columns = computed(() => [
  { title: t('kbMgmt.ext.instanceCol'), dataIndex: 'instance_name', key: 'instance_name' },
  { title: t('kbMgmt.common.status'), key: 'status', width: 110 },
  { title: t('kbMgmt.ext.added'), dataIndex: 'added', key: 'added', width: 80 },
  { title: t('kbMgmt.ext.updated'), dataIndex: 'updated', key: 'updated', width: 80 },
  { title: t('kbMgmt.ext.deletedCol'), dataIndex: 'deleted', key: 'deleted', width: 80 },
  { title: t('kbMgmt.ext.duration'), dataIndex: 'duration_ms', key: 'duration_ms', width: 100 },
  { title: t('kbMgmt.common.errorCol'), key: 'error' },
])

async function loadInstances() {
  try {
    const r: any = await api.listInstances()
    instances.value = r.data || r || []
  } catch { /* ignore */ }
}
async function load() {
  loading.value = true
  try {
    const r: any = await api.listSyncJobs(instanceId.value)
    jobs.value = r.data || r || []
  } catch (e: any) {
    message.warning(t('kbMgmt.ext.syncJobsRouterMissing'))
  } finally {
    loading.value = false
  }
}
onMounted(async () => {
  await loadInstances()
  load()
})
</script>

<style scoped>
.ext-sync__toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
.err { color: var(--err); font-size: 12px; }
</style>
