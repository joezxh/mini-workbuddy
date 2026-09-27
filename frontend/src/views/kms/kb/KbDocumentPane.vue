<template>
  <div class="kb-doc-pane">
    <a-upload :before-upload="handleUpload" :show-upload-list="false">
      <a-button type="primary" :loading="uploading">{{ t('kbMgmt.uploadDocument') }}</a-button>
    </a-upload>

    <a-table
      class="kb-doc-pane__table"
      size="small"
      :data-source="documents"
      :columns="columns"
      :pagination="false"
      row-key="document_id"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">
            {{ record.status }}<template v-if="record.status === 'processing'">…</template>
          </a-tag>
        </template>
        <template v-else-if="column.key === 'op'">
          <a-popconfirm :title="t('kbMgmt.confirmDeleteDoc')" @confirm="removeDoc(record)">
            <a-button size="small" danger>{{ t('common.delete') }}</a-button>
          </a-popconfirm>
        </template>
      </template>
    </a-table>

    <a-card class="kb-doc-pane__tester" :title="t('kbMgmt.retrievalTest')" size="small">
      <a-input-search
        v-model:value="query"
        :placeholder="t('kbMgmt.searchPlaceholder')"
        enter-button
        @search="runRetrieve"
      />
      <a-list v-if="results.length" size="small" :data-source="results">
        <template #renderItem="{ item }">
          <a-list-item>
            <div class="kb-doc-pane__hit">
              <span class="kb-doc-pane__score">{{ item.score.toFixed(4) }}</span>
              <span class="kb-doc-pane__content">{{ item.content }}</span>
            </div>
          </a-list-item>
        </template>
      </a-list>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  deleteDocument,
  getDocumentStatus,
  listDocuments,
  retrieve,
  uploadDocument,
  type KbDocument,
  type RetrieveResult,
} from '@/api/kb'

const props = defineProps<{ knowledgeId: number }>()
const { t } = useI18n()

const documents = ref<KbDocument[]>([])
const uploading = ref(false)
const query = ref('')
const results = ref<RetrieveResult[]>([])
let pollTimer: number | null = null

const columns = [
  { title: '文档', dataIndex: 'name', key: 'name' },
  { title: '状态', key: 'status', width: 110 },
  { title: '切片', dataIndex: 'segment_count', width: 70 },
  { title: '大小', dataIndex: 'file_size', width: 90 },
  { title: '操作', key: 'op', width: 80 },
]

function statusColor(status: string) {
  return (
    { pending: 'default', processing: 'processing', completed: 'success', failed: 'error' }[
      status
    ] || 'default'
  )
}

async function loadDocs() {
  const res: any = await listDocuments(props.knowledgeId)
  documents.value = res.items || res || []
  schedulePoll()
}

/** processing/pending 文档 3s 轮询（spec §10.6） */
function schedulePoll() {
  const busy = documents.value.some(
    (d) => d.status === 'processing' || d.status === 'pending',
  )
  if (busy && !pollTimer) {
    pollTimer = window.setInterval(pollStatus, 3000)
  } else if (!busy && pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollStatus() {
  const busy = documents.value.filter(
    (d) => d.status === 'processing' || d.status === 'pending',
  )
  if (!busy.length) return
  const res: any = await getDocumentStatus(busy.map((d) => d.document_id))
  for (const doc of documents.value) {
    const s = res[doc.document_id]
    if (s) {
      doc.status = s.status
      doc.segment_count = s.segment_count
      doc.error_detail = s.error_detail
    }
  }
  schedulePoll()
}

async function handleUpload(file: File) {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    await uploadDocument(props.knowledgeId, fd)
    message.success(t('kbMgmt.uploadAccepted'))
    await loadDocs()
  } catch (e) {
    message.error(t('kbMgmt.uploadFailed'))
  } finally {
    uploading.value = false
  }
  return false // 阻止 a-upload 默认上传
}

async function removeDoc(record: KbDocument) {
  await deleteDocument(record.document_id)
  await loadDocs()
}

async function runRetrieve() {
  if (!query.value.trim()) return
  const res: any = await retrieve(`kb_${props.knowledgeId}`, { query: query.value })
  results.value = res.results || []
}

onMounted(loadDocs)
onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})
</script>

<style scoped>
.kb-doc-pane__table {
  margin-top: 12px;
}
.kb-doc-pane__tester {
  margin-top: 16px;
}
.kb-doc-pane__hit {
  display: flex;
  gap: 8px;
  width: 100%;
}
.kb-doc-pane__score {
  font-family: monospace;
  color: var(--ant-primary-color, #3371fc);
}
.kb-doc-pane__content {
  flex: 1;
  word-break: break-word;
}
</style>
