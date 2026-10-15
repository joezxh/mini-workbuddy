<template>
  <div class="kb-doc-pane">
    <!-- 面板头：知识库名 + 副标题 + 操作区（操作从列表头部上移） -->
    <div class="kb-doc-pane__head">
      <div>
        <h2 class="kb-doc-pane__pane-title">
          <BookOutlined class="kb-doc-pane__pane-icon" />
          {{ props.knowledgeName || t('kbMgmt.generalKb') }}
        </h2>
        <div class="kb-doc-pane__pane-sub">
          {{ t('kbMgmt.generalKb') }} · {{ formatLabels[formatMode] }} ·
          {{ t('kbMgmt.docCount') }} {{ documents.length }}
        </div>
      </div>
      <a-space size="small">
        <a-tooltip :title="t('kbMgmt.rechunkTip')">
          <a-button size="small" :loading="rechunking" @click="runRechunk">
            {{ t('kbMgmt.rechunk') }}
          </a-button>
        </a-tooltip>
        <a-upload :before-upload="handleUpload" :show-upload-list="false">
          <a-button type="primary" size="small" :loading="uploading">
            {{ t('kbMgmt.uploadDocument') }}
          </a-button>
        </a-upload>
      </a-space>
    </div>

    <!-- 顶部：文档形态 tab 菜单（按所选知识库二级形态显示，管线调试作为调试入口常驻） -->
    <a-radio-group v-model:value="formatMode" button-style="solid" size="small" class="kb-doc-pane__tabs">
      <a-radio-button v-for="f in visibleFormats" :key="f" :value="f">
        {{ formatLabels[f] }}
      </a-radio-button>
    </a-radio-group>

    <!-- 文档上传形态 -->
    <template v-if="formatMode === 'document'">
      <!-- 统计卡：文档数 / 已完成 / 处理中 / 失败 -->
      <div class="kb-doc-stats">
        <div class="kb-doc-stat">
          <div class="kb-doc-stat__k">{{ t('kbMgmt.docCount') }}</div>
          <div class="kb-doc-stat__v">{{ docStats.total }}</div>
        </div>
        <div class="kb-doc-stat">
          <div class="kb-doc-stat__k">{{ t('kbMgmt.statCompleted') }}</div>
          <div class="kb-doc-stat__v kb-doc-stat__v--ok">{{ docStats.completed }}</div>
        </div>
        <div class="kb-doc-stat">
          <div class="kb-doc-stat__k">{{ t('kbMgmt.statProcessing') }}</div>
          <div class="kb-doc-stat__v">{{ docStats.processing }}</div>
        </div>
        <div class="kb-doc-stat">
          <div class="kb-doc-stat__k">{{ t('kbMgmt.statFailed') }}</div>
          <div class="kb-doc-stat__v kb-doc-stat__v--err">{{ docStats.failed }}</div>
        </div>
      </div>

      <a-empty v-if="!documents.length" :description="t('common.noData')">
        <a-upload :before-upload="handleUpload" :show-upload-list="false">
          <a-button type="primary" :loading="uploading">{{ t('kbMgmt.uploadDocument') }}</a-button>
        </a-upload>
      </a-empty>
      <a-table
        v-else
        class="kb-doc-pane__table"
        size="small"
        :data-source="documents"
        :columns="columns"
        :pagination="false"
        row-key="document_id"
      >
        <template #bodyCell="{ column, record }">
          <!-- 文档名 + 大小·类型（预览中并入名称单元格） -->
          <template v-if="column.key === 'name'">
            <div class="kb-doc-name">{{ record.name }}</div>
            <div class="kb-doc-name-sub">{{ formatSize(record.file_size) }} · {{ record.file_type || '—' }}</div>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">
              {{ record.status }}<template v-if="record.status === 'processing'">…</template>
            </a-tag>
          </template>
          <template v-else-if="column.key === 'op'">
            <a-space size="small">
              <a-button size="small" @click="openSegments(record)">{{ t('kbMgmt.segments') }}</a-button>
              <a-button size="small" @click="openFlow(record)">{{ t('kbMgmt.flow') }}</a-button>
              <a-tooltip :title="t('kbMgmt.retryTip')">
                <a-button size="small" :loading="retryingId === record.document_id" @click="onRetry(record)">
                  {{ t('kbMgmt.retry') }}
                </a-button>
              </a-tooltip>
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

    <!-- 处理流程抽屉：各步状态 + 失败步骤 + 错误信息 -->
    <DocumentFlowDrawer
      v-model:open="flowOpen"
      :record="flowDoc"
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { BookOutlined } from '@ant-design/icons-vue'
import {
  createQaRecords,
  deleteDocument,
  getDocumentStatus,
  importTableRecords,
  listDocuments,
  pipelineDryRun,
  previewTableRecords,
  rechunkKnowledge,
  retryDocument,
  retrieve,
  uploadDocument,
  type KbDocument,
  type RetrieveResult,
} from '@/api/kb'
import DocumentFlowDrawer from './DocumentFlowDrawer.vue'
import SegmentDetail from './SegmentDetail.vue'
import TableRecordList from './TableRecordList.vue'
import QaRecordList from './QaRecordList.vue'

const props = defineProps<{
  knowledgeId: number
  kbFormat?: string | null
  /** 知识库名称：用于面板头展示（由 KnowledgeBaseManager 传入） */
  knowledgeName?: string
}>()
const { t } = useI18n()

const collection = computed(() => `kb_${props.knowledgeId}`)
const formatMode = ref<'document' | 'table' | 'qa' | 'pipeline'>('document')

/** 知识库二级形态 → 允许显示的形态 tab（一一对应）；管线调试（dry-run）作为调试入口对所有形态保留 */
const FORMAT_TABS: Record<string, ('document' | 'table' | 'qa')[]> = {
  document: ['document'],
  table: ['table'],
  qa: ['qa'],
}

const formatLabels = computed<Record<string, string>>(() => ({
  document: t('kbMgmt.fmtDocument'),
  table: t('kbMgmt.fmtTable'),
  qa: t('kbMgmt.fmtQa'),
  pipeline: t('kbMgmt.fmtPipeline'),
}))

/** 当前可见的形态 tab 列表（末位固定为管线调试） */
const visibleFormats = computed(() => {
  const fmt = String(props.kbFormat || 'document').trim() || 'document'
  return [...(FORMAT_TABS[fmt] ?? ['document']), 'pipeline'] as ('document' | 'table' | 'qa' | 'pipeline')[]
})

// 切换知识库（形态变化）后，若当前 tab 不在允许列表内则回落到首个允许的形态
watch(
  visibleFormats,
  (list) => {
    if (!list.includes(formatMode.value)) formatMode.value = list[0]
  },
  { immediate: true },
)

const documents = ref<KbDocument[]>([])
const uploading = ref(false)
const query = ref('')
const results = ref<RetrieveResult[]>([])
const indexMode = ref<string>('')
let pollTimer: number | null = null

const columns = computed(() => [
  { title: t('kbMgmt.colDocName'), dataIndex: 'name', key: 'name' },
  { title: t('kbMgmt.colStatus'), key: 'status', width: 110 },
  { title: t('kbMgmt.colChunks'), dataIndex: 'segment_count', width: 70 },
  { title: t('kbMgmt.colUpdated'), dataIndex: 'updated_at', width: 150 },
  { title: t('kbMgmt.colActions'), key: 'op', width: 220 },
])

/**
 * 统计卡：文档不分页（:pagination="false"），故这里的计数是全量而非当前页。
 * pending 与 processing 都归入「处理中」。
 */
const docStats = computed(() => {
  const list = documents.value || []
  const inFlight = (s: string) => s === 'processing' || s === 'pending'
  return {
    total: list.length,
    completed: list.filter((d: any) => d.status === 'completed').length,
    processing: list.filter((d: any) => inFlight(d.status)).length,
    failed: list.filter((d: any) => d.status === 'failed').length,
  }
})

/** 字节数格式化（名称单元格展示「大小 · 类型」） */
function formatSize(bytes: number | null | undefined): string {
  if (!bytes && bytes !== 0) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

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

// ── 处理流程抽屉 ──
const flowOpen = ref(false)
const flowDoc = ref<KbDocument>({} as KbDocument)

function openFlow(record: KbDocument) {
  flowDoc.value = record
  flowOpen.value = true
}

// ── 重试（重新执行 解析→清洗→切块→向量化）──
const retryingId = ref<string | null>(null)

async function onRetry(record: KbDocument) {
  retryingId.value = record.document_id
  try {
    await retryDocument(record.document_id)
    message.success(t('kbMgmt.retryStarted'))
    await loadDocs()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.retryFailed'))
  } finally {
    retryingId.value = null
  }
}

// ── 按当前切片方案重新分段（全库执行）──
const rechunking = ref(false)

async function runRechunk() {
  rechunking.value = true
  try {
    const res: any = await rechunkKnowledge(props.knowledgeId)
    message.success(`${t('kbMgmt.rechunkQueued')}：${res.queued ?? 0}`)
    if (res.skipped?.length) {
      message.warning(`${t('kbMgmt.rechunkSkipped')}：${res.skipped.length}`)
    }
    await loadDocs()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.rechunkFailed'))
  } finally {
    rechunking.value = false
  }
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
.kb-doc-pane__tabs {
  margin-bottom: 12px;
}
/* 列表标题行：标题靠左，上传文档等按钮靠右 */
/* 统计卡：文档数 / 已完成 / 处理中 / 失败 */
.kb-doc-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}
.kb-doc-stat {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--bg-secondary, #fff);
  transition: box-shadow 0.18s ease, transform 0.18s ease;
}
.kb-doc-stat:hover {
  box-shadow: 0 4px 12px rgba(16, 24, 40, 0.08);
  transform: translateY(-1px);
}
.kb-doc-stat__k {
  font-size: 11.5px;
  color: var(--fg-secondary);
}
.kb-doc-stat__v {
  margin-top: 2px;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
  color: var(--accent);
}
.kb-doc-stat__v--ok {
  color: var(--success, #52c41a);
}
.kb-doc-stat__v--err {
  color: var(--error, #ff4d4f);
}

/* 面板头：知识库名 + 副标题 + 操作区 */
.kb-doc-pane__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.kb-doc-pane__pane-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.kb-doc-pane__pane-icon {
  color: #52c41a;
}
.kb-doc-pane__pane-sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--fg-secondary);
}
/* 文档名称单元格 */
.kb-doc-name {
  font-weight: 500;
}
.kb-doc-name-sub {
  font-size: 11.5px;
  color: var(--fg-muted, #8f959e);
}

.kb-doc-pane__header {</new_string>
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.kb-doc-pane__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--fg);
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
