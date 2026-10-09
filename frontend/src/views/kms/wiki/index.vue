<template>
  <div class="wiki-index" :class="{ 'wiki-index--embedded': embedded }">
    <div class="wiki-layout">
      <!-- 左栏：侧边栏（标题 + 操作入口 + 分类树） -->
      <aside class="wiki-side">
        <div class="wiki-side__head">
          <h2 v-if="!embedded" class="wiki-side__title">{{ t('kmsWiki.title') }}</h2>
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
            :field-names="{ title: 'name', key: 'treeKey', children: 'children' }"
            :selected-keys="selectedKeys"
            :expanded-keys="expandedKeys"
            @select="handleCategorySelect"
            @expand="(keys: any[]) => (expandedKeys = keys)"
          >
            <template #title="{ data }">
              <a-dropdown
                v-if="data.kind === 'knowledge' || data.kind === 'category'"
                :trigger="['contextmenu']"
              >
                <span class="cat-node">
                  <BookOutlined v-if="data.kind === 'knowledge'" class="kb-icon" />
                  {{ data.name }}
                </span>
                <template #overlay>
                  <a-menu @click="onMenuClick($event, data)">
                    <a-menu-item key="view">{{ t('kmsWiki.viewInfo') }}</a-menu-item>
                    <template v-if="data.kind === 'knowledge'">
                      <a-menu-item key="edit">{{ t('kmsWiki.editKnowledge') }}</a-menu-item>
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
              <span v-else class="cat-node">
                <BookOutlined v-if="data.kind === 'knowledge'" class="kb-icon" />
                {{ data.name }}
              </span>
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
            @change="onSearchInputChange"
            allow-clear
          />
          <a-space>
            <a-select
              v-model:value="sortField"
              style="width: 130px"
              @change="handleSortChange"
            >
              <a-select-option value="updated_at">{{ t('kmsWiki.sortUpdated') }}</a-select-option>
              <a-select-option value="title">{{ t('kmsWiki.sortTitle') }}</a-select-option>
              <a-select-option value="version">{{ t('kmsWiki.sortVersion') }}</a-select-option>
              <a-select-option value="view_count">{{ t('kmsWiki.sortViews') }}</a-select-option>
            </a-select>
            <a-button @click="toggleSortOrder">
              {{ sortOrder === 'desc' ? t('kmsWiki.sortDesc') : t('kmsWiki.sortAsc') }}
            </a-button>
            <a-tooltip :title="t('kmsWiki.reindexTip')">
              <a-button @click="handleReindex">
                <template #icon><ReloadOutlined /></template>
              </a-button>
            </a-tooltip>
            <a-tooltip :title="t('kmsWiki.ragEntry')">
              <a-button @click="openRag">
                <template #icon><ExperimentOutlined /></template>
              </a-button>
            </a-tooltip>
            <!-- OKF 合规层入口（spec §9.5）：按左栏选中的知识库导出/导入 -->
            <a-button @click="handleOkfExport">
              <template #icon><ExportOutlined /></template>
              {{ t('kmsWiki.okfExport') }}
            </a-button>
            <a-button @click="okfFileInput?.click()">
              <template #icon><ImportOutlined /></template>
              {{ t('kmsWiki.okfImport') }}
            </a-button>
            <!-- 导入的是导出物本身（zip），解包与安全限制都在服务端 -->
            <input
              ref="okfFileInput"
              type="file"
              accept=".zip"
              style="display: none"
              @change="handleOkfImport"
            />
            <!-- OKF 导入报告分项（§11.3 报告化）：逐源耗时 / 正文行数 -->
            <a-modal
              v-model:open="reportModalVisible"
              :title="t('kmsWiki.okfImportReport')"
              :width="680"
            >
              <template v-if="reportData">
                <p class="okf-report-summary">
                  {{ t('kmsWiki.okfImportReportSummary', {
                    imported: reportData.imported,
                    skipped: reportData.skipped,
                    ms: reportData.totals?.duration_ms ?? 0,
                    lines: reportData.totals?.body_lines ?? 0,
                  }) }}
                </p>
                <a-table
                  :columns="reportColumns"
                  :data-source="reportData.per_file || []"
                  size="small"
                  :pagination="false"
                  row-key="path"
                >
                  <template #bodyCell="{ column, record }">
                    <template v-if="column.dataIndex === 'warnings'">
                      <span v-if="!record.warnings?.length" class="okf-muted">—</span>
                      <a-tooltip v-else :title="record.warnings.join('\n')">
                        <a-tag color="orange">{{ record.warnings.length }}</a-tag>
                      </a-tooltip>
                    </template>
                  </template>
                </a-table>
              </template>
            </a-modal>
            <a-button type="primary" @click="openCreateModal">
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

        <!-- 批量操作条 -->
        <div v-if="checkedIds.length" class="wiki-main__batch">
          <span>{{ t('kmsWiki.selectedCount', { count: checkedIds.length }) }}</span>
          <a-popconfirm
            :title="t('kmsWiki.batchDeleteConfirm', { count: checkedIds.length })"
            @confirm="handleBatchDelete"
          >
            <a-button danger size="small" :loading="deleting">
              {{ t('common.delete') }}
            </a-button>
          </a-popconfirm>
          <a-button size="small" @click="checkedIds = []">{{ t('common.cancel') }}</a-button>
        </div>

        <a-list
          :data-source="articles"
          :loading="loading"
          item-layout="vertical"
        >
          <template #renderItem="{ item }">
            <a-list-item>
              <template #extra>
                <a-checkbox
                  :checked="checkedIds.includes(item.id)"
                  @change="(e: any) => toggleSelect(item.id, e.target.checked)"
                />
              </template>
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
                <a-tag v-if="item.okf_type" :color="okfColor(item.okf_type)">{{ okfLabel(item.okf_type) }}</a-tag>
                <!-- OKF §5.5：已过期的知识需要显式标记，避免被当作最新结论 -->
                <a-tag v-if="isStale(item)" color="orange">{{ t('kmsWiki.stale') }}</a-tag>
                <span v-if="item.sources?.length" class="meta-text">
                  {{ t('kmsWiki.sourceCount', { count: item.sources.length }) }}
                </span>
                <span class="meta-text">v{{ item.version }} · {{ t('kmsWiki.views', { count: item.view_count }) }} · {{ formatDate(item.updated_at) }}</span>
              </div>
              <template #actions>
                <a @click="viewArticle(item.slug)">{{ t('wikiMgmt.art.view') }}</a>
                <a @click="editArticle(item.id)">{{ t('common.edit') }}</a>
                <a-popconfirm
                  :title="t('kmsWiki.deleteConfirm')"
                  @confirm="handleDelete(item.id)"
                >
                  <a class="wiki-main__danger">{{ t('common.delete') }}</a>
                </a-popconfirm>
              </template>
            </a-list-item>
          </template>
        </a-list>

        <a-pagination
          v-if="total > pageSize"
          :current="page"
          :total="total"
          :page-size="pageSize"
          :page-size-options="['10', '20', '50', '100']"
          show-size-changer
          @change="handlePageChange"
          @showSizeChange="handlePageSizeChange"
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
        <a-form-item :label="t('kmsWiki.articleKb')">
          <a-select
            v-model:value="newArticle.knowledge_id"
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
        </a-form-item>
        <a-form-item :label="t('kmsWiki.summary')">
          <a-textarea v-model:value="newArticle.summary" :rows="2" :placeholder="t('kmsWiki.summaryPlaceholder')" />
        </a-form-item>
        <a-form-item :label="t('kmsWiki.docUpload')">
          <DocUploadPanel @converted="onConvertedCreate" />
        </a-form-item>
        <a-form-item v-if="newArticle.content" :label="t('kmsWiki.body')">
          <a-textarea v-model:value="newArticle.content" :rows="6" style="font-family: monospace" />
        </a-form-item>
        <a-form-item v-if="createExtractedFields.length">
          <ArticleExtractedFields v-model:values="createExtracted" :fields="createExtractedFields" />
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
        <a-form-item :label="t('wikiMgmt.tabCategory')">
          <a-tree-select
            v-model:value="knowledgeModal.category_id"
            :tree-data="categoryTree"
            :field-names="{ label: 'name', value: 'id', children: 'children' }"
            :placeholder="t('kbMgmt.categoryPlaceholder')"
            allow-clear
            tree-default-expand-all
          />
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
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { BookOutlined, ExperimentOutlined, PlusOutlined, ExportOutlined, ImportOutlined } from '@ant-design/icons-vue'
import { message, Modal } from 'ant-design-vue'
import { listArticles, createArticle, deleteArticle, reindexWiki, createCategory, updateCategory, deleteCategory, listCategories, listKnowledges, createKnowledge, updateKnowledge, deleteKnowledge } from '@/api/wiki'
import DocUploadPanel from './components/DocUploadPanel.vue'
import ArticleExtractedFields from './components/ArticleExtractedFields.vue'
import { openDynamicTab } from '@/utils/shellTab'

interface FieldDef {
  key: string
  label: string
  type: 'text' | 'textarea' | 'select' | 'tags' | 'sources'
  options?: string[]
  optionLabels?: Record<string, string>
}
import { exportOkfBundle, importOkfBundle } from '@/api/kb'
import dayjs from 'dayjs'

const { t } = useI18n()
withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })

const articles = ref<any[]>([])
const categoryTree = ref<any[]>([])
const knowledges = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const searchQuery = ref('')
/** 已提交的搜索关键字（与输入框分离，避免边输入边请求） */
const keyword = ref('')
/** 排序：字段 + 方向，随列表请求一起提交 */
const sortField = ref<'updated_at' | 'title' | 'version' | 'view_count'>('updated_at')
const sortOrder = ref<'asc' | 'desc'>('desc')
/** 批量选择的文章 id（与左栏树的 selectedKeys 区分开） */
const checkedIds = ref<number[]>([])
const deleting = ref(false)

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
  knowledge_id: null as number | null,
  content: '',
  tags: [] as string[],
})

/** 新建弹窗里由文档提取到的 OKF 字段（提取到什么就渲染什么） */
const createExtracted = ref<Record<string, any>>({})
const createExtractedFields = ref<FieldDef[]>([])

const OKF_TYPES = ['concept', 'howto', 'reference', 'decision', 'metric']
const OKF_LABELS: Record<string, string> = {
  concept: t('kmsWiki.okfConcept'),
  howto: t('kmsWiki.okfHowto'),
  reference: t('kmsWiki.okfReference'),
  decision: t('kmsWiki.okfDecision'),
  metric: t('kmsWiki.okfMetric'),
}
const OKF_COLORS: Record<string, string> = {
  concept: 'default',
  howto: 'blue',
  reference: 'cyan',
  decision: 'purple',
  metric: 'orange',
}

function okfLabel(type: string) {
  return OKF_LABELS[type] || type
}
function okfColor(type: string) {
  return OKF_COLORS[type] || 'default'
}

/** 仅渲染「有值」的 OKF 字段 */
function buildOkfFieldDefs(src: { okf_type?: string | null; resource?: string | null; sources?: any[] }): FieldDef[] {
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

/** 打开新建弹窗：默认归属左栏当前选中的知识库 */
function openCreateModal() {
  newArticle.value = {
    title: '',
    slug: '',
    summary: '',
    category_id: null,
    knowledge_id: selectedKind.value === 'knowledge' ? selectedId.value : null,
    content: '',
    tags: [],
  }
  createExtracted.value = {}
  createExtractedFields.value = []
  showCreateModal.value = true
}

/** 文档转换完成：回填正文/标题/摘要/标签，并动态补出 OKF 字段 */
function onConvertedCreate(res: any) {
  newArticle.value.content = res.markdown
  if (!newArticle.value.title.trim() && res.title) newArticle.value.title = res.title
  if (!newArticle.value.summary.trim() && res.summary) newArticle.value.summary = res.summary
  if (!newArticle.value.tags.length && res.tags?.length) newArticle.value.tags = res.tags
  createExtracted.value = {
    okf_type: res.okf_type ?? null,
    resource: res.resource ?? '',
    sources: res.sources || [],
  }
  createExtractedFields.value = buildOkfFieldDefs(res)
}

onMounted(() => {
  loadArticles()
  loadTreeData()
})

async function loadArticles() {
  loading.value = true
  try {
    const params: any = {
      page: page.value,
      page_size: pageSize.value,
      sort: sortField.value,
      order: sortOrder.value,
    }
    if (selectedKind.value === 'category' && selectedId.value) {
      params.category_id = selectedId.value
    } else if (selectedKind.value === 'knowledge' && selectedId.value) {
      params.knowledge_id = selectedId.value
    }
    // 搜索走列表接口的 keyword 参数：与分页、筛选共用一套 total，
    // 不再出现"搜索结果覆盖列表且分页 total 不同步"的问题。
    if (keyword.value) params.keyword = keyword.value
    const res = await listArticles(params)
    articles.value = res.items || []
    total.value = res.total || 0
    checkedIds.value = []
  } catch (e: any) {
    message.error(t('wikiMgmt.art.loadFailed'))
  } finally {
    loading.value = false
  }
}

/** 排序或每页条数变化：回到第一页并重新拉取 */
function handleSortChange() {
  page.value = 1
  loadArticles()
}

function toggleSortOrder() {
  sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  handleSortChange()
}

function handlePageSizeChange(_current: number, size: number) {
  pageSize.value = size
  page.value = 1
  loadArticles()
}

async function handleDelete(id: number) {
  try {
    await deleteArticle(id)
    message.success(t('common.deleteSuccess'))
    loadArticles()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('common.deleteFailed'))
  }
}

function toggleSelect(id: number, checked: boolean) {
  checkedIds.value = checked
    ? [...checkedIds.value, id]
    : checkedIds.value.filter((k) => k !== id)
}

async function handleBatchDelete() {
  if (!checkedIds.value.length) return
  deleting.value = true
  try {
    await Promise.all(checkedIds.value.map((id) => deleteArticle(id)))
    message.success(t('kmsWiki.batchDeleteSuccess', { count: checkedIds.value.length }))
    page.value = 1
    loadArticles()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('common.deleteFailed'))
  } finally {
    deleting.value = false
  }
}

/** OKF §5.5：stale_after 已过期 → 列表标记 */
function isStale(item: any): boolean {
  return !!item?.stale_after && dayjs(item.stale_after).isBefore(dayjs())
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
 * 组合树（与新 spec 一致）：分类为父节点，知识库作为叶子挂在「所属类别」(kb.category_id) 下；
 * 未归属任何分类的知识库归入「未分类知识库」分组（分组本身不可选中，仅作容器）。
 * 旧关系（category.knowledge_id：每知识库一套分类）不再用于左栏结构，文章仍可按 category_id 过滤。
 *
 * 注意：categoryTree 由服务端返回「已嵌套」的层级（根类别 + 递归 children），
 * 必须递归遍历 c.children 来重建，否则子类别（及更深层级）会被丢弃。
 */
const treeData = computed(() => {
  const cats = categoryTree.value || []
  const kbs = knowledges.value || []

  const buildKb = (kb: any) => ({
    kind: 'knowledge',
    treeKey: `kb-${kb.id}`,
    id: kb.id,
    kbId: kb.id,
    name: kb.name,
    isLeaf: true,
    children: [],
  })

  /** 递归重建：保留服务端返回的任意深度子类别，并把该类别下的知识库挂为叶子 */
  const buildCat = (c: any): any => {
    const children = [
      ...(c.children || []).map(buildCat),
      ...kbs.filter((k: any) => k.category_id === c.id).map(buildKb),
    ]
    return {
      ...c,
      kind: 'category',
      treeKey: `cat-${c.id}`,
      id: c.id,
      name: c.name,
      isLeaf: children.length === 0,
      children,
    }
  }

  const roots: any[] = cats.map(buildCat)

  const uncatKbs = kbs.filter((k: any) => k.category_id == null).map(buildKb)
  if (uncatKbs.length) {
    roots.push({
      kind: 'group',
      treeKey: 'uncat',
      id: 'uncat',
      name: t('kbMgmt.uncategorized'),
      selectable: false,
      children: uncatKbs,
    })
  }
  return roots
})

/** 默认将含子节点的分类 / 未分类组全部展开 */
const expandedKeys = ref<string[]>([])
watch(
  treeData,
  (nodes) => {
    const keys: string[] = []
    const walk = (arr: any[]) =>
      arr.forEach((n) => {
        if (n.children && n.children.length) {
          keys.push(n.treeKey)
          walk(n.children)
        }
      })
    walk(nodes || [])
    expandedKeys.value = keys
  },
  { immediate: true },
)

// ── 分类管理（新建 / 重命名 / 删除） ──
const categoryModal = reactive({
  open: false,
  mode: 'create' as 'create' | 'rename',
  targetId: null as number | null,
  parentId: null as number | null,
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
    categoryModal.parentName = ''
  } else {
    categoryModal.targetId = null
    categoryModal.name = ''
    categoryModal.description = ''
    categoryModal.sort_order = 0
    categoryModal.parentId = node ? node.id : null
    categoryModal.parentName = node ? node.name : ''
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
  category_id: null as number | null,
})
const knowledgeSaving = ref(false)

function openKnowledgeModal(mode: 'create' | 'edit', node?: any) {
  knowledgeModal.mode = mode
  if (mode === 'edit' && node) {
    const kb = knowledges.value.find(k => k.id === node.kbId) || {}
    knowledgeModal.targetId = node.kbId
    knowledgeModal.name = kb.name || ''
    knowledgeModal.description = kb.description || ''
    // 所属类别（spec 知识库管理）：优先用知识库已有类别
    knowledgeModal.category_id = kb.category_id ?? null
  } else {
    knowledgeModal.targetId = null
    knowledgeModal.name = ''
    knowledgeModal.description = ''
    // 默认归属到当前选中的分类节点（spec 知识库管理）
    knowledgeModal.category_id = selectedKind.value === 'category' ? selectedId.value : null
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
        category_id: knowledgeModal.category_id ?? undefined,
      })
      message.success(t('kmsWiki.updateKnowledgeSuccess'))
    } else {
      await createKnowledge({
        name,
        description: knowledgeModal.description || undefined,
        category_id: knowledgeModal.category_id ?? undefined,
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
    { label: t('wikiMgmt.tabCategory'), value: findCategoryName(kb.category_id) },
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
  if (typeof key === 'string' && key.startsWith('kb-')) {
    selectedKind.value = 'knowledge'
    selectedId.value = Number(key.slice(3))
  } else if (typeof key === 'string' && key.startsWith('cat-')) {
    selectedKind.value = 'category'
    selectedId.value = Number(key.slice(4))
  } else {
    selectedKind.value = null
    selectedId.value = null
  }
  page.value = 1
  loadArticles()
}

/** 受控选中态：回填树的选中高亮 */
const selectedKeys = computed(() => {
  if (selectedKind.value === 'category' && selectedId.value) return [`cat-${selectedId.value}`]
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
    if (node.treeKey === key) return node.name
    const found = node.children?.length ? findNodeName(node.children, key) : ''
    if (found) return found
  }
  return ''
}

/** 由分类 id 反查分类名称（用于信息弹窗展示所属类别） */
function findCategoryName(id: number | null): string {
  if (id == null) return '-'
  return findNodeName(categoryTree.value, id) || String(id)
}

function clearFilter() {
  selectedKind.value = null
  selectedId.value = null
  page.value = 1
  loadArticles()
}

// ── OKF 合规层（spec §9.5）──────────────────────────────────────────────
const okfFileInput = ref<HTMLInputElement | null>(null)

// OKF 导入报告 Modal（§11.3 报告化：逐源耗时 / 正文行数）
const reportModalVisible = ref(false)
const reportData = ref<any>(null)
const reportColumns = [
  { title: t('kmsWiki.okfReportPath'), dataIndex: 'path' },
  { title: t('kmsWiki.okfReportType'), dataIndex: 'okf_type' },
  { title: t('kmsWiki.okfReportAction'), dataIndex: 'action' },
  { title: t('kmsWiki.okfReportDuration'), dataIndex: 'duration_ms' },
  { title: t('kmsWiki.okfReportBodyLines'), dataIndex: 'body_lines' },
  { title: t('kmsWiki.okfReportWarnings'), dataIndex: 'warnings' },
]

/** 导出/导入都以左栏选中的知识库为作用域 */
function currentKnowledgeId(): number | null {
  return selectedKind.value === 'knowledge' ? selectedId.value : null
}

async function handleOkfExport() {
  const kid = currentKnowledgeId()
  if (!kid) {
    message.warning(t('kmsWiki.okfSelectFirst'))
    return
  }
  try {
    const res: any = await exportOkfBundle(kid)
    const url = URL.createObjectURL(new Blob([res.data ?? res]))
    const a = document.createElement('a')
    a.href = url
    a.download = `okf-${kid}.zip`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kmsWiki.okfExportFailed'))
  }
}

async function handleOkfImport(e: Event) {
  const kid = currentKnowledgeId()
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = '' // 允许重复选同一个文件
  if (!kid) {
    message.warning(t('kmsWiki.okfSelectFirst'))
    return
  }
  if (!file) return
  if (!/\.zip$/i.test(file.name)) {
    message.warning(t('kmsWiki.okfImportZipOnly'))
    return
  }
  try {
    const report: any = await importOkfBundle(kid, file)
    let msg = t('kmsWiki.okfImportSuccess', {
      imported: report.imported ?? 0,
      skipped: report.skipped ?? 0,
    })
    // 报告分项（§11.3）：未知键 / 未知 type / 断链 / slug 冲突 / 缺推荐标题
    const d = report.details || {}
    const parts: string[] = []
    if (d.unknown_type) parts.push(t('kmsWiki.okfReportUnknownType', { n: d.unknown_type }))
    if (d.unknown_keys) parts.push(t('kmsWiki.okfReportUnknownKeys', { n: d.unknown_keys }))
    if (d.broken_links) parts.push(t('kmsWiki.okfReportBrokenLinks', { n: d.broken_links }))
    if (d.slug_conflicts) parts.push(t('kmsWiki.okfReportSlugConflicts', { n: d.slug_conflicts }))
    if (d.missing_headings) parts.push(t('kmsWiki.okfReportMissingHeadings', { n: d.missing_headings }))
    if (d.attested_missing_runtime) parts.push(t('kmsWiki.okfReportAttestedRuntime', { n: d.attested_missing_runtime }))
    if (report.warnings?.length) {
      msg += t('kmsWiki.okfImportWarnings', { warnings: report.warnings.length })
    }
    if (parts.length) msg += `（${parts.join(' · ')}）`
    message.success(msg)
    // §11.3 报告化：逐源细分（耗时 / 正文行数）在 Modal 中展开
    reportData.value = report
    reportModalVisible.value = true
    page.value = 1
    loadArticles()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || t('kmsWiki.okfImportFailed'))
  }
}

/** 重建向量索引：存量 content_vector 为 NULL 的文章的唯一修复入口 */
async function handleReindex() {
  try {
    await reindexWiki(currentKnowledgeId())
    message.success(t('kmsWiki.reindexStarted'))
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kmsWiki.reindexFailed'))
  }
}

function handlePageChange(p: number) {
  page.value = p
  loadArticles()
}

async function handleSearch() {
  keyword.value = searchQuery.value.trim()
  page.value = 1
  loadArticles()
}

/** 输入框被清空（allow-clear）时回到列表态 */
function onSearchInputChange() {
  if (!searchQuery.value.trim() && keyword.value) {
    keyword.value = ''
    page.value = 1
    loadArticles()
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
      knowledge_id: newArticle.value.knowledge_id ?? undefined,
      content: newArticle.value.content || undefined,
      tags: newArticle.value.tags.length ? newArticle.value.tags : undefined,
      okf_type: createExtracted.value.okf_type ?? undefined,
      resource: createExtracted.value.resource || undefined,
      sources: createExtracted.value.sources?.length ? createExtracted.value.sources : undefined,
    })
    message.success(t('kbMgmt.dataset.createSuccess'))
    showCreateModal.value = false
    newArticle.value = {
      title: '', slug: '', summary: '', category_id: null,
      knowledge_id: null, content: '', tags: [],
    }
    createExtracted.value = {}
    createExtractedFields.value = []
    loadArticles()
  } catch (e: any) {
    message.error(e.response?.data?.detail || t('kbMgmt.dataset.createFailed'))
  } finally {
    creating.value = false
  }
}

function viewArticle(slug: string) {
  openDynamicTab(
    { key: `kg-wiki-view:${slug}`, component: 'kg-wiki-view', titleKey: 'kmsWiki.articleView', icon: 'ReadOutlined', props: { slug } },
    `/wiki/${slug}`,
  )
}

function editArticle(id: number) {
  openDynamicTab(
    { key: `kg-wiki-edit:${id}`, component: 'kg-wiki-edit', titleKey: 'common.edit', icon: 'EditOutlined', props: { id } },
    `/wiki/edit/${id}`,
  )
}

function openRag() {
  openDynamicTab(
    { key: 'kg-wiki-rag', component: 'kg-wiki-rag', titleKey: 'wikiMgmt.rag.title', icon: 'ExperimentOutlined' },
    '/wiki/rag',
  )
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
  display: flex;
  flex-direction: column;
}

/* 左右两栏：侧栏定宽区间，主窗体自适应；窄屏纵向堆叠 */
.wiki-layout {
  display: grid;
  grid-template-columns: minmax(240px, 320px) 1fr;
  gap: 20px;
  align-items: stretch;
  flex: 1;
  min-height: 0;
}

.wiki-side {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  height: 100%;
  min-height: 0;
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

/* 类别树：撑满侧栏剩余高度；内容超出时纵向 + 横向滚动；树内浅色背景 */
.wiki-side__tree {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-radius: 8px;
}

.wiki-side__tree :deep(.ant-card-body) {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: var(--bg-subtle, #f5f7fa);
  border-radius: 6px;
}

.wiki-main {
  min-width: 0;
  min-height: 0;
  overflow: auto;
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

.wiki-main__batch {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 8px 0;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-secondary);
}

.wiki-main__danger {
  color: var(--error, #ff4d4f);
}

.wiki-main__filter-label {
  font-size: 12px;
  color: var(--fg-muted);
}

.article-meta {
  margin-top: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
  white-space: nowrap;
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

/* 内嵌于知识库管理 tab：去掉页面级留白、高度改自适应、隐藏与 tab 标签重复的标题 */
.wiki-index--embedded {
  padding: 0;
  height: auto;
}

.wiki-index--embedded .wiki-side__head {
  justify-content: flex-end;
}
</style>
