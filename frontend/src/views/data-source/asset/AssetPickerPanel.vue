<template>
  <div class="asset-picker">
    <div class="asset-picker__body">
      <div class="asset-picker__tree">
        <AssetTypeTree ref="treeRef" @select-source="onSource" />
      </div>
      <div class="asset-picker__main">
        <AssetSearchBar :loading="loading" @search="onSearch" />
        <AssetCardList
          ref="cardRef"
          :items="items"
          :total="total"
          :page="page"
          :size="size"
          :loading="loading"
          :selected="selected"
          :kw="lastQuery.kw"
          :probe="probe"
          @toggle="onToggle"
          @page-change="onPage"
          @test="onTest"
          @edit="openEdit"
          @tag="openTag"
        />
      </div>
    </div>

    <div class="asset-picker__send">
      <span class="asset-picker__count">
        {{ t2('已勾选') }} {{ selected.length }} {{ t2('张表') }}
        <template v-if="selected.length">（{{ t2('来源') }} #{{ selected[0].source_id }}）</template>
      </span>
      <a-button :disabled="!selected.length" @click="openTagBatch">{{ t2('打标签') }}</a-button>
      <a-button :disabled="!selected.length" :loading="probing" @click="onProbeBatch">{{ t2('批量探活') }}</a-button>
      <a-button :loading="reclassifying" @click="onReclassify">{{ t2('重新分级') }}</a-button>
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

    <!-- 打标弹窗（单卡 ＋标签 / 选择条 打标签 复用） -->
    <a-modal v-model:open="tagOpen" :title="t2('打标签')" :confirm-loading="tagging" @ok="doTag">
      <a-select v-model:value="tagPick" style="width: 100%" :placeholder="t2('选择标签')" :loading="loadingTags"
        show-search option-filter-prop="label" :options="tagOptions" />
    </a-modal>

    <!-- 编辑弹窗：表注释 + 列注释局部可编辑 -->
    <a-modal v-model:open="editOpen" :title="t2('编辑元数据')" :confirm-loading="saving" width="640px" @ok="doEdit">
      <a-form layout="vertical">
        <a-form-item :label="t2('表说明')">
          <a-textarea v-model:value="editForm.table_comment" :rows="2" />
        </a-form-item>
        <a-form-item :label="t2('业务名')">
          <a-input v-model:value="editForm.biz_name" />
        </a-form-item>
        <a-spin :spinning="loadingCols">
          <a-table :data-source="editColumns" :columns="colEditCols" :pagination="false" size="small" row-key="column_name">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'column_comment'">
                <a-input v-model:value="record.column_comment" size="small" />
              </template>
            </template>
          </a-table>
        </a-spin>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
/**
 * 资产送数面板（AF-03/06/07/08，§4.7 / §6.5）：类型树 + 全文检索 + 卡片多选 → PUT draft-scope。
 * 卡片操作区（测试/编辑/＋标签）与选择条（打标签/批量探活/重新分级）经此编排：
 * 探活限流、打标载荷等决策委托 :mod:`assetOps` 纯函数；跨源约束在卡片层拦截。
 * 送数**不写结构表**，只落 `meta_ontology.draft_scope_json`；一个作用域仅单一 source_id（§4.7-5）。
 */
import { computed, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  assetsSearch, bindAssetTag, getDraftScope, listAssetTags, listMetaColumns, listOntologies,
  putDraftScope, reclassifyTags, testTable, testTables, updateTableMeta,
} from '@/api/dataops'
import { t2 } from '../ontology/ontologyText'
import AssetTypeTree from './AssetTypeTree.vue'
import AssetSearchBar from './AssetSearchBar.vue'
import AssetCardList from './AssetCardList.vue'
import { buildBindTagPayload, checkBatchProbeLimit } from './assetOps'
import { restoreSelection, staleNotice } from './assetSend'

const treeRef = ref<any>(null)
const cardRef = ref<any>(null)
const loading = ref(false)
const items = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(50)
const selected = ref<any[]>([])
const probe = ref<Record<number, { ok: boolean; code?: string | null }>>({})

const sourceId = ref<number | null>(null)
const lastQuery = reactive<{
  kw: string; tag_ids: number[]; kind: string; table_type?: string; sort: string; size: number
}>({ kw: '', tag_ids: [], kind: 'table', table_type: undefined, sort: 'score', size: 50 })

const ontologies = ref<any[]>([])
const loadingOnt = ref(false)
const sending = ref(false)
const targetId = ref<number | null>(null)
const ontOptions = computed(() =>
  ontologies.value.map((o) => ({ label: `${o.name} (${o.code})`, value: o.id })),
)

// 送数回显（AF-08）：目标本体锁定单一 source_id 的 draft_scope，按 table_name 回显当前页勾选
const draftScope = ref<{ source_id?: number; tables?: string[] } | null>(null)

function applyRestore() {
  if (!draftScope.value) return
  for (const it of restoreSelection(draftScope.value, items.value)) {
    if (!selected.value.some((s) => s.table_id === it.table_id)) selected.value.push(it)
  }
}

async function syncDraftScope() {
  if (!targetId.value) {
    draftScope.value = null
    return
  }
  const resp: any = await getDraftScope(targetId.value)
  draftScope.value = resp?.draft_scope || null
  const notice = staleNotice(resp?.removed_stale)
  if (notice) message.info(t2(notice))
  applyRestore()
}

// 切换目标本体：清空跨目标勾选，重新回显该本体的 draft_scope
watch(targetId, () => {
  selected.value = []
  syncDraftScope()
})

async function runSearch() {
  loading.value = true
  try {
    const resp: any = await assetsSearch({
      kw: lastQuery.kw || undefined,
      source_id: sourceId.value || undefined,
      tag_ids: lastQuery.tag_ids.length ? lastQuery.tag_ids : undefined,
      kind: lastQuery.kind as any,
      table_type: lastQuery.table_type,
      sort: lastQuery.sort,
      page: page.value,
      size: size.value,
    })
    items.value = resp?.items || []
    total.value = resp?.total || 0
    applyRestore() // 回显：当前页命中 draft_scope 的表恢复勾选
  } finally {
    loading.value = false
  }
}

function onSource(id: number | null) {
  sourceId.value = id
  page.value = 1
  runSearch()
}

function onSearch(payload: {
  kw: string; tag_ids: number[]; kind: string; table_type?: string; sort: string; size: number
}) {
  Object.assign(lastQuery, payload)
  if (payload.size) size.value = payload.size
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

// ── 探活（单表 + 批量限流 20） ────────────────────────────────────
const probing = ref(false)
async function onTest(row: any) {
  const sid = row.source_id
  cardRef.value?.setProbing?.(row.table_id, true)
  try {
    const resp: any = await testTable(sid, row.table_id)
    probe.value = { ...probe.value, [row.table_id]: { ok: resp?.ok ?? true, code: null } }
  } catch (err: any) {
    const code = err?.code || err?.response?.data?.code || null
    probe.value = { ...probe.value, [row.table_id]: { ok: false, code } }
  } finally {
    cardRef.value?.setProbing?.(row.table_id, false)
  }
}

async function onProbeBatch() {
  const ids = selected.value.map((s) => s.table_id)
  const guard = checkBatchProbeLimit(ids)
  if (!guard.ok) {
    message.warning(t2(guard.message || '批量探活数量不合规'))
    return
  }
  const sid = selected.value[0].source_id
  probing.value = true
  try {
    const resp: any = await testTables(sid, ids)
    const next = { ...probe.value }
    for (const r of resp?.results || []) next[r.table_id] = { ok: r.ok, code: r.code ?? null }
    probe.value = next
  } finally {
    probing.value = false
  }
}

// ── 重新分级（security 规则自动打标手动补刷） ─────────────────────
const reclassifying = ref(false)
async function onReclassify() {
  reclassifying.value = true
  try {
    const resp: any = await reclassifyTags()
    message.success(t2(`已重跑 pii 规则：新增 ${resp?.bound ?? 0} · 移除 ${resp?.removed ?? 0}`))
    runSearch()
  } finally {
    reclassifying.value = false
  }
}

// ── 打标（单卡 / 批量） ───────────────────────────────────────────
const tagOpen = ref(false)
const tagging = ref(false)
const tagPick = ref<number | null>(null)
const tagTargetIds = ref<number[]>([])
const tagOptions = ref<{ label: string; value: number }[]>([])
const loadingTags = ref(false)

async function ensureTags() {
  if (tagOptions.value.length) return
  loadingTags.value = true
  try {
    const resp: any = await listAssetTags()
    const arr = Array.isArray(resp) ? resp : (resp?.items || [])
    tagOptions.value = arr.map((t: any) => ({ label: t.name || t.code, value: t.id }))
  } finally {
    loadingTags.value = false
  }
}

function openTag(row: any) {
  tagTargetIds.value = [row.table_id]
  tagPick.value = null
  tagOpen.value = true
  ensureTags()
}

function openTagBatch() {
  tagTargetIds.value = selected.value.map((s) => s.table_id)
  tagPick.value = null
  tagOpen.value = true
  ensureTags()
}

async function doTag() {
  if (!tagPick.value || !tagTargetIds.value.length) return
  tagging.value = true
  try {
    await bindAssetTag(buildBindTagPayload(tagPick.value, tagTargetIds.value))
    message.success(t2('已打标'))
    tagOpen.value = false
    runSearch()
  } finally {
    tagging.value = false
  }
}

// ── 编辑元数据（表注释 + 列注释） ─────────────────────────────────
const editOpen = ref(false)
const saving = ref(false)
const loadingCols = ref(false)
const editRow = ref<any>(null)
const editForm = reactive<{ table_comment: string; biz_name: string }>({ table_comment: '', biz_name: '' })
const editColumns = ref<any[]>([])
const colEditCols = [
  { title: t2('列名'), dataIndex: 'column_name', key: 'column_name', width: 160 },
  { title: t2('列说明'), key: 'column_comment', dataIndex: 'column_comment' },
]

async function openEdit(row: any) {
  editRow.value = row
  editForm.table_comment = row.table_comment || ''
  editForm.biz_name = row.biz_name || ''
  editColumns.value = []
  editOpen.value = true
  loadingCols.value = true
  try {
    const resp: any = await listMetaColumns(row.source_id, row.table_id)
    const arr = Array.isArray(resp) ? resp : (resp?.items || [])
    editColumns.value = arr.map((c: any) => ({
      column_name: c.column_name, column_comment: c.column_comment || '',
    }))
  } finally {
    loadingCols.value = false
  }
}

async function doEdit() {
  const row = editRow.value
  if (!row) return
  saving.value = true
  try {
    await updateTableMeta(row.source_id, row.table_id, {
      table_comment: editForm.table_comment,
      biz_name: editForm.biz_name || undefined,
      columns: editColumns.value.map((c) => ({ column_name: c.column_name, column_comment: c.column_comment })),
    })
    message.success(t2('已保存'))
    editOpen.value = false
    runSearch()
  } finally {
    saving.value = false
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
  syncDraftScope()
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
