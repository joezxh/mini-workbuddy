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
            <a-form-item :label="t('kmsWiki.body')">
              <a-textarea
                v-model:value="article.content"
                :rows="20"
                :placeholder="t('kmsWiki.bodyPlaceholder')"
                style="font-family: monospace"
              />
            </a-form-item>
            <a-form-item :label="t('kmsWiki.changeNote')">
              <a-input v-model:value="changeNote" :placeholder="t('kmsWiki.changeNotePlaceholder')" />
            </a-form-item>
          </a-form>
        </a-card>
      </a-col>

      <a-col :span="6">
        <!-- 分类 -->
        <a-card :title="t('wikiMgmt.tabCategory')" size="small">
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
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { getArticleBySlug, updateArticle, listCategories } from '@/api/wiki'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const article = ref<any>(null)
const categories = ref<any[]>([])
const changeNote = ref('')
const saving = ref(false)

onMounted(async () => {
  await loadArticle()
  await loadCategories()
})

async function loadArticle() {
  const articleId = route.params.id as string
  // 先通过列表找到 slug, 或直接通过 ID 获取
  // 由于编辑页面用 ID, 但 API 用 slug, 这里做一个适配
  try {
    // 尝试通过 API 获取 (需要先知道 slug)
    // 简化: 使用 list API 按 ID 查找
    const { listArticles } = await import('@/api/wiki')
    const res = await listArticles({ page: 1, page_size: 1000 })
    const found = (res.data.items || []).find((a: any) => a.id === Number(articleId))
    if (found) {
      // 获取完整文章
      const detailRes = await getArticleBySlug(found.slug)
      article.value = detailRes.data
    } else {
      message.error(t('kmsWiki.notFound'))
      router.push('/wiki')
    }
  } catch (e) {
    message.error(t('wikiMgmt.art.loadFailed'))
    router.push('/wiki')
  }
}

async function loadCategories() {
  try {
    const res = await listCategories()
    categories.value = res.data || []
  } catch (e) {
    // 分类加载失败不阻断
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
      category_id: article.value.category_id,
      tags: article.value.tags || [],
      owl_class_uris: article.value.owl_class_uris || [],
      status: article.value.status,
      change_note: changeNote.value || undefined,
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
