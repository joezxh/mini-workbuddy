<template>
  <div class="ext-pane">
    <div class="ext-pane__head">
      <div>
        <h2 class="ext-pane__title">
          <LinkOutlined class="ext-pane__icon" />
          {{ t('kbMgmt.externalKb') }}
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
      row-key="external_doc_id"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'platform'">
          <a-tag :color="platformColor(record.source_type)">
            {{ platformName(record.source_type) }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ record.status || '-' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'op'">
          <a-space size="small">
            <a-button size="small" :disabled="!record.url" @click="openSource(record)">
              {{ t('kbExt.viewSource') }}
            </a-button>
            <a-button size="small" @click="reimportOne(record)">{{ t('kbExt.reimport') }}</a-button>
          </a-space>
        </template>
      </template>
    </a-table>

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
  importExternalDocuments,
  listExternalDocuments,
  listExternalProviders,
  type ExternalDocumentItem,
  type ExternalProvider,
} from '@/api/kbExternalSource'
import ExternalSourceWizard from './ExternalSourceWizard.vue'

const props = defineProps<{ knowledgeId: number }>()

const { t } = useI18n()

const items = ref<ExternalDocumentItem[]>([])
const providers = ref<ExternalProvider[]>([])
const loading = ref(false)
const syncing = ref(false)
const wizardOpen = ref(false)
const presetSourceType = ref<string | undefined>(undefined)
const presetNodeIds = ref<string[] | undefined>(undefined)

const columns = [
  { title: t('kbExt.colTitle'), dataIndex: 'title', key: 'title', width: '38%' },
  { title: t('kbExt.colPlatform'), key: 'platform', width: '16%' },
  { title: t('kbExt.colUpdated'), dataIndex: 'external_updated_at', key: 'updated', width: '15%' },
  { title: t('kbExt.colStatus'), key: 'status', width: '13%' },
  { title: '', key: 'op' },
]

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
  dingtalk: 'cyan',
  yuque: 'purple',
  wecom: 'green',
  notion: 'default',
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

function openWizard() {
  // 预填平台与已选节点，使「重新选择文档」落在同一平台上
  presetSourceType.value = items.value[0]?.source_type || undefined
  presetNodeIds.value = items.value.map((i) => i.external_doc_id)
  wizardOpen.value = true
}

function openSource(record: ExternalDocumentItem) {
  const node = items.value.find((i) => i.external_doc_id === record.external_doc_id)
  void node
  message.info(t('kbExt.viewSource'))
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
  background: var(--bg-secondary, #fff);
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
  color: var(--error, #ff4d4f);
}
</style>
