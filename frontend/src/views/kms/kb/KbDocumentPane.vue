<template>
  <div class="kb-doc-pane">
    <!-- 顶部：文档上传 + 形态切换 -->
    <a-space class="kb-doc-pane__actions" wrap>
      <a-upload :before-upload="handleUpload" :show-upload-list="false">
        <a-button type="primary" :loading="uploading">{{ t('kbMgmt.uploadDocument') }}</a-button>
      </a-upload>
      <a-radio-group v-model:value="formatMode" button-style="solid" size="small">
        <a-radio-button value="document">{{ t('kbMgmt.fmtDocument') }}</a-radio-button>
        <a-radio-button value="table">{{ t('kbMgmt.fmtTable') }}</a-radio-button>
        <a-radio-button value="qa">{{ t('kbMgmt.fmtQa') }}</a-radio-button>
        <a-radio-button value="pipeline">{{ t('kbMgmt.fmtPipeline') }}</a-radio-button>
      </a-radio-group>
    </a-space>

    <!-- 文档上传形态 -->
    <template v-if="formatMode === 'document'">
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
            <a-space size="small">
              <a-button size="small" @click="openSegments(record)">{{ t('kbMgmt.segments') }}</a-button>
              <a-popconfirm :title="t('kbMgmt.confirmDeleteDoc')" @confirm="removeDoc(record)">
                <a-button size="small" danger>{{ t('common.delete') }}</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </template>

    <!-- 表格导入形态：字段映射面板（Dify 对齐）+ 行级条目列表 -->
    <a-card v-else-if="formatMode === 'table'" class="kb-doc-pane__panel" :title="t('kbMgmt.tableImport')" size="small">
      <a-upload :before-upload="handleTableFile" :show-upload-list="false" accept=".csv,.xlsx,.xls">
        <a-button :loading="tableParsing">{{ t('kbMgmt.selectTableFile') }}</a-button>
      </a-upload>
      <template v-if="tableColumns.length">
        <a-alert class="kb-doc-pane__hint" type="info" :message="t('kbMgmt.embedFieldHint')" show-icon />
        <a-form layout="vertical" class="kb-doc-pane__form">
          <a-form-item :label="t('kbMgmt.embedField')">
            <a-select v-model:value="embedField" :options="tableColumns.map((c) => ({ label: c, value: c }))" />
          </a-form-item>
          <a-form-item>
            <a-button type="primary" :loading="tableImporting" @click="runTableImport">
              {{ t('kbMgmt.importTable') }}
            </a-button>
          </a-form-item>
        </a-form>
        <a-table size="small" :data-source="tablePreview" :columns="tableColumns.map((c) => ({ title: c, dataIndex: c, key: c }))" :pagination="{ pageSize: 5 }" row-key="__i" />
      </template>
    </a-card>
    <TableRecordList
      v-if="formatMode === 'table'"
      class="kb-doc-pane__panel"
      :knowledge-id="props.knowledgeId"
      :collection="collection"
    />

    <!-- Q&A 导入形态 -->
    <a-card v-else-if="formatMode === 'qa'" class="kb-doc-pane__panel" :title="t('kbMgmt.qaImport')" size="small">
      <a-alert class="kb-doc-pane__hint" type="info" :message="t('kbMgmt.qaHint')" show-icon />
      <a-textarea v-model:value="qaText" :rows="8" :placeholder="t('kbMgmt.qaPlaceholder')" />
      <a-button class="kb-doc-pane__form" type="primary" :loading="qaImporting" @click="runQaImport">
        {{ t('kbMgmt.importQa') }}
      </a-button>
    </a-card>
    <QaRecordList
      v-if="formatMode === 'qa'"
      class="kb-doc-pane__panel"
      :collection="collection"
    />

    <!-- 管线调试形态：dry-run -->
    <a-card v-else-if="formatMode === 'pipeline'" class="kb-doc-pane__panel" :title="t('kbMgmt.pipelineDryRun')" size="small">
      <a-upload :before-upload="handleDryRun" :show-upload-list="false">
        <a-button :loading="dryRunning">{{ t('kbMgmt.selectSampleFile') }}</a-button>
      </a-upload>
      <a-collapse v-if="dryResult" class="kb-doc-pane__form">
        <a-collapse-panel :header="`${t('kbMgmt.sections')} (${dryResult.sections.length})`">
          <div v-for="(s, i) in dryResult.sections.slice(0, 5)" :key="i" class="kb-doc-pane__preview">{{ s.preview }}</div>
        </a-collapse-panel>
        <a-collapse-panel :header="`${t('kbMgmt.chunks')} (${dryResult.chunks.length})`">
          <div v-for="(c, i) in dryResult.chunks.slice(0, 5)" :key="i" class="kb-doc-pane__preview">
            #{{ c.chunk_index }}/{{ c.total_chunks }} — {{ c.preview }}
          </div>
        </a-collapse-panel>
      </a-collapse>
    </a-card>

    <!-- 分段详情抽屉（spec §10.5） -->
    <SegmentDetail
      v-model:open="segmentOpen"
      :document-id="segmentDocId"
      @changed="loadDocs"
    />

    <!-- 检索测试（economy / high_quality 由后端自动路由） -->
    <a-card class="kb-doc-pane__tester" :title="t('kbMgmt.retrievalTest')" size="small">
      <a-input-search
        v-model:value="query"
        :placeholder="t('kbMgmt.searchPlaceholder')"
        enter-button
        @search="runRetrieve"
      />
      <a-tag v-if="indexMode" class="kb-doc-pane__mode">{{ indexMode }}</a-tag>
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
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  createQaRecords,
  deleteDocument,
  getDocumentStatus,
  importTableRecords,
  listDocuments,
  pipelineDryRun,
  previewTableRecords,
  retrieve,
  uploadDocument,
  type KbDocument,
  type RetrieveResult,
} from '@/api/kb'
import SegmentDetail from './SegmentDetail.vue'
import TableRecordList from './TableRecordList.vue'
import QaRecordList from './QaRecordList.vue'

const props = defineProps<{ knowledgeId: number }>()
const { t } = useI18n()

const collection = computed(() => `kb_${props.knowledgeId}`)
const formatMode = ref<'document' | 'table' | 'qa' | 'pipeline'>('document')

const documents = ref<KbDocument[]>([])
const uploading = ref(false)
const query = ref('')
const results = ref<RetrieveResult[]>([])
const indexMode = ref<string>('')
let pollTimer: number | null = null

const columns = [
  { title: '文档', dataIndex: 'name', key: 'name' },
  { title: '状态', key: 'status', width: 110 },
  { title: '切片', dataIndex: 'segment_count', width: 70 },
  { title: '大小', dataIndex: 'file_size', width: 90 },
  { title: '操作', key: 'op', width: 80 },
]

// ── 表格导入 ──
const tableColumns = ref<string[]>([])
const tablePreview = ref<any[]>([])
const tableFile = ref<File | null>(null)
const embedField = ref<string>('')
const tableParsing = ref(false)
const tableImporting = ref(false)

// ── Q&A 导入 ──
const qaText = ref('')
const qaImporting = ref(false)

// ── dry-run ──
const dryRunning = ref(false)
const dryResult = ref<{ sections: any[]; chunks: any[] } | null>(null)

// ── 分段详情抽屉 ──
const segmentOpen = ref(false)
const segmentDocId = ref<string | null>(null)

function openSegments(record: KbDocument) {
  segmentDocId.value = record.document_id
  segmentOpen.value = true
}

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

function schedulePoll() {
  const busy = documents.value.some((d) => d.status === 'processing' || d.status === 'pending')
  if (busy && !pollTimer) pollTimer = window.setInterval(pollStatus, 3000)
  else if (!busy && pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollStatus() {
  const busy = documents.value.filter((d) => d.status === 'processing' || d.status === 'pending')
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
  return false
}

async function removeDoc(record: KbDocument) {
  await deleteDocument(record.document_id)
  await loadDocs()
}

async function runRetrieve() {
  if (!query.value.trim()) return
  const res: any = await retrieve(collection.value, { query: query.value })
  results.value = res.results || []
  indexMode.value = res.index_mode || ''
}

// ── 表格字段映射 ──
async function handleTableFile(file: File) {
  tableFile.value = file
  tableParsing.value = true
  try {
    const res: any = await previewTableRecords(collection.value, file, 20)
    tableColumns.value = res.columns || []
    tablePreview.value = (res.rows || []).map((r: any, i: number) => ({ __i: i, ...r }))
    embedField.value = tableColumns.value[0] || ''
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.parseFailed'))
  } finally {
    tableParsing.value = false
  }
  return false
}

async function runTableImport() {
  if (!tableFile.value) return
  if (!embedField.value) {
    message.warning(t('kbMgmt.embedFieldRequired'))
    return
  }
  tableImporting.value = true
  try {
    const res: any = await importTableRecords(collection.value, tableFile.value, embedField.value)
    message.success(`${t('kbMgmt.importTable')} ✓ ${res.ingested ?? 0}`)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.importFailed'))
  } finally {
    tableImporting.value = false
  }
}

// ── Q&A 导入（每行 "问题|答案"，可带 tags 用 "问题|答案|tag1,tag2"）──
async function runQaImport() {
  const records: { question: string; answer: string; tags: string[] }[] = []
  for (const line of qaText.value.split('\n')) {
    const parts = line.split('|').map((s) => s.trim())
    if (parts.length < 2 || !parts[0]) continue
    records.push({
      question: parts[0],
      answer: parts[1],
      tags: parts[2] ? parts[2].split(',').map((s) => s.trim()).filter(Boolean) : [],
    })
  }
  if (!records.length) {
    message.warning(t('kbMgmt.qaEmpty'))
    return
  }
  qaImporting.value = true
  try {
    const res: any = await createQaRecords(collection.value, records)
    message.success(`${t('kbMgmt.importQa')} ✓ ${res.ingested ?? 0}`)
    qaText.value = ''
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.importFailed'))
  } finally {
    qaImporting.value = false
  }
}

// ── dry-run ──
async function handleDryRun(file: File) {
  dryRunning.value = true
  try {
    const res: any = await pipelineDryRun(file, { chunkerType: 'approx_token' })
    dryResult.value = res
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.dryRunFailed'))
  } finally {
    dryRunning.value = false
  }
  return false
}

onMounted(loadDocs)
onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})
</script>

<style scoped>
.kb-doc-pane__actions {
  margin-bottom: 12px;
}
.kb-doc-pane__table {
  margin-top: 4px;
}
.kb-doc-pane__panel {
  margin-top: 12px;
}
.kb-doc-pane__hint {
  margin: 12px 0;
}
.kb-doc-pane__form {
  margin-top: 12px;
}
.kb-doc-pane__preview {
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-word;
  padding: 4px 0;
  border-bottom: 1px dashed #f0f0f0;
}
.kb-doc-pane__tester {
  margin-top: 16px;
}
.kb-doc-pane__mode {
  margin-left: 8px;
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
