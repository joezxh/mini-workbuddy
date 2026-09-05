<template>
  <div class="wiki-index">
    <div class="wiki-header">
      <h2>知识库 Wiki</h2>
      <div class="wiki-actions">
        <a-input-search
          v-model:value="searchQuery"
          placeholder="搜索文章..."
          style="width: 300px"
          @search="handleSearch"
          allow-clear
        />
        <a-button type="primary" @click="showCreateModal = true">
          <template #icon><PlusOutlined /></template>
          新建文章
        </a-button>
      </div>
    </div>

    <a-row :gutter="16">
      <!-- 左侧分类树 -->
      <a-col :span="6">
        <a-card title="分类" size="small">
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
                :description="item.summary || '暂无摘要'"
              >
                <template #avatar>
                  <a-avatar style="background-color: #1890ff">
                    {{ (item.title || '?')[0] }}
                  </a-avatar>
                </template>
              </a-list-item-meta>
              <div class="article-meta">
                <a-tag v-for="tag in (item.tags || []).slice(0, 3)" :key="tag">{{ tag }}</a-tag>
                <span class="meta-text">v{{ item.version }} · {{ item.view_count }} 次浏览 · {{ formatDate(item.updated_at) }}</span>
              </div>
              <template #actions>
                <a @click="viewArticle(item.slug)">查看</a>
                <a @click="editArticle(item.id)">编辑</a>
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
      title="新建文章"
      @ok="handleCreate"
      :confirm-loading="creating"
    >
      <a-form layout="vertical">
        <a-form-item label="标题" required>
          <a-input v-model:value="newArticle.title" placeholder="文章标题" />
        </a-form-item>
        <a-form-item label="Slug">
          <a-input v-model:value="newArticle.slug" placeholder="URL 标识 (留空自动生成)" />
        </a-form-item>
        <a-form-item label="摘要">
          <a-textarea v-model:value="newArticle.summary" :rows="2" placeholder="文章摘要" />
        </a-form-item>
        <a-form-item label="分类">
          <a-tree-select
            v-model:value="newArticle.category_id"
            :tree-data="categoryTree"
            :field-names="{ label: 'name', value: 'id', children: 'children' }"
            placeholder="选择分类"
            allow-clear
          />
        </a-form-item>
        <a-form-item label="标签">
          <a-select
            v-model:value="newArticle.tags"
            mode="tags"
            placeholder="输入标签后回车"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { PlusOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { listArticles, createArticle, listCategories, searchArticles } from '@/api/wiki'
import dayjs from 'dayjs'

const router = useRouter()

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
    message.error('加载文章失败')
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
    message.error('搜索失败')
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!newArticle.value.title.trim()) {
    message.warning('请输入标题')
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
    message.success('创建成功')
    showCreateModal.value = false
    newArticle.value = { title: '', slug: '', summary: '', category_id: null, tags: [] }
    loadArticles()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '创建失败')
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
  color: #999;
  font-size: 12px;
  margin-left: 8px;
}
</style>
