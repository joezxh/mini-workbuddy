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
        <!-- 表格形态的上传入口 + 「所属集合」下拉已收进 TableRecordList 的「已上传文件」tab，此处不重复 -->
        <a-upload
          v-if="formatMode !== 'table'"
          :before-upload="handleUpload"
          :show-upload-list="false"
        >
          <a-button type="primary" size="small" :loading="uploading">
            {{ t('kbMgmt.uploadDocument') }}
          </a-button>
        </a-upload>
      </a-space>
    </div>

    <!-- 顶部：文档形态 tab 菜单（按所选知识库二级形态显示，管线调试作为调试入口常驻）
         问答库的形态切换已合并进下方 3 个 Tab（问答条目/问答导入/测试），此处不再显示 -->
    <a-radio-group
      v-if="!isQaKb"
      v-model:value="formatMode"
      button-style="solid"
      size="small"
      class="kb-doc-pane__tabs"
    >
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

    <!-- 表格形态：上传 / 条目 / 测试三个 tab 由 TableRecordList 内部承载 -->
    <TableRecordList
      v-if="formatMode === 'table'"
      class="kb-doc-pane__panel"
      :knowledge-id="props.knowledgeId"
      :collection="collection"
    />

    <!-- Q&A 形态：「问答条目」列表 与「问答导入」手动录入以 Tab 切换（条目在前且默认激活） -->
    <a-tabs v-else-if="formatMode === 'qa'" v-model:activeKey="qaTab" class="kb-doc-pane__qa-tabs">
      <a-tab-pane key="list" :tab="t('kbMgmt.qaRecords')" force-render>
        <QaRecordList :collection="collection" />
      </a-tab-pane>
      <a-tab-pane key="import" :tab="t('kbMgmt.qaImport')">
        <a-alert class="kb-doc-pane__hint" type="info" :message="t('kbMgmt.qaHint')" show-icon />
        <a-textarea
          v-model:value="qaText"
          :rows="14"
          :auto-size="{ minRows: 14, maxRows: 24 }"
          :placeholder="t('kbMgmt.qaPlaceholder')"
        />
        <a-button class="kb-doc-pane__form" type="primary" :loading="qaImporting" @click="runQaImport">
          {{ t('kbMgmt.importQa') }}
        </a-button>
      </a-tab-pane>
      <!-- 测试：管线 dry-run + 检索测试（问答库形态下统一收在此 Tab） -->
      <a-tab-pane key="pipeline" :tab="formatLabels.pipeline">
        <a-card class="kb-doc-pane__test-card" :title="t('kbMgmt.pipelineDryRun')" size="small">
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

        <a-card class="kb-doc-pane__test-card" :title="t('kbMgmt.retrievalTest')" size="small">
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
      </a-tab-pane>
    </a-tabs>

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

    <!-- 检索测试（economy / high_quality 由后端自动路由）
         文档 / 表格 / 问答形态均不在此渲染（见 HIDE_TESTER_FORMATS），
         检索能力统一由知识库「检索」标签页 SearchTester 提供 -->
    <a-card
      v-if="!HIDE_TESTER_FORMATS.includes(formatMode)"
      class="kb-doc-pane__tester"
      :title="t('kbMgmt.retrievalTest')"
      size="small"
    >
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
  listDocuments,
  pipelineDryRun,
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

/** 这些形态不在面板内重复渲染检索测试（已由知识库「检索」标签页 SearchTester 提供） */
const HIDE_TESTER_FORMATS: Array<typeof formatMode.value> = ['document', 'table', 'qa']

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

/** 问答库：形态切换已合并进下方 3 个 Tab（问答条目 / 问答导入 / 测试），顶部形态栏不再显示 */
const isQaKb = computed(() => String(props.kbFormat || '').trim() === 'qa')

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

// ── Q&A 导入 ──
/** 默认范例：开箱即可点「导入问答」，或清空后按 问题|答案|标签 格式自行录入 */
const QA_SAMPLE = [
  '退款政策?|支持 7 天无理由退款，商品需保持完好并附带原包装',
  '如何查询物流?|在「我的订单」中点击「查看物流」即可实时跟踪|物流,售后',
  '发票怎么开?|订单完成后在订单详情页申请电子发票，1 个工作日内发送到预留邮箱|发票,财务',
  '会员有哪些权益?|会员可享全场包邮、专属折扣与优先客服响应|会员,权益',
].join('\n')

/** 默认激活「问答条目」：进入先看已有问答资产与批量导入入口 */
const qaTab = ref('list')
const qaText = ref(QA_SAMPLE)
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

onMounted(async () => {
  await loadDocs()
})
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

.kb-doc-pane__header {
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
/* 问答形态：Tab 容器替代原上下两栏，条目 Tab 内表格不再重复加外边距 */
.kb-doc-pane__qa-tabs {
  margin-top: 12px;
}
.kb-doc-pane__qa-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 0;
}
/* 测试 Tab 内两张卡片（管线 dry-run / 检索测试）间距 */
.kb-doc-pane__test-card {
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
