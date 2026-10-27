<template>
  <div class="ext-pane">
    <div class="ext-pane__head">
      <div>
        <h2 class="ext-pane__title">
          <LinkOutlined class="ext-pane__icon" />
          {{ props.knowledgeName || t('kbMgmt.externalKb') }}
        </h2>
        <div class="ext-pane__sub">
          {{ subtitle }}
        </div>
      </div>
      <a-space>
        <a-button :loading="syncing" @click="resyncAll">{{ t('kbExt.fullSync') }}</a-button>
        <a-button type="primary" @click="openWizard">
          <template #icon><PlusOutlined /></template>
          {{ t('kbExt.resync') }}
        </a-button>
      </a-space>
    </div>

    <div v-if="stats.total" class="ext-pane__stats">
      <div class="ext-stat">
        <div class="ext-stat__k">{{ t('kbExt.created') }}</div>
        <div class="ext-stat__v">{{ stats.total - stats.failed }}</div>
      </div>
      <div class="ext-stat">
        <div class="ext-stat__k">{{ t('kbExt.unchanged') }}</div>
        <div class="ext-stat__v ext-stat__v--muted">{{ stats.completed }}</div>
      </div>
      <div class="ext-stat">
        <div class="ext-stat__k">{{ t('kbExt.failed') }}</div>
        <div class="ext-stat__v ext-stat__v--err">{{ stats.failed }}</div>
      </div>
      <div class="ext-stat">
        <div class="ext-stat__k">{{ t('kbMgmt.segments') }}</div>
        <div class="ext-stat__v">{{ stats.segments }}</div>
      </div>
    </div>

    <a-spin v-if="loading" />
    <a-empty
      v-else-if="!items.length"
      :description="t('kbExt.emptyDesc')"
    >
      <a-button type="primary" @click="openWizard">{{ t('kbExt.importDocs') }}</a-button>
    </a-empty>
    <a-table
      v-else
      size="small"
      :data-source="items"
      :columns="columns"
      :pagination="false"
      :scroll="{ x: 1280 }"
      row-key="external_doc_id"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'platform'">
          <a-tag :color="platformColor(record.source_type)">
            {{ platformName(record.source_type) }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'segments'">
          <span v-if="record.segment_count != null">{{ record.segment_count }}</span>
          <span v-else class="ext-pane__muted">—</span>
        </template>
        <template v-else-if="column.key === 'size'">
          <span class="ext-pane__muted">{{ formatSize(record.file_size) }}</span>
        </template>
        <template v-else-if="column.key === 'created'">
          <span class="ext-pane__muted">{{ formatTime(record.created_at) }}</span>
        </template>
        <template v-else-if="column.key === 'updated'">
          <span class="ext-pane__muted">{{ formatTime(record.external_updated_at) }}</span>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ record.status || '-' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'op'">
          <a-space size="small">
            <!-- 全文回源需落地文档 uuid：未落地的记录无从校验归属，故置灰 -->
            <a-button size="small" :disabled="!record.document_uuid" @click="openContent(record)">
              {{ t('kbExt.viewContent') }}
            </a-button>
            <a-button size="small" :disabled="!record.document_uuid" @click="openSegments(record)">
              {{ t('kbMgmt.segments') }}
            </a-button>
            <a-button size="small" @click="reimportOne(record)">{{ t('kbExt.reimport') }}</a-button>
            <a-popconfirm :title="t('kbMgmt.confirmDeleteDoc')" @confirm="removeOne(record)">
              <a-button size="small" danger :loading="removingId === record.document_uuid">
                {{ t('common.delete') }}
              </a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 文档全文预览（服务端回源拉取，见 ExternalDocumentViewer） -->
    <ExternalDocumentViewer
      v-model:open="viewerOpen"
      :document-uuid="viewerDocUuid"
      :fallback-title="viewerTitle"
      :platform-label="viewerPlatform"
    />

    <!-- 分段详情（复用文档知识库的分段抽屉） -->
    <SegmentDetail v-model:open="segmentsOpen" :document-id="segmentsDocId" @changed="load" />

    <ExternalSourceWizard
      v-model:open="wizardOpen"
      :knowledge-id="knowledgeId"
      :preset-source-type="presetSourceType"
      :preset-node-ids="presetNodeIds"
      @imported="load"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { LinkOutlined, PlusOutlined } from '@ant-design/icons-vue'
import {
  getExternalConfig,
  importExternalDocuments,
  listExternalDocuments,
  listExternalProviders,
  type ExternalDocumentItem,
  type ExternalProvider,
} from '@/api/kbExternalSource'
import { deleteDocument } from '@/api/kb'
import ExternalDocumentViewer from './ExternalDocumentViewer.vue'
import ExternalSourceWizard from './ExternalSourceWizard.vue'
import SegmentDetail from './SegmentDetail.vue'

const props = defineProps<{ knowledgeId: number; knowledgeName?: string }>()

const { t } = useI18n()

const items = ref<ExternalDocumentItem[]>([])
const providers = ref<ExternalProvider[]>([])
const loading = ref(false)
const syncing = ref(false)
const wizardOpen = ref(false)
const presetSourceType = ref<string | undefined>(undefined)
const presetNodeIds = ref<string[] | undefined>(undefined)

// ── 全文预览抽屉 ──
const viewerOpen = ref(false)
const viewerDocUuid = ref<string | null>(null)
const viewerTitle = ref('')
const viewerPlatform = ref('')

const columns = computed(() => [
  { title: t('kbExt.colTitle'), dataIndex: 'title', key: 'title', width: 260, ellipsis: true },
  { title: t('kbExt.colPlatform'), key: 'platform', width: 110 },
  { title: t('kbExt.colSegments'), dataIndex: 'segment_count', key: 'segments', width: 80, align: 'right' },
  { title: t('kbExt.colSize'), dataIndex: 'file_size', key: 'size', width: 100 },
  { title: t('kbExt.colImported'), dataIndex: 'created_at', key: 'created', width: 160 },
  { title: t('kbExt.colUpdated'), dataIndex: 'external_updated_at', key: 'updated', width: 160 },
  { title: t('kbExt.colStatus'), key: 'status', width: 110 },
  { title: t('kbMgmt.colActions'), key: 'op', width: 300, fixed: 'right' as const },
])

const stats = computed(() => ({
  total: items.value.length,
  completed: items.value.filter((i) => i.status === 'completed').length,
  failed: items.value.filter((i) => i.status === 'failed').length,
  segments: items.value.reduce((s, i) => s + (i.segment_count || 0), 0),
}))

const subtitle = computed(() => {
  if (!items.value.length) return t('kbExt.emptyTitle')
  const types = [...new Set(items.value.map((i) => platformName(i.source_type)))]
  return `${types.join(' / ')} · ${t('kbExt.created')} ${items.value.length}`
})

function platformName(sourceType: string) {
  const p = providers.value.find((x) => x.source_type === sourceType)
  return p?.name || sourceType
}

const PLATFORM_COLORS: Record<string, string> = {
  feishu: 'blue',
  lark: 'blue',
  feishu_drive: 'cyan',
  lark_drive: 'cyan',
  dingtalk: 'geekblue',
  yuque: 'purple',
  wecom: 'green',
  notion: 'default',
  gitlab: 'orange',
  github: 'default',
  ima: 'magenta',
  rss: 'gold',
  confluence: 'blue',
  seafile: 'volcano',
  google_drive: 'lime',
  onedrive: 'blue',
  web_crawler: 'geekblue',
  slack: 'purple',
  imap: 'gold',
}
function platformColor(sourceType: string) {
  return PLATFORM_COLORS[sourceType] || 'default'
}

function statusColor(status: string | null) {
  if (status === 'completed') return 'green'
  if (status === 'failed') return 'red'
  if (status === 'processing' || status === 'pending') return 'blue'
  return 'default'
}

/** 字节数格式化（与文档知识库列表保持一致的口径） */
function formatSize(bytes: number | null | undefined): string {
  if (!bytes && bytes !== 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/**
 * 时间列统一格式：
 * - 本地时间戳形如 ``2026-10-27 10:00:00.123456``（后端 str(datetime)）
 * - 外部平台给的是各自原始格式（多为 ISO 8601）
 * 统一裁剪到「日期 + 时分」，避免列宽被毫秒与时区撑爆。
 */
function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  const s = String(value).replace('T', ' ').replace(/Z$/, '')
  return s.length >= 16 ? s.slice(0, 16) : s
}

async function load() {
  loading.value = true
  try {
    const res: any = await listExternalDocuments(props.knowledgeId)
    items.value = res?.items || res || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

async function loadProviders() {
  try {
    const res: any = await listExternalProviders()
    providers.value = res?.items || res || []
  } catch {
    providers.value = []
  }
}

async function openWizard() {
  // 平台由知识库自身绑定的外部类型决定（spec 知识库管理：每个外部库固定平台与凭据）
  try {
    const cfg: any = await getExternalConfig(props.knowledgeId)
    if (!cfg?.external_type) {
      message.warning(t('kbMgmt.externalTypeRequired'))
      return
    }
    if (!cfg?.has_credentials) {
      message.warning(t('kbExt.configureCredsFirst'))
      return
    }
    presetSourceType.value = cfg.external_type
  } catch {
    // 兜底：沿用已导入文档的平台
    presetSourceType.value = items.value[0]?.source_type || undefined
  }
  presetNodeIds.value = items.value.map((i) => i.external_doc_id)
  wizardOpen.value = true
}

function openContent(record: ExternalDocumentItem) {
  if (!record.document_uuid) return
  viewerDocUuid.value = record.document_uuid
  viewerTitle.value = record.title
  viewerPlatform.value = platformName(record.source_type)
  viewerOpen.value = true
}

// ── 分段详情抽屉 ──
const segmentsOpen = ref(false)
const segmentsDocId = ref<string | null>(null)

function openSegments(record: ExternalDocumentItem) {
  if (!record.document_uuid) return
  segmentsDocId.value = record.document_uuid
  segmentsOpen.value = true
}

// ── 删除（连带切片与向量，映射由后端列表过滤隐藏）──
const removingId = ref<string | null>(null)

async function removeOne(record: ExternalDocumentItem) {
  if (!record.document_uuid) return
  removingId.value = record.document_uuid
  try {
    await deleteDocument(record.document_uuid)
    message.success(t('kbExt.deleteOk'))
    await load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbExt.deleteFailed'))
  } finally {
    removingId.value = null
  }
}

/** 单篇重导入：沿用已保存凭据（不传 credentials），后端按映射覆盖 */
async function reimportOne(record: ExternalDocumentItem) {
  try {
    await importExternalDocuments({
      knowledge_id: props.knowledgeId,
      source_type: record.source_type,
      doc_refs: [{ doc_id: record.external_doc_id, title: record.title }],
    })
    message.success(t('kbExt.resultOk'))
    await load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbExt.importFailed'))
  }
}

/** 全量同步：把已导入的文档按平台分组重新导入（存在则覆盖） */
async function resyncAll() {
  if (!items.value.length) {
    openWizard()
    return
  }
  syncing.value = true
  try {
    const byType = new Map<string, { doc_id: string; title: string }[]>()
    for (const i of items.value) {
      const list = byType.get(i.source_type) || []
      list.push({ doc_id: i.external_doc_id, title: i.title })
      byType.set(i.source_type, list)
    }
    for (const [sourceType, docRefs] of byType) {
      await importExternalDocuments({
        knowledge_id: props.knowledgeId,
        source_type: sourceType,
        doc_refs: docRefs,
      })
    }
    message.success(t('kbExt.resultOk'))
    await load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbExt.importFailed'))
  } finally {
    syncing.value = false
  }
}

onMounted(() => {
  load()
  loadProviders()
})

watch(() => props.knowledgeId, () => {
  items.value = []
  load()
})
</script>

<style scoped>
.ext-pane__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.ext-pane__title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.ext-pane__icon {
  color: var(--accent);
}
.ext-pane__sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--fg-secondary);
}
.ext-pane__stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}
.ext-stat {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  /* 用皮肤令牌而非 #fff：--bg-secondary 并未在 tokens.css 中定义，
     深色皮肤下会回落成白底，与整体深色面板割裂 */
  background: var(--bg-subtle);
  transition: box-shadow 0.18s ease, transform 0.18s ease;
}
.ext-stat:hover {
  box-shadow: 0 4px 12px rgba(16, 24, 40, 0.08);
  transform: translateY(-1px);
}
.ext-stat__k {
  font-size: 11.5px;
  color: var(--fg-secondary);
}
.ext-stat__v {
  margin-top: 2px;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
  color: var(--accent);
}
.ext-stat__v--muted {
  color: var(--fg-secondary);
}
.ext-stat__v--err {
  color: var(--err);
}
.ext-pane__muted {
  color: var(--fg-muted);
}
</style>
