<template>
  <div class="std-mgr">
    <div class="std-mgr__body">
      <!-- 目录/场景树：目录与对象、标准图两个视图共用同一份选中态 -->
      <aside class="std-mgr__aside">
        <div class="std-mgr__toolbar std-mgr__toolbar--aside">
          <a-button type="link" size="small" :disabled="!catalogId" @click="selectCatalog(null)">
            {{ t('kbMgmt.catalog.all') }}
          </a-button>
          <span class="std-mgr__spacer" />
          <a-button type="text" size="small" :title="t('kbMgmt.catalog.create')" @click="openCatalogForm()">
            <PlusOutlined />
          </a-button>
          <a-button
            type="text"
            size="small"
            :disabled="!catalogId"
            :title="t('kbMgmt.common.edit')"
            @click="editCurrentCatalog"
          >
            <EditOutlined />
          </a-button>
          <a-popconfirm :title="t('kbMgmt.common.deleteConfirm')" @confirm="removeCatalog">
            <a-button type="text" size="small" danger :disabled="!catalogId" :title="t('kbMgmt.catalog.delete')">
              <DeleteOutlined />
            </a-button>
          </a-popconfirm>
        </div>
        <StdCatalogTree
          :tree-data="catalogs"
          :selected-keys="catalogId ? [catalogId] : []"
          :loading="catalogLoading"
          @select="selectCatalog"
        />
        <!-- 属性是全局字典（不进 catalog）：用页签呈现，左侧树保持可见 -->
        <a-button
          class="std-mgr__attr-entry"
          :type="activeTab === 'attributes' ? 'primary' : 'default'"
          block
          @click="activeTab = 'attributes'"
        >
          <TagsOutlined /> {{ t('kbMgmt.catalog.tabAttributes') }}
        </a-button>
      </aside>

      <div class="std-mgr__content">
        <a-tabs v-model:active-key="activeTab" class="std-mgr__tabs">
          <!-- 目录/场景 → 对象标准 -->
          <a-tab-pane key="catalog" :tab="t('kbMgmt.catalog.tabObjects')">
            <div class="std-mgr__toolbar">
              <a-button type="primary" @click="openObjectForm()">
                <PlusOutlined /> {{ t('kbMgmt.catalog.createObject') }}
              </a-button>
              <a-button @click="loadObjects"><ReloadOutlined /> {{ t('kbMgmt.common.refresh') }}</a-button>
            </div>
            <div class="std-mgr__table-box">
              <DataTable
                :columns="objectColumns"
                :data-source="pagedObjects"
                :loading="objectLoading"
                row-key="id"
                :page-visible="false"
                :scroll="{ x: 1200 }"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'catalog'">
                    <div class="std-mgr__catalog-cell">{{ catalogName(record.catalog_id) }}</div>
                  </template>
                  <template v-else-if="column.key === 'aliases'">
                    {{ (record.aliases || []).join(', ') || '—' }}
                  </template>
                  <template v-else-if="column.key === 'action'">
                    <a-button size="small" @click="openObjectForm(record)">{{ t('kbMgmt.common.edit') }}</a-button>
                    <a-popconfirm :title="t('kbMgmt.common.deleteConfirm')" @confirm="removeObject(record)">
                      <a-button size="small" danger>{{ t('kbMgmt.common.delete') }}</a-button>
                    </a-popconfirm>
                  </template>
                </template>
              </DataTable>
            </div>
            <!-- 分页贴在表格下方、靠右：表格按内容高度排布，页码不会再被撑到可视区之外 -->
            <div class="std-mgr__pager">
              <a-pagination
                v-model:current="objectPage"
                v-model:page-size="objectPageSize"
                :total="objects.length"
                :page-size-options="['10', '20', '30', '50']"
                :show-size-changer="true"
                :show-quick-jumper="true"
                @change="onObjectPageChange"
                @show-size-change="onObjectPageSizeChange"
              />
            </div>
          </a-tab-pane>

          <!-- 标准图 + 检视面板 -->
          <a-tab-pane key="graph" :tab="t('kbMgmt.graph.tab')">
            <div class="std-mgr__toolbar">
              <a-segmented v-model:value="graphView" :options="graphViewOptions" size="small" />
              <span class="std-mgr__spacer" />
              <a-button type="primary" @click="openRelationForm()">
                <PlusOutlined /> {{ t('kbMgmt.graph.createRelation') }}
              </a-button>
              <a-button @click="loadGraph"><ReloadOutlined /> {{ t('kbMgmt.common.refresh') }}</a-button>
            </div>
            <div class="std-mgr__graph-body">
              <div class="std-mgr__graph" :class="{ 'std-mgr__graph--overview': graphView === 'overview' }">
                <StdGraphView
                  v-if="graphView === 'graph'"
                  :nodes="graph.nodes"
                  :edges="graph.edges"
                  :highlight-codes="highlightCodes"
                  :highlight-relation-codes="highlightRelationCodes"
                  @node-click="onNodeClick"
                  @edge-click="onEdgeClick"
                />
                <template v-else>
                  <StdGuidTour class="std-mgr__tour" :current="tourStep" />
                  <StdOverviewView
                    :stats="stats"
                    :loading="statsLoading"
                    :summary="nlSummary"
                    :degraded="nlDegraded"
                    :degraded-reason="nlDegradedReason"
                    :hits="nlHits"
                    :search-empty="nlSearchEmpty"
                    :searching="nlSearching"
                    @search="onNlSearch"
                    @view-in-graph="graphView = 'graph'"
                  />
                </template>
              </div>
              <div v-if="graphView === 'graph'" class="std-mgr__inspector">
                <StdInspector
                  :selected="selected"
                  :objects="graph.nodes"
                  :relations="relations"
                  @edit-object="editObjectById"
                  @edit-relation="editRelationById"
                  @delete-relation="removeRelation"
                  @drill-down="onDrillDown"
                />
              </div>
            </div>
          </a-tab-pane>

          <!-- 属性标准 → 全局字典（不属于任何目录，左侧树保持显示） -->
          <a-tab-pane key="attributes" :tab="t('kbMgmt.catalog.tabAttributes')">
            <div class="std-mgr__toolbar">
              <a-button type="primary" @click="openForm()"><PlusOutlined /> {{ t('kbMgmt.common.create') }}</a-button>
              <a-button @click="seed"><DatabaseOutlined /> {{ t('kbMgmt.std.seed') }}</a-button>
              <a-button @click="load()"><ReloadOutlined /> {{ t('kbMgmt.common.refresh') }}</a-button>
              <a-input-search
                v-model:value="attrKeyword"
                :placeholder="t('kbMgmt.catalog.attrSearch')"
                style="width: 220px"
                allow-clear
              />
              <a-checkbox v-model:checked="onlyOrphan">{{ t('kbMgmt.catalog.onlyOrphan') }}</a-checkbox>
            </div>
            <a-alert
              class="std-mgr__alert"
              type="info"
              show-icon
              :message="t('kbMgmt.catalog.attrDictHint')"
            />
            <div class="std-mgr__table-box std-mgr__table-box--attr">
              <DataTable
                :columns="columns"
                :data-source="pagedAttributes"
                :loading="loading"
                row-key="id"
                :page-visible="false"
                :scroll="{ x: 1100 }"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'aliases'">{{ (record.aliases || []).join(', ') || '—' }}</template>
                  <template v-else-if="column.key === 'usage'">
                    <a-tag v-if="isOrphan(record)" color="orange">{{ t('kbMgmt.catalog.orphan') }}</a-tag>
                    <span v-else class="std-mgr__usage">
                      {{ usageOf(record).columns }} / {{ usageOf(record).objects }} / {{ usageOf(record).relations }}
                    </span>
                  </template>
                  <template v-else-if="column.key === 'action'">
                    <a-button size="small" @click="openForm(record)">{{ t('kbMgmt.common.edit') }}</a-button>
                    <a-popconfirm :title="t('kbMgmt.common.deleteConfirm')" @confirm="remove(record)">
                      <a-button size="small" danger>{{ t('kbMgmt.common.delete') }}</a-button>
                    </a-popconfirm>
                  </template>
                </template>
              </DataTable>
            </div>
            <div class="std-mgr__pager">
              <a-pagination
                v-model:current="attrPage"
                v-model:page-size="attrPageSize"
                :total="filteredAttributes.length"
                :page-size-options="['10', '20', '30', '50']"
                :show-size-changer="true"
                :show-quick-jumper="true"
                @change="onAttrPageChange"
                @show-size-change="onAttrPageSizeChange"
              />
            </div>
          </a-tab-pane>
        </a-tabs>
      </div>
    </div>

    <ObjectFormModal
      v-model:open="objectFormOpen"
      :record="editingObject"
      :catalogs="catalogs"
      :standards="standards"
      :default-catalog-id="catalogId"
      @saved="onObjectSaved"
      @attribute-created="onAttributeCreated"
    />

    <RelationFormModal
      v-model:open="relationFormOpen"
      :record="editingRelation"
      :objects="graph.nodes"
      :catalogs="catalogs"
      :default-catalog-id="catalogId"
      @saved="loadGraph"
    />

    <a-modal
      v-model:open="catalogFormOpen"
      :title="catalogForm.id ? t('kbMgmt.common.edit') : t('kbMgmt.catalog.create')"
      :confirm-loading="catalogSaving"
      @ok="saveCatalog"
    >
      <a-form :model="catalogForm" layout="vertical">
        <a-form-item label="code" required><a-input v-model:value="catalogForm.code" /></a-form-item>
        <a-form-item :label="t('kbMgmt.common.name')" required><a-input v-model:value="catalogForm.name" /></a-form-item>
        <a-form-item :label="t('kbMgmt.catalog.parent')">
          <a-tree-select
            v-model:value="catalogForm.parent_id"
            :tree-data="parentTreeData"
            :field-names="catalogFieldNames"
            :placeholder="t('kbMgmt.catalog.parent')"
            tree-default-expand-all
            allow-clear
          />
        </a-form-item>
        <a-form-item :label="t('kbMgmt.catalog.description')">
          <a-textarea v-model:value="catalogForm.description" :rows="2" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="formOpen" :title="form.id ? t('kbMgmt.common.edit') : t('kbMgmt.common.create')" @ok="save">
      <a-form :model="form" layout="vertical">
        <a-form-item label="code" required><a-input v-model:value="form.code" /></a-form-item>
        <a-form-item :label="t('kbMgmt.common.name')" required><a-input v-model:value="form.name" /></a-form-item>
        <a-form-item :label="t('kbMgmt.std.semanticType')"><a-input v-model:value="form.semantic_type" /></a-form-item>
        <a-form-item :label="t('kbMgmt.std.dataTypeExpect')"><a-input v-model:value="form.data_type_expect" /></a-form-item>
        <a-form-item :label="t('kbMgmt.std.securityLevel')"><a-input v-model:value="form.security_level" /></a-form-item>
        <a-form-item :label="t('kbMgmt.meta.domain')"><a-input v-model:value="form.domain" /></a-form-item>
        <a-form-item :label="t('kbMgmt.std.aliases')"><a-input v-model:value="aliasesText" /></a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
/**
 * 标准中心 shell：左「目录/场景」树 + 右侧三个页签（目录与对象 / 标准图 + 检视 / 属性标准）。
 * 属性标准是全局字典（不进 catalog），以独立页签治理，左侧树始终保留：
 * 主流程是在对象表单里就地新建属性并引用，属性页签负责存量清理（引用计数 / 孤儿项）。
 * 总览视图（F3）在标准图页签内以 segmented 切换占位；下钻事件向上抛给 DataSourcePanel。
 */
import { computed, ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  PlusOutlined, ReloadOutlined, DatabaseOutlined, DeleteOutlined, EditOutlined, TagsOutlined,
} from '@ant-design/icons-vue'
import DataTable from '@/components/common/DataTable/index.vue'
import StdCatalogTree from './standard/StdCatalogTree.vue'
import StdGraphView from './standard/StdGraphView.vue'
import StdInspector from './standard/StdInspector.vue'
import ObjectFormModal from './standard/ObjectFormModal.vue'
import RelationFormModal from './standard/RelationFormModal.vue'
import StdOverviewView from './standard/StdOverviewView.vue'
import StdGuidTour from './standard/StdGuidTour.vue'
import { toNlFocus } from './standard/nlFocus'
import { keywordHits } from './standard/keywordSearch'
import { filterAttributes, isOrphan, usageOf } from './standard/attrDict'
import * as api from '@/api/dataops'

const { t } = useI18n()
const emit = defineEmits<{
  (e: 'drill-down', payload: { source_id: number; db_name?: string; database?: string; table: string }): void
}>()

const activeTab = ref('catalog')

// ── 目录 / 对象 ────────────────────────────────────────────────
const catalogs = ref<any[]>([])
const catalogLoading = ref(false)
const catalogId = ref<number | null>(null)
const objects = ref<any[]>([])
const objectLoading = ref(false)
// 对象列表分页：后端 list 接口无分页参数，切片在本地做，DataTable 只负责渲染分页器
const objectPage = ref(1)
const objectPageSize = ref(10)
const pagedObjects = computed(() => {
  const start = (objectPage.value - 1) * objectPageSize.value
  return objects.value.slice(start, start + objectPageSize.value)
})
const objectFormOpen = ref(false)
const editingObject = ref<any>(null)
const catalogFormOpen = ref(false)
const catalogForm = ref<any>({})
const catalogSaving = ref(false)
// a-tree-select 用 label 取节点文案（a-tree 才是 title/key）；配错会只剩 -- 和数字 id
const catalogFieldNames = { label: 'name', value: 'id', children: 'children' }

const objectColumns = computed(() => [
  { title: 'code', dataIndex: 'code', key: 'code', width: 160 },
  { title: t('kbMgmt.common.name'), dataIndex: 'name', key: 'name' },
  { title: t('kbMgmt.catalog.parent'), key: 'catalog', width: 320 },
  { title: t('kbMgmt.meta.domain'), dataIndex: 'domain', key: 'domain', width: 120 },
  { title: t('kbMgmt.std.aliases'), key: 'aliases' },
  { title: t('kbMgmt.common.actions'), key: 'action', width: 140 },
])

/** 目录 id → 名称（扁平化一层，用于表格列展示） */
const catalogNames = computed(() => {
  const map: Record<number, string> = {}
  const walk = (nodes: any[], prefix = '') => {
    nodes.forEach((n) => {
      map[n.id] = prefix + n.name
      if (n.children?.length) walk(n.children, `${prefix}${n.name} / `)
    })
  }
  walk(catalogs.value)
  return map
})
function catalogName(id?: number | null) {
  return id ? catalogNames.value[id] || `#${id}` : '—'
}

/** 目录 id → 树节点（编辑回填用：树是嵌套结构，需要递归查找） */
function findCatalogNode(id: number | null | undefined): any | null {
  if (!id) return null
  const walk = (nodes: any[]): any | null => {
    for (const n of nodes) {
      if (n.id === id) return n
      const hit = n.children?.length ? walk(n.children) : null
      if (hit) return hit
    }
    return null
  }
  return walk(catalogs.value)
}

/** 编辑目录时的父节点候选：裁掉自身子树，避免出现「挂到自己下面」的无效选项 */
const parentTreeData = computed(() => {
  const selfId = catalogForm.value.id
  if (!selfId) return catalogs.value
  const prune = (nodes: any[]): any[] =>
    nodes
      .filter((n) => n.id !== selfId)
      .map((n) => (n.children?.length ? { ...n, children: prune(n.children) } : n))
  return prune(catalogs.value)
})

async function loadCatalogs() {
  catalogLoading.value = true
  try {
    const r: any = await api.listCatalogs()
    catalogs.value = r.data || r || []
  } finally {
    catalogLoading.value = false
  }
}
async function loadObjects() {
  objectLoading.value = true
  try {
    const r: any = await api.listObjects(catalogId.value ?? undefined)
    objects.value = r.data || r || []
    clampObjectPage()
  } finally {
    objectLoading.value = false
  }
}

/** 删除对象后当前页可能越界，回退到最后一个有数据的页 */
function clampObjectPage() {
  const maxPage = Math.max(1, Math.ceil(objects.value.length / objectPageSize.value))
  if (objectPage.value > maxPage) objectPage.value = maxPage
}

function onObjectPageChange(page: number) {
  objectPage.value = page
}

/** ant 的 showSizeChange 回调是 (current, size)，不能只收一个参数 */
function onObjectPageSizeChange(_current: number, size: number) {
  objectPageSize.value = size
  objectPage.value = 1
}

function selectCatalog(id: number | null) {
  catalogId.value = id
  objectPage.value = 1
  loadObjects()
  if (activeTab.value === 'graph') loadGraph()
}
function openObjectForm(row?: any) {
  editingObject.value = row ? { ...row } : null
  objectFormOpen.value = true
}
function onObjectSaved() {
  loadObjects()
  loadGraph()
}
async function editObjectById(id: number) {
  const node = graph.value.nodes.find((n: any) => n.id === id)
  openObjectForm(node)
}
async function removeObject(row: any) {
  try {
    await api.deleteObject(row.id)
    message.success(t('kbMgmt.catalog.objectDeleted'))
    loadObjects()
    loadGraph()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.common.deleteFailed'))
  }
}
/**
 * 编辑左侧选中的目录。选中 id 在树里查不到节点时不做任何事——
 * 否则会把「编辑」误落到 openCatalogForm 的新建分支上。
 */
function editCurrentCatalog() {
  const node = findCatalogNode(catalogId.value)
  if (node) openCatalogForm(node)
}

/** 新建（无参：父节点默认取当前选中）或编辑（传入树节点） */
function openCatalogForm(row?: any | null) {
  if (row?.id) {
    catalogForm.value = {
      id: row.id,
      code: row.code,
      name: row.name,
      parent_id: row.parent_id ?? null,
      description: row.description ?? '',
      // 原父节点快照：update 接口不含 parent_id，变更需走 move
      _origParentId: row.parent_id ?? null,
    }
  } else {
    catalogForm.value = { parent_id: catalogId.value ?? null }
  }
  catalogFormOpen.value = true
}
async function saveCatalog() {
  const f = catalogForm.value
  catalogSaving.value = true
  try {
    if (f.id) {
      await api.updateCatalog(f.id, {
        code: f.code,
        name: f.name,
        description: f.description || undefined,
      })
      if ((f.parent_id ?? null) !== (f._origParentId ?? null)) {
        await api.moveCatalog(f.id, f.parent_id ?? null)
      }
    } else {
      await api.createCatalog({
        code: f.code,
        name: f.name,
        parent_id: f.parent_id ?? undefined,
        description: f.description || undefined,
      })
    }
    message.success(t('kbMgmt.catalog.catalogSaved'))
    catalogFormOpen.value = false
    await loadCatalogs()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.catalog.saveFailed'))
  } finally {
    catalogSaving.value = false
  }
}
async function removeCatalog() {
  if (!catalogId.value) return
  try {
    await api.deleteCatalog(catalogId.value)
    message.success(t('kbMgmt.catalog.catalogDeleted'))
    catalogId.value = null
    objectPage.value = 1
    await loadCatalogs()
    await loadObjects()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.common.deleteFailed'))
  }
}

// ── 标准图 / 关系 / 检视 ─────────────────────────────────────────
const graph = ref<{ nodes: any[]; edges: any[] }>({ nodes: [], edges: [] })
const relations = ref<any[]>([])
const graphView = ref<'graph' | 'overview'>('graph')
const selected = ref<{ kind: 'node' | 'edge'; id: number } | null>(null)
const highlightCodes = ref<string[]>([])
const highlightRelationCodes = ref<string[]>([])
const relationFormOpen = ref(false)
const editingRelation = ref<any>(null)

// ── 总览 / NL 检索 ─────────────────────────────────────────────
const stats = ref({
  catalogs: 0,
  objects: 0,
  relations: 0,
  relation_check: { hit: 0, missing: 0, conflict: 0 },
})
const statsLoading = ref(false)
const nlSummary = ref('')
const nlDegraded = ref(false)
/** 降级原因：后端会把 LLM 异常透传回来，直接告诉用户为什么不可用 */
const nlDegradedReason = ref('')
/** 命中结果：与标准图高亮同一份 code，总览里就地展示 */
const nlHits = ref<{ objects: string[]; relations: string[] }>({ objects: [], relations: [] })
/** 检索跑完了但零命中 */
const nlSearchEmpty = ref(false)
const nlSearching = ref(false)

/** 导览当前步：按数据充实度推进（属性/绑定无汇总字段，命中对象即视为已过属性步） */
const tourStep = computed(() => {
  const s = stats.value
  if (!s.catalogs) return 0
  if (!s.objects) return 1
  if (!s.relations) return 3
  const checked = s.relation_check.hit + s.relation_check.missing + s.relation_check.conflict
  return checked ? 5 : 4
})

const graphViewOptions = computed(() => [
  { label: t('kbMgmt.graph.viewGraph'), value: 'graph' },
  { label: t('kbMgmt.overview.tab'), value: 'overview' },
])

async function loadGraph() {
  statsLoading.value = true
  try {
    const [g, r, s]: any[] = await Promise.all([
      api.listGraph(catalogId.value ?? undefined),
      api.listRelations(catalogId.value ?? undefined),
      api.getStats(),
    ])
    graph.value = (g.data || g) || { nodes: [], edges: [] }
    relations.value = r.data || r || []
    const st = s.data || s
    if (st) stats.value = { ...stats.value, ...st }
  } finally {
    statsLoading.value = false
  }
  // 选中项可能已被本次刷新移除
  if (selected.value) {
    const pool = selected.value.kind === 'node' ? graph.value.nodes : relations.value
    if (!pool.some((x: any) => x.id === selected.value!.id)) selected.value = null
  }
}
function onNodeClick(id: number) {
  selected.value = { kind: 'node', id }
}
function onEdgeClick(id: number) {
  selected.value = { kind: 'edge', id }
}
function openRelationForm(row?: any) {
  editingRelation.value = row ? { ...row } : null
  relationFormOpen.value = true
}
function editRelationById(id: number) {
  const row = relations.value.find((r: any) => r.id === id)
  if (row) openRelationForm(row)
}
async function removeRelation(id: number) {
  try {
    await api.deleteRelation(id)
    message.success(t('kbMgmt.graph.deleted'))
    if (selected.value?.id === id) selected.value = null
    await loadGraph()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.common.deleteFailed'))
  }
}
function onDrillDown(payload: { source_id: number; db_name?: string; database?: string; table: string }) {
  emit('drill-down', payload)
}

/** 目录 code → id（NL 返回的 focus_catalog_code 用 code 指代目录） */
function findCatalogIdByCode(code?: string | null): number | null {
  if (!code) return null
  const walk = (nodes: any[]): number | null => {
    for (const n of nodes) {
      if (n.code === code) return n.id
      const hit = n.children?.length ? walk(n.children) : null
      if (hit) return hit
    }
    return null
  }
  return walk(catalogs.value)
}

/** 每次检索前清掉上一次的摘要与命中，避免旧结果冒充新结果 */
function resetSearchResult() {
  nlSummary.value = ''
  nlDegraded.value = false
  nlDegradedReason.value = ''
  nlHits.value = { objects: [], relations: [] }
  nlSearchEmpty.value = false
  highlightCodes.value = []
  highlightRelationCodes.value = []
}

/** 检索候选：图谱节点没有 aliases，用对象列表补上，以此满足「按 code / 名称 / 别名」检索 */
function searchablePool() {
  const aliases: Record<number, string[]> = {}
  objects.value.forEach((o: any) => {
    aliases[o.id] = o.aliases || []
  })
  const nodes = graph.value.nodes.length ? graph.value.nodes : objects.value
  return {
    objects: nodes.map((n: any) => ({ code: n.code, name: n.name, aliases: aliases[n.id] || [] })),
    relations: relations.value.map((r: any) => ({ code: r.code, name: r.name })),
  }
}

/**
 * 关键字检索兜底：AI 不可用（或检索接口自身异常）时仍能给出命中结果。
 * 命中 code 与标准图高亮同源，所以不会出现「有结果但图上亮不起来」。
 */
async function runKeywordSearch(question: string) {
  if (!graph.value.nodes.length && !objects.value.length) await loadGraph()
  const pool = searchablePool()
  const hits = keywordHits(question, pool.objects, pool.relations)
  nlHits.value = { objects: hits.objectCodes, relations: hits.relationCodes }
  highlightCodes.value = hits.objectCodes
  highlightRelationCodes.value = hits.relationCodes
  nlSearchEmpty.value = !hits.objectCodes.length && !hits.relationCodes.length
}

/**
 * NL 检索：AI 可用时高亮命中并给解读；不可用时就地降级为关键字检索并告知原因。
 * 结果都在总览里展示，是否跳到标准图由用户点「在标准图中查看」决定。
 */
async function onNlSearch(question: string) {
  nlSearching.value = true
  resetSearchResult()
  try {
    const r: any = await api.nlQuery(question, catalogId.value ?? undefined)
    const focus = toNlFocus(r.data || r)
    if (focus.degraded) {
      nlDegraded.value = true
      nlDegradedReason.value = focus.error
      await runKeywordSearch(question)
      return
    }
    nlSummary.value = focus.summary
    nlHits.value = { objects: focus.objectCodes, relations: focus.relationCodes }
    highlightCodes.value = focus.objectCodes
    highlightRelationCodes.value = focus.relationCodes
    nlSearchEmpty.value = !focus.summary && !focus.objectCodes.length && !focus.relationCodes.length
    const cid = findCatalogIdByCode(focus.focusCatalogCode)
    if (cid && cid !== catalogId.value) {
      catalogId.value = cid
      objectPage.value = 1
      await Promise.all([loadGraph(), loadObjects()])
    }
  } catch (e: any) {
    // 接口本身失败也走关键字兜底：输入框不能点了没反应
    nlDegraded.value = true
    nlDegradedReason.value = e?.response?.data?.detail || e?.message || ''
    await runKeywordSearch(question)
  } finally {
    nlSearching.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'graph' && !graph.value.nodes.length) loadGraph()
  // 引用计数随对象/关系变更，切到属性页签就重拉一次
  if (tab === 'attributes') load()
})

// ── 属性字典（全局字典治理）─────────────────────────────────────
const standards = ref<any[]>([])
const loading = ref(false)
const formOpen = ref(false)
const form = ref<any>({})
const aliasesText = ref('')
const attrKeyword = ref('')
const onlyOrphan = ref(false)

const columns = computed(() => [
  { title: 'code', dataIndex: 'code', key: 'code', width: 160 },
  { title: t('kbMgmt.common.name'), dataIndex: 'name', key: 'name' },
  { title: t('kbMgmt.std.semanticType'), dataIndex: 'semantic_type', key: 'semantic_type', width: 130 },
  { title: t('kbMgmt.std.dataTypeExpect'), dataIndex: 'data_type_expect', key: 'data_type_expect', width: 120 },
  { title: t('kbMgmt.std.securityLevel'), dataIndex: 'security_level', key: 'security_level', width: 100 },
  { title: t('kbMgmt.std.aliases'), key: 'aliases' },
  { title: t('kbMgmt.catalog.usage'), key: 'usage', width: 130 },
  { title: t('kbMgmt.common.actions'), key: 'action', width: 140 },
])

/** 属性页签列表：孤儿过滤 + 关键字（纯函数在 standard/attrDict.ts，有单测） */
const filteredAttributes = computed(() =>
  filterAttributes(standards.value, { onlyOrphan: onlyOrphan.value, keyword: attrKeyword.value }),
)

// 属性列表分页：与对象列表同一套做法（接口全量返回，切片在前端做）
const attrPage = ref(1)
const attrPageSize = ref(10)
const pagedAttributes = computed(() => {
  const start = (attrPage.value - 1) * attrPageSize.value
  return filteredAttributes.value.slice(start, start + attrPageSize.value)
})

/** 删除 / 过滤后当前页可能越界，回退到最后一个有数据的页 */
function clampAttrPage() {
  const maxPage = Math.max(1, Math.ceil(filteredAttributes.value.length / attrPageSize.value))
  if (attrPage.value > maxPage) attrPage.value = maxPage
}

function onAttrPageChange(page: number) {
  attrPage.value = page
}

/** ant 的 showSizeChange 回调是 (current, size)，不能只收一个参数 */
function onAttrPageSizeChange(_current: number, size: number) {
  attrPageSize.value = size
  attrPage.value = 1
}

// 关键字 / 孤儿过滤变化后结果集变了，回到第一页
watch([attrKeyword, onlyOrphan], () => {
  attrPage.value = 1
})

/** 对象表单里就地新建属性后回调：刷新字典池，新建项已被表单自动勾选 */
function onAttributeCreated() {
  load()
}

async function load() {
  loading.value = true
  try {
    const r: any = await api.listStandards(true)
    standards.value = r.data || r || []
    clampAttrPage()
  } finally {
    loading.value = false
  }
}
function openForm(row?: any) {
  form.value = row ? { ...row } : {}
  aliasesText.value = row?.aliases ? row.aliases.join(',') : ''
  formOpen.value = true
}
async function save() {
  const payload = { ...form.value, aliases: aliasesText.value.split(',').map((s) => s.trim()).filter(Boolean) }
  try {
    // 编辑走 PUT，新增走 POST（修复：此前编辑也调 create 导致重复建项）
    if (form.value.id) await api.updateStandard(form.value.id, payload)
    else await api.createStandard(payload)
    message.success(t('kbMgmt.std.saveSuccess'))
    formOpen.value = false
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.std.saveFailed'))
  }
}
async function remove(row?: any) {
  if (!row?.id) return
  try {
    await api.deleteStandard(row.id)
    message.success(t('kbMgmt.common.deleted'))
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.common.deleteFailed'))
  }
}
async function seed() {
  try {
    await api.seedStandards()
    message.success(t('kbMgmt.std.seeded'))
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.std.seedFailed'))
  }
}

onMounted(async () => {
  // 属性标准同时是对象表单的属性池，先拉一次供两处共用
  await Promise.all([load(), loadCatalogs()])
  await loadObjects()
})
</script>

<style scoped>
.std-mgr {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.std-mgr__body {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 16px;
}
.std-mgr__aside {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px;
  overflow: auto;
}
/* 属性字典入口贴底：它是治理入口，不是树的一部分 */
.std-mgr__attr-entry {
  margin-top: auto;
  flex-shrink: 0;
}
/* 上级目录：路径不换行，超出列宽时单元格内横向滚动（不撑宽表格）；320 与 objectColumns 的 catalog 列宽对齐 */
.std-mgr__catalog-cell {
  max-width: 320px;
  white-space: nowrap;
  overflow-x: auto;
  overflow-y: hidden;
}
.std-mgr__catalog-cell::-webkit-scrollbar {
  height: 4px;
}
.std-mgr__catalog-cell::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 2px;
}
/* 表格容器：按内容高度排布（不撑满整页），超过一屏时才在表格内部滚动 */
.std-mgr__table-box :deep(.d-table) {
  height: auto;
}
/* flex-basis 取 auto：高度由内容撑开，而不是从 0 起步撑满父级 */
.std-mgr__table-box :deep(.d-table .d-table__list-content) {
  flex: 1 1 auto;
  max-height: calc(100vh - 400px);
}
/* 属性页签的说明条：与下方表格留白 */
.std-mgr__alert {
  margin-bottom: 12px;
}
/* 属性页签比对象页签多一条说明条，表高上限相应收窄，保证分页条始终在可视区内 */
.std-mgr__table-box--attr :deep(.d-table .d-table__list-content) {
  max-height: calc(100vh - 460px);
}
/* 分页条：贴表格下方、靠右，不再沉到页面最底部 */
.std-mgr__pager {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  padding: 8px 0 4px;
}
/* 引用计数：列 / 对象 / 关系，等宽数字右对齐不跳动 */
.std-mgr__usage {
  color: var(--fg-muted);
  font-variant-numeric: tabular-nums;
}
.std-mgr__content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.std-mgr__tabs {
  flex: 1;
  min-height: 0;
}
.std-mgr__toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  align-items: center;
}
.std-mgr__toolbar--aside {
  margin-bottom: 4px;
}
.std-mgr__spacer {
  flex: 1;
}
.std-mgr__graph-body {
  display: flex;
  gap: 12px;
  height: calc(100vh - 280px);
  min-height: 360px;
}
.std-mgr__graph {
  flex: 1;
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
/* 总览：导览步骤条在上，统计与检索可滚动 */
.std-mgr__graph--overview {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  overflow: auto;
}
.std-mgr__tour {
  flex-shrink: 0;
}
.std-mgr__inspector {
  width: 340px;
  flex-shrink: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px;
  overflow: hidden;
}
</style>
