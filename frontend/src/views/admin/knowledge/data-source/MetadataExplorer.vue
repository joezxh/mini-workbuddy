<template>
  <div class="meta-explorer">
    <div class="meta-explorer__filters">
      <a-select v-model:value="sourceId" placeholder="选择数据源" style="width: 220px" @change="onSourceChange">
        <a-select-option v-for="s in sources" :key="s.id" :value="s.id">{{ s.name }}</a-select-option>
      </a-select>
      <a-select v-model:value="database" placeholder="选择库" style="width: 200px" @change="loadTables" :disabled="!sourceId">
        <a-select-option v-for="d in databases" :key="d" :value="d">{{ d }}</a-select-option>
      </a-select>
      <a-button type="primary" :disabled="!sourceId || !database" @click="doScan">
        <ScanOutlined /> 扫描元数据
      </a-button>
      <a-switch v-model:checked="withProfile" /> <span class="muted">含列画像</span>
    </div>

    <div class="meta-explorer__body">
      <div class="meta-explorer__tree">
        <SchemaTree :data="treeData" @select="onSelect" />
      </div>
      <div class="meta-explorer__detail" v-if="selected">
        <a-descriptions :column="2" size="small" bordered>
          <a-descriptions-item label="表">{{ selected.table_name }}</a-descriptions-item>
          <a-descriptions-item label="类型">{{ selected.table_type }}</a-descriptions-item>
          <a-descriptions-item label="注释">{{ selected.table_comment || '—' }}</a-descriptions-item>
          <a-descriptions-item label="行数">{{ selected.row_count ?? '—' }}</a-descriptions-item>
          <a-descriptions-item label="列数">{{ selected.column_count ?? '—' }}</a-descriptions-item>
          <a-descriptions-item label="领域">{{ selected.domain || '—' }}</a-descriptions-item>
        </a-descriptions>
        <a-divider>列画像</a-divider>
        <JsonViewer :value="selected.profile_json || '（未画像，点击「扫描元数据」并勾选含列画像）'" :copyable="false" />
      </div>
      <a-empty v-else class="meta-explorer__placeholder" :description="'选择左侧表查看详情'" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { ScanOutlined } from '@ant-design/icons-vue'
import SchemaTree, { type SchemaNode } from '@/components/common/SchemaTree.vue'
import JsonViewer from '@/components/common/JsonViewer.vue'
import * as api from '@/api/dataops'

const sources = ref<any[]>([])
const sourceId = ref<number>()
const databases = ref<string[]>([])
const database = ref<string>()
const withProfile = ref(false)
const tables = ref<any[]>([])
const selected = ref<any>(null)

const treeData = ref<SchemaNode[]>([])

async function loadSources() {
  const r: any = await api.listSources()
  sources.value = r.data || r || []
}
async function onSourceChange() {
  database.value = undefined
  databases.value = (sources.value.find((s) => s.id === sourceId.value)?.database) ? [sources.value.find((s) => s.id === sourceId.value)?.database] : []
}
async function loadTables() {
  if (!sourceId.value) return
  const r: any = await api.listTables(sourceId.value, database.value)
  tables.value = r.data || r || []
  treeData.value = [{
    key: `db-${database.value}`,
    title: database.value || 'db',
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
  if (!sourceId.value || !database.value) return
  try {
    await api.scanSource(sourceId.value, database.value, withProfile.value)
    message.success('已提交扫描任务')
    loadTables()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '扫描失败')
  }
}
function onSelect(node: SchemaNode) {
  if (node.level === 'table') {
    const id = Number(node.key.replace('t-', ''))
    selected.value = tables.value.find((t) => t.id === id) || null
  }
}
onMounted(loadSources)
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
