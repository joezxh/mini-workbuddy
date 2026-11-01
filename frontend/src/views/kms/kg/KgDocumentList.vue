<template>
  <div class="kg-doc-list">
    <!-- 文档是图谱的唯一来源：显式说明「上传 ≠ 构建」 -->
    <div class="kg-alert">{{ t('kbMgmt.kg.docAlert') }}</div>

    <div class="kg-doc-list__toolbar">
      <a-upload
        :before-upload="onUpload"
        :show-upload-list="false"
        accept=".pdf,.docx,.doc,.md,.txt,.html"
      >
        <a-button type="primary" size="small">
          <template #icon><UploadOutlined /></template>
          {{ t('kbMgmt.kg.uploadDocument') }}
        </a-button>
      </a-upload>
      <a-button size="small" :loading="loading" @click="reload">{{ t('common.refresh') }}</a-button>
      <span class="kg-muted">{{ t('kbMgmt.kg.docHint') }}</span>
      <span class="kg-doc-list__spacer" />
      <span class="kg-muted">{{ t('kbMgmt.kg.totalCount', { count: docs.length }) }}</span>
    </div>

    <a-table
      :columns="columns"
      :data-source="docs"
      :loading="loading"
      row-key="document_id"
      size="small"
      :pagination="false"
      :scroll="{ x: 1100 }"
      :locale="{ emptyText: t('kbMgmt.kg.noDocuments') }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <div class="kg-doc-name">
            <span class="kg-doc-name__main" :title="record.name">{{ record.name }}</span>
            <span class="kg-muted">
              {{ (record.file_type || '').toUpperCase() || '—' }} · {{ formatSize(record.file_size) }}
            </span>
          </div>
        </template>
        <template v-else-if="column.key === 'status'">
          <span class="kg-status" :class="`kg-status--${record.status}`">{{ statusText(record.status) }}</span>
        </template>
        <template v-else-if="column.key === 'graph'">
          <div class="kg-graph-stage">
            <span class="kg-stage-tag" :class="`kg-stage-tag--${graphTone(record)}`">
              {{ graphToneText(record) }}
            </span>
            <span class="kg-muted kg-graph-stage__num">
              {{ t('kbMgmt.kg.stageStructure') }} {{ record.graph?.structure || 0 }}/{{ record.graph?.segments || 0 }}
              · {{ t('kbMgmt.kg.stageVector') }} {{ record.graph?.vector || 0 }}/{{ record.graph?.segments || 0 }}
            </span>
          </div>
        </template>
        <template v-else-if="column.key === 'updated_at'">
          <span class="kg-muted">{{ formatTime(record.updated_at || record.created_at) }}</span>
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-space :size="2">
            <a-button size="small" type="link" @click="openSegments(record)">
              {{ t('kbMgmt.kg.actionSegments') }}
            </a-button>
            <a-button size="small" type="link" @click="openFlow(record)">
              {{ t('kbMgmt.kg.actionFlow') }}
            </a-button>
            <a-button
              v-if="record.status === 'failed'"
              size="small"
              type="link"
              :title="t('kbMgmt.retryTip')"
              :loading="retrying === record.document_id"
              @click="onRetry(record)"
            >
              {{ t('kbMgmt.retry') }}
            </a-button>
            <a-button
              size="small"
              type="link"
              :loading="rebuilding === record.document_id"
              @click="onRebuild(record)"
            >
              {{ t('kbMgmt.kg.rebuildGraph') }}
            </a-button>
            <a-popconfirm :title="t('kbMgmt.kg.confirmDeleteDocument')" @confirm="onDelete(record)">
              <a-button size="small" type="link" danger>{{ t('common.delete') }}</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <div class="kg-note">{{ t('kbMgmt.kg.docFooterNote') }}</div>

    <!-- 分段流程抽屉：parse → clean → chunk → vectorize → graph_extract -->
    <a-drawer
      v-model:open="flowOpen"
      :title="t('kbMgmt.flowTitle')"
      width="440"
      placement="right"
    >
      <a-spin :spinning="flowLoading">
        <div v-if="flowDoc" class="kg-flow">
          <div class="kg-flow__meta">
            <span class="kg-doc-name__main">{{ flowDoc.name }}</span>
            <span class="kg-status" :class="`kg-status--${flowDoc.status}`">
              {{ statusText(flowDoc.status) }}
            </span>
            <span class="kg-muted">{{ t('kbMgmt.kg.segmentCount') }} {{ flowDoc.segment_count ?? 0 }}</span>
          </div>

          <ul class="kg-flow__steps">
            <li
              v-for="(step, idx) in flowSteps"
              :key="`${step.key}-${idx}`"
              class="kg-flow__step"
              :class="stepToneClass(step)"
            >
              <span class="kg-flow__dot" />
              <div class="kg-flow__body">
                <div class="kg-flow__name">
                  {{ step.label }}
                  <span class="kg-flow__badge">{{ step.toneText }}</span>
                </div>
                <div v-if="step.summary" class="kg-muted">{{ step.summary }}</div>
              </div>
            </li>
          </ul>

          <div v-if="flowError" class="kg-alert kg-alert--warn kg-flow__error">
            {{ flowError }}
          </div>
        </div>
        <div v-else-if="!flowLoading" class="kg-muted">{{ t('kbMgmt.flowNoDetail') }}</div>
      </a-spin>
    </a-drawer>

    <!-- 分段详情：复用 kb 模块的 SegmentDetail（零改动） -->
    <SegmentDetail v-model:open="segmentOpen" :document-id="segmentDocId" @changed="reload" />
  </div>
</template>

<script setup lang="ts">
/**
 * 图谱库文档面板：上传文档 + 两阶段图谱进度 + 单文档重抽 + 分段流程抽屉。
 *
 * 上传后由后端摄取管线在切片就绪时自动提交图谱构建（无需前端干预）；
 * 「重新抽取」用于抽取失败或需要刷新时按文档重建。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { UploadOutlined } from '@ant-design/icons-vue'
import * as kbApi from '@/api/kb'
import * as kgApi from '@/api/kg'
import SegmentDetail from '@/views/kms/kb/SegmentDetail.vue'

const props = defineProps<{ knowledgeId: number }>()

const { t } = useI18n()

const docs = ref<any[]>([])
const loading = ref(false)
const rebuilding = ref('')
const retrying = ref('')

const flowOpen = ref(false)
const flowLoading = ref(false)
const flowDoc = ref<any | null>(null)
const flow = ref<any | null>(null)
const flowError = ref('')

/** 分段抽屉：零改动复用既有 SegmentDetail */
const segmentOpen = ref(false)
const segmentDocId = ref<string | null>(null)

const columns = computed(() => [
  { title: t('kbMgmt.kg.docName'), key: 'name', width: 260, ellipsis: true },
  { title: t('kbMgmt.common.status'), key: 'status', width: 100 },
  { title: t('kbMgmt.kg.graphStage'), key: 'graph', width: 260 },
  { title: t('kbMgmt.kg.segmentCount'), dataIndex: 'segment_count', key: 'segment_count', width: 80 },
  { title: t('kbMgmt.kg.updatedAt'), key: 'updated_at', width: 150 },
  { title: t('kbMgmt.colActions'), key: 'actions', width: 300, fixed: 'right' },
])

/** 流程节点：固定序列 + 图谱抽取（图谱库特有） */
const STEP_KEYS = ['parse', 'clean', 'chunk', 'vectorize', 'graph_extract'] as const

const STEP_LABELS = computed<Record<string, string>>(() => ({
  parse: t('kbMgmt.flowParse'),
  clean: t('kbMgmt.flowClean'),
  chunk: t('kbMgmt.flowChunk'),
  vectorize: t('kbMgmt.flowVectorize'),
  graph_extract: 'graph_extract',
}))

const flowSteps = computed(() => {
  const steps: any[] = flow.value?.steps || []
  const failedStep = flow.value?.failed_step as string | undefined
  const items = STEP_KEYS.map((key) => {
    const raw = steps.find((s) => s?.step === key)
    let tone: 'ok' | 'warn' | 'err' | 'idle' = raw ? 'ok' : 'idle'
    if (failedStep === key) tone = 'err'
    else if (key === 'graph_extract') {
      // 图谱抽取不在摄取管线 meta 里，按文档两阶段状态推导
      const graph = flowDoc.value?.graph
      if (graph?.failed) tone = 'err'
      else if (graph?.segments && graph?.structure >= graph.segments) tone = 'ok'
      else if (graph?.structure) tone = 'warn'
      else tone = 'idle'
    }
    return {
      key,
      label: STEP_LABELS.value[key] || key,
      tone,
      toneText:
        tone === 'ok'
          ? t('kbMgmt.kg.stageExtracted')
          : tone === 'err'
            ? t('kbMgmt.kg.stageFailed')
            : tone === 'warn'
              ? t('kbMgmt.kg.stagePartial')
              : t('kbMgmt.kg.stageNotExtracted'),
      summary: summarize(stepSummarySource(key, raw)),
    }
  })
  return items
})

function stepSummarySource(key: string, raw: any) {
  if (key === 'graph_extract') {
    const graph = flowDoc.value?.graph
    if (!graph) return null
    return {
      [t('kbMgmt.kg.stageStructure')]: `${graph.structure || 0}/${graph.segments || 0}`,
      [t('kbMgmt.kg.stageVector')]: `${graph.vector || 0}/${graph.segments || 0}`,
      ...(graph.failed ? { [t('kbMgmt.kg.stageFailed')]: graph.failed } : {}),
    }
  }
  if (!raw) return null
  const { step: _step, ...rest } = raw
  return rest
}

/** 摘要：只保留标量，键名做本地化兜底（parser/chunker 等保留原样） */
function summarize(obj: Record<string, any> | null) {
  if (!obj) return ''
  const parts: string[] = []
  Object.entries(obj).forEach(([key, value]) => {
    if (value === null || value === undefined || typeof value === 'object') return
    const label = labelOf(key)
    parts.push(`${label} ${value}`)
  })
  return parts.slice(0, 4).join(' · ')
}

function labelOf(key: string) {
  const dict: Record<string, string> = {
    chunks: t('kbMgmt.flowChunks'),
    sections: t('kbMgmt.flowSections'),
    vectors: t('kbMgmt.flowVectors'),
    operators: t('kbMgmt.flowOperators'),
  }
  return dict[key] || key
}

function stepToneClass(step: { tone: string }) {
  return `kg-flow__step--${step.tone}`
}

function statusText(status?: string) {
  if (status === 'completed') return t('kbMgmt.statCompleted')
  if (status === 'failed') return t('kbMgmt.statFailed')
  return t('kbMgmt.statProcessing')
}

/** 图谱阶段三态：失败 > 已完成 > 部分/进行中 > 未抽取（与原型 tag 同口径） */
function graphTone(record: any): 'ok' | 'warn' | 'err' | 'idle' {
  const graph = record.graph
  if (!graph) return 'idle'
  if (graph.failed) return 'err'
  const total = Number(graph.segments || 0)
  const structure = Number(graph.structure || 0)
  const vector = Number(graph.vector || 0)
  if (total && structure >= total && vector >= total) return 'ok'
  if (structure || vector) return 'warn'
  return 'idle'
}

function graphToneText(record: any) {
  const tone = graphTone(record)
  if (tone === 'ok') return `✓ ${t('kbMgmt.kg.stageExtracted')}`
  if (tone === 'err') return t('kbMgmt.kg.stageFailed')
  if (tone === 'warn') return `◐ ${t('kbMgmt.kg.stagePartial')}`
  return `— ${t('kbMgmt.kg.stageNotExtracted')}`
}

function formatSize(size?: number) {
  const value = Number(size || 0)
  if (!value) return '—'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function formatTime(value?: string) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function reloadQuiet() {
  const res = await kbApi.listDocuments(props.knowledgeId)
  docs.value = (res as any)?.data || (res as any) || []
}

async function reload() {
  loading.value = true
  try {
    await reloadQuiet()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.loadFailed'))
    docs.value = []
  } finally {
    loading.value = false
  }
}

let pollTimer: ReturnType<typeof setTimeout> | null = null

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

/**
 * 后台任务（重抽/重试/上传）期间短轮询：阶段进度自动出现，
 * 避免用户提交后看到自己那行「未抽取」而误以为没生效。
 * 静默刷新（不动表格 loading 遮罩），轮询结束后仍可手动刷新。
 */
function pollProgress(times = 6, interval = 5000) {
  stopPolling()
  let left = times
  const tick = async () => {
    if (left <= 0) {
      pollTimer = null
      return
    }
    left -= 1
    try {
      await reloadQuiet()
    } catch {
      // 单次轮询失败不打断：下次 tick 继续
    }
    pollTimer = setTimeout(tick, interval)
  }
  pollTimer = setTimeout(tick, interval)
}

onUnmounted(stopPolling)

async function openFlow(record: any) {
  flowDoc.value = record
  flow.value = null
  flowError.value = ''
  flowOpen.value = true
  flowLoading.value = true
  try {
    flow.value = await kbApi.getDocumentFlow(record.document_id)
    flowError.value = flow.value?.error_detail || ''
  } catch (e: any) {
    flowError.value = e?.response?.data?.detail || t('kbMgmt.flowLoadFailed')
  } finally {
    flowLoading.value = false
  }
}

function openSegments(record: any) {
  segmentDocId.value = record.document_id
  segmentOpen.value = true
}

async function onUpload(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  try {
    await kbApi.uploadDocument(props.knowledgeId, fd)
    message.success(t('kbMgmt.kg.docUploaded'))
    await reload()
    pollProgress()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.uploadFailed'))
  }
  return false
}

async function onRebuild(record: any) {
  rebuilding.value = record.document_id
  try {
    await kgApi.rebuildDocumentGraph(props.knowledgeId, record.document_id)
    message.success(t('kbMgmt.kg.rebuildSubmitted'))
    await reload()
    // 仅重抽本行：其他文档的阶段标志不受影响（后端已改成单文档撤销）
    pollProgress()
  } catch (e: any) {
    // 后端前置校验（无切片/无留存原文件）会带可执行提示：直接透传
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.actionFailed'))
  } finally {
    rebuilding.value = ''
  }
}

/** 摄取失败（无切片）的文档：图谱无从抽取，先重跑整条解析→切块→向量化 */
async function onRetry(record: any) {
  retrying.value = record.document_id
  try {
    await kbApi.retryDocument(record.document_id)
    message.success(t('kbMgmt.retryStarted'))
    await reload()
    // 重试＝整条管线重跑，成功后图谱库会自动提交抽取：多轮询几轮
    pollProgress(12, 5000)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.retryFailed'))
  } finally {
    retrying.value = ''
  }
}

async function onDelete(record: any) {
  try {
    await kbApi.deleteDocument(record.document_id)
    message.success(t('kbMgmt.kg.deleted'))
    await reload()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.actionFailed'))
  }
}

onMounted(reload)
</script>

<style scoped>
.kg-doc-list__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.kg-doc-list__spacer {
  flex: 1;
}
.kg-doc-name {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.kg-doc-name__main {
  overflow: hidden;
  color: var(--kg-text);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kg-graph-stage {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.kg-graph-stage__num {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
/* 图谱阶段标签：✓ 已抽取 / ◐ 部分完成 / — 未抽取 / ✕ 失败 */
.kg-stage-tag {
  display: inline-flex;
  align-items: center;
  height: 19px;
  padding: 0 6px;
  border: 1px solid var(--kg-border);
  border-radius: var(--kg-r-xs);
  background: var(--kg-subtle);
  color: var(--kg-text-3);
  font-size: 11px;
  line-height: 1;
  white-space: nowrap;
}
.kg-stage-tag--ok {
  border-color: var(--kg-ok-border);
  background: var(--kg-ok-bg);
  color: var(--kg-ok-fg);
}
.kg-stage-tag--warn {
  border-color: var(--kg-warn-border);
  background: var(--kg-warn-bg);
  color: var(--kg-warn-fg);
}
.kg-stage-tag--err {
  border-color: var(--kg-err-border);
  background: var(--kg-err-bg);
  color: var(--kg-err-fg);
}
/* 摄取状态：与关系表同款小胶囊 */
.kg-status {
  display: inline-flex;
  align-items: center;
  height: 19px;
  padding: 0 6px;
  border: 1px solid var(--kg-border);
  border-radius: var(--kg-r-xs);
  background: var(--kg-subtle);
  color: var(--kg-text-2);
  font-size: 11px;
  line-height: 1;
}
.kg-status--completed {
  border-color: var(--kg-ok-border);
  background: var(--kg-ok-bg);
  color: var(--kg-ok-fg);
}
.kg-status--failed {
  border-color: var(--kg-err-border);
  background: var(--kg-err-bg);
  color: var(--kg-err-fg);
}
.kg-status--processing,
.kg-status--pending {
  border-color: var(--kg-warn-border);
  background: var(--kg-warn-bg);
  color: var(--kg-warn-fg);
}

/* 流程抽屉 */
.kg-flow__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--kg-border);
}
.kg-flow__steps {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}
.kg-flow__step {
  position: relative;
  display: flex;
  gap: 10px;
  padding: 0 0 14px 4px;
}
.kg-flow__step::before {
  content: '';
  position: absolute;
  top: 14px;
  bottom: 0;
  left: 7px;
  width: 1px;
  background: var(--kg-border);
}
.kg-flow__step:last-child::before {
  display: none;
}
.kg-flow__dot {
  width: 7px;
  height: 7px;
  margin-top: 6px;
  flex: none;
  border-radius: 50%;
  background: var(--kg-border);
}
.kg-flow__step--ok .kg-flow__dot {
  background: var(--kg-ok);
}
.kg-flow__step--warn .kg-flow__dot {
  background: var(--kg-warn);
}
.kg-flow__step--err .kg-flow__dot {
  background: var(--kg-err);
}
.kg-flow__body {
  min-width: 0;
}
.kg-flow__name {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--kg-text);
  font-size: 12.5px;
}
.kg-flow__badge {
  padding: 0 6px;
  border-radius: var(--kg-r-xs);
  background: var(--kg-subtle);
  color: var(--kg-text-3);
  font-size: 10.5px;
}
.kg-flow__step--ok .kg-flow__badge {
  background: var(--kg-ok-bg);
  color: var(--kg-ok-fg);
}
.kg-flow__step--warn .kg-flow__badge {
  background: var(--kg-warn-bg);
  color: var(--kg-warn-fg);
}
.kg-flow__step--err .kg-flow__badge {
  background: var(--kg-err-bg);
  color: var(--kg-err-fg);
}
.kg-flow__error {
  margin-top: 10px;
  margin-bottom: 0;
}
</style>
