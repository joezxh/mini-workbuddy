<template>
  <div class="trl">
    <a-tabs v-model:activeKey="activeTab" size="small" class="trl__tabs">
      <!-- ① 已上传文件：列表 + 上传入口（仅本 tab 显示） -->
      <a-tab-pane key="files" :tab="t('kbMgmt.tableFilesUploaded')">
        <a-space class="trl__bar" wrap>
          <a-select
            v-model:value="tableCollectionId"
            allow-clear
            size="small"
            style="min-width: 190px"
            :placeholder="t('kbMgmt.tableCollectionPlaceholder')"
            :options="collectionOptions"
          />
          <a-upload
            :before-upload="handleImport"
            :show-upload-list="false"
            accept=".csv,.xlsx,.xls"
          >
            <a-button type="primary" size="small" :loading="importing">
              {{ t('kbMgmt.selectTableFile') }}
            </a-button>
          </a-upload>
          <span class="trl__tip">{{ t('kbMgmt.tableCollectionTip') }}</span>
        </a-space>

        <a-table
          size="small"
          :data-source="docs"
          :columns="fileColumns"
          :pagination="filePagination"
          :loading="fileLoading"
          row-key="document_id"
          :custom-row="fileRowProps"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="statusColor(record.status)">
                {{ record.status }}<template v-if="record.status === 'processing'">…</template>
              </a-tag>
            </template>
            <template v-else-if="column.key === 'op'">
              <a-space size="small">
                <a-button size="small" @click.stop="openFlow(record)">{{ t('kbMgmt.flow') }}</a-button>
                <a-tooltip :title="t('kbMgmt.retryTip')">
                  <a-button
                    size="small"
                    :loading="retryingId === record.document_id"
                    @click.stop="onRetry(record)"
                  >
                    {{ t('kbMgmt.retry') }}
                  </a-button>
                </a-tooltip>
                <a-popconfirm :title="t('kbMgmt.confirmDeleteDoc')" @confirm="removeFile(record)">
                  <a-button size="small" danger @click.stop>{{ t('common.delete') }}</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-tab-pane>

      <!-- ② 表格条目：按「当前文件」过滤（点文件自动切到本 tab） -->
      <a-tab-pane key="rows" :tab="t('kbMgmt.tableRecords')">
        <a-space class="trl__bar" wrap>
          <a-tag v-if="filterDocName" closable color="blue" @close="clearFileFilter">
            {{ t('kbMgmt.currentFile', { name: filterDocName }) }}
          </a-tag>
          <a-tag v-else>{{ t('kbMgmt.allFiles') }}</a-tag>
          <a-input-search
            v-model:value="keyword"
            style="width: 220px"
            allow-clear
            :placeholder="t('kbMgmt.searchRecords')"
            @search="onSearch"
          />
          <a-button :loading="loading" @click="load">{{ t('common.refresh') }}</a-button>
          <a-button type="primary" @click="startCreate">{{ t('kbMgmt.addRow') }}</a-button>
        </a-space>

        <a-alert
          v-if="!schemaFields.length"
          class="trl__hint"
          type="info"
          :message="t('kbMgmt.tableSchemaEmptyHint')"
          show-icon
        />

        <a-empty v-if="!rows.length && !loading" :description="t('kbMgmt.noRows')" />
        <a-table
          v-else
          size="small"
          :data-source="rows"
          :columns="columns"
          :pagination="pagination"
          :loading="loading"
          row-key="id"
          @change="onTableChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'op'">
              <a-space size="small">
                <a-button size="small" @click="startEdit(record)">{{ t('common.edit') }}</a-button>
                <a-popconfirm :title="t('kbMgmt.confirmDeleteRow')" @confirm="remove(record)">
                  <a-button size="small" danger>{{ t('common.delete') }}</a-button>
                </a-popconfirm>
              </a-space>
            </template>
            <template v-else-if="column.key.startsWith('m_')">
              {{ record.metadata?.[column.key.slice(2)] ?? '' }}
            </template>
          </template>
        </a-table>
      </a-tab-pane>

      <!-- ③ 测试：上半导入预校验（不落库），下半检索测试 -->
      <a-tab-pane key="test" :tab="t('kbMgmt.testTab')">
        <a-card size="small" :title="t('kbMgmt.importDryRun')" class="trl__card">
          <a-space wrap>
            <a-upload
              :before-upload="handlePreview"
              :show-upload-list="false"
              accept=".csv,.xlsx,.xls"
            >
              <a-button size="small" :loading="previewing">
                {{ t('kbMgmt.dryRunPickFile') }}
              </a-button>
            </a-upload>
            <span class="trl__tip">{{ t('kbMgmt.importDryRunHint') }}</span>
          </a-space>
          <a-alert
            v-if="previewError"
            class="trl__hint"
            type="error"
            :message="previewError"
            show-icon
          />
          <template v-if="preview">
            <a-descriptions size="small" :column="2" bordered class="trl__hint">
              <a-descriptions-item :label="t('kbMgmt.dryRunColumns')">
                {{ preview.columns.join('、') }}
              </a-descriptions-item>
              <a-descriptions-item :label="t('kbMgmt.dryRunEmbedFields')">
                {{ (preview.embed_fields || []).join('、') || '-' }}
              </a-descriptions-item>
            </a-descriptions>
            <a-table
              size="small"
              :data-source="preview.rows"
              :columns="previewColumns"
              :pagination="false"
              row-key="__i"
            />
          </template>
        </a-card>

        <a-card size="small" :title="t('kbMgmt.retrievalTest')" class="trl__card">
          <a-space wrap>
            <a-input-search
              v-model:value="query"
              style="width: 320px"
              allow-clear
              :placeholder="t('kbMgmt.searchPlaceholder')"
              enter-button
              @search="runRetrieve"
            />
            <a-tag v-if="indexMode">{{ indexMode }}</a-tag>
          </a-space>
          <a-list v-if="results.length" size="small" :data-source="results" class="trl__hits">
            <template #renderItem="{ item }">
              <a-list-item>
                <div class="trl__hit">
                  <div class="trl__hit-content">{{ item.content }}</div>
                  <div class="trl__hit-meta">
                    <a-tag color="blue">{{ t('kbMgmt.similarity') }} {{ item.score?.toFixed?.(3) ?? item.score }}</a-tag>
                    <span>{{ t('kbMgmt.sourceFile') }}：{{ fileNameOf(item.document_id) }}</span>
                  </div>
                </div>
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-else :description="t('kbMgmt.noHits')" />
        </a-card>
      </a-tab-pane>
    </a-tabs>

    <!-- 新增/编辑条目 -->
    <a-modal
      v-model:open="editorOpen"
      :title="editing ? t('kbMgmt.editRow') : t('kbMgmt.addRow')"
      @ok="submit"
      :confirm-loading="saving"
    >
      <a-alert
        class="trl__hint"
        type="info"
        :message="
          embedFields.length
            ? t('kbMgmt.embeddedColumnNamed', { col: embedFields.join('、') })
            : t('kbMgmt.embeddedColumnHint')
        "
        show-icon
      />
      <a-form layout="vertical">
        <a-form-item :label="embedFieldLabel" required>
          <a-input v-model:value="form.content" />
        </a-form-item>
        <a-form-item v-for="f in metaFields" :key="f.name" :label="f.name">
          <a-input-number
            v-if="f.type === 'number'"
            v-model:value="form.meta[f.name]"
            style="width: 100%"
          />
          <a-select
            v-else-if="f.type === 'boolean'"
            v-model:value="form.meta[f.name]"
            :options="boolOptions"
          />
          <a-input v-else v-model:value="form.meta[f.name]" />
        </a-form-item>
        <a-form-item v-if="!schemaFields.length && !metaFields.length" :label="t('kbMgmt.filterableField')">
          <a-input
            v-model:value="newField"
            :placeholder="t('kbMgmt.newFieldPlaceholder')"
            @press-enter="addField"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 处理流程抽屉（复用文档知识库组件） -->
    <DocumentFlowDrawer v-model:open="flowOpen" :record="flowDoc" @changed="loadDocs" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  createTableRecord,
  deleteDocument,
  deleteSegment,
  getCollectionSchema,
  importTableRecords,
  importTableRecordsToKnowledge,
  listCollectionSegments,
  listDocuments,
  listKnowledgeCollections,
  listKnowledgeSegments,
  previewTableRecords,
  retrieve,
  retrieveKnowledge,
  retryDocument,
  updateSegment,
  type KbCollectionItem,
  type KbSchemaField,
  type KbSegment,
  type RetrieveResult,
} from '@/api/kb'
import { tableImportErrorMessage } from './tableImportError'
import DocumentFlowDrawer from './DocumentFlowDrawer.vue'

const props = defineProps<{
  knowledgeId: number
  /** 默认集合名（kb_{kid}）；选中文件后按该文件所属集合取字段定义 */
  collection: string
}>()
const { t } = useI18n()

/** 非业务列：写入切片 metadata 的内部键，不应作为表格列展示 */
const RESERVED_META_KEYS = ['chunk_type', 'tenant_id', 'source', 'embed_field', 'embed_fields', 'filename', 'mime']

const activeTab = ref<'files' | 'rows' | 'test'>('files')

const loading = ref(false)
const fileLoading = ref(false)
const docs = ref<any[]>([])
/** 当前过滤的文件（null = 全部文件） */
const selectedDoc = ref<string | null>(null)
const rows = ref<KbSegment[]>([])
const keyword = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const schemaFields = ref<KbSchemaField[]>([])

const editorOpen = ref(false)
const saving = ref(false)
const editing = ref<KbSegment | null>(null)
const newField = ref('')
const form = ref<{ content: string; meta: Record<string, any> }>({ content: '', meta: {} })

const boolOptions = [
  { label: 'true', value: true },
  { label: 'false', value: false },
]

const fileColumns = [
  { title: t('kbMgmt.fileColumnName'), dataIndex: 'name', key: 'name' },
  { title: t('kbMgmt.fileColumnType'), dataIndex: 'file_type', key: 'file_type', width: 90 },
  { title: t('kbMgmt.fileColumnCount'), dataIndex: 'segment_count', key: 'segment_count', width: 100 },
  { title: t('common.status'), dataIndex: 'status', key: 'status', width: 110 },
  { title: t('kbMgmt.fileColumnTime'), dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: t('kbMgmt.common.actions'), key: 'op', width: 210 },
]

/** 文档状态色（与文档知识库一致） */
function statusColor(status: string) {
  return (
    { pending: 'default', processing: 'processing', completed: 'success', failed: 'error' }[
      status
    ] || 'default'
  )
}

const filePagination = computed(() => ({
  pageSize: 5,
  size: 'small',
  showSizeChanger: false,
  hideOnSinglePage: false,
  showTotal: (n: number) => t('kbMgmt.fileTotal', { count: n }),
}))

/** 选中文件所属集合（表格库可多集合，字段定义按文件关联集合取） */
const selectedDocCollection = computed(() => {
  if (!selectedDoc.value) return props.collection
  const doc = docs.value.find((d: any) => d.document_id === selectedDoc.value)
  return String(doc?.collection || '') || props.collection
})

const filterDocName = computed(() => {
  if (!selectedDoc.value) return ''
  return docs.value.find((d: any) => d.document_id === selectedDoc.value)?.name || ''
})

/** 向量化字段组合（1~N 个）：顺序即每段 CSV 行的列序 */
const embedFields = computed<string[]>(() =>
  schemaFields.value.filter((f) => f.embedding && f.enabled).map((f) => f.name),
)
const embedField = computed(() => embedFields.value[0] || '')
const embedFieldLabel = computed(() =>
  embedFields.value.length > 1
    ? embedFields.value.join('、')
    : embedField.value || t('kbMgmt.embeddedColumn'),
)

const metaFields = computed<KbSchemaField[]>(() => {
  const defined = schemaFields.value.filter((f) => f.enabled && !f.embedding)
  if (defined.length) return defined
  const keys = new Set<string>()
  for (const r of rows.value) {
    for (const k of Object.keys(r.metadata || {})) {
      if (!RESERVED_META_KEYS.includes(k)) keys.add(k)
    }
  }
  return [...keys].sort().map((name) => ({
    name, type: 'string', enabled: true, embedding: false, filterable: true,
  }))
})

const columns = computed(() => [
  { title: embedFieldLabel.value, dataIndex: 'content', key: 'content' },
  ...metaFields.value.map((f) => ({ title: f.name, key: `m_${f.name}` })),
  { title: t('kbMgmt.common.actions'), key: 'op', width: 130 },
])

const pagination = computed(() => ({
  current: page.value,
  pageSize: pageSize.value,
  total: total.value,
  size: 'small',
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100'],
  showTotal: (n: number) => t('kbMgmt.recordTotal', { count: n }),
}))

async function loadSchema(collection?: string) {
  const name = collection || selectedDocCollection.value || props.collection
  try {
    const res: any = await getCollectionSchema(name)
    schemaFields.value = (res?.fields || []) as KbSchemaField[]
  } catch {
    schemaFields.value = []
  }
}

async function loadDocs() {
  fileLoading.value = true
  try {
    const res: any = await listDocuments(props.knowledgeId)
    docs.value = res.items || res || []
  } finally {
    fileLoading.value = false
  }
}

async function load() {
  await loadSchema()
  loading.value = true
  try {
    const params = {
      document_id: selectedDoc.value || undefined,
      chunk_type: 'table_row',
      q: keyword.value.trim() || undefined,
      page: page.value,
      page_size: pageSize.value,
    }
    // 选中文件 → 按该文件所属集合取；未选中（全部文件）→ 跨该知识库全部集合聚合
    const res: any = selectedDoc.value
      ? await listCollectionSegments(selectedDocCollection.value, params)
      : await listKnowledgeSegments(props.knowledgeId, params)
    rows.value = res.items || []
    total.value = res.total ?? rows.value.length
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function reload() {
  await loadCollections()
  await loadDocs()
  await load()
}

/** 点击文件行 → 切到「表格条目」tab 并按该文件过滤（tab 切换替代原来的同页过滤） */
function fileRowProps(record: any) {
  return {
    style: { cursor: 'pointer' },
    onClick: () => {
      selectedDoc.value = record.document_id
      keyword.value = ''
      page.value = 1
      activeTab.value = 'rows'
      load()
    },
  }
}

function clearFileFilter() {
  selectedDoc.value = null
  page.value = 1
  load()
}

// ── 上传：可选「所属集合」，不指定则后端按文件自动新建集合 ──
const kbCollections = ref<KbCollectionItem[]>([])
const tableCollectionId = ref<number | undefined>(undefined)
const importing = ref(false)

const collectionOptions = computed(() => [
  { label: t('kbMgmt.tableCollectionAuto'), value: 0 },
  ...kbCollections.value.map((c) => ({
    label: c.field_count ? `${c.name}（${c.field_count}）` : c.name,
    value: c.id,
  })),
])

async function loadCollections() {
  try {
    const res: any = await listKnowledgeCollections(props.knowledgeId)
    kbCollections.value = res?.items || []
  } catch {
    kbCollections.value = []
  }
}

async function handleImport(file: File) {
  importing.value = true
  try {
    const cid = tableCollectionId.value || 0
    let res: any
    if (cid) {
      const target = kbCollections.value.find((c) => c.id === cid)
      if (!target) {
        message.error(t('kbMgmt.importFailed'))
        return false
      }
      res = await importTableRecords(target.name, file)
    } else {
      res = await importTableRecordsToKnowledge(props.knowledgeId, file, {})
    }
    message.success(t('kbMgmt.tableImported', { count: res.ingested ?? 0 }))
    if (res.schema_created) message.info(t('kbMgmt.tableSchemaAutoCreated'))
    await loadCollections()
    await loadDocs()
  } catch (e: any) {
    message.error(tableImportErrorMessage(e, t))
  } finally {
    importing.value = false
  }
  return false
}

// ── ③ 测试：导入预校验（不落库） ──
const previewing = ref(false)
const preview = ref<any>(null)
const previewError = ref('')

const previewColumns = computed(() => [
  ...(preview.value?.columns || []).map((c: string) => ({ title: c, dataIndex: c, key: c })),
])

async function handlePreview(file: File) {
  previewing.value = true
  previewError.value = ''
  preview.value = null
  try {
    const cid = tableCollectionId.value || 0
    const collName = cid
      ? kbCollections.value.find((c) => c.id === cid)?.name || props.collection
      : props.collection
    const res: any = await previewTableRecords(collName, file, 10)
    preview.value = {
      columns: res.columns || [],
      embed_fields: res.embed_fields || [],
      rows: (res.rows || []).map((r: any, i: number) => ({ ...r, __i: i })),
    }
  } catch (e: any) {
    previewError.value = tableImportErrorMessage(e, t)
  } finally {
    previewing.value = false
  }
  return false
}

// ── ③ 测试：检索测试 ──
const query = ref('')
const results = ref<RetrieveResult[]>([])
const indexMode = ref('')

function fileNameOf(documentId: string) {
  return docs.value.find((d: any) => d.document_id === documentId)?.name || documentId
}

async function runRetrieve() {
  if (!query.value.trim()) return
  try {
    // 未选中文件 → 跨该知识库全部集合检索；选中文件 → 只检索该文件所属集合
    const res: any = selectedDoc.value
      ? await retrieve(selectedDocCollection.value, { query: query.value })
      : await retrieveKnowledge(props.knowledgeId, { query: query.value })
    results.value = res.results || []
    indexMode.value = res.index_mode || ''
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.retrieveFailed'))
  }
}

// ── 处理流程抽屉 ──
const flowOpen = ref(false)
const flowDoc = ref<any>({})

function openFlow(record: any) {
  flowDoc.value = record
  flowOpen.value = true
}

// ── 重试 / 删除 ──
const retryingId = ref<string | null>(null)

async function onRetry(record: any) {
  retryingId.value = record.document_id
  try {
    await retryDocument(record.document_id)
    message.success(t('kbMgmt.retryStarted'))
    await loadDocs()
    await load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.retryFailed'))
  } finally {
    retryingId.value = null
  }
}

async function removeFile(record: any) {
  try {
    await deleteDocument(record.document_id)
    message.success(t('kbMgmt.common.deleted'))
    if (selectedDoc.value === record.document_id) selectedDoc.value = null
    await loadDocs()
    await load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.common.deleteFailed'))
  }
}

function onSearch() {
  page.value = 1
  load()
}

function onTableChange(pag: any) {
  page.value = pag.current ?? 1
  pageSize.value = pag.pageSize ?? 20
  load()
}

function addField() {
  const name = newField.value.trim()
  if (!name) return
  form.value.meta[name] = ''
  newField.value = ''
}

function startCreate() {
  editing.value = null
  const meta: Record<string, any> = {}
  for (const f of metaFields.value) meta[f.name] = f.type === 'boolean' ? undefined : ''
  form.value = { content: '', meta }
  editorOpen.value = true
}

function startEdit(row: KbSegment) {
  editing.value = row
  const meta: Record<string, any> = {}
  for (const f of metaFields.value) {
    const raw = (row.metadata || {})[f.name]
    meta[f.name] = raw === undefined || raw === null ? (f.type === 'boolean' ? undefined : '') : raw
  }
  form.value = { content: row.content || '', meta }
  editorOpen.value = true
}

async function submit() {
  const content = String(form.value.content ?? '').trim()
  if (!content) {
    message.warning(t('kbMgmt.contentRequired'))
    return
  }
  const metadata: Record<string, unknown> = { chunk_type: 'table_row' }
  for (const f of metaFields.value) {
    const raw = form.value.meta[f.name]
    metadata[f.name] = f.type === 'boolean' ? (raw === undefined ? '' : raw) : (raw ?? '')
  }

  saving.value = true
  try {
    if (editing.value) {
      await updateSegment(editing.value.id, { content, metadata })
    } else {
      await createTableRecord(selectedDocCollection.value, {
        document_id: selectedDoc.value || '',
        content,
        metadata,
      })
    }
    message.success(t('kbMgmt.saved'))
    editorOpen.value = false
    await loadDocs()
    await load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function remove(row: KbSegment) {
  try {
    await deleteSegment(row.id)
    message.success(t('kbMgmt.common.deleted'))
    await load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.common.deleteFailed'))
  }
}

onMounted(reload)
watch(() => props.knowledgeId, async () => {
  selectedDoc.value = null
  page.value = 1
  await reload()
})
</script>

<style scoped>
.trl {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.trl__bar {
  margin-bottom: 12px;
}
.trl__hint {
  margin-bottom: 12px;
}
.trl__card {
  margin-bottom: 12px;
}
.trl__tip {
  font-size: 12px;
  color: var(--fg-muted, #8f959e);
}
.trl__hit {
  width: 100%;
}
.trl__hit-content {
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.trl__hit-meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--fg-muted, #8f959e);
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
