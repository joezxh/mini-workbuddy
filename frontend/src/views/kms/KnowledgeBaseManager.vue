<template>
  <div class="kb-manager">
    <a-tabs v-model:activeKey="activeType">
      <a-tab-pane key="1" :tab="t('kmsWiki.title')" />
      <a-tab-pane key="2" :tab="t('kbMgmt.generalKb')" />
      <a-tab-pane key="3" :tab="t('kbMgmt.externalKb')" />
    </a-tabs>

    <a-row v-if="activeType !== '1'" :gutter="16" align="stretch" class="kb-manager__body">
      <a-col :span="6" class="kb-manager__side">
        <a-card :title="t('wikiMgmt.tabCategory')" size="small" class="kb-manager__tree">
          <template #extra>
            <a-button size="small" @click="openEdit" :disabled="!selectedId">{{ t('kbMgmt.edit') }}</a-button>
            <a-button size="small" type="primary" @click="openCreate">{{ t('kbMgmt.create') }}</a-button>
          </template>
          <a-spin v-if="loading" />
          <a-empty v-else-if="!treeData.length" />
          <a-tree
            v-else
            :tree-data="treeData"
            @select="onSelectKnowledge"
          />
        </a-card>
      </a-col>
      <a-col :span="18" class="kb-manager__main">
        <KbDocumentPane v-if="activeType === '2' && selectedId" :knowledge-id="selectedId" />
        <a-empty v-else-if="activeType === '2'" :description="t('kbMgmt.selectKbFirst')" />
        <ExternalLinkPane v-else />
      </a-col>
    </a-row>
    <WikiHome v-else embedded />

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
          <a-select v-model:value="form.type">
            <a-select-option :value="1">{{ t('kbMgmt.typeWiki') }}</a-select-option>
            <a-select-option :value="2">{{ t('kbMgmt.typeGeneral') }}</a-select-option>
            <a-select-option :value="3">{{ t('kbMgmt.typeExternal') }}</a-select-option>
          </a-select>
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

        <!-- 表格形态：字段映射（enabled / embedding 单选 / filterable） -->
        <a-form-item v-if="form.type === 2 && form.kb_format === 'table'" :label="t('kbMgmt.schemaConfig')">
          <a-alert class="kb-manager__tip" type="info" :message="t('kbMgmt.schemaConfigHint')" show-icon />
          <div v-for="(f, i) in form.schema_config" :key="i" class="kb-manager__field">
            <a-input v-model:value="f.name" :placeholder="t('kbMgmt.fieldName')" style="width: 40%" />
            <a-select v-model:value="f.type" style="width: 25%">
              <a-select-option value="string">{{ t('kbMgmt.typeString') }}</a-select-option>
              <a-select-option value="number">{{ t('kbMgmt.typeNumber') }}</a-select-option>
              <a-select-option value="boolean">{{ t('kbMgmt.typeBoolean') }}</a-select-option>
            </a-select>
            <a-checkbox v-model:checked="f.filterable">{{ t('kbMgmt.filterable') }}</a-checkbox>
            <a-radio :checked="f.embedding" @change="setEmbedField(i)">{{ t('kbMgmt.embedField') }}</a-radio>
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { createKnowledge, listKnowledges, listCategories, updateKnowledge } from '@/api/wiki'
import { createProxyEndpoint } from '@/api/kb'
import KbDocumentPane from './kb/KbDocumentPane.vue'
import ExternalLinkPane from './kb/ExternalLinkPane.vue'
import WikiHome from '@/views/kms/wiki/index.vue'

const { t } = useI18n()
const activeType = ref('2')
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
const form = reactive({
  name: '',
  description: '',
  type: 2,
  kb_format: 'document' as string | null,
  index_mode: 'high_quality',
  multimodal_enabled: false,
  embedding_model: '' as string,
  category_id: null as number | null,
  schema_config: [] as { name: string; type: string; filterable: boolean; embedding: boolean }[],
  endpoint: { endpoint_url: '', auth_key: '', index_name: '' },
})

/** 多模态仅文搜图（D9），要求嵌入模型是 Vision 系列 */
const isVisionModel = computed(() => /vl|vision|multimodal/.test((form.embedding_model || '').toLowerCase()))

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

/** 被嵌入字段单选 */
function setEmbedField(i: number) {
  form.schema_config.forEach((f, idx) => {
    f.embedding = idx === i
  })
}

/** 左侧类别树：类别为父节点，知识库作为叶子挂到所属类别下 */
function rebuildTree() {
  const typeKbs = knowledges.value.filter((k) => String(k.type) === activeType.value)
  const nodeMap = new Map<number, any>()
  const roots: any[] = []

  const ensureNode = (c: any): any => {
    if (nodeMap.has(c.id)) return nodeMap.get(c.id)
    const node = { key: 'c-' + c.id, title: c.name, type: 'category', rawId: c.id, isLeaf: false, children: [] }
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
    const leaf = { key: 'k-' + k.id, title: k.name, type: 'kb', rawId: k.id, isLeaf: true }
    const parent = k.category_id != null ? nodeMap.get(k.category_id) : null
    if (parent) parent.children.push(leaf)
    else uncategorized.push(leaf)
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
      children: uncategorized,
    })
  }
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
  form.type = Number(activeType.value)
  form.kb_format = form.type === 2 ? 'document' : form.type === 3 ? 'proxy' : null
  form.index_mode = 'high_quality'
  form.multimodal_enabled = false
  form.embedding_model = ''
  form.schema_config = []
  form.endpoint = { endpoint_url: '', auth_key: '', index_name: '' }
}

function openCreate() {
  editingId.value = null
  resetForm()
  // 默认归属到当前选中的类别（spec 知识库管理）
  form.category_id = selectedCategoryId.value
  createOpen.value = true
}

function openEdit() {
  const kb = knowledges.value.find((k) => k.id === selectedId.value)
  if (!kb) return
  editingId.value = kb.id
  form.name = kb.name
  form.description = kb.description || ''
  form.type = Number(kb.type || activeType.value)
  form.kb_format = kb.kb_format || (form.type === 2 ? 'document' : form.type === 3 ? 'proxy' : null)
  form.index_mode = kb.index_mode || 'high_quality'
  form.multimodal_enabled = !!kb.multimodal_enabled
  form.embedding_model = kb.pipeline_config?.embedding?.model || ''
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
    // 表格：被嵌入字段必须唯一且已命名
    if (form.type === 2 && form.kb_format === 'table') {
      const fields = form.schema_config.filter((f) => f.name.trim())
      const embeddeds = fields.filter((f) => f.embedding)
      if (!fields.length || embeddeds.length !== 1) {
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
        // 嵌入模型经 pipeline_config.embedding 下发（D8 原生键名）
        pipeline_config: form.embedding_model
          ? { embedding: { model: form.embedding_model } }
          : undefined,
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

onMounted(load)

// 切换顶部形态标签时，按当前类型重建左侧类别树
watch(activeType, () => {
  selectedId.value = null
  selectedCategoryId.value = null
  rebuildTree()
})
</script>

<style scoped>
.kb-manager {
  padding: 8px 0;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

/* 主体两栏撑满剩余高度：左栏类别树满高度到底部 */
.kb-manager__body {
  flex: 1;
  min-height: 0;
}
.kb-manager__side {
  display: flex;
  flex-direction: column;
  min-height: 0;
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
</style>
