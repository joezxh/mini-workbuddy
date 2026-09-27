<template>
  <div class="wiki-index">
    <div class="wiki-layout">
      <!-- 左栏：侧边栏（标题 + 操作入口 + 分类树） -->
      <aside class="wiki-side">
        <div class="wiki-side__head">
          <h2 class="wiki-side__title">{{ t('kmsWiki.title') }}</h2>
          <div class="wiki-side__actions">
            <a-tooltip :title="t('kmsWiki.addCategory')">
              <a-button class="wiki-side__icon-btn" size="small" @click="openCategoryModal('create')">
                <template #icon><PlusOutlined /></template>
              </a-button>
            </a-tooltip>
            <a-tooltip :title="t('kmsWiki.addKnowledge')">
              <a-button class="wiki-side__icon-btn" size="small" @click="openKnowledgeModal('create')">
                <template #icon><BookOutlined /></template>
              </a-button>
            </a-tooltip>
          </div>
        </div>
        <a-card size="small" class="wiki-side__tree">
          <a-tree
            :tree-data="treeData"
            :field-names="{ title: 'name', key: 'id', children: 'children' }"
            :selected-keys="selectedKeys"
            @select="handleCategorySelect"
            default-expand-all
          >
            <template #title="{ data }">
              <a-dropdown :trigger="['contextmenu']">
                <span class="cat-node">
                  <BookOutlined v-if="data.kind === 'knowledge'" class="kb-icon" />
                  {{ data.name }}
                </span>
                <template #overlay>
                  <a-menu @click="onMenuClick($event, data)">
                    <a-menu-item key="view">{{ t('kmsWiki.viewInfo') }}</a-menu-item>
                    <template v-if="data.kind === 'knowledge'">
                      <a-menu-item key="edit">{{ t('kmsWiki.editKnowledge') }}</a-menu-item>
                      <a-menu-item key="add-child">{{ t('kmsWiki.addChildCategory') }}</a-menu-item>
                      <a-menu-divider />
                      <a-menu-item key="delete" danger>{{ t('kmsWiki.deleteKnowledge') }}</a-menu-item>
                    </template>
                    <template v-else>
                      <a-menu-item key="add-child">{{ t('kmsWiki.addChildCategory') }}</a-menu-item>
                      <a-menu-item key="rename">{{ t('kmsWiki.renameCategory') }}</a-menu-item>
                      <a-menu-divider />
                      <a-menu-item key="delete" danger>{{ t('kmsWiki.deleteCategory') }}</a-menu-item>
                    </template>
                  </a-menu>
                </template>
              </a-dropdown>
            </template>
          </a-tree>
        </a-card>
      </aside>

      <!-- 右栏：内容主窗体（文章列表） -->
      <main class="wiki-main">
        <div class="wiki-main__toolbar">
          <a-input-search
            v-model:value="searchQuery"
            :placeholder="t('kmsWiki.searchPlaceholder')"
            style="width: 260px"
            @search="handleSearch"
            allow-clear
          />
          <a-space>
            <a-tooltip :title="t('kmsWiki.ragEntry')">
              <a-button @click="router.push('/wiki/rag')">
                <template #icon><ExperimentOutlined /></template>
              </a-button>
            </a-tooltip>
            <a-button type="primary" @click="showCreateModal = true">
              <template #icon><PlusOutlined /></template>
              {{ t('kmsWiki.createArticle') }}
            </a-button>
          </a-space>
        </div>

        <!-- 当前筛选条件（来自左栏选中节点） -->
        <div v-if="selectedNodeName" class="wiki-main__filter">
          <span class="wiki-main__filter-label">{{ t('kmsWiki.filterLabel') }}</span>
          <a-tag closable @close.prevent="clearFilter">{{ selectedNodeName }}</a-tag>
        </div>

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
      </main>
    </div>

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

    <!-- 新建/编辑分类弹窗 -->
    <a-modal
      v-model:open="categoryModal.open"
      :title="categoryModal.mode === 'rename' ? t('kmsWiki.renameCategory') : t('kmsWiki.addCategory')"
      :confirm-loading="categorySaving"
      @ok="submitCategory"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('kmsWiki.categoryName')" required>
          <a-input v-model:value="categoryModal.name" :placeholder="t('kmsWiki.categoryName')" />
        </a-form-item>
        <a-form-item :label="t('kmsWiki.categoryDesc')">
          <a-textarea v-model:value="categoryModal.description" :rows="2" />
        </a-form-item>
        <a-form-item :label="t('kmsWiki.categorySort')">
          <a-input-number v-model:value="categoryModal.sort_order" :min="0" style="width: 100%" />
        </a-form-item>
        <div v-if="categoryModal.parentName" class="category-parent-hint">
          {{ t('wikiMgmt.tabCategory') }}: {{ categoryModal.parentName }}
        </div>
      </a-form>
    </a-modal>

    <!-- 新建/编辑知识库弹窗 -->
    <a-modal
      v-model:open="knowledgeModal.open"
      :title="knowledgeModal.mode === 'edit' ? t('kmsWiki.editKnowledge') : t('kmsWiki.addKnowledge')"
      :confirm-loading="knowledgeSaving"
      @ok="submitKnowledge"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('kmsWiki.knowledgeName')" required>
          <a-input v-model:value="knowledgeModal.name" :placeholder="t('kmsWiki.knowledgeName')" />
        </a-form-item>
        <a-form-item :label="t('kmsWiki.categoryDesc')">
          <a-textarea v-model:value="knowledgeModal.description" :rows="2" />
        </a-form-item>
        <div class="category-parent-hint">{{ t('kmsWiki.knowledgeTypeHint') }}</div>
      </a-form>
    </a-modal>

    <!-- 节点信息查看弹窗（只读） -->
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
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { BookOutlined, ExperimentOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { message, Modal } from 'ant-design-vue'
import { listArticles, createArticle, createCategory, updateCategory, deleteCategory, listCategories, searchArticles, listKnowledges, createKnowledge, updateKnowledge, deleteKnowledge } from '@/api/wiki'
import dayjs from 'dayjs'

const router = useRouter()
const { t } = useI18n()

const articles = ref<any[]>([])
const categoryTree = ref<any[]>([])
const knowledges = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)
const searchQuery = ref('')

/** 左栏树选中项：kind=category 按分类过滤；kind=knowledge 按知识库过滤 */
const selectedKind = ref<'category' | 'knowledge' | null>(null)
const selectedId = ref<number | null>(null)

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
  loadTreeData()
})

async function loadArticles() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize }
    if (selectedKind.value === 'category' && selectedId.value) {
      params.category_id = selectedId.value
    } else if (selectedKind.value === 'knowledge' && selectedId.value) {
      params.knowledge_id = selectedId.value
    }
    const res = await listArticles(params)
    articles.value = res.items || []
    total.value = res.total || 0
  } catch (e: any) {
    message.error(t('wikiMgmt.art.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function loadCategories() {
  try {
    const res = await listCategories()
    categoryTree.value = res || []
  } catch (e) {
    // 分类加载失败不阻断
  }
}

async function loadKnowledges() {
  try {
    const res = await listKnowledges()
    knowledges.value = res || []
  } catch {
    knowledges.value = []
  }
}

/** 同时刷新分类与知识库 */
async function loadTreeData() {
  await Promise.all([loadCategories(), loadKnowledges()])
}

/**
 * 组合树：知识库节点（kind='knowledge'，key 为 'kb-{id}' 避免与分类 id 冲突）
 * 作为其下分类的父节点展示；未归属知识库的分类保持顶级。
 */
const treeData = computed(() => {
  const roots = categoryTree.value
  const kbNodes = knowledges.value.map((kb: any) => ({
    kind: 'knowledge',
    id: `kb-${kb.id}`,
    kbId: kb.id,
    name: kb.name,
    children: roots.filter((c: any) => c.knowledge_id === kb.id),
  }))
  const orphans = roots.filter((c: any) => !c.knowledge_id)
  return [...kbNodes, ...orphans]
})

// ── 分类管理（新建 / 重命名 / 删除） ──
const categoryModal = reactive({
  open: false,
  mode: 'create' as 'create' | 'rename',
  targetId: null as number | null,
  parentId: null as number | null,
  kbId: null as number | null,
  parentName: '',
  name: '',
  description: '',
  sort_order: 0,
})
const categorySaving = ref(false)

/** 打开分类弹窗：create（可指定父分类或所属知识库）或 rename */
function openCategoryModal(mode: 'create' | 'rename', node?: any) {
  categoryModal.mode = mode
  if (mode === 'rename' && node) {
    categoryModal.targetId = node.id
    categoryModal.name = node.name
    categoryModal.description = node.description || ''
    categoryModal.sort_order = node.sort_order || 0
    categoryModal.parentId = null
    categoryModal.kbId = null
    categoryModal.parentName = ''
  } else {
    categoryModal.targetId = null
    categoryModal.name = ''
    categoryModal.description = ''
    categoryModal.sort_order = 0
    if (node && node.kind === 'knowledge') {
      // 知识库节点下新建子分类：归属该知识库
      categoryModal.parentId = null
      categoryModal.kbId = node.kbId
      categoryModal.parentName = node.name
    } else if (node) {
      categoryModal.parentId = node.id
      categoryModal.kbId = null
      categoryModal.parentName = node.name
    } else {
      categoryModal.parentId = null
      categoryModal.kbId = null
      categoryModal.parentName = ''
    }
  }
  categoryModal.open = true
}

/** 树节点右键菜单：按节点类型（知识库/分类）分发 */
function onMenuClick(e: { key: string | number }, node: any) {
  onNodeMenu(String(e.key), node)
}

function onNodeMenu(key: string, node: any) {
  if (node.kind === 'knowledge') {
    if (key === 'view') openKnowledgeInfo(node)
    else if (key === 'edit') openKnowledgeModal('edit', node)
    else if (key === 'add-child') openCategoryModal('create', node)
    else if (key === 'delete') confirmDeleteKnowledge(node)
  } else {
    if (key === 'view') openCategoryInfo(node)
    else if (key === 'add-child') openCategoryModal('create', node)
    else if (key === 'rename') openCategoryModal('rename', node)
    else if (key === 'delete') confirmDeleteCategory(node)
  }
}

function confirmDeleteCategory(node: { id: number; name: string }) {
  Modal.confirm({
    title: t('kmsWiki.deleteCategory'),
    content: `${node.name}：${t('kmsWiki.deleteCategoryConfirm')}`,
    okType: 'danger',
    okText: t('common.confirm'),
    cancelText: t('common.cancel'),
    onOk: async () => {
      try {
        await deleteCategory(node.id)
        message.success(t('kmsWiki.deleteCategorySuccess'))
        // 被删除的分类若正被筛选，清空筛选
        if (selectedKind.value === 'category' && selectedId.value === node.id) {
          selectedKind.value = null
          selectedId.value = null
          page.value = 1
        }
        await loadTreeData()
        loadArticles()
      } catch (e: any) {
        const detail = e?.response?.data?.detail
        message.error(typeof detail === 'string' ? detail : t('kbMgmt.common.deleteFailed'))
      }
    },
  })
}

async function submitCategory() {
  const name = categoryModal.name.trim()
  if (!name) {
    message.warning(t('kmsWiki.categoryName'))
    return
  }
  categorySaving.value = true
  try {
    if (categoryModal.mode === 'rename' && categoryModal.targetId) {
      await updateCategory(categoryModal.targetId, {
        name,
        description: categoryModal.description || undefined,
        sort_order: categoryModal.sort_order,
      })
      message.success(t('kmsWiki.updateCategorySuccess'))
    } else {
      await createCategory({
        name,
        description: categoryModal.description || undefined,
        sort_order: categoryModal.sort_order,
        parent_id: categoryModal.parentId ?? undefined,
        knowledge_id: categoryModal.kbId ?? undefined,
      })
      message.success(t('kmsWiki.createCategorySuccess'))
    }
    categoryModal.open = false
    await loadTreeData()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    message.error(typeof detail === 'string' ? detail : t('common.error'))
  } finally {
    categorySaving.value = false
  }
}

// ── 知识库管理（新建 / 编辑 / 删除，仅 wiki 类型） ──
const knowledgeModal = reactive({
  open: false,
  mode: 'create' as 'create' | 'edit',
  targetId: null as number | null,
  name: '',
  description: '',
})
const knowledgeSaving = ref(false)

function openKnowledgeModal(mode: 'create' | 'edit', node?: any) {
  knowledgeModal.mode = mode
  if (mode === 'edit' && node) {
    const kb = knowledges.value.find(k => k.id === node.kbId) || {}
    knowledgeModal.targetId = node.kbId
    knowledgeModal.name = kb.name || ''
    knowledgeModal.description = kb.description || ''
  } else {
    knowledgeModal.targetId = null
    knowledgeModal.name = ''
    knowledgeModal.description = ''
  }
  knowledgeModal.open = true
}

async function submitKnowledge() {
  const name = knowledgeModal.name.trim()
  if (!name) {
    message.warning(t('kmsWiki.knowledgeName'))
    return
  }
  knowledgeSaving.value = true
  try {
    if (knowledgeModal.mode === 'edit' && knowledgeModal.targetId) {
      await updateKnowledge(knowledgeModal.targetId, {
        name,
        description: knowledgeModal.description || undefined,
      })
      message.success(t('kmsWiki.updateKnowledgeSuccess'))
    } else {
      await createKnowledge({
        name,
        description: knowledgeModal.description || undefined,
      })
      message.success(t('kmsWiki.createKnowledgeSuccess'))
    }
    knowledgeModal.open = false
    await loadTreeData()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    message.error(typeof detail === 'string' ? detail : t('common.error'))
  } finally {
    knowledgeSaving.value = false
  }
}

function confirmDeleteKnowledge(node: any) {
  Modal.confirm({
    title: t('kmsWiki.deleteKnowledge'),
    content: `${node.name}：${t('kmsWiki.deleteKnowledgeConfirm')}`,
    okType: 'danger',
    okText: t('common.confirm'),
    cancelText: t('common.cancel'),
    onOk: async () => {
      try {
        await deleteKnowledge(node.kbId)
        message.success(t('kmsWiki.deleteKnowledgeSuccess'))
        // 被删除知识库下的分类随之失去归属，清空筛选
        selectedKind.value = null
        selectedId.value = null
        page.value = 1
        await loadTreeData()
        loadArticles()
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

function openCategoryInfo(node: any) {
  openInfoModal(node.name, [
    { label: t('kmsWiki.categoryName'), value: node.name },
    { label: 'Slug', value: node.slug },
    { label: t('kmsWiki.categoryDesc'), value: node.description || '-' },
    { label: t('kmsWiki.categorySort'), value: node.sort_order ?? 0 },
    { label: t('kmsWiki.articleCount'), value: node.article_count ?? 0 },
  ])
}

function openKnowledgeInfo(node: any) {
  const kb = knowledges.value.find(k => k.id === node.kbId) || {}
  openInfoModal(kb.name || node.name, [
    { label: t('kmsWiki.knowledgeName'), value: kb.name },
    { label: 'Slug', value: kb.slug },
    { label: t('kmsWiki.knowledgeType'), value: t('kmsWiki.knowledgeTypeWiki') },
    { label: t('kmsWiki.categoryDesc'), value: kb.description || '-' },
    { label: t('kmsWiki.categoryCount'), value: kb.category_count ?? 0 },
    { label: t('kmsWiki.articleCount'), value: kb.article_count ?? 0 },
    { label: t('kmsWiki.publishStatus'), value: kb.status === 0 ? t('kmsWiki.statusArchived') : t('kmsWiki.statusActive') },
    { label: t('kmsWiki.createdAt'), value: formatDate(kb.created_at) || '-' },
  ])
}

/** 树选中 → 右栏内容联动过滤 */
function handleCategorySelect(keys: any) {
  const key = keys[0]
  if (typeof key === 'number') {
    selectedKind.value = 'category'
    selectedId.value = key
  } else if (typeof key === 'string' && key.startsWith('kb-')) {
    selectedKind.value = 'knowledge'
    selectedId.value = Number(key.slice(3))
  } else {
    selectedKind.value = null
    selectedId.value = null
  }
  page.value = 1
  loadArticles()
}

/** 受控选中态：回填树的选中高亮 */
const selectedKeys = computed(() => {
  if (selectedKind.value === 'category' && selectedId.value) return [selectedId.value]
  if (selectedKind.value === 'knowledge' && selectedId.value) return [`kb-${selectedId.value}`]
  return []
})

/** 当前选中节点名称（用于右栏筛选提示） */
const selectedNodeName = computed(() => {
  const key = selectedKeys.value[0]
  if (key === undefined || key === null) return ''
  return findNodeName(treeData.value, key)
})

function findNodeName(nodes: any[], key: string | number): string {
  for (const node of nodes) {
    if (node.id === key) return node.name
    const found = node.children?.length ? findNodeName(node.children, key) : ''
    if (found) return found
  }
  return ''
}

function clearFilter() {
  selectedKind.value = null
  selectedId.value = null
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
    articles.value = res.items || []
    total.value = res.total || 0
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
    await createArticle({
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
  height: 100%;
  box-sizing: border-box;
}

/* 左右两栏：侧栏定宽区间，主窗体自适应；窄屏纵向堆叠 */
.wiki-layout {
  display: grid;
  grid-template-columns: minmax(240px, 320px) 1fr;
  gap: 20px;
  align-items: start;
}

.wiki-side {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.wiki-side__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.wiki-side__title {
  margin: 0;
  font-size: 18px;
  color: var(--fg);
}

.wiki-side__actions {
  display: flex;
  gap: 6px;
}

.wiki-side__icon-btn {
  color: var(--fg-secondary);
}

.wiki-side__icon-btn:hover {
  color: var(--accent);
}

.wiki-side__tree {
  border-radius: 8px;
}

.wiki-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.wiki-main__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.wiki-main__filter {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wiki-main__filter-label {
  font-size: 12px;
  color: var(--fg-muted);
}

.article-meta {
  margin-top: 8px;
}
.meta-text {
  color: var(--fg-muted);
  font-size: 12px;
  margin-left: 8px;
}
.cat-node {
  display: inline-block;
  width: 100%;
  user-select: none;
}
.kb-icon {
  margin-right: 4px;
  color: var(--accent);
}
.category-parent-hint {
  font-size: 12px;
  color: var(--fg-secondary);
  background: var(--bg-hover);
  border-radius: 4px;
  padding: 6px 10px;
}

@media (max-width: 900px) {
  .wiki-layout {
    grid-template-columns: 1fr;
  }

  .wiki-side__tree {
    max-height: 320px;
    overflow: auto;
  }
}
</style>
