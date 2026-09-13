<template>
  <div class="kb-ds">
    <div class="kb-ds__toolbar">
      <a-button type="primary" @click="openForm()"><PlusOutlined /> {{ t('kbMgmt.common.create') }}</a-button>
      <a-button @click="load"><ReloadOutlined /> {{ t('kbMgmt.common.refresh') }}</a-button>
    </div>
    <DataTable :columns="columns" :data-source="datasets" :loading="loading" row-key="kb_id" :page-visible="false">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'action'">
          <a-button size="small" @click="rebuild(record)">{{ t('kbMgmt.dataset.rebuildIndex') }}</a-button>
          <a-popconfirm :title="t('kbMgmt.common.deleteConfirm')" @confirm="remove(record)">
            <a-button size="small" danger>{{ t('kbMgmt.common.delete') }}</a-button>
          </a-popconfirm>
        </template>
      </template>
    </DataTable>

    <a-modal v-model:open="formOpen" :title="t('kbMgmt.common.create')" @ok="save">
      <a-form :model="form" layout="vertical">
        <a-form-item :label="t('kbMgmt.common.name')" required><a-input v-model:value="form.name" /></a-form-item>
        <a-form-item :label="t('kbMgmt.dataset.embeddingModel')">
          <a-select v-model:value="form.embedding_model">
            <a-select-option v-for="m in embeddingModels" :key="m.id" :value="m.id">{{ m.name || m.id }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="t('kbMgmt.dataset.chunker')">
          <a-select v-model:value="form.chunker">
            <a-select-option v-for="c in chunkers" :key="c.key" :value="c.key">{{ c.label || c.key }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import DataTable from '@/components/common/DataTable/index.vue'
import * as api from '@/api/knowledgeBase'

const { t } = useI18n()
const datasets = ref<any[]>([])
const loading = ref(false)
const formOpen = ref(false)
const form = ref<any>({})
const embeddingModels = ref<any[]>([])
const chunkers = ref<any[]>([])

const columns = computed(() => [
  { title: t('kbMgmt.common.name'), dataIndex: 'name', key: 'name' },
  { title: 'Embedding', dataIndex: 'embedding_model', key: 'embedding_model' },
  { title: t('kbMgmt.dataset.dimension'), dataIndex: 'dimension', key: 'dimension', width: 90 },
  { title: t('kbMgmt.dataset.chunker'), dataIndex: 'chunker', key: 'chunker', width: 120 },
  { title: t('kbMgmt.dataset.docCount'), dataIndex: 'doc_count', key: 'doc_count', width: 90 },
  { title: t('kbMgmt.common.actions'), key: 'action', width: 160 },
])

async function load() {
  loading.value = true
  try {
    const r: any = await api.listDatasets()
    datasets.value = r.data || r || []
  } finally {
    loading.value = false
  }
}
async function loadCaps() {
  try {
    const em: any = await api.getEmbeddingModels()
    embeddingModels.value = em.data || em || []
    const ck: any = await api.getChunkers()
    chunkers.value = ck.data || ck || []
  } catch {
    /* 能力发现端点未就绪时忽略 */
  }
}
function openForm() {
  form.value = {}
  formOpen.value = true
}
async function save() {
  try {
    await api.createDataset(form.value)
    message.success(t('kbMgmt.dataset.createSuccess'))
    formOpen.value = false
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.dataset.createFailed'))
  }
}
async function remove(row: any) {
  try {
    await api.deleteDataset(row.kb_id)
    message.success(t('kbMgmt.common.deleted'))
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.common.deleteFailed'))
  }
}
function rebuild(row: any) {
  message.info(t('kbMgmt.dataset.rebuildHint', { name: row.name }))
}
onMounted(async () => {
  await loadCaps()
  load()
})
</script>

<style scoped>
.kb-ds__toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
</style>
