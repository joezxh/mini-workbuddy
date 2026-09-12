<template>
  <div class="ext-sync">
    <div class="ext-sync__toolbar">
      <a-select v-model:value="instanceId" placeholder="按实例过滤" allow-clear style="width: 220px" @change="load">
        <a-select-option v-for="i in instances" :key="i.id" :value="i.id">{{ i.name }}</a-select-option>
      </a-select>
      <a-button @click="load"><ReloadOutlined /> {{ t('knowledge.common.refresh') }}</a-button>
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
import { ref, onMounted } from 'vue'
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

const columns = [
  { title: '实例', dataIndex: 'instance_name', key: 'instance_name' },
  { title: t('knowledge.common.status'), key: 'status', width: 110 },
  { title: '新增', dataIndex: 'added', key: 'added', width: 80 },
  { title: '更新', dataIndex: 'updated', key: 'updated', width: 80 },
  { title: '删除', dataIndex: 'deleted', key: 'deleted', width: 80 },
  { title: '耗时(ms)', dataIndex: 'duration_ms', key: 'duration_ms', width: 100 },
  { title: '错误', key: 'error' },
]

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
    message.warning('同步任务需后端 router')
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
