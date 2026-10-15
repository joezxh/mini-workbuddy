<template>
  <a-modal
    :open="open"
    :width="880"
    :mask-closable="false"
    @cancel="close"
  >
    <template #title>
      <div>
        <div class="extw__modal-title">{{ t('kbExt.title') }}</div>
        <div v-if="currentProviderName" class="extw__modal-sub">{{ currentProviderName }}</div>
      </div>
    </template>
    <template #footer>
      <div class="extw__foot">
        <span class="extw__hint">{{ footHint }}</span>
        <a-space>
          <a-button @click="close">{{ t('common.cancel') }}</a-button>
          <a-button v-if="step > 0 && step < 4" @click="prev">{{ t('kbExt.prev') }}</a-button>
          <a-button
            v-if="step < 3"
            type="primary"
            :disabled="!canNext"
            @click="next"
          >{{ t('kbExt.next') }}</a-button>
          <a-button
            v-if="step === 3"
            type="primary"
            :loading="importing"
            :disabled="!selected.length"
            @click="doImport"
          >{{ t('kbExt.startImport') }}</a-button>
          <a-button v-if="step === 4" type="primary" @click="close">{{ t('kbExt.done') }}</a-button>
        </a-space>
      </div>
    </template>

    <a-steps :current="step" size="small" class="extw__steps">
      <a-step :title="t('kbExt.step1')" :disabled="false" @click="go(0)" />
      <a-step :title="t('kbExt.step2')" :disabled="!sourceType" @click="go(1)" />
      <a-step :title="t('kbExt.step3')" :disabled="!tested" @click="go(2)" />
      <a-step :title="t('kbExt.step4')" :disabled="!selected.length" @click="go(3)" />
      <a-step :title="t('kbExt.step5')" :disabled="step < 4" />
    </a-steps>

    <!-- 步骤 1：选择平台 -->
    <div v-if="step === 0" class="extw__pane">
      <div class="extw__sec-title">{{ t('kbExt.pickPlatform') }}</div>
      <div class="extw__desc">{{ t('kbExt.pickPlatformDesc') }}</div>
      <a-spin v-if="providersLoading" />
      <div v-else class="extw__grid">
        <div
          v-for="p in providers"
          :key="p.source_type"
          class="extw__card"
          :class="{ 'extw__card--on': sourceType === p.source_type }"
          @click="pickProvider(p.source_type)"
        >
          <div class="extw__card-logo" :style="{ background: platformColor(p.source_type) }">
            {{ p.name.slice(0, 1) }}
          </div>
          <div class="extw__card-name">{{ p.name }}</div>
          <div class="extw__card-desc">{{ p.desc }}</div>
        </div>
      </div>
    </div>

    <!-- 步骤 2：配置凭据 + 测试连通 -->
    <div v-else-if="step === 1" class="extw__pane">
      <div class="extw__sec-title">{{ t('kbExt.credentials') }}</div>
      <div class="extw__desc">{{ t('kbExt.credentialsDesc') }}</div>
      <a-form layout="vertical">
        <a-form-item
          v-for="f in currentFields"
          :key="f.name"
          :label="f.label"
          :required="f.required"
        >
          <a-input-password
            v-if="f.secret"
            v-model:value="credentials[f.name]"
            :placeholder="f.placeholder"
          />
          <a-input v-else v-model:value="credentials[f.name]" :placeholder="f.placeholder" />
          <div v-if="f.hint" class="extw__hint-block">{{ f.hint }}</div>
        </a-form-item>
      </a-form>
      <a-space>
        <a-button type="primary" :loading="testing" @click="doTest">
          {{ t('kbExt.testConnection') }}
        </a-button>
        <span class="extw__tip">{{ t('kbExt.tokenTip') }}</span>
      </a-space>
      <a-alert
        v-if="testResult"
        class="extw__mt"
        :type="testResult.ok ? 'success' : 'error'"
        :message="testResult.ok ? t('kbExt.testOk') : t('kbExt.testFail')"
        :description="testResult.ok ? testResult.identity : testResult.message"
        show-icon
      />
    </div>

    <!-- 步骤 3：选择文档 -->
    <div v-else-if="step === 2" class="extw__pane">
      <div class="extw__sec-title">{{ t('kbExt.pickDocs') }}</div>
      <div class="extw__desc">{{ t('kbExt.pickDocsDesc') }}</div>
      <div class="extw__browse">
        <div class="extw__tree-box">
          <div class="extw__tree-head">
            <span class="extw__tree-label">{{ t('kbExt.step3') }}</span>
            <a-checkbox
              :checked="allSelected"
              :indeterminate="someSelected"
              @change="(e: any) => selectAllLoaded(e.target.checked)"
            >{{ t('kbExt.selectAll') }}</a-checkbox>
          </div>
          <a-spin v-if="treeLoading" />
          <a-empty v-else-if="!treeData.length" :description="t('common.noData')" />
          <a-tree
            v-else
            v-model:checkedKeys="checkedKeys"
            :tree-data="treeData"
            :load-data="onLoadData"
            checkable
            check-strictly
            :selectable="false"
          />
        </div>
        <div class="extw__sel-box">
          <div class="extw__sel-head">
            <span>{{ t('kbExt.selectedList') }}</span>
            <span class="extw__sel-count">{{ selected.length }} {{ t('kbExt.unit') }}</span>
          </div>
          <div v-if="!selected.length" class="extw__sel-empty">
            {{ t('kbExt.selectedEmpty') }}
          </div>
          <div v-for="s in selected" :key="s.doc_id" class="extw__sel-item">
            <span class="extw__sel-name">{{ s.title }}</span>
            <a class="extw__sel-rm" @click="removeSelected(s.doc_id)">×</a>
          </div>
        </div>
      </div>
    </div>

    <!-- 步骤 4：切片方案 -->
    <div v-else-if="step === 3" class="extw__pane">
      <div class="extw__sec-title">{{ t('kbExt.chunker') }}</div>
      <div class="extw__desc">{{ t('kbExt.chunkerDesc') }}</div>
      <a-form-item :label="t('kbMgmt.chunkerType')">
        <a-select
          v-model:value="chunkerType"
          style="max-width: 320px"
          :options="chunkerOptions"
          :loading="chunkersLoading"
          @change="onChunkerChange"
        />
      </a-form-item>
      <div v-for="f in chunkerFields" :key="f.name" class="extw__param">
        <span class="extw__param-label">{{ f.name }}</span>
        <a-switch v-if="f.type === 'boolean'" v-model:checked="chunkerParams[f.name]" size="small" />
        <a-input-number
          v-else-if="f.type === 'integer'"
          v-model:value="chunkerParams[f.name]"
          size="small"
          :min="0"
          style="width: 132px"
        />
        <a-input v-else v-model:value="chunkerParams[f.name]" size="small" style="width: 210px" />
      </div>
      <a-alert class="extw__mt" type="info" :message="t('kbMgmt.chunkerHint')" show-icon />
    </div>

    <!-- 步骤 5：导入结果 -->
    <div v-else class="extw__pane">
      <a-result
        :status="summary && summary.failed ? 'warning' : 'success'"
        :title="summary && summary.failed ? t('kbExt.resultPartial') : t('kbExt.resultOk')"
      >
        <template #extra>
          <a-descriptions :column="4" size="small" bordered class="extw__mt">
            <a-descriptions-item :label="t('kbExt.created')">
              {{ summary?.created ?? 0 }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('kbExt.updated')">
              {{ summary?.updated ?? 0 }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('kbExt.unchanged')">
              {{ summary?.unchanged ?? 0 }}
            </a-descriptions-item>
            <a-descriptions-item :label="t('kbExt.failed')">
              {{ summary?.failed ?? 0 }}
            </a-descriptions-item>
          </a-descriptions>
        </template>
      </a-result>
      <a-table
        v-if="summary?.items?.length"
        size="small"
        :data-source="summary.items"
        :columns="resultColumns"
        :pagination="false"
        row-key="external_doc_id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <a-tag :color="actionColor(record.action)">{{ actionLabel(record.action) }}</a-tag>
          </template>
        </template>
      </a-table>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  importExternalDocuments,
  listExternalNodes,
  listExternalProviders,
  testExternalSource,
  type ExternalNode,
  type ExternalProvider,
  type ImportSummary,
} from '@/api/kbExternalSource'
import { listChunkers } from '@/api/kb'

const props = defineProps<{
  open: boolean
  knowledgeId: number
  presetSourceType?: string
  presetNodeIds?: string[]
}>()
const emit = defineEmits<{ 'update:open': [boolean]; imported: [] }>()

const { t } = useI18n()

const step = ref(0)
const providers = ref<ExternalProvider[]>([])
const providersLoading = ref(false)
const sourceType = ref<string>('')
const credentials = ref<Record<string, any>>({})
const testing = ref(false)
const tested = ref(false)
const testResult = ref<{ ok: boolean; message: string; identity: string } | null>(null)

const treeData = ref<any[]>([])
const treeLoading = ref(false)
const checkedKeys = ref<string[]>([])
const nodeMap = new Map<string, ExternalNode>()

const chunkers = ref<any[]>([])
const chunkersLoading = ref(false)
const chunkerType = ref('approx_token')
const chunkerParams = ref<Record<string, any>>({})

const importing = ref(false)
const summary = ref<ImportSummary | null>(null)

const currentFields = computed(() => {
  const p = providers.value.find((x) => x.source_type === sourceType.value)
  return p?.credential_fields ?? []
})

const currentProviderName = computed(
  () => providers.value.find((p) => p.source_type === sourceType.value)?.name || '',
)

/** 平台品牌色（与预览一致：飞书蓝 / 钉钉青 / 语雀紫 / 企微绿 / Notion 灰） */
const PLATFORM_COLORS: Record<string, string> = {
  feishu: '#1a5fd6',
  dingtalk: '#0b7ac4',
  yuque: '#6b3fd4',
  wecom: '#12874a',
  notion: '#333333',
}
function platformColor(sourceType: string) {
  return PLATFORM_COLORS[sourceType] || 'var(--accent)'
}

/** 递归收集当前已加载树中的文档节点 key（用于「全选本层」） */
function collectDocKeys(nodes: any[], out: string[] = []): string[] {
  for (const n of nodes || []) {
    if (n.node_type === 'doc') out.push(n.key)
    if (n.children && n.children.length) collectDocKeys(n.children, out)
  }
  return out
}

const loadedDocKeys = computed(() => collectDocKeys(treeData.value))
const allSelected = computed(
  () => loadedDocKeys.value.length > 0 && loadedDocKeys.value.every((k) => checkedKeys.value.includes(k)),
)
const someSelected = computed(
  () => !allSelected.value && loadedDocKeys.value.some((k) => checkedKeys.value.includes(k)),
)

function selectAllLoaded(checked: boolean) {
  const keys = new Set(loadedDocKeys.value)
  checkedKeys.value = checked
    ? [...new Set([...checkedKeys.value, ...keys])]
    : checkedKeys.value.filter((k) => !keys.has(k))
}

const selected = computed<ExternalNode[]>(() =>
  checkedKeys.value
    .map((k) => nodeMap.get(k))
    .filter((n): n is ExternalNode => !!n && n.node_type === 'doc'),
)

const canNext = computed(() => {
  if (step.value === 0) return !!sourceType.value
  if (step.value === 1) return tested.value
  if (step.value === 2) return selected.value.length > 0
  return true
})

const footHint = computed(() => {
  if (step.value === 1 && !tested.value) return t('kbExt.needTest')
  if (step.value === 2 && !selected.value.length) return t('kbExt.needSelect')
  return ''
})

const chunkerOptions = computed(() =>
  chunkers.value.map((c) => ({ label: c.label || c.chunker_type, value: c.chunker_type })),
)

const chunkerFields = computed(() => {
  const hit = chunkers.value.find((c) => c.chunker_type === chunkerType.value)
  const propsSchema = hit?.parameters_schema?.properties || {}
  return Object.keys(propsSchema).map((name) => ({
    name,
    type: propsSchema[name]?.type || 'string',
    default: propsSchema[name]?.default,
  }))
})

const resultColumns = [
  { title: '文档', dataIndex: 'title', key: 'title' },
  { title: '动作', key: 'action', width: 110 },
  { title: '说明', dataIndex: 'detail', key: 'detail' },
]

function actionColor(action: string) {
  return { created: 'green', updated: 'blue', unchanged: 'default', failed: 'red' }[action] || 'default'
}
function actionLabel(action: string) {
  return { created: t('kbExt.created'), updated: t('kbExt.updated'), unchanged: t('kbExt.unchanged'), failed: t('kbExt.failed') }[action] || action
}

async function loadProviders() {
  providersLoading.value = true
  try {
    const res: any = await listExternalProviders()
    providers.value = res?.items || res || []
  } finally {
    providersLoading.value = false
  }
}

async function loadChunkers() {
  chunkersLoading.value = true
  try {
    const res: any = await listChunkers()
    chunkers.value = res || []
    if (chunkers.value.length && !chunkerType.value) {
      chunkerType.value = chunkers.value[0].chunker_type
    }
    onChunkerChange()
  } finally {
    chunkersLoading.value = false
  }
}

function onChunkerChange() {
  const next: Record<string, any> = {}
  for (const f of chunkerFields.value) next[f.name] = f.default
  chunkerParams.value = next
}

function pickProvider(st: string) {
  if (sourceType.value === st) return
  sourceType.value = st
  credentials.value = {}
  tested.value = false
  testResult.value = null
  treeData.value = []
  checkedKeys.value = []
  nodeMap.clear()
}

async function doTest() {
  const missing = currentFields.value.filter((f) => f.required && !credentials.value[f.name])
  if (missing.length) {
    message.warning(t('kbExt.missingCred', { name: missing[0].label }))
    return
  }
  testing.value = true
  try {
    const res: any = await testExternalSource(sourceType.value, credentials.value)
    testResult.value = res
    tested.value = !!res?.ok
  } catch (e: any) {
    tested.value = false
    testResult.value = {
      ok: false,
      message: e?.response?.data?.detail || t('kbExt.testFail'),
      identity: '',
    }
  } finally {
    testing.value = false
  }
}

function toTreeNode(n: ExternalNode): any {
  nodeMap.set(n.doc_id, n)
  return {
    key: n.doc_id,
    title: n.title,
    isLeaf: n.node_type === 'doc',
    node_type: n.node_type,
    children: [],
  }
}

async function loadNodes(parentId?: string | null) {
  treeLoading.value = true
  try {
    const res: any = await listExternalNodes(sourceType.value, credentials.value, parentId)
    return (res?.items || res || []).map(toTreeNode)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbExt.loadNodesFailed'))
    return []
  } finally {
    treeLoading.value = false
  }
}

async function onLoadData(treeNode: any) {
  const children = await loadNodes(treeNode.key)
  treeNode.children = children
  treeData.value = [...treeData.value]
}

async function ensureTree() {
  if (treeData.value.length) return
  treeData.value = await loadNodes(null)
}

function removeSelected(docId: string) {
  checkedKeys.value = checkedKeys.value.filter((k) => k !== docId)
}

async function doImport() {
  importing.value = true
  try {
    const res: any = await importExternalDocuments({
      knowledge_id: props.knowledgeId,
      source_type: sourceType.value,
      doc_refs: selected.value.map((s) => ({ doc_id: s.doc_id, title: s.title })),
      credentials: Object.keys(credentials.value).length ? credentials.value : null,
      chunker_type: chunkerType.value,
      chunker_params: chunkerParams.value,
      save_credentials: true,
    })
    summary.value = res
    step.value = 4
    emit('imported')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbExt.importFailed'))
  } finally {
    importing.value = false
  }
}

function go(n: number) {
  if (n > 1 && !tested.value) return
  if (n > 2 && !selected.value.length) return
  step.value = n
}
function next() {
  if (step.value === 2) {
    step.value = 3
    if (!chunkers.value.length) loadChunkers()
    return
  }
  step.value += 1
}
function prev() {
  step.value -= 1
}
function close() {
  emit('update:open', false)
}

watch(
  () => props.open,
  async (open) => {
    if (!open) return
    step.value = 0
    summary.value = null
    if (!providers.value.length) await loadProviders()
    // 从「重新选择文档」进入：预填平台并直接进入文档浏览步骤
    if (props.presetSourceType) {
      sourceType.value = props.presetSourceType
      tested.value = true
      step.value = 2
      await ensureTree()
      if (props.presetNodeIds?.length) checkedKeys.value = [...props.presetNodeIds]
    }
  },
)
</script>

<style scoped>
.extw__steps {
  margin-bottom: 18px;
}
.extw__modal-title {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.3;
}
.extw__modal-sub {
  font-size: 12px;
  font-weight: 400;
  color: var(--fg-secondary);
}
.extw__tree-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0 2px 8px;
  margin-bottom: 6px;
  border-bottom: 1px solid var(--border);
}
.extw__tree-label {
  font-size: 11.5px;
  color: var(--fg-secondary);
}
.extw__pane {
  min-height: 260px;
}
.extw__sec-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 2px;
}
.extw__desc {
  font-size: 12px;
  color: var(--fg-secondary);
  margin-bottom: 12px;
}
.extw__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.extw__card {
  border: 1.5px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.18s ease;
}
.extw__card:hover {
  border-color: var(--accent);
  box-shadow: 0 4px 12px rgba(16, 24, 40, 0.08);
  transform: translateY(-1px);
}
.extw__card--on {
  border-color: var(--accent);
  background: var(--bg-subtle, #e6f0ff);
}
.extw__card-logo {
  width: 30px;
  height: 30px;
  border-radius: 7px;
  background: var(--accent);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  margin-bottom: 8px;
}
.extw__card-name {
  font-size: 13px;
  font-weight: 600;
}
.extw__card-desc {
  font-size: 11.5px;
  color: var(--fg-secondary);
  margin-top: 2px;
}
.extw__browse {
  display: grid;
  grid-template-columns: 1fr 240px;
  gap: 12px;
}
.extw__tree-box,
.extw__sel-box {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px;
  height: 250px;
  overflow: auto;
}
.extw__sel-box {
  background: var(--bg-subtle, #f5f7fa);
}
.extw__sel-head {
  display: flex;
  justify-content: space-between;
  font-size: 11.5px;
  color: var(--fg-secondary);
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 8px;
}
.extw__sel-count {
  color: var(--accent);
  font-weight: 600;
}
.extw__sel-empty {
  padding: 40px 8px;
  text-align: center;
  font-size: 12px;
  color: var(--fg-muted, #8f959e);
}
.extw__sel-item {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 5px 7px;
  margin-bottom: 5px;
  font-size: 12px;
}
.extw__sel-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.extw__sel-rm {
  color: var(--fg-muted, #8f959e);
  cursor: pointer;
}
.extw__sel-rm:hover {
  color: var(--error, #ff4d4f);
}
.extw__param {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}
.extw__param-label {
  min-width: 130px;
  font-size: 12px;
  color: var(--fg-secondary);
}
.extw__hint-block {
  font-size: 11.5px;
  color: var(--fg-muted, #8f959e);
  margin-top: 4px;
}
.extw__tip {
  font-size: 11.5px;
  color: var(--fg-muted, #8f959e);
}
.extw__mt {
  margin-top: 12px;
}
.extw__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.extw__hint {
  font-size: 11.5px;
  color: var(--fg-muted, #8f959e);
}
</style>
