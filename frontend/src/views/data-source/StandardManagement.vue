<template>
  <div class="std-mgr">
    <a-tabs v-model:active-key="activeTab" class="std-mgr__tabs">
      <!-- 目录/场景 → 对象标准 -->
      <a-tab-pane key="catalog" :tab="t('kbMgmt.catalog.tabObjects')">
        <div class="std-mgr__split">
          <aside class="std-mgr__aside">
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

          <section class="std-mgr__main">
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
          </section>
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

    <ObjectFormModal
      v-model:open="objectFormOpen"
      :record="editingObject"
      :catalogs="catalogs"
      :standards="standards"
      :default-catalog-id="catalogId"
      @saved="loadObjects"
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
 * 标准中心 shell（F1）：左「目录/场景」树 + 右「对象标准」表；属性标准保留为独立页签。
 * 图视图/检视面板/总览在 F2/F3 接入同一 shell。
 */
import { computed, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined, DatabaseOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import DataTable from '@/components/common/DataTable/index.vue'
import StdCatalogTree from './standard/StdCatalogTree.vue'
import ObjectFormModal from './standard/ObjectFormModal.vue'
import * as api from '@/api/dataops'

const { t } = useI18n()
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
}
function openObjectForm(row?: any) {
  editingObject.value = row ? { ...row } : null
  objectFormOpen.value = true
}
async function removeObject(row: any) {
  try {
    await api.deleteObject(row.id)
    message.success(t('kbMgmt.catalog.objectDeleted'))
    loadObjects()
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
.std-mgr__tabs {
  flex: 1;
  min-height: 0;
}
.std-mgr__split {
  display: flex;
  gap: 16px;
  height: 100%;
  min-height: 420px;
}
.std-mgr__aside {
  width: 260px;
  flex-shrink: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px;
  overflow: auto;
}
.std-mgr__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.std-mgr__toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.std-mgr__toolbar--aside {
  margin-bottom: 4px;
  align-items: center;
}
.std-mgr__spacer {
  flex: 1;
}
</style>
