<template>
  <div class="kb-doc">
    <div class="kb-doc__toolbar">
      <a-select v-model:value="kbId" :placeholder="t('kbMgmt.doc.selectDataset')" style="width: 240px" @change="loadDocs">
        <a-select-option v-for="d in datasets" :key="d.kb_id" :value="d.kb_id">{{ d.name }}</a-select-option>
      </a-select>
    </div>

    <a-upload-dragger
      v-if="kbId"
      :multiple="true"
      :before-upload="upload"
      :show-upload-list="false"
      style="margin-bottom: 12px"
    >
      <p class="ant-upload-text">{{ t('kbMgmt.doc.uploadHint') }}</p>
      <p class="ant-upload-hint">{{ t('kbMgmt.doc.uploadSubHint') }}</p>
    </a-upload-dragger>

    <DataTable :columns="columns" :data-source="docs" :loading="loading" row-key="doc_id" :page-visible="false">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ record.status }}</a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button size="small" @click="preview(record)">{{ t('kbMgmt.doc.chunkPreview') }}</a-button>
          <a-button v-if="record.status === 'error'" size="small" @click="reupload(record)">{{ t('kbMgmt.doc.reupload') }}</a-button>
        </template>
      </template>
    </DataTable>

    <a-drawer :title="t('kbMgmt.doc.chunkPreview')" :open="previewOpen" @close="previewOpen = false" width="520">
      <ChunkPreview :chunks="chunks" />
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import DataTable from '@/components/common/DataTable/index.vue'
import ChunkPreview from '@/components/common/ChunkPreview.vue'
import * as api from '@/api/knowledgeBase'

const { t } = useI18n()
const datasets = ref<any[]>([])
const kbId = ref<string>()
const docs = ref<any[]>([])
const loading = ref(false)
const previewOpen = ref(false)
const chunks = ref<any[]>([])

const columns = computed(() => [
  { title: t('kbMgmt.common.title'), dataIndex: 'title', key: 'title' },
  { title: t('kbMgmt.common.type'), dataIndex: 'type', key: 'type', width: 100 },
  { title: t('kbMgmt.common.status'), key: 'status', width: 110 },
  { title: t('kbMgmt.doc.chunkCount'), dataIndex: 'chunk_count', key: 'chunk_count', width: 90 },
  { title: t('kbMgmt.common.actions'), key: 'action', width: 160 },
])

function statusColor(s: string) {
  return s === 'ready' ? 'success' : s === 'error' ? 'error' : s === 'pending' ? 'default' : 'processing'
}

async function loadDatasets() {
  const r: any = await api.listDatasets()
  datasets.value = r.data || r || []
}
async function loadDocs() {
  if (!kbId.value) return
  loading.value = true
  try {
    const r: any = await api.listDocuments(kbId.value)
    docs.value = r.data || r || []
  } finally {
    loading.value = false
  }
}
async function upload(file: File) {
  if (!kbId.value) return false
  const fd = new FormData()
  fd.append('file', file)
  try {
    await api.uploadDocument(kbId.value, fd)
    message.success(t('kbMgmt.doc.uploaded', { name: file.name }))
    loadDocs()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.doc.uploadFailed'))
  }
  return false
}
function reupload(_row?: any) {
  message.info(t('kbMgmt.doc.reuploadHint'))
}
function preview(row: any) {
  chunks.value = row.chunks || [{ index: 1, content: row.content_preview || t('kbMgmt.doc.chunkPreviewPending') }]
  previewOpen.value = true
}
onMounted(loadDatasets)
</script>

<style scoped>
.kb-doc__toolbar { margin-bottom: 12px; }
</style>
