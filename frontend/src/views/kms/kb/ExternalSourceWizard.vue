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
          <a-button v-if="step === 1" @click="prev">{{ t('kbExt.prev') }}</a-button>
          <a-button
            v-if="step === 0"
            type="primary"
            :disabled="!canNext"
            @click="next"
          >{{ t('kbExt.next') }}</a-button>
          <a-button
            v-if="step === 1"
            type="primary"
            :loading="importing"
            :disabled="!selected.length"
            @click="doImport"
          >{{ t('kbExt.startImport') }}</a-button>
          <a-button v-if="step === 2" type="primary" @click="close">{{ t('kbExt.done') }}</a-button>
        </a-space>
      </div>
    </template>

    <a-steps :current="step" size="small" class="extw__steps">
      <a-step :title="t('kbExt.step1')" @click="go(0)" />
      <a-step :title="t('kbExt.step2')" :disabled="!selected.length" @click="go(1)" />
      <a-step :title="t('kbExt.step3')" :disabled="step < 2" />
    </a-steps>

    <!-- 步骤 1：选择文档（平台/凭据在知识库新建·编辑时已固化，服务端按已保存凭据浏览） -->
    <div v-if="step === 0" class="extw__pane">
      <div class="extw__sec-title">{{ t('kbExt.pickDocs') }}</div>
      <div class="extw__desc">{{ t('kbExt.pickDocsDesc') }}</div>
      <a-alert
        v-if="configError"
        class="extw__mt"
        type="warning"
        :message="configError"
        show-icon
      />
      <a-alert
        v-else-if="treeError"
        class="extw__mt"
        type="error"
        :message="t('kbExt.loadNodesFailed')"
        :description="treeError"
        show-icon
      />
      <div v-else class="extw__browse">
        <div class="extw__tree-box">
          <div class="extw__tree-head">
            <span class="extw__tree-label">{{ t('kbExt.step1') }}</span>
            <a-checkbox
              :checked="allSelected"
              :indeterminate="someSelected"
              @change="(e: any) => selectAllLoaded(e.target.checked)"
            >{{ t('kbExt.selectAll') }}</a-checkbox>
          </div>
          <a-spin v-if="treeLoading" />
          <a-empty v-else-if="!treeData.length" :description="t('kbExt.nodesEmpty')" />
          <a-tree
            v-else
            :checked-keys="checkedKeys"
            v-model:expandedKeys="expandedKeys"
            :tree-data="treeData"
            :load-data="onLoadData"
            checkable
            check-strictly
            :selectable="false"
            @check="onTreeCheck"
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

    <!-- 步骤 2：切片方案 -->
    <div v-else-if="step === 1" class="extw__pane">
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

    <!-- 步骤 3：导入结果 -->
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
  getExternalConfig,
  importExternalDocuments,
  listExternalNodes,
  listExternalProviders,
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
/** 平台由知识库自身绑定（新建/编辑时已固化），不再在向导内选择 */
const sourceType = ref<string>('')
const configError = ref('')

const treeData = ref<any[]>([])
const treeLoading = ref(false)
const treeError = ref('')
const expandedKeys = ref<string[]>([])
const checkedKeys = ref<string[]>([])
const nodeMap = new Map<string, ExternalNode>()

const chunkers = ref<any[]>([])
const chunkersLoading = ref(false)
const chunkerType = ref('approx_token')
const chunkerParams = ref<Record<string, any>>({})

const importing = ref(false)
const summary = ref<ImportSummary | null>(null)

const currentProviderName = computed(
  () => providers.value.find((p) => p.source_type === sourceType.value)?.name || '',
)

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

/** 勾选回调归一化。
 *
 *  ``check-strictly`` 下 vc-tree 给的不是 key 数组，而是 ``{ checked, halfChecked }``
 *  对象；若用 ``v-model:checkedKeys`` 直接接收，``checkedKeys`` 会变成对象，
 *  下游的 ``.map()/.includes()`` 立即抛 TypeError。故统一收敛为 key 数组。 */
function onTreeCheck(payload: any) {
  checkedKeys.value = Array.isArray(payload) ? payload : payload?.checked || []
}

const selected = computed<ExternalNode[]>(() =>
  checkedKeys.value
    .map((k) => nodeMap.get(k))
    .filter((n): n is ExternalNode => !!n && n.node_type === 'doc'),
)

const canNext = computed(() => {
  if (step.value === 0) return selected.value.length > 0
  return true
})

const footHint = computed(() => {
  if (step.value === 0 && !selected.value.length) return t('kbExt.needSelect')
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

/** 凭据不在前端持有：留空由服务端按 (tenant, knowledge_id, source_type) 读取已加密凭据。
 *
 *  ``silent=true`` 表示这是懒加载的下一层：只用节点自身的 switcher 转圈。
 *  若此时置 ``treeLoading``，模板会整块切到全局 spinner，Tree 被卸载重建、
 *  展开状态丢失——表现为「点开目录后下面什么都没有」。 */
async function loadNodes(parentId?: string | null, silent = false) {
  if (!silent) treeLoading.value = true
  try {
    const res: any = await listExternalNodes(
      sourceType.value,
      {},
      parentId,
      props.knowledgeId,
    )
    return (res?.items || res || []).map(toTreeNode)
  } catch (e: any) {
    // 目录拉取失败要在面板里说清楚（平台权限/凭据不足等），不能只留一个空列表；
    // 子层失败时保留已加载的树，只做提示，避免整棵树被错误面板顶掉
    const detail = e?.response?.data?.detail || t('kbExt.loadNodesFailed')
    if (silent) message.error(detail)
    else treeError.value = detail
    return []
  } finally {
    if (!silent) treeLoading.value = false
  }
}

/** 懒加载子层级。
 *
 *  ant-design-vue 4 的 ``load-data`` 回调参数是包装节点，真正的数据在 ``dataRef`` 上；
 *  直接给它塞 ``children`` 不会进入 ``treeData``，前端就永远看不到子节点。 */
async function onLoadData(treeNode: any) {
  const dataNode: any = treeNode?.dataRef || treeNode
  if (!dataNode) return
  if (dataNode.children?.length) return
  const children = await loadNodes(dataNode.key, true)
  if (children.length) {
    dataNode.children = children
  } else {
    // 空目录置为叶子，避免反复展开却始终加载不出内容
    dataNode.children = []
    dataNode.isLeaf = true
  }
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
      chunker_type: chunkerType.value,
      chunker_params: chunkerParams.value,
    })
    summary.value = res
    step.value = 2
    emit('imported')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbExt.importFailed'))
  } finally {
    importing.value = false
  }
}

function go(n: number) {
  if (n === 1 && !selected.value.length) return
  if (n === 2 && step.value < 2) return
  step.value = n
}
function next() {
  if (step.value === 0) {
    step.value = 1
    if (!chunkers.value.length) loadChunkers()
  }
}
function prev() {
  if (step.value === 1) step.value = 0
}
function close() {
  emit('update:open', false)
}

/** 解析平台：优先用调用方预置值，否则回读知识库的外部配置 */
async function resolveSourceType() {
  if (props.presetSourceType) {
    sourceType.value = props.presetSourceType
    return
  }
  try {
    const cfg: any = await getExternalConfig(props.knowledgeId)
    sourceType.value = cfg?.external_type || ''
  } catch {
    sourceType.value = ''
  }
}

function resetState() {
  step.value = 0
  summary.value = null
  configError.value = ''
  treeError.value = ''
  treeData.value = []
  expandedKeys.value = []
  checkedKeys.value = []
  nodeMap.clear()
}

/** 每次打开都重新初始化：组件可能挂载即处于 open 状态（知识库创建后立即打开），
 *  非 immediate 的 watch 不会触发回调，故此处必须 immediate。 */
watch(
  () => props.open,
  async (open) => {
    if (!open) return
    resetState()
    if (!providers.value.length) await loadProviders()
    await resolveSourceType()
    if (!sourceType.value) {
      configError.value = t('kbExt.configureCredsFirst')
      return
    }
    await ensureTree()
    if (props.presetNodeIds?.length) checkedKeys.value = [...props.presetNodeIds]
  },
  { immediate: true },
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
  /* 与左侧树面板保持对称：透明底 + 边框，卡片色由皮肤令牌提供，避免硬编码浅色底 */
  background: transparent;
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
  color: var(--fg-muted);
}
.extw__sel-item {
  display: flex;
  align-items: center;
  gap: 6px;
  /* 用皮肤令牌而非 #fff：深色皮肤下 --fg 是近白色，白底会变成“白底白字” */
  background: var(--bg-subtle);
  color: var(--fg);
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
  color: var(--fg-muted);
  cursor: pointer;
}
.extw__sel-rm:hover {
  color: var(--err);
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
  color: var(--fg-muted);
}
</style>
