<template>
  <div class="article-edit" v-if="article">
    <div class="edit-header">
      <a-breadcrumb>
        <a-breadcrumb-item><a @click="$router.push('/wiki')">{{ t('kmsWiki.title') }}</a></a-breadcrumb-item>
        <a-breadcrumb-item>
          <a @click="$router.push(`/wiki/${article.slug}`)">{{ article.title }}</a>
        </a-breadcrumb-item>
        <a-breadcrumb-item>{{ t('common.edit') }}</a-breadcrumb-item>
      </a-breadcrumb>
      <div class="edit-actions">
        <a-button @click="$router.back()">{{ t('common.cancel') }}</a-button>
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
      </a-col>
    </a-row>
  </div>
  <a-spin v-else style="display: flex; justify-content: center; padding: 100px" />
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { getArticle, updateArticle, listCategories, listKnowledges } from '@/api/wiki'
import DocUploadPanel from './components/DocUploadPanel.vue'
import ArticleExtractedFields from './components/ArticleExtractedFields.vue'

interface FieldDef {
  key: string
  label: string
  type: 'text' | 'textarea' | 'select' | 'tags' | 'sources'
  options?: string[]
}

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const article = ref<any>(null)
const categories = ref<any[]>([])
const knowledges = ref<any[]>([])
const changeNote = ref('')
const saving = ref(false)

/** 上传文档后提取到的 OKF 字段（okf_type / resource / sources），动态渲染 */
const extracted = ref<Record<string, any>>({})
const extractedFields = ref<FieldDef[]>([])

const OKF_TYPES = ['concept', 'howto', 'reference', 'decision', 'metric']
const OKF_LABELS: Record<string, string> = {
  concept: t('kmsWiki.okfConcept'),
  howto: t('kmsWiki.okfHowto'),
  reference: t('kmsWiki.okfReference'),
  decision: t('kmsWiki.okfDecision'),
  metric: t('kmsWiki.okfMetric'),
}

/** 正文为空时才显示上传入口，避免覆盖已有内容 */
const hasContent = computed(() => !!article.value?.content?.trim())

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
  const articleId = Number(route.params.id)
  if (!Number.isFinite(articleId) || articleId <= 0) {
    message.error(t('kmsWiki.notFound'))
    router.push('/wiki')
    return
  }
  try {
    // 直接按 ID 获取（后端 GET /wiki/articles/{id}，G4：消除 page_size=1000 列表遍历 hack）
    article.value = await getArticle(articleId)
    // 回填已保存的 OKF 字段，便于继续编辑
    extracted.value = {
      okf_type: article.value.okf_type ?? null,
      resource: article.value.resource ?? '',
      sources: article.value.sources || [],
    }
    extractedFields.value = buildFieldDefs(article.value)
  } catch (e) {
    message.error(t('wikiMgmt.art.loadFailed'))
    router.push('/wiki')
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
    })
    message.success(t('wikiMgmt.saved'))
    router.push(`/wiki/${article.value.slug}`)
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
</style>
