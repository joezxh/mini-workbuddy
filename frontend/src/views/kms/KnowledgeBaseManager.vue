<template>
  <div class="kb-manager">
    <a-row class="kb-manager__body">
      <a-col class="kb-manager__side">
        <div class="kb-manager__tree-head">
          <a-tooltip :title="t('kmsWiki.addCategory')">
            <a-button class="kb-manager__tree-icon-btn" size="small" @click="openCreateCategory">
              <template #icon><PlusOutlined /></template>
            </a-button>
          </a-tooltip>
          <a-tooltip :title="t('kmsWiki.addKnowledge')">
            <a-button class="kb-manager__tree-icon-btn" size="small" @click="openCreate">
              <template #icon><BookOutlined /></template>
            </a-button>
          </a-tooltip>
        </div>
        <a-card size="small" class="kb-manager__tree">
          <div class="kb-manager__tree-title">{{ t('kbMgmt.treeTitle') }}</div>
          <a-spin v-if="loading" />
          <a-empty v-else-if="!treeData.length" />
          <a-tree
            v-else
            :tree-data="treeData"
            :expanded-keys="expandedKeys"
            @select="onSelectKnowledge"
            @expand="(keys: any) => expandedKeys = keys"
          >
            <template #title="{ data }">
              <a-dropdown
                v-if="data && (data.type === 'kb' || data.type === 'category')"
                :trigger="['contextmenu']"
              >
                <span class="kb-cat-node">
                  <FolderOutlined v-if="data.type === 'category'" class="kb-icon kb-icon--folder" />
                  <FolderOpenOutlined v-else-if="data.type === 'group'" class="kb-icon kb-icon--folder" />
                  <ReadOutlined v-else-if="data.kbType === 1" class="kb-icon kb-icon--wiki" />
                  <LinkOutlined v-else-if="data.kbType === 3" class="kb-icon kb-icon--external" />
                  <BookOutlined v-else class="kb-icon kb-icon--general" />
                  <span class="kb-node-name">{{ data.title }}</span>
                  <span v-if="data.count != null" class="kb-node-count">{{ data.count }}</span>
                </span>
                <template #overlay>
                  <a-menu @click="(e: any) => onNodeMenu(String(e.key), data)">
                    <a-menu-item key="view">{{ t('kmsWiki.viewInfo') }}</a-menu-item>
                    <a-menu-item v-if="data.type === 'kb'" key="edit">{{ t('kmsWiki.editKnowledge') }}</a-menu-item>
                    <a-menu-divider v-if="data.type === 'kb'" />
                    <a-menu-item v-if="data.type === 'kb'" key="delete" danger>{{ t('kmsWiki.deleteKnowledge') }}</a-menu-item>
                    <template v-else>
                      <a-menu-item key="add-child">{{ t('kmsWiki.addChildCategory') }}</a-menu-item>
                      <a-menu-item key="rename">{{ t('kmsWiki.renameCategory') }}</a-menu-item>
                      <a-menu-divider />
                      <a-menu-item key="delete" danger>{{ t('kmsWiki.deleteCategory') }}</a-menu-item>
                    </template>
                  </a-menu>
                </template>
              </a-dropdown>
              <span v-else class="kb-cat-node">
                <FolderOutlined v-if="data?.type === 'category'" class="kb-icon kb-icon--folder" />
                <FolderOpenOutlined v-else-if="data?.type === 'group'" class="kb-icon kb-icon--folder" />
                <ReadOutlined v-else-if="data?.kbType === 1" class="kb-icon kb-icon--wiki" />
                <LinkOutlined v-else-if="data?.kbType === 3" class="kb-icon kb-icon--external" />
                <BookOutlined v-else-if="data" class="kb-icon kb-icon--general" />
                <span class="kb-node-name">{{ data?.title }}</span>
                <span v-if="data?.count != null" class="kb-node-count">{{ data?.count }}</span>
              </span>
            </template>
          </a-tree>
        </a-card>
      </a-col>
      <a-col class="kb-manager__main">
        <WikiHome v-if="selectedKbType === 1" :wiki-id="selectedId" embedded />
        <KbDocumentPane
          v-else-if="selectedKbType === 2 && selectedId"
          :knowledge-id="selectedId"
          :knowledge-name="selectedKbName"
          :kb-format="selectedKbFormat"
        />
        <a-empty v-else-if="selectedKbType === 2" :description="t('kbMgmt.selectKbFirst')" />
        <ExternalLinkPane
          v-else-if="selectedKbType === 3 && selectedId"
          :knowledge-id="selectedId"
          :knowledge-name="selectedKbName"
        />
        <a-empty v-else :description="t('kbMgmt.selectKbFirst')" />
      </a-col>
    </a-row>

    <!-- 新建知识库向导（spec §3.1 / §10.2） -->
    <a-modal
      v-model:open="createOpen"
      :title="editingId ? t('kbMgmt.edit') : t('kbMgmt.createWizard')"
      @ok="submit"
      :confirm-loading="creating"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('kbMgmt.name')" required>
          <a-input v-model:value="form.name" :placeholder="t('kbMgmt.namePlaceholder')" />
        </a-form-item>
        <a-form-item :label="t('kbMgmt.type')">
          <!-- 编辑态锁定类型：后端同样不允许变更（需求 4） -->
          <a-select v-model:value="form.type" :disabled="!!editingId">
            <a-select-option :value="1">{{ t('kbMgmt.typeWiki') }}</a-select-option>
            <a-select-option :value="2">{{ t('kbMgmt.typeGeneral') }}</a-select-option>
            <a-select-option :value="3">{{ t('kbMgmt.typeExternal') }}</a-select-option>
          </a-select>
          <a-alert
            v-if="editingId"
            class="kb-manager__tip"
            type="info"
            :message="t('kbMgmt.typeLocked')"
            show-icon
          />
        </a-form-item>
        <a-form-item :label="t('kbMgmt.category')">
          <a-tree-select
            v-model:value="form.category_id"
            :tree-data="catSelectTree"
            :placeholder="t('kbMgmt.categoryPlaceholder')"
            allow-clear
            tree-default-expand-all
            :dropdown-style="{ maxHeight: '320px', overflow: 'auto' }"
          />
        </a-form-item>
        <a-form-item v-if="form.type === 2" :label="t('kbMgmt.kbFormat')">
          <a-select v-model:value="form.kb_format" allow-clear>
            <a-select-option value="document">{{ t('kbMgmt.fmtDocument') }}</a-select-option>
            <a-select-option value="table">{{ t('kbMgmt.fmtTable') }}</a-select-option>
            <a-select-option value="qa">{{ t('kbMgmt.fmtQa') }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item v-if="form.type === 3" :label="t('kbMgmt.kbFormat')">
          <a-select v-model:value="form.kb_format">
            <a-select-option value="proxy">{{ t('kbMgmt.fmtProxy') }}</a-select-option>
            <a-select-option value="connector">{{ t('kbMgmt.fmtConnector') }}</a-select-option>
          </a-select>
          <a-alert
            v-if="form.kb_format === 'connector'"
            class="kb-manager__tip"
            type="info"
            :message="t('kbMgmt.connectorHint')"
            show-icon
          />
        </a-form-item>
        <a-form-item v-if="form.type === 2" :label="t('kbMgmt.indexMode')">
          <a-radio-group v-model:value="form.index_mode">
            <a-radio value="high_quality">{{ t('kbMgmt.highQuality') }}</a-radio>
            <a-radio value="economy">{{ t('kbMgmt.economy') }}</a-radio>
          </a-radio-group>
          <div class="kb-manager__tip">{{ t('kbMgmt.indexModeTip') }}</div>
        </a-form-item>

        <!-- 多模态开关：type=2/document，仅文搜图（D9） -->
        <a-form-item v-if="form.type === 2 && form.kb_format === 'document'" :label="t('kbMgmt.multimodal')">
          <a-switch v-model:checked="form.multimodal_enabled" />
          <div class="kb-manager__tip">{{ t('kbMgmt.multimodalTip') }}</div>
          <a-alert
            v-if="form.multimodal_enabled && !isVisionModel"
            class="kb-manager__tip"
            type="warning"
            :message="t('kbMgmt.visionModelRequired')"
            show-icon
          />
          <a-select
            v-if="form.multimodal_enabled"
            v-model:value="form.embedding_model"
            class="kb-manager__tip"
            :placeholder="t('kbMgmt.selectEmbeddingModel')"
            allow-clear
          >
            <a-select-option value="qwen3-vl-embedding">qwen3-vl-embedding（Vision）</a-select-option>
            <a-select-option value="multimodal-embedding-v1">multimodal-embedding-v1（Vision）</a-select-option>
            <a-select-option value="text-embedding-v4">text-embedding-v4（纯文本）</a-select-option>
          </a-select>
        </a-form-item>

        <!-- 切片方案：按二级形态过滤（问答→仅问答对切分；文档→其它方案；表格→不切分） -->
        <a-form-item :label="t('kbMgmt.chunkerType')">
          <a-select
            v-model:value="form.chunker_type"
            class="kb-manager__tip"
            :placeholder="t('kbMgmt.selectChunker')"
            :loading="chunkersLoading"
            :disabled="chunkerRule === 'none'"
            :options="chunkerOptions"
            @change="onChunkerChange"
          />
          <a-alert
            v-if="chunkerRule === 'none'"
            class="kb-manager__tip"
            type="info"
            :message="t('kbMgmt.chunkerNoneHint')"
            show-icon
          />
          <a-alert
            v-else
            class="kb-manager__tip"
            type="info"
            :message="t('kbMgmt.chunkerHint')"
            show-icon
          />
          <!-- 参数按后端 JSON Schema 动态渲染 -->
          <div
            v-for="f in chunkerFields"
            :key="f.name"
            class="kb-manager__chunker-param"
          >
            <span class="kb-manager__param-label">{{ f.name }}</span>
            <a-switch v-if="f.type === 'boolean'" v-model:checked="form.chunker_params[f.name]" size="small" />
            <a-input-number
              v-else-if="f.type === 'integer'"
              v-model:value="form.chunker_params[f.name]"
              size="small"
              :min="0"
              style="width: 140px"
            />
            <a-input
              v-else
              v-model:value="form.chunker_params[f.name]"
              size="small"
              style="width: 240px"
            />
          </div>
        </a-form-item>

        <!-- 表格形态：字段定义（可留空；embedding 可多选，组合成向量化内容） -->
        <a-form-item v-if="form.type === 2 && form.kb_format === 'table'" :label="t('kbMgmt.schemaConfig')">
          <a-alert class="kb-manager__tip" type="info" :message="t('kbMgmt.schemaConfigHint')" show-icon />
          <a-alert
            v-if="!form.schema_config.length"
            class="kb-manager__tip"
            type="warning"
            :message="t('kbMgmt.schemaConfigEmptyHint')"
            show-icon
          />
          <div v-for="(f, i) in form.schema_config" :key="i" class="kb-manager__field">
            <a-input v-model:value="f.name" :placeholder="t('kbMgmt.fieldName')" style="width: 40%" />
            <a-select v-model:value="f.type" style="width: 25%">
              <a-select-option value="string">{{ t('kbMgmt.typeString') }}</a-select-option>
              <a-select-option value="number">{{ t('kbMgmt.typeNumber') }}</a-select-option>
              <a-select-option value="boolean">{{ t('kbMgmt.typeBoolean') }}</a-select-option>
            </a-select>
            <a-checkbox v-model:checked="f.filterable">{{ t('kbMgmt.filterable') }}</a-checkbox>
            <a-checkbox v-model:checked="f.embedding">{{ t('kbMgmt.embedField') }}</a-checkbox>
            <a-button size="small" danger @click="removeField(i)">{{ t('common.delete') }}</a-button>
          </div>
          <a-button size="small" @click="addField">{{ t('kbMgmt.addField') }}</a-button>
        </a-form-item>

        <!-- 外部代理形态：端点配置 -->
        <template v-if="form.type === 3 && form.kb_format === 'proxy'">
          <a-form-item :label="t('kbMgmt.endpointUrl')" required>
            <a-input v-model:value="form.endpoint.endpoint_url" placeholder="https://..." />
          </a-form-item>
          <a-form-item :label="t('kbMgmt.authKey')">
            <a-input-password v-model:value="form.endpoint.auth_key" />
          </a-form-item>
          <a-form-item :label="t('kbMgmt.indexName')">
            <a-input v-model:value="form.endpoint.index_name" />
          </a-form-item>
        </template>

        <a-form-item :label="t('kbMgmt.description')">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 新建/编辑分类（与 Wiki 左树右键菜单一致） -->
    <a-modal
      v-model:open="catModal.open"
      :title="catModal.mode === 'rename' ? t('kmsWiki.renameCategory') : t('kmsWiki.addCategory')"
      :confirm-loading="catSaving"
      @ok="submitCategory"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('kmsWiki.categoryName')" required>
          <a-input v-model:value="catModal.name" :placeholder="t('kmsWiki.categoryName')" />
        </a-form-item>
        <a-form-item :label="t('kmsWiki.categoryDesc')">
          <a-textarea v-model:value="catModal.description" :rows="2" />
        </a-form-item>
        <a-form-item :label="t('kmsWiki.categorySort')">
          <a-input-number v-model:value="catModal.sort_order" :min="0" style="width: 100%" />
        </a-form-item>
        <div v-if="catModal.parentName" class="category-parent-hint">
          {{ t('wikiMgmt.tabCategory') }}: {{ catModal.parentName }}
        </div>
      </a-form>
    </a-modal>

    <!-- 外部知识库文档导入向导（type=3 / kb_format=connector 创建后打开） -->
    <ExternalSourceWizard
      v-if="wizardKnowledgeId"
      v-model:open="wizardOpen"
      :knowledge-id="wizardKnowledgeId"
      @imported="load"
    />

    <!-- 节点信息查看弹窗（只读，右键「查看信息」） -->
    <a-modal v-model:open="infoModal.open" :title="infoModal.title" :footer="null">
      <a-descriptions :column="1" size="small" bordered>
        <a-descriptions-item v-for="f in infoModal.fields" :key="f.label" :label="f.label">
          {{ f.value }}
        </a-descriptions-item>
      </a-descriptions>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message, Modal } from 'ant-design-vue'
import { createKnowledge, listKnowledges, listCategories, updateKnowledge, createCategory, updateCategory, deleteCategory, deleteKnowledge } from '@/api/wiki'
import { createProxyEndpoint, listChunkers } from '@/api/kb'
import { PlusOutlined, BookOutlined, ReadOutlined, LinkOutlined, FolderOutlined, FolderOpenOutlined } from '@ant-design/icons-vue'
import KbDocumentPane from './kb/KbDocumentPane.vue'
import ExternalLinkPane from './kb/ExternalLinkPane.vue'
import ExternalSourceWizard from './kb/ExternalSourceWizard.vue'
import WikiHome from '@/views/kms/wiki/index.vue'

const { t } = useI18n()
const loading = ref(false)
const knowledges = ref<any[]>([])
const categories = ref<any[]>([])
const selectedId = ref<number | null>(null)
const selectedCategoryId = ref<number | null>(null)
const editingId = ref<number | null>(null)

const treeData = ref<any[]>([])
// 类别下拉树（与左侧类别树同源，仅用于表单选择）
const catSelectTree = computed(() => toSelectTree(categories.value))

function toSelectTree(cats: any[]): any[] {
  return (cats || []).map((c) => ({
    value: c.id,
    title: c.name,
    children: toSelectTree(c.children || []),
  }))
}

const createOpen = ref(false)
const creating = ref(false)
/** 外部知识库「文档导入」向导：建完容器后打开，选择平台与文档 */
const wizardOpen = ref(false)
const wizardKnowledgeId = ref<number | null>(null)
const form = reactive({
  name: '',
  description: '',
  type: 2,
  kb_format: 'document' as string | null,
  index_mode: 'high_quality',
  multimodal_enabled: false,
  embedding_model: '' as string,
  chunker_type: 'approx_token' as string,
  chunker_params: {} as Record<string, any>,
  category_id: null as number | null,
  schema_config: [] as { name: string; type: string; filterable: boolean; embedding: boolean }[],
  endpoint: { endpoint_url: '', auth_key: '', index_name: '' },
})

/** 多模态仅文搜图（D9），要求嵌入模型是 Vision 系列 */
const isVisionModel = computed(() => /vl|vision|multimodal/.test((form.embedding_model || '').toLowerCase()))

// ── 切片方案（chunker）──────────────────────────────────────────────
const chunkers = ref<any[]>([])
const chunkersLoading = ref(false)

/** 当前所选 chunker 的参数字段（来自后端 JSON Schema） */
const chunkerFields = computed(() => {
  const hit = visibleChunkers.value.find((c) => c.chunker_type === form.chunker_type)
  const props = hit?.parameters_schema?.properties || {}
  return Object.keys(props).map((name) => ({
    name,
    type: props[name]?.type || 'string',
    default: props[name]?.default,
  }))
})

/**
 * 切片方案按二级形态联动：
 * - 问答（qa）→ 只能选「问答对切分」（chunker_type=qa）
 * - 文档（document）→ 其它切分方式（排除 qa）
 * - 表格（table）→ 不选切分（按行入库，不生成 chunker 配置）
 * - 外部知识库（type≠2）→ 不做形态限制
 */
const CHUNKER_RULES: Record<string, 'qa' | 'doc' | 'none'> = {
  qa: 'qa',
  document: 'doc',
  table: 'none',
}

const chunkerRule = computed<'qa' | 'doc' | 'none' | 'all'>(() =>
  form.type === 2 ? CHUNKER_RULES[form.kb_format || ''] ?? 'all' : 'all',
)

const visibleChunkers = computed(() => {
  if (chunkerRule.value === 'none') return []
  if (chunkerRule.value === 'qa') return chunkers.value.filter((c) => c.chunker_type === 'qa')
  if (chunkerRule.value === 'doc') return chunkers.value.filter((c) => c.chunker_type !== 'qa')
  return chunkers.value
})

const chunkerOptions = computed(() =>
  visibleChunkers.value.map((c) => ({ label: c.label || c.chunker_type, value: c.chunker_type })),
)

// 形态切换后若当前方案已被排除，回落到该形态允许的默认值
watch([chunkerRule, chunkers], () => {
  if (chunkerRule.value === 'none') return
  if (visibleChunkers.value.some((c) => c.chunker_type === form.chunker_type)) return
  form.chunker_type =
    chunkerRule.value === 'qa' ? 'qa' : visibleChunkers.value[0]?.chunker_type || 'approx_token'
  onChunkerChange()
})

function onChunkerChange() {
  // 切换方案时重置为该方案默认参数，避免上一方案的字段残留
  const next: Record<string, any> = {}
  for (const f of chunkerFields.value) next[f.name] = f.default
  form.chunker_params = next
}

/** 组装 pipeline_config：嵌入模型 + 切片方案（原生键名，D8）；表格形态不落 chunker */
function buildPipelineConfig() {
  const cfg: Record<string, any> = {}
  if (form.embedding_model) cfg.embedding = { model: form.embedding_model }
  if (chunkerRule.value !== 'none' && form.chunker_type) {
    cfg.chunker = {
      type: form.chunker_type,
      params: { ...form.chunker_params },
    }
  }
  return Object.keys(cfg).length ? cfg : undefined
}

async function loadChunkers() {
  chunkersLoading.value = true
  try {
    const res: any = await listChunkers()
    chunkers.value = res || []
    // 首次加载时若参数为空，填入当前方案默认值
    if (!Object.keys(form.chunker_params).length) onChunkerChange()
  } catch {
    chunkers.value = []
  } finally {
    chunkersLoading.value = false
  }
}

function addField() {
  form.schema_config.push({
    name: '',
    type: 'string',
    filterable: true,
    embedding: form.schema_config.length === 0,
  })
}

function removeField(i: number) {
  form.schema_config.splice(i, 1)
}

/** 向量化字段改为**多选**（模板用 v-model:checked 直接切换），无需单选辅助函数 */

const expandedKeys = ref<string[]>([])

/** 当前选中知识库的二级形态（驱动右侧形态 tab 与切片方案联动） */
const selectedKbFormat = computed(() => {
  const kb = knowledges.value.find((k) => k.id === selectedId.value)
  return kb?.kb_format || null
})

/** 当前选中知识库的类型（1=Wiki / 2=通用 / 3=外部），驱动右栏界面与左树叶子图标 */
const selectedKbType = computed<number | null>(() => {
  const kb = knowledges.value.find((k) => k.id === selectedId.value)
  return kb?.type ?? null
})

/** 当前选中知识库名称：供各面板头展示 */
const selectedKbName = computed(() => {
  const kb = knowledges.value.find((k) => k.id === selectedId.value)
  return kb?.name || ''
})

/** 左侧类别树：类别为父节点，知识库作为叶子挂到所属类别下 */
function rebuildTree() {
  // 不再按类型过滤：三类知识库共享同一分类树，叶子仅用图标区分类型
  const typeKbs = knowledges.value
  const nodeMap = new Map<number, any>()
  const roots: any[] = []

  const ensureNode = (c: any): any => {
    if (nodeMap.has(c.id)) return nodeMap.get(c.id)
    const node = { key: 'c-' + c.id, title: c.name, type: 'category', rawId: c.id, rawDesc: c.description, rawSort: c.sort_order, isLeaf: !(c.children && c.children.length), children: [] }
    nodeMap.set(c.id, node)
    return node
  }

  // 递归遍历服务端返回的嵌套层级，保留任意深度的子类别（此前只挂一层，孙类别会丢失）
  const visit = (c: any): any => {
    const node = ensureNode(c)
    ;(c.children || []).forEach((child: any) => node.children.push(visit(child)))
    return node
  }
  ;(categories.value || []).forEach((c) => visit(c))

  const uncategorized: any[] = []
  typeKbs.forEach((k) => {
    const leaf = {
      key: 'k-' + k.id,
      title: k.name,
      type: 'kb',
      rawId: k.id,
      kbType: k.type,
      isLeaf: true,
      // 叶子徽标：文章/文档数（无该字段时不显示）
      count: k.article_count != null ? k.article_count : undefined,
    }
    const parent = k.category_id != null ? nodeMap.get(k.category_id) : null
    if (parent) parent.children.push(leaf)
    else uncategorized.push(leaf)
  })

  // 分类徽标：其下（含子分类）挂的知识库数量
  const countKb = (nodes: any[]): number =>
    nodes.reduce((sum, n) => sum + (n.type === 'kb' ? 1 : countKb(n.children || [])), 0)
  nodeMap.forEach((n) => {
    n.count = countKb(n.children || [])
  })

  const present = new Set(nodeMap.keys())
  ;(categories.value || []).forEach((c) => {
    const node = nodeMap.get(c.id)
    if (!c.parent_id || !present.has(c.parent_id)) roots.push(node)
  })
  if (uncategorized.length) {
    roots.push({
      key: 'uncat',
      title: t('kbMgmt.uncategorized'),
      type: 'group',
      isLeaf: false,
      selectable: false,
      count: uncategorized.length,
      children: uncategorized,
    })
  }
  const collect = (nodes: any[]): string[] => {
    const keys: string[] = []
    nodes.forEach((n) => {
      if (n.children && n.children.length) {
        keys.push(n.key)
        keys.push(...collect(n.children))
      }
    })
    return keys
  }
  expandedKeys.value = collect(roots)
  treeData.value = roots
}

function onSelectKnowledge(_keys: unknown, info: any) {
  const node = info.node
  if (node.type === 'kb') {
    selectedId.value = Number(node.rawId)
    selectedCategoryId.value = null
  } else if (node.type === 'category') {
    selectedCategoryId.value = Number(node.rawId)
    selectedId.value = null
  } else {
    selectedId.value = null
    selectedCategoryId.value = null
  }
}

function resetForm() {
  form.name = ''
  form.description = ''
  form.type = 2
  form.kb_format = form.type === 2 ? 'document' : form.type === 3 ? 'proxy' : null
  form.index_mode = 'high_quality'
  form.multimodal_enabled = false
  form.embedding_model = ''
  form.chunker_type = 'approx_token'
  form.chunker_params = {}
  if (chunkers.value.length) onChunkerChange()
  form.schema_config = []
  form.endpoint = { endpoint_url: '', auth_key: '', index_name: '' }
}

function openCreate() {
  editingId.value = null
  resetForm()
  // 默认归属到当前选中的类别（spec 知识库管理）
  form.category_id = selectedCategoryId.value
  // 默认类型：有选中知识库取其类型，否则默认通用(2)
  form.type = selectedKbType.value ?? 2
  createOpen.value = true
}

function openEdit() {
  const kb = knowledges.value.find((k) => k.id === selectedId.value)
  if (!kb) return
  editingId.value = kb.id
  form.name = kb.name
  form.description = kb.description || ''
  form.type = Number(kb.type || 2)
  form.kb_format = kb.kb_format || (form.type === 2 ? 'document' : form.type === 3 ? 'proxy' : null)
  form.index_mode = kb.index_mode || 'high_quality'
  form.multimodal_enabled = !!kb.multimodal_enabled
  form.embedding_model = kb.pipeline_config?.embedding?.model || ''
  // 切片方案回显：无配置时回落默认方案
  form.chunker_type = kb.pipeline_config?.chunker?.type || 'approx_token'
  form.chunker_params = kb.pipeline_config?.chunker?.params
    ? { ...kb.pipeline_config.chunker.params }
    : {}
  if (!Object.keys(form.chunker_params).length) onChunkerChange()
  form.schema_config = kb.schema_config ? JSON.parse(JSON.stringify(kb.schema_config)) : []
  form.endpoint = kb.endpoint || { endpoint_url: '', auth_key: '', index_name: '' }
  // 优先用知识库已有类别，否则默认到当前选中的类别
  form.category_id = kb.category_id ?? selectedCategoryId.value
  createOpen.value = true
}

async function submit() {
  if (!form.name.trim()) {
    message.warning(t('kbMgmt.nameRequired'))
    return
  }
  // 多模态强制校验 Vision 嵌入模型（spec §10.6）
  if (form.type === 2 && form.kb_format === 'document' && form.multimodal_enabled && !isVisionModel.value) {
    message.warning(t('kbMgmt.visionModelRequired'))
    return
  }
  // 新建时才校验需要表单完整数据的形态规则（编辑态这些明细未回显，避免误拦）
  if (!editingId.value) {
    // 外部代理：端点地址必填且必须 https（后端 SSRF 校验前的客户端提示）
    if (form.type === 3 && form.kb_format === 'proxy') {
      if (!form.endpoint.endpoint_url.startsWith('https://')) {
        message.warning(t('kbMgmt.endpointHttpsRequired'))
        return
      }
    }
    // 表格：字段定义**可留空**（留空则上传文件时按表头自动生成，默认全字段为向量化内容）；
    // 已定义字段时，至少需要一个向量化字段（可多个）。
    if (form.type === 2 && form.kb_format === 'table') {
      const fields = form.schema_config.filter((f) => f.name.trim())
      if (fields.length && !fields.some((f) => f.embedding)) {
        message.warning(t('kbMgmt.embedFieldRequired'))
        return
      }
    }
  }

  creating.value = true
  try {
    if (editingId.value) {
      await updateKnowledge(editingId.value, {
        name: form.name.trim(),
        description: form.description || undefined,
        category_id: form.category_id ?? undefined,
      })
    } else {
      const res: any = await createKnowledge({
        name: form.name.trim(),
        description: form.description || undefined,
        type: form.type,
        kb_format: form.kb_format,
        index_mode: form.type === 2 ? form.index_mode : undefined,
        multimodal_enabled: form.type === 2 ? form.multimodal_enabled : undefined,
        category_id: form.category_id ?? undefined,
        // 嵌入模型 + 切片方案经 pipeline_config 下发（D8 原生键名）
        pipeline_config: buildPipelineConfig(),
      })
      const kid = res?.id

      // proxy 形态：建完容器后补建检索代理端点
      if (form.type === 3 && form.kb_format === 'proxy' && kid) {
        await createProxyEndpoint({
          name: form.name.trim(),
          endpoint_url: form.endpoint.endpoint_url,
          index_name: form.endpoint.index_name || undefined,
          auth_key: form.endpoint.auth_key || undefined,
        })
      }
      // connector 形态（文档导入）：建完容器后直接打开导入向导选文档
      if (form.type === 3 && form.kb_format === 'connector' && kid) {
        wizardKnowledgeId.value = kid
        wizardOpen.value = true
      }
    }
    message.success(t('kbMgmt.created'))
    createOpen.value = false
    await load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.createFailed'))
  } finally {
    creating.value = false
  }
}

// ── 分类新建/编辑（左树头部 +分类 与右键菜单，与 Wiki 左树一致） ──
const catModal = reactive({
  open: false,
  mode: 'create' as 'create' | 'rename',
  targetId: null as number | null,
  parentId: null as number | null,
  parentName: '',
  name: '',
  description: '',
  sort_order: 0,
})
const catSaving = ref(false)

function openCreateCategory(node?: any) {
  catModal.mode = 'create'
  catModal.targetId = null
  catModal.parentId = node ? node.rawId : null
  catModal.parentName = node ? node.title : ''
  catModal.name = ''
  catModal.description = ''
  catModal.sort_order = 0
  catModal.open = true
}

function openRenameCategory(node: any) {
  catModal.mode = 'rename'
  catModal.targetId = node.rawId
  catModal.parentId = null
  catModal.parentName = ''
  catModal.name = node.title
  catModal.description = node.rawDesc || ''
  catModal.sort_order = node.rawSort || 0
  catModal.open = true
}

async function submitCategory() {
  const name = catModal.name.trim()
  if (!name) {
    message.warning(t('kmsWiki.categoryName'))
    return
  }
  catSaving.value = true
  try {
    if (catModal.mode === 'rename' && catModal.targetId) {
      await updateCategory(catModal.targetId, {
        name,
        description: catModal.description || undefined,
        sort_order: catModal.sort_order,
      })
      message.success(t('kmsWiki.updateCategorySuccess'))
    } else {
      await createCategory({
        name,
        description: catModal.description || undefined,
        sort_order: catModal.sort_order,
        parent_id: catModal.parentId ?? undefined,
      })
      message.success(t('kmsWiki.createCategorySuccess'))
    }
    catModal.open = false
    await load()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    message.error(typeof detail === 'string' ? detail : t('common.error'))
  } finally {
    catSaving.value = false
  }
}

// ── 左树右键菜单（分类 / 知识库） ──
function onNodeMenu(key: string, node: any) {
  if (node.type === 'kb') {
    if (key === 'view') openKbInfo(node)
    else if (key === 'edit') {
      selectedId.value = Number(node.rawId)
      openEdit()
    } else if (key === 'delete') confirmDeleteKb(node)
  } else {
    if (key === 'view') openCatInfo(node)
    else if (key === 'add-child') openCreateCategory(node)
    else if (key === 'rename') openRenameCategory(node)
    else if (key === 'delete') confirmDeleteCategory(node)
  }
}

function confirmDeleteCategory(node: { rawId: number; title: string }) {
  Modal.confirm({
    title: t('kmsWiki.deleteCategory'),
    content: `${node.title}：${t('kmsWiki.deleteCategoryConfirm')}`,
    okType: 'danger',
    okText: t('common.confirm'),
    cancelText: t('common.cancel'),
    onOk: async () => {
      try {
        await deleteCategory(node.rawId)
        message.success(t('kmsWiki.deleteCategorySuccess'))
        await load()
      } catch (e: any) {
        const detail = e?.response?.data?.detail
        message.error(typeof detail === 'string' ? detail : t('kbMgmt.common.deleteFailed'))
      }
    },
  })
}

function confirmDeleteKb(node: any) {
  Modal.confirm({
    title: t('kmsWiki.deleteKnowledge'),
    content: `${node.title}：${t('kmsWiki.deleteKnowledgeConfirm')}`,
    okType: 'danger',
    okText: t('common.confirm'),
    cancelText: t('common.cancel'),
    onOk: async () => {
      try {
        await deleteKnowledge(Number(node.rawId))
        message.success(t('kmsWiki.deleteKnowledgeSuccess'))
        selectedId.value = null
        await load()
      } catch (e: any) {
        const detail = e?.response?.data?.detail
        message.error(typeof detail === 'string' ? detail : t('kbMgmt.common.deleteFailed'))
      }
    },
  })
}

// ── 节点信息查看（只读） ──
const infoModal = reactive({
  open: false,
  title: '',
  fields: [] as { label: string; value: any }[],
})

function openInfoModal(title: string, fields: { label: string; value: any }[]) {
  infoModal.title = title
  infoModal.fields = fields
  infoModal.open = true
}

function findCategoryName(id: number | null): string {
  if (id == null) return '-'
  const walk = (cats: any[]): string => {
    for (const c of cats) {
      if (c.id === id) return c.name
      const found = c.children?.length ? walk(c.children) : ''
      if (found) return found
    }
    return ''
  }
  return walk(categories.value) || String(id)
}

function openCatInfo(node: any) {
  openInfoModal(node.title, [
    { label: t('kmsWiki.categoryName'), value: node.title },
    { label: t('kmsWiki.categoryDesc'), value: node.rawDesc || '-' },
    { label: t('kmsWiki.categorySort'), value: node.rawSort ?? 0 },
  ])
}

function openKbInfo(node: any) {
  const kb = knowledges.value.find((k) => k.id === Number(node.rawId)) || {}
  openInfoModal(kb.name || node.title, [
    { label: t('kmsWiki.knowledgeName'), value: kb.name },
    { label: t('wikiMgmt.tabCategory'), value: findCategoryName(kb.category_id) },
    { label: 'Slug', value: kb.slug },
    { label: t('kmsWiki.knowledgeType'), value: t('kmsWiki.knowledgeTypeWiki') },
    { label: t('kmsWiki.categoryDesc'), value: kb.description || '-' },
    { label: t('kmsWiki.articleCount'), value: kb.article_count ?? 0 },
    { label: t('kmsWiki.publishStatus'), value: kb.status === 0 ? t('kmsWiki.statusArchived') : t('kmsWiki.statusActive') },
    { label: t('kmsWiki.createdAt'), value: formatDate(kb.created_at) || '-' },
  ])
}

function formatDate(dateStr: string) {
  if (!dateStr) return ''
  return String(dateStr).replace('T', ' ').slice(0, 16)
}

async function load() {
  loading.value = true
  try {
    const [kbRes, catRes] = await Promise.all([listKnowledges(), listCategories()])
    knowledges.value = kbRes?.items || kbRes || []
    categories.value = catRes || []
    rebuildTree()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  loadChunkers()
})

// 选中知识库变化无需重建左树（树已含全部类型），类型由 selectedKbType 派生
</script>

<style scoped>
.kb-manager {
  padding: 8px 0;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

/* 主体两栏：与 Wiki 左树一致（侧栏流式宽 240–320px，主窗体自适应） */
.kb-manager__body {
  display: grid;
  grid-template-columns: minmax(240px, 320px) 1fr;
  gap: 20px;
  align-items: stretch;
  flex: 1;
  min-height: 0;
}
.kb-manager__side {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  height: 100%;
  min-height: 0;
}
.kb-manager__tree-head {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
}
.kb-manager__tree-icon-btn {
  color: var(--fg-secondary);
}
.kb-manager__tree-icon-btn:hover {
  color: var(--accent);
}
.kb-cat-node {
  display: flex;
  align-items: center;
  width: 100%;
  user-select: none;
  white-space: nowrap;
}
.kb-node-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* 知识库/分类数量徽标 */
.kb-node-count {
  flex-shrink: 0;
  margin-left: 6px;
  padding: 0 6px;
  font-size: 11px;
  line-height: 18px;
  color: var(--fg-muted, #8f959e);
  background: var(--bg-subtle, #f5f7fa);
  border-radius: 10px;
}
.kb-icon {
  margin-right: 4px;
  color: var(--accent);
  flex-shrink: 0;
}
/* 分类/分组用中性色，与知识库类型图标区分 */
.kb-icon--folder {
  color: var(--fg-muted, #8f959e);
}
/* 三类知识库用不同颜色区分：Wiki 蓝 / 通用 绿 / 外部 橙 */
.kb-icon--wiki {
  color: var(--accent);
}
.kb-icon--general {
  color: #52c41a;
}
.kb-icon--external {
  color: #fa8c16;
}
/* 树上部标题 */
.kb-manager__tree-title {
  font-size: 11px;
  color: var(--fg-muted, #8f959e);
  letter-spacing: 0.6px;
  padding: 0 4px 8px;
}
.kb-manager__main {
  min-height: 0;
  overflow: auto;
}

/* 类别树：内容超出时纵向 + 横向滚动，树内浅色背景 */
.kb-manager__tree {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.kb-manager__tree :deep(.ant-card-body) {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: var(--bg-subtle, #f5f7fa);
  border-radius: 6px;
}
.kb-manager__tree :deep(.ant-tree-node-content-wrapper) {
  white-space: nowrap;
}

.kb-manager__tip {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
.kb-manager__chunker-param {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}
.kb-manager__param-label {
  min-width: 130px;
  font-size: 12px;
  color: var(--fg-secondary);
}
.category-parent-hint {
  font-size: 12px;
  color: var(--fg-secondary);
  background: var(--bg-hover);
  border-radius: 4px;
  padding: 6px 10px;
}
</style>
