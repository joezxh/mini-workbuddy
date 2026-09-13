<template>
  <div class="wiki-index">
    <div class="wiki-header">
      <h2>{{ t('kmsWiki.title') }}</h2>
      <div class="wiki-actions">
        <a-input-search
          v-model:value="searchQuery"
          :placeholder="t('kmsWiki.searchPlaceholder')"
          style="width: 300px"
          @search="handleSearch"
          allow-clear
        />
        <a-button type="primary" @click="showCreateModal = true">
          <template #icon><PlusOutlined /></template>
          {{ t('kmsWiki.createArticle') }}
        </a-button>
      </div>
    </div>

    <a-row :gutter="16">
      <!-- 左侧分类树 -->
      <a-col :span="6">
        <a-card :title="t('wikiMgmt.tabCategory')" size="small">
          <a-tree
            :tree-data="categoryTree"
            :field-names="{ title: 'name', key: 'id', children: 'children' }"
            @select="handleCategorySelect"
            default-expand-all
          />
        </a-card>
      </a-col>

      <!-- 右侧文章列表 -->
      <a-col :span="18">
        <a-list
          :data-source="articles"
          :loading="loading"
          item-layout="vertical"
        >
          <template #renderItem="{ item }">
            <a-list-item>
              <a-list-item-meta
                :title="item.title"
                :description="item.summary || t('kmsWiki.noSummary')"
              >
                <template #avatar>
                  <a-avatar style="background-color: var(--accent)">
                    {{ (item.title || '?')[0] }}
                  </a-avatar>
                </template>
              </a-list-item-meta>
              <div class="article-meta">
                <a-tag v-for="tag in (item.tags || []).slice(0, 3)" :key="tag">{{ tag }}</a-tag>
                <span class="meta-text">v{{ item.version }} · {{ t('kmsWiki.views', { count: item.view_count }) }} · {{ formatDate(item.updated_at) }}</span>
              </div>
              <template #actions>
                <a @click="viewArticle(item.slug)">{{ t('wikiMgmt.art.view') }}</a>
                <a @click="editArticle(item.id)">{{ t('common.edit') }}</a>
              </template>
            </a-list-item>
          </template>
        </a-list>

        <a-pagination
          v-if="total > pageSize"
          :current="page"
          :total="total"
          :page-size="pageSize"
          @change="handlePageChange"
          style="margin-top: 16px; text-align: right"
        />
      </a-col>
    </a-row>

    <!-- 新建文章弹窗 -->
    <a-modal
      v-model:open="showCreateModal"
      :title="t('kmsWiki.createArticle')"
      @ok="handleCreate"
      :confirm-loading="creating"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('kbMgmt.common.title')" required>
          <a-input v-model:value="newArticle.title" :placeholder="t('kmsWiki.titlePlaceholder')" />
        </a-form-item>
        <a-form-item label="Slug">
          <a-input v-model:value="newArticle.slug" :placeholder="t('kmsWiki.slugPlaceholder')" />
        </a-form-item>
        <a-form-item :label="t('kmsWiki.summary')">
          <a-textarea v-model:value="newArticle.summary" :rows="2" :placeholder="t('kmsWiki.summaryPlaceholder')" />
        </a-form-item>
        <a-form-item :label="t('wikiMgmt.tabCategory')">
          <a-tree-select
            v-model:value="newArticle.category_id"
            :tree-data="categoryTree"
            :field-names="{ label: 'name', value: 'id', children: 'children' }"
            :placeholder="t('kmsWiki.selectCategory')"
            allow-clear
          />
        </a-form-item>
        <a-form-item :label="t('kmsWiki.tags')">
          <a-select
            v-model:value="newArticle.tags"
            mode="tags"
            :placeholder="t('kmsWiki.tagsPlaceholder')"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { PlusOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { listArticles, createArticle, listCategories, searchArticles } from '@/api/wiki'
import dayjs from 'dayjs'

const router = useRouter()
const { t } = useI18n()

const articles = ref<any[]>([])
const categoryTree = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)
const searchQuery = ref('')
const selectedCategoryId = ref<number | null>(null)

// 新建文章
const showCreateModal = ref(false)
const creating = ref(false)
const newArticle = ref({
  title: '',
  slug: '',
  summary: '',
  category_id: null as number | null,
  tags: [] as string[],
})

onMounted(() => {
  loadArticles()
  loadCategories()
})

async function loadArticles() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize }
    if (selectedCategoryId.value) params.category_id = selectedCategoryId.value
    const res = await listArticles(params)
    articles.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e: any) {
    message.error(t('wikiMgmt.art.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function loadCategories() {
  try {
    const res = await listCategories()
    categoryTree.value = res.data || []
  } catch (e) {
    // 分类加载失败不阻断
  }
}

function handleCategorySelect(keys: any) {
  selectedCategoryId.value = keys[0] || null
  page.value = 1
  loadArticles()
}

function handlePageChange(p: number) {
  page.value = p
  loadArticles()
}

async function handleSearch() {
  if (!searchQuery.value.trim()) {
    loadArticles()
    return
  }
  loading.value = true
  try {
    const res = await searchArticles(searchQuery.value)
    articles.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    message.error(t('kmsWiki.searchFailed'))
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!newArticle.value.title.trim()) {
    message.warning(t('kmsWiki.titleRequired'))
    return
  }
  creating.value = true
  try {
    const res = await createArticle({
      title: newArticle.value.title,
      slug: newArticle.value.slug || undefined,
      summary: newArticle.value.summary || undefined,
      category_id: newArticle.value.category_id || undefined,
      tags: newArticle.value.tags.length ? newArticle.value.tags : undefined,
    })
    message.success(t('kbMgmt.dataset.createSuccess'))
    showCreateModal.value = false
    newArticle.value = { title: '', slug: '', summary: '', category_id: null, tags: [] }
    loadArticles()
  } catch (e: any) {
    message.error(e.response?.data?.detail || t('kbMgmt.dataset.createFailed'))
  } finally {
    creating.value = false
  }
}

function viewArticle(slug: string) {
  router.push(`/wiki/${slug}`)
}

function editArticle(id: number) {
  router.push(`/wiki/edit/${id}`)
}

function formatDate(dateStr: string) {
  if (!dateStr) return ''
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm')
}
</script>

<style scoped>
.wiki-index {
  padding: 24px;
}
.wiki-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.wiki-actions {
  display: flex;
  gap: 12px;
}
.article-meta {
  margin-top: 8px;
}
.meta-text {
  color: var(--fg-muted);
  font-size: 12px;
  margin-left: 8px;
}
</style>
