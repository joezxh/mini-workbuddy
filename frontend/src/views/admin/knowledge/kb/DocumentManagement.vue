<template>
  <div class="kb-doc">
    <div class="kb-doc__toolbar">
      <a-select v-model:value="kbId" placeholder="选择数据集" style="width: 240px" @change="loadDocs">
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
      <p class="ant-upload-text">拖拽或点击上传文档</p>
      <p class="ant-upload-hint">多文件批量，索引在后台异步进行</p>
    </a-upload-dragger>

    <DataTable :columns="columns" :data-source="docs" :loading="loading" row-key="doc_id" :page-visible="false">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ record.status }}</a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button size="small" @click="preview(record)">切片预览</a-button>
          <a-button v-if="record.status === 'error'" size="small" @click="reupload(record)">重新上传</a-button>
        </template>
      </template>
    </DataTable>

    <a-drawer title="切片预览" :open="previewOpen" @close="previewOpen = false" width="520">
      <ChunkPreview :chunks="chunks" />
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
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

const columns = [
  { title: '标题', dataIndex: 'title', key: 'title' },
  { title: '类型', dataIndex: 'type', key: 'type', width: 100 },
  { title: t('knowledge.common.status'), key: 'status', width: 110 },
  { title: '切片数', dataIndex: 'chunk_count', key: 'chunk_count', width: 90 },
  { title: t('knowledge.common.actions'), key: 'action', width: 160 },
]

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
    message.success(`已上传 ${file.name}`)
    loadDocs()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '上传失败')
  }
  return false
}
function reupload(_row?: any) {
  message.info('重新上传：重新选择文件即可')
}
function preview(row: any) {
  chunks.value = row.chunks || [{ index: 1, content: row.content_preview || '（切片预览待后端返回 chunks 字段）' }]
  previewOpen.value = true
}
onMounted(loadDatasets)
</script>

<style scoped>
.kb-doc__toolbar { margin-bottom: 12px; }
</style>
