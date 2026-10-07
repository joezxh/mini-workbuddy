<template>
  <div class="kb-manager">
    <a-tabs v-model:activeKey="activeType">
      <a-tab-pane key="1" :tab="t('kmsWiki.title')" />
      <a-tab-pane key="2" :tab="t('kbMgmt.generalKb')" />
      <a-tab-pane key="3" :tab="t('kbMgmt.externalKb')" />
    </a-tabs>

    <a-row v-if="activeType !== '1'" :gutter="16">
      <a-col :span="6">
        <a-card :title="t('wikiMgmt.tabCategory')" size="small">
          <template #extra>
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
      <a-col :span="18">
        <KbDocumentPane v-if="activeType === '2' && selectedId" :knowledge-id="selectedId" />
        <a-empty v-else-if="activeType === '2'" :description="t('kbMgmt.selectKbFirst')" />
        <ExternalLinkPane v-else />
      </a-col>
    </a-row>
    <WikiHome v-else embedded />

    <!-- 新建知识库向导（spec §3.1 / §10.2） -->
    <a-modal
      v-model:open="createOpen"
      :title="t('kbMgmt.createWizard')"
      @ok="submitCreate"
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
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { createKnowledge, listKnowledges } from '@/api/wiki'
import { createProxyEndpoint } from '@/api/kb'
import KbDocumentPane from './kb/KbDocumentPane.vue'
import ExternalLinkPane from './kb/ExternalLinkPane.vue'
import WikiHome from '@/views/kms/wiki/index.vue'

const { t } = useI18n()
const activeType = ref('2')
const loading = ref(false)
const knowledges = ref<any[]>([])
const selectedId = ref<number | null>(null)

const treeData = ref<any[]>([])

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

function rebuildTree() {
  treeData.value = knowledges.value
    .filter((k) => String(k.type) === activeType.value)
    .map((k) => ({ key: String(k.id), title: k.name, isLeaf: true }))
}

function onSelectKnowledge(_keys: unknown, info: any) {
  selectedId.value = Number(info.node.key)
}

function openCreate() {
  form.name = ''
  form.description = ''
  form.type = Number(activeType.value)
  form.kb_format = form.type === 2 ? 'document' : form.type === 3 ? 'proxy' : null
  form.index_mode = 'high_quality'
  form.multimodal_enabled = false
  form.embedding_model = ''
  form.schema_config = []
  form.endpoint = { endpoint_url: '', auth_key: '', index_name: '' }
  createOpen.value = true
}

async function submitCreate() {
  if (!form.name.trim()) {
    message.warning(t('kbMgmt.nameRequired'))
    return
  }
  // 多模态强制校验 Vision 嵌入模型（spec §10.6）
  if (form.type === 2 && form.kb_format === 'document' && form.multimodal_enabled && !isVisionModel.value) {
    message.warning(t('kbMgmt.visionModelRequired'))
    return
  }
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

  creating.value = true
  try {
    const res: any = await createKnowledge({
      name: form.name.trim(),
      description: form.description || undefined,
      type: form.type,
      kb_format: form.kb_format,
      index_mode: form.type === 2 ? form.index_mode : undefined,
      multimodal_enabled: form.type === 2 ? form.multimodal_enabled : undefined,
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
    const res: any = await listKnowledges()
    knowledges.value = res.items || res || []
    rebuildTree()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.kb-manager {
  padding: 8px 0;
}
.kb-manager__tip {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
</style>
