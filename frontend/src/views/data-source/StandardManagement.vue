<template>
  <div class="std-mgr">
    <div class="std-mgr__body">
      <!-- 目录/场景树：目录与对象、标准图两个视图共用同一份选中态 -->
      <aside v-if="activeTab !== 'attributes'" class="std-mgr__aside">
        <div class="std-mgr__toolbar std-mgr__toolbar--aside">
          <a-button type="link" size="small" :disabled="!catalogId" @click="selectCatalog(null)">
            {{ t('kbMgmt.catalog.all') }}
          </a-button>
          <span class="std-mgr__spacer" />
          <a-button type="text" size="small" :title="t('kbMgmt.catalog.create')" @click="openCatalogForm">
            <PlusOutlined />
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
            <DataTable
              :columns="objectColumns"
              :data-source="objects"
              :loading="objectLoading"
              row-key="id"
              :page-visible="false"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'catalog'">{{ catalogName(record.catalog_id) }}</template>
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
              <div class="std-mgr__graph">
                <StdGraphView
                  v-if="graphView === 'graph'"
                  :nodes="graph.nodes"
                  :edges="graph.edges"
                  :highlight-codes="highlightCodes"
                  @node-click="onNodeClick"
                  @edge-click="onEdgeClick"
                />
                <a-empty v-else :description="t('kbMgmt.overview.placeholder')" />
              </div>
              <div class="std-mgr__inspector">
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

          <!-- 属性标准（原扁平字典，保持独立页签） -->
          <a-tab-pane key="attributes" :tab="t('kbMgmt.catalog.tabAttributes')">
            <div class="std-mgr__toolbar">
              <a-button type="primary" @click="openForm()"><PlusOutlined /> {{ t('kbMgmt.common.create') }}</a-button>
              <a-button @click="seed"><DatabaseOutlined /> {{ t('kbMgmt.std.seed') }}</a-button>
              <a-button @click="load"><ReloadOutlined /> {{ t('kbMgmt.common.refresh') }}</a-button>
            </div>
            <DataTable :columns="columns" :data-source="standards" :loading="loading" row-key="id" :page-visible="false">
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'aliases'">{{ (record.aliases || []).join(', ') || '—' }}</template>
                <template v-else-if="column.key === 'action'">
                  <a-button size="small" @click="openForm(record)">{{ t('kbMgmt.common.edit') }}</a-button>
                  <a-popconfirm :title="t('kbMgmt.common.deleteConfirm')" @confirm="remove(record)">
                    <a-button size="small" danger>{{ t('kbMgmt.common.delete') }}</a-button>
                  </a-popconfirm>
                </template>
              </template>
            </DataTable>
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
    />

    <RelationFormModal
      v-model:open="relationFormOpen"
      :record="editingRelation"
      :objects="graph.nodes"
      :catalogs="catalogs"
      :default-catalog-id="catalogId"
      @saved="loadGraph"
    />

    <a-modal v-model:open="catalogFormOpen" :title="t('kbMgmt.catalog.create')" @ok="saveCatalog">
      <a-form :model="catalogForm" layout="vertical">
        <a-form-item label="code" required><a-input v-model:value="catalogForm.code" /></a-form-item>
        <a-form-item :label="t('kbMgmt.common.name')" required><a-input v-model:value="catalogForm.name" /></a-form-item>
        <a-form-item :label="t('kbMgmt.catalog.parent')">
          <a-tree-select
            v-model:value="catalogForm.parent_id"
            :tree-data="catalogs"
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
 * 标准中心 shell：左「目录/场景」树 + 右视图（目录与对象 / 标准图 + 检视 / 属性标准）。
 * 总览视图（F3）在标准图页签内以 segmented 切换占位；下钻事件向上抛给 DataSourcePanel。
 */
import { computed, ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined, DatabaseOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import DataTable from '@/components/common/DataTable/index.vue'
import StdCatalogTree from './standard/StdCatalogTree.vue'
import StdGraphView from './standard/StdGraphView.vue'
import StdInspector from './standard/StdInspector.vue'
import ObjectFormModal from './standard/ObjectFormModal.vue'
import RelationFormModal from './standard/RelationFormModal.vue'
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
const objectFormOpen = ref(false)
const editingObject = ref<any>(null)
const catalogFormOpen = ref(false)
const catalogForm = ref<any>({})
const catalogFieldNames = { title: 'name', value: 'id', children: 'children' }

const objectColumns = computed(() => [
  { title: 'code', dataIndex: 'code', key: 'code', width: 160 },
  { title: t('kbMgmt.common.name'), dataIndex: 'name', key: 'name' },
  { title: t('kbMgmt.catalog.parent'), key: 'catalog', width: 160 },
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
  } finally {
    objectLoading.value = false
  }
}
function selectCatalog(id: number | null) {
  catalogId.value = id
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
function openCatalogForm() {
  catalogForm.value = { parent_id: catalogId.value ?? null }
  catalogFormOpen.value = true
}
async function saveCatalog() {
  try {
    await api.createCatalog({
      code: catalogForm.value.code,
      name: catalogForm.value.name,
      parent_id: catalogForm.value.parent_id ?? undefined,
      description: catalogForm.value.description || undefined,
    })
    message.success(t('kbMgmt.catalog.catalogSaved'))
    catalogFormOpen.value = false
    await loadCatalogs()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.catalog.saveFailed'))
  }
}
async function removeCatalog() {
  if (!catalogId.value) return
  try {
    await api.deleteCatalog(catalogId.value)
    message.success(t('kbMgmt.catalog.catalogDeleted'))
    catalogId.value = null
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
const relationFormOpen = ref(false)
const editingRelation = ref<any>(null)

const graphViewOptions = computed(() => [
  { label: t('kbMgmt.graph.viewGraph'), value: 'graph' },
  { label: t('kbMgmt.overview.tab'), value: 'overview' },
])

async function loadGraph() {
  const [g, r]: any[] = await Promise.all([
    api.listGraph(catalogId.value ?? undefined),
    api.listRelations(catalogId.value ?? undefined),
  ])
  graph.value = (g.data || g) || { nodes: [], edges: [] }
  relations.value = r.data || r || []
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

watch(activeTab, (tab) => {
  if (tab === 'graph' && !graph.value.nodes.length) loadGraph()
})

// ── 属性标准（原逻辑）──────────────────────────────────────────
const standards = ref<any[]>([])
const loading = ref(false)
const formOpen = ref(false)
const form = ref<any>({})
const aliasesText = ref('')

const columns = computed(() => [
  { title: 'code', dataIndex: 'code', key: 'code', width: 160 },
  { title: t('kbMgmt.common.name'), dataIndex: 'name', key: 'name' },
  { title: t('kbMgmt.std.semanticType'), dataIndex: 'semantic_type', key: 'semantic_type', width: 130 },
  { title: t('kbMgmt.std.dataTypeExpect'), dataIndex: 'data_type_expect', key: 'data_type_expect', width: 120 },
  { title: t('kbMgmt.std.securityLevel'), dataIndex: 'security_level', key: 'security_level', width: 100 },
  { title: t('kbMgmt.std.aliases'), key: 'aliases' },
  { title: t('kbMgmt.common.actions'), key: 'action', width: 140 },
])

async function load() {
  loading.value = true
  try {
    const r: any = await api.listStandards()
    standards.value = r.data || r || []
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
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px;
  overflow: auto;
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
.std-mgr__inspector {
  width: 340px;
  flex-shrink: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px;
  overflow: hidden;
}
</style>
