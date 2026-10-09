<template>
  <div class="article-edit" v-if="article">
    <div class="edit-header">
      <a-breadcrumb>
        <a-breadcrumb-item><a @click="backToList">{{ t('kmsWiki.title') }}</a></a-breadcrumb-item>
        <a-breadcrumb-item>
          <a @click="openView">{{ article.title }}</a>
        </a-breadcrumb-item>
        <a-breadcrumb-item>{{ t('common.edit') }}</a-breadcrumb-item>
      </a-breadcrumb>
      <div class="edit-actions">
        <a-button @click="backToList">{{ t('common.cancel') }}</a-button>
        <a-button type="primary" @click="handleSave" :loading="saving">
          {{ t('common.save') }}
        </a-button>
      </div>
    </div>

    <a-row :gutter="24">
      <a-col :span="18">
        <a-card>
          <a-form layout="vertical">
            <a-form-item :label="t('kbMgmt.common.title')">
              <a-input v-model:value="article.title" size="large" :placeholder="t('kmsWiki.titlePlaceholder')" />
            </a-form-item>
            <a-form-item :label="t('kmsWiki.summary')">
              <a-textarea
                v-model:value="article.summary"
                :rows="2"
                :placeholder="t('kmsWiki.summaryPlaceholder')"
              />
            </a-form-item>
            <a-form-item v-if="!hasContent" :label="t('kmsWiki.docUpload')">
              <DocUploadPanel @converted="onConverted" />
            </a-form-item>
            <a-form-item :label="t('kmsWiki.body')">
              <a-textarea
                v-model:value="article.content"
                :rows="20"
                :placeholder="t('kmsWiki.bodyPlaceholder')"
                style="font-family: monospace"
              />
            </a-form-item>
            <a-form-item v-if="extractedFields.length">
              <ArticleExtractedFields v-model:values="extracted" :fields="extractedFields" />
            </a-form-item>
            <a-form-item :label="t('kmsWiki.changeNote')">
              <a-input v-model:value="changeNote" :placeholder="t('kmsWiki.changeNotePlaceholder')" />
            </a-form-item>
          </a-form>
        </a-card>
      </a-col>

      <a-col :span="6">
        <!-- 所属知识库 -->
        <a-card :title="t('kmsWiki.articleKb')" size="small">
          <a-select
            v-model:value="article.knowledge_id"
            :placeholder="t('kmsWiki.articleKbPlaceholder')"
            allow-clear
            show-search
            option-filter-prop="label"
            style="width: 100%"
          >
            <a-select-option v-for="kb in knowledges" :key="kb.id" :value="kb.id">
              {{ kb.name }}
            </a-select-option>
          </a-select>
        </a-card>

        <!-- 分类 -->
        <a-card :title="t('wikiMgmt.tabCategory')" size="small" style="margin-top: 16px">
          <a-tree-select
            v-model:value="article.category_id"
            :tree-data="categories"
            :field-names="{ label: 'name', value: 'id', children: 'children' }"
            :placeholder="t('kmsWiki.selectCategory')"
            allow-clear
            style="width: 100%"
          />
        </a-card>

        <!-- 标签 -->
        <a-card :title="t('kmsWiki.tags')" size="small" style="margin-top: 16px">
          <a-select
            v-model:value="article.tags"
            mode="tags"
            :placeholder="t('kmsWiki.tagsInputPlaceholder')"
            style="width: 100%"
          />
        </a-card>

        <!-- OWL 类 -->
        <a-card :title="t('kmsWiki.owlClasses')" size="small" style="margin-top: 16px">
          <a-select
            v-model:value="article.owl_class_uris"
            mode="tags"
            placeholder="OWL Class URI"
            style="width: 100%"
          />
          <div class="hint-text">{{ t('kmsWiki.owlHint') }}</div>
        </a-card>

        <!-- 状态 -->
        <a-card :title="t('kmsWiki.publishStatus')" size="small" style="margin-top: 16px">
          <a-radio-group v-model:value="article.status">
            <a-radio :value="0">{{ t('wikiMgmt.art.draft') }}</a-radio>
            <a-radio :value="1">{{ t('wikiMgmt.art.published') }}</a-radio>
            <a-radio :value="-1">{{ t('wikiMgmt.art.archived') }}</a-radio>
          </a-radio-group>
        </a-card>

        <!-- OKF §5.2 / §5.5：验证记录与过期时间 -->
        <a-card :title="t('kmsWiki.okfProvenance')" size="small" style="margin-top: 16px">
          <div class="field-label">{{ t('kmsWiki.okfVerified') }}</div>
          <div v-for="(v, i) in article.verified || []" :key="i" class="verified-row">
            <a-input v-model:value="v.by" :placeholder="t('kmsWiki.okfVerifiedBy')" style="flex: 1" />
            <a-input v-model:value="v.at" placeholder="2026-01-01T00:00:00Z" style="flex: 1" />
            <a-button danger size="small" @click="removeVerified(i)">
              {{ t('common.delete') }}
            </a-button>
          </div>
          <a-button size="small" block @click="addVerified">
            <template #icon><PlusOutlined /></template>{{ t('kmsWiki.okfAddVerified') }}
          </a-button>

          <div class="field-label" style="margin-top: 12px">{{ t('kmsWiki.okfStaleAfter') }}</div>
          <a-date-picker
            v-model:value="staleAfterValue"
            show-time
            style="width: 100%"
            :placeholder="t('kmsWiki.okfStaleAfterHint')"
          />
          <div class="hint-text">{{ t('kmsWiki.okfStaleAfterHint') }}</div>
        </a-card>

        <!-- OKF §10 Attested Computation：仅当 type=Attested Computation 时编辑 -->
        <a-card
          :title="t('kmsWiki.okfAttestedComputation')"
          size="small"
          style="margin-top: 16px"
          v-if="extracted.okf_type === 'Attested Computation'"
        >
          <div class="field-label">{{ t('kmsWiki.okfRuntime') }} <span class="req">*</span></div>
          <a-select
            v-model:value="attested.runtime"
            :placeholder="t('kmsWiki.okfRuntimeHint')"
            style="width: 100%"
          >
            <a-select-option v-for="r in RUNTIMES" :key="r" :value="r">{{ r }}</a-select-option>
          </a-select>

          <div class="field-label" style="margin-top: 12px">{{ t('kmsWiki.okfParameters') }}</div>
          <div v-for="(p, i) in (attested.parameters || [])" :key="i" class="param-row">
            <a-input v-model:value="p.name" :placeholder="t('kmsWiki.okfParamName')" style="flex: 1" />
            <a-input v-model:value="p.type" :placeholder="t('kmsWiki.okfParamType')" style="flex: 1" />
            <a-checkbox v-model:checked="p.required">{{ t('kmsWiki.okfParamRequired') }}</a-checkbox>
            <a-button danger size="small" @click="removeParam(i)">
              {{ t('common.delete') }}
            </a-button>
          </div>
          <a-button size="small" block @click="addParam">
            <template #icon><PlusOutlined /></template>{{ t('kmsWiki.okfAddParam') }}
          </a-button>

          <div class="field-label" style="margin-top: 12px">{{ t('kmsWiki.okfComputation') }}</div>
          <a-input
            v-model:value="attested.computation"
            :placeholder="t('kmsWiki.okfComputationHint')"
            style="width: 100%"
          />

          <div class="field-label" style="margin-top: 12px">{{ t('kmsWiki.okfExecutorResource') }}</div>
          <a-input
            v-model:value="attested.executor.resource"
            :placeholder="t('kmsWiki.okfExecutorResourceHint')"
            style="width: 100%"
          />
          <div class="field-label" style="margin-top: 12px">{{ t('kmsWiki.okfExecutorReceipt') }}</div>
          <a-select
            v-model:value="attested.executor.receipt"
            mode="tags"
            :placeholder="t('kmsWiki.okfExecutorReceiptHint')"
            style="width: 100%"
          />

          <div class="field-label" style="margin-top: 12px">{{ t('kmsWiki.okfAttesterResource') }}</div>
          <a-input
            v-model:value="attested.attester.resource"
            :placeholder="t('kmsWiki.okfAttesterResourceHint')"
            style="width: 100%"
          />
          <div class="hint-text">{{ t('kmsWiki.okfAttestedHint') }}</div>
        </a-card>
      </a-col>
    </a-row>
  </div>
  <a-spin v-else style="display: flex; justify-content: center; padding: 100px" />
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { getArticle, updateArticle, listCategories, listKnowledges } from '@/api/wiki'
import { PlusOutlined } from '@ant-design/icons-vue'
import dayjs from 'dayjs'
import DocUploadPanel from './components/DocUploadPanel.vue'
import ArticleExtractedFields from './components/ArticleExtractedFields.vue'
import { openDynamicTab, closeShellTab, setShellTabTitle } from '@/utils/shellTab'

interface FieldDef {
  key: string
  label: string
  type: 'text' | 'textarea' | 'select' | 'tags' | 'sources'
  options?: string[]
  optionLabels?: Record<string, string>
}

const route = useRoute()
const { t } = useI18n()
const props = defineProps<{ id?: number }>()
const articleId = computed(() => {
  const v = props.id ?? Number(route.params.id)
  return Number.isFinite(v) ? v : 0
})
const editKey = computed(() => `kg-wiki-edit:${articleId.value}`)

const article = ref<any>(null)
const categories = ref<any[]>([])
const knowledges = ref<any[]>([])
const changeNote = ref('')
const saving = ref(false)

/** 上传文档后提取到的 OKF 字段（okf_type / resource / sources），动态渲染 */
const extracted = ref<Record<string, any>>({})
const extractedFields = ref<FieldDef[]>([])

/** OKF §10 Attested Computation 编辑态（仅 type=Attested Computation 时生效） */
const attested = ref<any>({
  runtime: undefined,
  parameters: [] as { name: string; type: string; required: boolean }[],
  computation: '',
  executor: { resource: '', receipt: [] as string[] },
  attester: { resource: '' },
})

function loadAttested(src: any) {
  if (!src) {
    return {
      runtime: undefined,
      parameters: [] as { name: string; type: string; required: boolean }[],
      computation: '',
      executor: { resource: '', receipt: [] as string[] },
      attester: { resource: '' },
    }
  }
  return {
    runtime: src.runtime,
    parameters: Array.isArray(src.parameters)
      ? src.parameters.map((p: any) => ({ name: p?.name ?? '', type: p?.type ?? '', required: !!p?.required }))
      : [],
    computation: src.computation || '',
    executor: { resource: src.executor?.resource || '', receipt: src.executor?.receipt || [] },
    attester: { resource: src.attester?.resource || '' },
  }
}

function addParam() {
  if (!attested.value.parameters) attested.value.parameters = []
  attested.value.parameters.push({ name: '', type: '', required: false })
}

function removeParam(index: number) {
  attested.value.parameters?.splice(index, 1)
}

const OKF_TYPES = ['concept', 'howto', 'reference', 'decision', 'metric', 'Attested Computation']
const OKF_LABELS: Record<string, string> = {
  concept: t('kmsWiki.okfConcept'),
  howto: t('kmsWiki.okfHowto'),
  reference: t('kmsWiki.okfReference'),
  decision: t('kmsWiki.okfDecision'),
  metric: t('kmsWiki.okfMetric'),
  'Attested Computation': t('kmsWiki.okfAttestedComputation'),
}

/** §10 常见 runtime 选项（spec §10.2） */
const RUNTIMES = ['bigquery', 'postgres', 'dbt', 'python', 'Looker']

/** 正文为空时才显示上传入口，避免覆盖已有内容 */
const hasContent = computed(() => !!article.value?.content?.trim())

/** OKF §5.5 过期时间：a-date-picker 绑定 dayjs，保存时转 ISO 8601 UTC */
const staleAfterValue = ref<any>(null)

function addVerified() {
  if (!article.value.verified) article.value.verified = []
  article.value.verified.push({ by: '', at: '' })
}

function removeVerified(index: number) {
  article.value.verified?.splice(index, 1)
}

/** 仅渲染「有值」的字段 —— 提取到什么就补什么 */
function buildFieldDefs(src: { okf_type?: string | null; resource?: string | null; sources?: any[] }): FieldDef[] {
  const defs: FieldDef[] = []
  if (src.okf_type) {
    defs.push({
      key: 'okf_type',
      label: t('kmsWiki.okfType'),
      type: 'select',
      options: OKF_TYPES,
      optionLabels: OKF_LABELS,
    })
  }
  if (src.resource) defs.push({ key: 'resource', label: t('kmsWiki.resource'), type: 'text' })
  if (src.sources?.length) defs.push({ key: 'sources', label: t('kmsWiki.sources'), type: 'sources' })
  return defs
}

/** 上传转换完成：回填正文/标题/摘要/标签，并补出 OKF 字段 */
function onConverted(res: any) {
  if (!article.value) return
  article.value.content = res.markdown
  if (!article.value.title?.trim() && res.title) article.value.title = res.title
  if (!article.value.summary?.trim() && res.summary) article.value.summary = res.summary
  if (!(article.value.tags || []).length && res.tags?.length) article.value.tags = res.tags
  extracted.value = {
    okf_type: res.okf_type ?? null,
    resource: res.resource ?? '',
    sources: res.sources || [],
  }
  extractedFields.value = buildFieldDefs(res)
}

onMounted(async () => {
  await loadArticle()
  await Promise.all([loadCategories(), loadKnowledges()])
})

async function loadArticle() {
  if (!articleId.value || articleId.value <= 0) {
    message.error(t('kmsWiki.notFound'))
    closeShellTab(editKey.value, '/wiki')
    return
  }
  try {
    // 直接按 ID 获取（后端 GET /wiki/articles/{id}，G4：消除 page_size=1000 列表遍历 hack）
    article.value = await getArticle(articleId.value)
    setShellTabTitle(editKey.value, article.value.title || t('common.edit'))
    // 回填已保存的 OKF 字段，便于继续编辑
    extracted.value = {
      okf_type: article.value.okf_type ?? null,
      resource: article.value.resource ?? '',
      sources: article.value.sources || [],
    }
    // OKF §5.2 / §5.5 回填
    article.value.verified = article.value.verified || []
    staleAfterValue.value = article.value.stale_after ? dayjs(article.value.stale_after) : null
    // OKF §10 Attested Computation 回填（仅该 type 才渲染编辑器）
    attested.value = loadAttested(article.value.attested_computation)
    extractedFields.value = buildFieldDefs(article.value)
  } catch (e) {
    message.error(t('wikiMgmt.art.loadFailed'))
    closeShellTab(editKey.value, '/wiki')
  }
}

async function loadCategories() {
  try {
    const res = await listCategories()
    categories.value = res || []
  } catch (e) {
    // 分类加载失败不阻断
  }
}

async function loadKnowledges() {
  try {
    const res = await listKnowledges()
    knowledges.value = res || []
  } catch (e) {
    // 知识库加载失败不阻断
  }
}

// ── 导航：保持在控制台 Tab 系统内，避免跳到外壳独立路由 ──
function backToList() {
  // 关闭当前编辑 Tab，回到上一页（外壳不可用时回退 /wiki）
  closeShellTab(editKey.value, '/wiki')
}

function openView() {
  if (!article.value?.slug) return
  const slug = article.value.slug
  closeShellTab(editKey.value)
  openDynamicTab(
    { key: `kg-wiki-view:${slug}`, component: 'kg-wiki-view', titleKey: 'kmsWiki.articleView', icon: 'ReadOutlined', props: { slug } },
    `/wiki/${slug}`,
  )
}

async function handleSave() {
  if (!article.value) return
  if (!article.value.title?.trim()) {
    message.warning(t('kmsWiki.titleRequired'))
    return
  }
  saving.value = true
  try {
    await updateArticle(article.value.id, {
      title: article.value.title,
      content: article.value.content,
      summary: article.value.summary || undefined,
      category_id: article.value.category_id,
      knowledge_id: article.value.knowledge_id ?? undefined,
      tags: article.value.tags || [],
      owl_class_uris: article.value.owl_class_uris || [],
      status: article.value.status,
      change_note: changeNote.value || undefined,
      okf_type: extracted.value.okf_type ?? undefined,
      resource: extracted.value.resource || undefined,
      sources: extracted.value.sources?.length ? extracted.value.sources : undefined,
      // OKF §5.2 / §5.5：验证记录与绝对过期时间
      verified: (article.value.verified || []).filter((v: any) => v?.by),
      stale_after: staleAfterValue.value
        ? staleAfterValue.value.toISOString()
        : undefined,
      // OKF §10 Attested Computation（仅该 type 才随文保存；其余类型不写，避免误带契约字段）
      attested_computation:
        extracted.value.okf_type === 'Attested Computation' ? attested.value : undefined,
    })
    message.success(t('wikiMgmt.saved'))
    const slug = article.value.slug
    // 关闭编辑 Tab，打开文章查看 Tab（保持在控制台 Tab 系统内）
    closeShellTab(editKey.value)
    openDynamicTab(
      { key: `kg-wiki-view:${slug}`, component: 'kg-wiki-view', titleKey: 'kmsWiki.articleView', icon: 'ReadOutlined', props: { slug } },
      `/wiki/${slug}`,
    )
  } catch (e: any) {
    message.error(e.response?.data?.detail || t('wikiMgmt.saveFailed'))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.article-edit {
  padding: 24px;
}
.edit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.edit-actions {
  display: flex;
  gap: 8px;
}
.hint-text {
  font-size: 12px;
  color: var(--fg-muted);
  margin-top: 4px;
}

.field-label {
  font-size: 12px;
  color: var(--fg-muted);
  margin-bottom: 6px;
}

.verified-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.param-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.req {
  color: #ff4d4f;
}
</style>
