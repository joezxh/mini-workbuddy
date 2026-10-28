<template>
  <div class="meta-explorer">
    <div class="meta-explorer__filters">
      <a-select v-model:value="sourceId" :placeholder="t('kbMgmt.meta.selectSource')" style="width: 220px" @change="onSourceChange">
        <a-select-option v-for="s in sources" :key="s.id" :value="s.id">{{ s.name }}</a-select-option>
      </a-select>
      <a-select v-model:value="database" :placeholder="t('kbMgmt.meta.selectDatabase')" style="width: 180px" @change="onDatabaseChange" :loading="loadingDbs" :disabled="!sourceId">
        <a-select-option v-for="d in databases" :key="d" :value="d">{{ d }}</a-select-option>
      </a-select>
      <!-- PG 族三级：数据库→schema→表；其余族无 schema 层 -->
      <a-select v-if="isPgFamily" v-model:value="schema" :placeholder="t('kbMgmt.meta.selectSchema')" style="width: 160px" @change="loadTables" :loading="loadingSchemas" :disabled="!database">
        <a-select-option v-for="s in schemas" :key="s" :value="s">{{ s }}</a-select-option>
      </a-select>
      <a-button type="primary" :disabled="!sourceId || !database || (isPgFamily && !schema)" @click="doScan">
        <ScanOutlined /> {{ t('kbMgmt.meta.scanMetadata') }}
      </a-button>
      <a-switch v-model:checked="withProfile" /> <span class="muted">{{ t('kbMgmt.meta.withProfile') }}</span>
    </div>

    <div class="meta-explorer__body">
      <div class="meta-explorer__tree">
        <SchemaTree :data="treeData" @select="onSelect" />
      </div>
      <div class="meta-explorer__detail" v-if="selected">
        <a-descriptions :column="2" size="small" bordered>
          <a-descriptions-item :label="t('kbMgmt.meta.table')">{{ selected.table_name }}</a-descriptions-item>
          <a-descriptions-item :label="t('kbMgmt.common.type')">{{ selected.table_type }}</a-descriptions-item>
          <a-descriptions-item :label="t('kbMgmt.meta.comment')">{{ selected.table_comment || '—' }}</a-descriptions-item>
          <a-descriptions-item :label="t('kbMgmt.meta.rowCount')">{{ selected.row_count ?? '—' }}</a-descriptions-item>
          <a-descriptions-item :label="t('kbMgmt.meta.columnCount')">{{ selected.column_count ?? '—' }}</a-descriptions-item>
          <a-descriptions-item :label="t('kbMgmt.meta.domain')">{{ selected.domain || '—' }}</a-descriptions-item>
        </a-descriptions>
        <a-divider>{{ t('kbMgmt.meta.columnInfo') }}</a-divider>
        <a-table
          :columns="columnColumns"
          :data-source="columns"
          :loading="loadingColumns"
          row-key="id"
          size="small"
          :pagination="false"
          :scroll="{ y: 320 }"
          :expandable="{ rowExpandable: (row: any) => !!row.profile_json }"
        >
          <template #expandedRowRender="{ record }">
            <JsonViewer :value="record.profile_json" :copyable="false" />
          </template>
        </a-table>
      </div>
      <a-empty v-else class="meta-explorer__placeholder" :description="t('kbMgmt.meta.selectTableHint')" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { ScanOutlined } from '@ant-design/icons-vue'
import SchemaTree, { type SchemaNode } from '@/components/common/SchemaTree.vue'
import JsonViewer from '@/components/common/JsonViewer.vue'
import * as api from '@/api/dataops'
import { resolveFocusScope, type DrillFocus } from './focusScope'

const { t } = useI18n()
const props = defineProps<{
  /** 标准检视面板下钻落点：定位到某数据源某库（schema）下的表 */
  focus?: DrillFocus | null
}>()
const sources = ref<any[]>([])
const sourceId = ref<number>()
const databases = ref<string[]>([])
const database = ref<string>()
const loadingDbs = ref(false)
const schemas = ref<string[]>([])
const schema = ref<string>()
const loadingSchemas = ref(false)
const withProfile = ref(false)
const tables = ref<any[]>([])
const selected = ref<any>(null)
const columns = ref<any[]>([])
const loadingColumns = ref(false)

const treeData = ref<SchemaNode[]>([])

const columnColumns = computed(() => [
  { title: '#', dataIndex: 'ordinal', key: 'ordinal', width: 50 },
  { title: t('kbMgmt.meta.columnName'), dataIndex: 'column_name', key: 'column_name', width: 180 },
  { title: t('kbMgmt.common.type'), dataIndex: 'column_type', key: 'column_type', width: 150 },
  { title: t('kbMgmt.meta.nullable'), dataIndex: 'nullable', key: 'nullable', width: 70, customRender: ({ text }: any) => (text ? 'Y' : 'N') },
  { title: t('kbMgmt.meta.columnKey'), dataIndex: 'column_key', key: 'column_key', width: 70 },
  { title: t('kbMgmt.meta.comment'), dataIndex: 'column_comment', key: 'column_comment' },
])

/** 当前选中数据源的连接族：pg 族为“物理库→schema→表”三级作用域 */
const currentSource = computed(() => sources.value.find((s) => s.id === sourceId.value) || null)
const isPgFamily = computed(() => {
  const code = currentSource.value?.source_type || ''
  return code === 'postgresql' || code === 'kingbase'
})

async function loadSources() {
  const r: any = await api.listSources()
  sources.value = r.data || r || []
}

function resetScope() {
  database.value = undefined
  databases.value = []
  schema.value = undefined
  schemas.value = []
  tables.value = []
  treeData.value = []
  selected.value = null
  columns.value = []
}

async function onSourceChange() {
  resetScope()
  if (!sourceId.value) return
  // 第一级“数据库”：pg 族=物理库清单；其余族=远端库清单（本就是可扫作用域）
  loadingDbs.value = true
  try {
    const r: any = await api.listRemoteDatabases(sourceId.value)
    databases.value = r.data || r || []
    // 唯一库时自动选中并进入下一级
    if (databases.value.length === 1) {
      database.value = databases.value[0]
      await onDatabaseChange()
    }
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.meta.remoteFail'))
  } finally {
    loadingDbs.value = false
  }
}

/** 选库：pg 族按所选物理库重连列 schema（三级第二级）；其余族直接加载表快照 */
async function onDatabaseChange() {
  schema.value = undefined
  schemas.value = []
  tables.value = []
  treeData.value = []
  selected.value = null
  columns.value = []
  if (!database.value || !sourceId.value) return
  if (isPgFamily.value) {
    loadingSchemas.value = true
    try {
      const r: any = await api.listRemoteSchemas(sourceId.value, database.value)
      schemas.value = r.data || r || []
      if (schemas.value.length === 1) {
        schema.value = schemas.value[0]
        await loadTables()
      }
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t('kbMgmt.meta.remoteFail'))
    } finally {
      loadingSchemas.value = false
    }
  } else {
    await loadTables()
  }
}

async function loadTables() {
  if (!sourceId.value) return
  // 快照过滤：pg 族按 物理库(db_name)+schema(database) 两级过滤；
  // 其余族 database=db_name（同一库名），仅按 database 过滤即可。
  const scopeDb = isPgFamily.value ? schema.value : database.value
  const physicalDb = isPgFamily.value ? database.value : undefined
  const r: any = await api.listTables(sourceId.value, scopeDb, physicalDb)
  tables.value = r.data || r || []
  treeData.value = [{
    key: `db-${isPgFamily.value ? `${database.value}.${schema.value}` : database.value}`,
    title: isPgFamily.value ? (schema.value || 'schema') : (database.value || 'db'),
    level: 'db',
    children: tables.value.map((tb) => ({
      key: `t-${tb.id}`,
      title: tb.table_name,
      level: 'table',
      tag: tb.table_comment || undefined,
      children: [],
    })),
  }]
}

async function doScan() {
  const src = sourceId.value
  const db = database.value
  const sch = schema.value
  if (!src || !db) return
  if (isPgFamily.value && !sch) return
  try {
    // pg 族：扫描作用域=schema、连接库=第一级选中的物理库；其余族直接扫所选库
    if (isPgFamily.value && sch) {
      await api.scanSource(src, sch, withProfile.value, db)
    } else {
      await api.scanSource(src, db, withProfile.value)
    }
    message.success(t('kbMgmt.meta.scanSubmitted'))
    loadTables()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.meta.scanFailed'))
  }
}

async function onSelect(node: SchemaNode) {
  if (node.level !== 'table') return
  const id = Number(node.key.replace('t-', ''))
  await selectTable(tables.value.find((tb) => tb.id === id) || null)
}

/** 选中表并展开列快照（树点击与下钻共用） */
async function selectTable(row: any) {
  selected.value = row
  columns.value = []
  if (!row || !sourceId.value) return
  loadingColumns.value = true
  try {
    const r: any = await api.listMetaColumns(sourceId.value, row.id)
    columns.value = r.data || r || []
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.meta.remoteFail'))
  } finally {
    loadingColumns.value = false
  }
}

/** 下钻落点：按 focus 还原作用域 → 取本地快照 → 定位表并展开列 */
async function applyFocus() {
  const f = props.focus
  if (!f) return
  if (!sources.value.length) await loadSources()
  resetScope()
  sourceId.value = f.source_id
  // pg 族：第一级=物理库(db_name)，第二级=schema(database)；其余族 database 即库名
  const target = resolveFocusScope(f, isPgFamily.value)
  database.value = isPgFamily.value ? target.physicalDb : target.scope
  if (isPgFamily.value) schema.value = target.scope
  if (database.value) {
    // 下拉选项异步补齐，失败不影响已确定的落点
    api.listRemoteDatabases(f.source_id)
      .then((r: any) => { databases.value = r.data || r || [] })
      .catch(() => undefined)
    if (isPgFamily.value) {
      api.listRemoteSchemas(f.source_id, database.value)
        .then((r: any) => { schemas.value = r.data || r || [] })
        .catch(() => undefined)
    }
  }
  try {
    await loadTables()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.meta.remoteFail'))
    return
  }
  const hit = tables.value.find((tb) => tb.table_name === target.table)
  if (hit) await selectTable(hit)
  else message.warning(t('kbMgmt.meta.focusMissing'))
}

onMounted(async () => {
  await loadSources()
  await applyFocus()
})

// 页签已挂载时再次下钻：props 换新对象即可触发
watch(() => props.focus, (f) => { if (f) applyFocus() })
</script>

<style scoped>
.meta-explorer { display: flex; flex-direction: column; height: 100%; gap: 10px; }
.meta-explorer__filters { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.meta-explorer__body { flex: 1; display: flex; gap: 12px; min-height: 0; }
.meta-explorer__tree { width: 320px; border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 8px; overflow: auto; }
.meta-explorer__detail { flex: 1; overflow: auto; }
.meta-explorer__placeholder { flex: 1; }
.muted { color: var(--fg-muted); }
</style>
