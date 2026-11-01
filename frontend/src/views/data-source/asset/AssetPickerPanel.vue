<template>
  <div class="asset-picker">
    <div class="asset-picker__body">
      <div class="asset-picker__tree">
        <AssetTypeTree ref="treeRef" @select-source="onSource" />
      </div>
      <div class="asset-picker__main">
        <AssetSearchBar :loading="loading" @search="onSearch" />
        <AssetCardList
          :items="items"
          :total="total"
          :page="page"
          :size="size"
          :loading="loading"
          :selected="selected"
          @toggle="onToggle"
          @page-change="onPage"
        />
      </div>
    </div>

    <div class="asset-picker__send">
      <span class="asset-picker__count">
        {{ t2('已勾选') }} {{ selected.length }} {{ t2('张表') }}
        <template v-if="selected.length">（{{ t2('来源') }} #{{ selected[0].source_id }}）</template>
      </span>
      <a-select
        v-model:value="targetId"
        style="min-width: 240px"
        :placeholder="t2('选择目标本体')"
        :loading="loadingOnt"
        show-search
        option-filter-prop="label"
        :options="ontOptions"
      />
      <a-button type="primary" :disabled="!selected.length || !targetId" :loading="sending" @click="doSend">
        {{ t2('送入本体建模') }}
      </a-button>
      <a-button :disabled="!selected.length" @click="selected = []">{{ t2('清空勾选') }}</a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 资产送数面板（AF-08 正向送数，§4.7 / §6.5）：类型树 + 全文检索 + 卡片多选 → PUT draft-scope。
 * 关键约束：送数**不写结构表**，只落 `meta_ontology.draft_scope_json`；一个作用域仅单一 source_id（§4.7-5）。
 * 复用 E40/E28/E1/E33，不改既有级联浏览（本面板为并列模式，由 MetadataExplorer 切换进入）。
 */
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import { assetsSearch, listOntologies, putDraftScope } from '@/api/dataops'
import { t2 } from '../ontology/ontologyText'
import AssetTypeTree from './AssetTypeTree.vue'
import AssetSearchBar from './AssetSearchBar.vue'
import AssetCardList from './AssetCardList.vue'

const treeRef = ref<any>(null)
const loading = ref(false)
const items = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(50)
const selected = ref<any[]>([])

const sourceId = ref<number | null>(null)
const lastQuery = ref<{ kw: string; tag_ids: number[]; kind: string }>({ kw: '', tag_ids: [], kind: 'table' })

const ontologies = ref<any[]>([])
const loadingOnt = ref(false)
const sending = ref(false)
const targetId = ref<number | null>(null)
const ontOptions = computed(() =>
  ontologies.value.map((o) => ({ label: `${o.name} (${o.code})`, value: o.id })),
)

async function runSearch() {
  loading.value = true
  try {
    const resp: any = await assetsSearch({
      kw: lastQuery.value.kw || undefined,
      source_id: sourceId.value || undefined,
      tag_ids: lastQuery.value.tag_ids.length ? lastQuery.value.tag_ids : undefined,
      kind: lastQuery.value.kind as any,
      page: page.value,
      size: size.value,
    })
    items.value = resp?.items || []
    total.value = resp?.total || 0
  } finally {
    loading.value = false
  }
}

function onSource(id: number | null) {
  sourceId.value = id
  page.value = 1
  runSearch()
}

function onSearch(payload: { kw: string; tag_ids: number[]; kind: string }) {
  lastQuery.value = payload
  page.value = 1
  runSearch()
}

function onPage(p: number) {
  page.value = p
  runSearch()
}

/** 跨页保留勾选：卡片 toggle 增删 selected（同源约束已在卡片层拦截） */
function onToggle(row: any, checked: boolean) {
  if (checked) {
    if (!selected.value.some((s) => s.table_id === row.table_id)) selected.value.push(row)
  } else {
    selected.value = selected.value.filter((s) => s.table_id !== row.table_id)
  }
}

async function loadOntologies() {
  if (ontologies.value.length) return
  loadingOnt.value = true
  try {
    const resp: any = await listOntologies({ sort: 'updated_at_desc' })
    ontologies.value = Array.isArray(resp) ? resp : (resp?.items || [])
  } finally {
    loadingOnt.value = false
  }
}

async function doSend() {
  if (!targetId.value || !selected.value.length) return
  const first = selected.value[0]
  const body = {
    mode: 'tables',
    source_id: first.source_id,
    db_name: first.db_name || undefined,
    database: first.database || undefined,
    tables: selected.value.map((s) => s.table_name),
    tag_ids: [],
    catalog_ids: [],
    origin: 'asset_picker',
  }
  sending.value = true
  try {
    await putDraftScope(targetId.value, body)
    message.success(t2('已送入本体建模作用域（未写结构表）'))
    selected.value = []
  } catch {
    /* ONTOLOGY_STOPPED / DRAFT_SCOPE_EMPTY 已由拦截器按 code 提示 */
  } finally {
    sending.value = false
  }
}

function activate() {
  loadOntologies()
  treeRef.value?.reload?.()
  if (!items.value.length) runSearch()
}

runSearch()
defineExpose({ activate })
</script>

<style lang="less" scoped>
.asset-picker {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 10px;

  &__body {
    flex: 1;
    display: flex;
    gap: 12px;
    min-height: 0;
  }
  &__tree {
    width: 260px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 8px;
    overflow: auto;
  }
  &__main {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 10px;
    min-width: 0;
    overflow: auto;
  }
  &__send {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    border-top: 1px solid var(--border);
    padding-top: 10px;
  }
  &__count {
    font-size: 13px;
    color: var(--fg-mute, #666);
  }
}
</style>
