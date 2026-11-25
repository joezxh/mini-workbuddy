<template>
  <div class="kg-triple-table">
    <!-- 工具栏：类型 / 状态 / 权重档 / 仅看待评审 + 批量操作 -->
    <div class="kg-triple-table__toolbar">
      <a-select
        v-model:value="query.relation_code"
        :placeholder="t('kbMgmt.kg.filterRelationType')"
        allow-clear
        size="small"
        style="width: 180px"
        @change="reload"
      >
        <a-select-option v-for="code in relationCodes" :key="code" :value="code">
          {{ code || t('kbMgmt.kg.freePredicate') }}
        </a-select-option>
      </a-select>

      <a-select
        v-model:value="query.status"
        :placeholder="t('kbMgmt.kg.filterStatus')"
        allow-clear
        size="small"
        style="width: 130px"
        @change="reload"
      >
        <a-select-option value="suggested">{{ t('kbMgmt.kg.statusSuggested') }}</a-select-option>
        <a-select-option value="accepted">{{ t('kbMgmt.kg.statusAccepted') }}</a-select-option>
        <a-select-option value="rejected">{{ t('kbMgmt.kg.statusRejected') }}</a-select-option>
      </a-select>

      <a-select
        v-model:value="weightTier"
        size="small"
        style="width: 132px"
      >
        <a-select-option value="all">{{ t('kbMgmt.kg.weightFilter') }}</a-select-option>
        <a-select-option value="high">{{ t('kbMgmt.kg.weightHigh') }}</a-select-option>
        <a-select-option value="mid">{{ t('kbMgmt.kg.weightMid') }}</a-select-option>
        <a-select-option value="low">{{ t('kbMgmt.kg.weightLow') }}</a-select-option>
      </a-select>

      <span class="kg-triple-table__spacer" />

      <template v-if="selectedRowKeys.length">
        <span class="kg-muted">
          {{ t('kbMgmt.kg.selectedCount', { count: selectedRowKeys.length }) }}
        </span>
      </template>
      <a-button
        size="small"
        :loading="batchLoading"
        :disabled="!pendingSelectedCount"
        @click="onBatchAccept"
      >
        {{ t('kbMgmt.kg.batchAccept') }}
      </a-button>
      <a-button
        size="small"
        :loading="batchLoading"
        :disabled="!pendingSelectedCount"
        @click="onBatchReject"
      >
        {{ t('kbMgmt.kg.batchReject') }}
      </a-button>
      <a-popconfirm
        :title="t('kbMgmt.kg.confirmDeleteRelation')"
        :disabled="!selectedRowKeys.length"
        @confirm="onBatchDelete"
      >
        <a-button size="small" danger :disabled="!selectedRowKeys.length">
          {{ t('kbMgmt.kg.batchDelete') }}
        </a-button>
      </a-popconfirm>
      <a-button
        size="small"
        :loading="reviewBatchLoading"
        :title="t('kbMgmt.kg.reviewBatchTip')"
        @click="onRunReviewBatch"
      >
        {{ t('kbMgmt.kg.reviewBatch') }}
      </a-button>
      <a-button size="small" type="primary" :disabled="!entities.length" @click="openCreate">
        ＋ {{ t('kbMgmt.kg.createRelation') }}
      </a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="viewRows"
      :loading="loading"
      row-key="id"
      size="small"
      :row-selection="rowSelection"
      :row-class-name="rowClass"
      :pagination="pagination"
      :scroll="{ x: 1160 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'from'">
          <div class="kg-ent-cell">
            <a class="kg-rel-link" @click="$emit('inspect-entity', record.from_entity_id)">
              {{ record.from_entity_name || `#${record.from_entity_id}` }}
            </a>
            <div v-if="entityTypeLabel(record.from_entity_id)" class="kg-muted">
              {{ entityTypeLabel(record.from_entity_id) }}
            </div>
          </div>
        </template>
        <template v-else-if="column.key === 'to'">
          <div class="kg-ent-cell">
            <a class="kg-rel-link" @click="$emit('inspect-entity', record.to_entity_id)">
              {{ record.to_entity_name || `#${record.to_entity_id}` }}
            </a>
            <div v-if="entityTypeLabel(record.to_entity_id)" class="kg-muted">
              {{ entityTypeLabel(record.to_entity_id) }}
            </div>
          </div>
        </template>
        <template v-else-if="column.key === 'relation'">
          <a-tag v-if="record.relation_code" color="purple">{{ record.relation_code }}</a-tag>
          <span v-else class="kg-muted">{{ t('kbMgmt.kg.freePredicate') }}</span>
          <div v-if="record.predicate" class="kg-muted kg-rel-pred">{{ record.predicate }}</div>
        </template>
        <template v-else-if="column.key === 'weight'">
          <div class="kg-weight">
            <span class="kg-wbar">
              <span
                class="kg-wbar__fill"
                :style="{ width: weightPct(record.weight) + '%', background: weightColor(record.weight) }"
              />
            </span>
            <span
              class="kg-weight__num"
              :style="{ color: weightColor(record.weight) }"
            >
              {{ formatWeight(record.weight) }}
            </span>
          </div>
        </template>
        <template v-else-if="column.key === 'status'">
          <span class="kg-status" :class="`kg-status--${record.status}`">
            {{ statusText(record.status) }}
          </span>
          <span
            v-if="record.review_verdict"
            class="kg-review-badge"
            :class="`kg-review-badge--${record.review_verdict}`"
            :title="record.review_note || ''"
          >
            {{ reviewBadgeText(record.review_verdict) }}
          </span>
        </template>
        <template v-else-if="column.key === 'extractor'">
          <span class="kg-code">{{ record.extractor || 'llm' }}</span>
        </template>
        <template v-else-if="column.key === 'mentions'">
          <span class="kg-muted kg-rel-mentions">{{ record.mention_count ?? 0 }}</span>
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-space :size="2">
            <a-button size="small" type="link" @click="onInspectEdge(record)">
              {{ t('kbMgmt.kg.actionInspect') }}
            </a-button>
            <a-button size="small" type="link" @click="openEdit(record)">
              {{ t('common.edit') }}
            </a-button>
            <a-button
              v-if="record.status === 'suggested'"
              size="small"
              type="link"
              @click="onReview(record, 'accepted')"
            >
              {{ t('kbMgmt.kg.actionReview') }}
            </a-button>
            <a-button size="small" type="link" @click="$emit('provenance', record.id)">
              {{ t('kbMgmt.kg.actionProvenance') }}
            </a-button>
            <a-popconfirm :title="t('kbMgmt.kg.confirmDeleteRelation')" @confirm="onDelete(record)">
              <a-button size="small" type="link" danger>{{ t('common.delete') }}</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <div class="kg-note">
      {{ t('kbMgmt.kg.weightNote', { high: t('kbMgmt.kg.weightHigh'), mid: t('kbMgmt.kg.weightMid'), low: t('kbMgmt.kg.weightLow') }) }}
    </div>

    <a-modal
      v-model:open="modalOpen"
      :title="editing ? t('kbMgmt.kg.editRelation') : t('kbMgmt.kg.createRelation')"
      :confirm-loading="saving"
      @ok="onSave"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('kbMgmt.kg.fromEntity')" required>
          <a-select
            v-model:value="form.from_entity_id"
            :options="entityOptions"
            show-search
            :disabled="!!editing"
            :placeholder="t('kbMgmt.kg.fromEntityPlaceholder')"
          />
        </a-form-item>
        <a-form-item :label="t('kbMgmt.kg.relationType')">
          <a-auto-complete
            v-model:value="form.relation_code"
            :options="relationCodeOptions"
            :placeholder="t('kbMgmt.kg.relationTypePlaceholder')"
          />
        </a-form-item>
        <a-form-item :label="t('kbMgmt.kg.predicate')">
          <a-input v-model:value="form.predicate" :placeholder="t('kbMgmt.kg.predicatePlaceholder')" />
        </a-form-item>
        <a-form-item :label="t('kbMgmt.kg.toEntity')" required>
          <a-select
            v-model:value="form.to_entity_id"
            :options="entityOptions"
            show-search
            :disabled="!!editing"
            :placeholder="t('kbMgmt.kg.toEntityPlaceholder')"
          />
        </a-form-item>
        <a-form-item :label="t('kbMgmt.kg.colWeight')">
          <a-input-number
            v-model:value="form.weight"
            :min="0"
            :max="1"
            :step="0.05"
            style="width: 160px"
            :placeholder="t('kbMgmt.kg.weightPlaceholder')"
          />
        </a-form-item>
        <a-form-item :label="t('kbMgmt.kg.evidenceText')">
          <a-textarea
            v-model:value="form.evidence"
            :rows="3"
            :placeholder="t('kbMgmt.kg.evidencePlaceholder')"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import * as api from '@/api/kg'
import type { KgEntity, KgRelation, KgRelationQuery, KgRelationStatus } from '@/api/kg'
import { formatWeight, typeLabel, weightColor } from '@/components/common/graph/graphTheme'

const props = defineProps<{
  knowledgeId: number
  /** 概览关系分布下钻预置的关系类型筛选 */
  initialRelationFilter?: string
}>()
const emit = defineEmits<{
  (e: 'inspect-entity', entityId: number): void
  (e: 'inspect-edge', relationId: number): void
  (e: 'provenance', relationId: number): void
}>()

const { t } = useI18n()

const rows = ref<KgRelation[]>([])
const entities = ref<KgEntity[]>([])
const relationCodes = ref<string[]>([])
const loading = ref(false)
const saving = ref(false)
const batchLoading = ref(false)
const modalOpen = ref(false)
const selectedRowKeys = ref<number[]>([])
/** 权重档筛选（客户端，不额外打后端） */
const weightTier = ref<'all' | 'high' | 'mid' | 'low'>('all')

/** 当前在画布/检视面板中选中的关系（行高亮，与原型选中态一致） */
const selectedEdgeId = ref<number | null>(null)

const query = reactive<{ relation_code?: string; status?: string }>({
  relation_code: props.initialRelationFilter || undefined,
})
const editing = ref<KgRelation | null>(null)
const form = reactive({
  from_entity_id: undefined as number | undefined,
  to_entity_id: undefined as number | undefined,
  relation_code: undefined as string | undefined,
  predicate: '',
  weight: null as number | null,
  evidence: '',
})

/** 「仅看待评审」已由状态筛选承载，避免两套状态互相打架 */

const entityOptions = computed(() =>
  entities.value.map((e) => ({ label: `${e.name}（${e.entity_key}）`, value: e.id })),
)
const relationCodeOptions = computed(() => relationCodes.value.map((c) => ({ value: c })))

/** 实体 id -> 类型码（关系表两端实体下方展示类型标签） */
const entityTypeMap = computed(() => {
  const map = new Map<number, string>()
  entities.value.forEach((e) => {
    if (e.type_code) map.set(e.id, e.type_code)
  })
  return map
})

function entityTypeLabel(entityId: number): string {
  return typeLabel(entityTypeMap.value.get(entityId))
}

/** 批量接受只对待评审关系生效，按钮据此置灰 */
const pendingSelectedCount = computed(
  () =>
    rows.value.filter(
      (r) => selectedRowKeys.value.includes(r.id) && r.status === 'suggested',
    ).length,
)

const columns = computed(() => [
  { title: t('kbMgmt.kg.colSource'), key: 'from', width: 180, ellipsis: true },
  { title: t('kbMgmt.kg.relationType'), key: 'relation', width: 130, ellipsis: true },
  { title: t('kbMgmt.kg.colTarget'), key: 'to', width: 180, ellipsis: true },
  { title: t('kbMgmt.kg.colWeight'), key: 'weight', width: 130 },
  { title: t('kbMgmt.kg.status'), key: 'status', width: 92 },
  { title: t('kbMgmt.kg.colExtractor'), key: 'extractor', width: 100 },
  { title: t('kbMgmt.kg.colMentions'), key: 'mentions', width: 72 },
  { title: t('kbMgmt.colActions'), key: 'actions', width: 196, fixed: 'right' },
])

const pagination = computed(() => ({
  pageSize: 10,
  size: 'small' as const,
  showSizeChanger: false,
  showTotal: (total: number) => t('kbMgmt.kg.totalCount', { count: total }),
}))

/** 权重三档：≥0.8 / 0.5–0.8 / <0.5（与色条同源） */
const viewRows = computed(() => {
  if (weightTier.value === 'all') return rows.value
  return rows.value.filter((row) => {
    const w = Number(row.weight ?? 0)
    if (weightTier.value === 'high') return w >= 0.8
    if (weightTier.value === 'mid') return w >= 0.5 && w < 0.8
    return w < 0.5
  })
})

const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: (string | number)[]) => {
    selectedRowKeys.value = keys.map((k) => Number(k))
  },
  getCheckboxProps: (record: KgRelation) => ({
    // 只有待评审的关系可以批量接受
    disabled: record.status !== 'suggested',
  }),
}))

function rowClass(record: KgRelation) {
  return selectedEdgeId.value === record.id ? 'kg-row--sel' : ''
}

/** 检视：切到图谱 Tab 并在画布与检视面板中选中该关系 */
function onInspectEdge(row: KgRelation) {
  selectedEdgeId.value = row.id
  emit('inspect-edge', row.id)
}

function statusText(s: KgRelationStatus) {
  if (s === 'accepted') return t('kbMgmt.kg.statusAccepted')
  if (s === 'rejected') return t('kbMgmt.kg.statusRejected')
  return t('kbMgmt.kg.statusSuggested')
}

function weightPct(w?: number | null) {
  const value = Number(w ?? 0)
  return Math.max(2, Math.min(100, Math.round(value * 100)))
}

async function reload() {
  loading.value = true
  try {
    const [relRes, entRes, stats] = await Promise.all([
      api.listRelations(props.knowledgeId, { ...query, limit: 500 } as KgRelationQuery),
      api.listEntities(props.knowledgeId, { limit: 500 }),
      api.getGraphStats(props.knowledgeId),
    ])
    rows.value = relRes?.items || []
    entities.value = entRes?.items || []
    relationCodes.value = Object.keys(stats?.by_relation || {})
    // 已选行可能在重新加载后消失，取交集避免残留
    const alive = new Set(rows.value.map((r) => r.id))
    selectedRowKeys.value = selectedRowKeys.value.filter((id) => alive.has(id))
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.loadFailed'))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.from_entity_id = undefined
  form.to_entity_id = undefined
  form.relation_code = undefined
  form.predicate = ''
  form.weight = null
  form.evidence = ''
  modalOpen.value = true
}

/** 编辑：端点锁定（后端约定：改端点=删了重建），类型/谓词/权重/证据可改 */
function openEdit(row: KgRelation) {
  editing.value = row
  form.from_entity_id = row.from_entity_id
  form.to_entity_id = row.to_entity_id
  form.relation_code = row.relation_code || undefined
  form.predicate = row.predicate || ''
  form.weight = row.weight == null ? null : Number(row.weight)
  const ev = row.evidence as Record<string, unknown> | null
  form.evidence = typeof ev?.text === 'string' ? ev.text : ''
  modalOpen.value = true
}

async function onSave() {
  if (!form.from_entity_id || !form.to_entity_id) {
    message.warning(t('kbMgmt.kg.relationEndpointsRequired'))
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      await api.updateRelation(props.knowledgeId, editing.value.id, {
        relation_code: form.relation_code || undefined,
        predicate: form.predicate || undefined,
        weight: form.weight ?? undefined,
        evidence: form.evidence.trim() ? { text: form.evidence.trim() } : undefined,
      })
      message.success(t('common.saved'))
    } else {
      await api.createRelation(props.knowledgeId, {
        from_entity_id: form.from_entity_id,
        to_entity_id: form.to_entity_id,
        relation_code: form.relation_code || undefined,
        predicate: form.predicate || undefined,
        weight: form.weight ?? undefined,
        evidence: form.evidence.trim() ? { text: form.evidence.trim() } : undefined,
      })
      message.success(t('kbMgmt.kg.created'))
    }
    modalOpen.value = false
    await reload()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function onReview(row: KgRelation, verdict: 'accepted' | 'rejected') {
  try {
    await api.reviewRelation(props.knowledgeId, row.id, verdict)
    message.success(t('kbMgmt.kg.reviewDone'))
    await reload()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.actionFailed'))
  }
}

/** 复核徽标文案（LLM 二次证据复核结论） */
function reviewBadgeText(verdict: string) {
  if (verdict === 'supported') return t('kbMgmt.kg.reviewSupported')
  if (verdict === 'weak') return t('kbMgmt.kg.reviewWeak')
  if (verdict === 'unsupported') return t('kbMgmt.kg.reviewUnsupported')
  return t('kbMgmt.kg.reviewFailed')
}

/** 批量评审（接受/驳回）：走后端批量端点，逐条容错 */
async function batchReview(verdict: 'accepted' | 'rejected') {
  const targets = rows.value.filter(
    (r) => selectedRowKeys.value.includes(r.id) && r.status === 'suggested',
  )
  if (!targets.length) return
  batchLoading.value = true
  try {
    const res = await api.batchReviewRelations(
      props.knowledgeId, targets.map((r) => r.id), verdict)
    if (res?.failed_count) {
      message.warning(t('kbMgmt.kg.batchPartial', { ok: res.ok_count, failed: res.failed_count }))
    } else {
      message.success(t('kbMgmt.kg.reviewDone'))
    }
    selectedRowKeys.value = []
    await reload()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.actionFailed'))
  } finally {
    batchLoading.value = false
  }
}

async function onBatchAccept() {
  await batchReview('accepted')
}

async function onBatchReject() {
  await batchReview('rejected')
}

/** 批量删除：走后端批量端点 */
async function onBatchDelete() {
  const ids = [...selectedRowKeys.value]
  if (!ids.length) return
  batchLoading.value = true
  try {
    const res = await api.batchDeleteRelations(props.knowledgeId, ids)
    if (res?.ok_count) message.success(t('kbMgmt.kg.deleted'))
    if (res?.failed_count) {
      message.warning(t('kbMgmt.kg.batchPartial', { ok: res.ok_count, failed: res.failed_count }))
    }
    selectedRowKeys.value = []
    await reload()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.actionFailed'))
  } finally {
    batchLoading.value = false
  }
}

// ── 手动触发关系 LLM 二次复核（构建后会自动跑一轮；此处补跑/重跑）────────
const reviewBatchLoading = ref(false)

async function onRunReviewBatch() {
  reviewBatchLoading.value = true
  try {
    const res = await api.runRelationReviewBatch(props.knowledgeId)
    message.success(
      t('kbMgmt.kg.reviewBatchDone', {
        reviewed: res?.reviewed ?? 0,
        supported: res?.supported ?? 0,
        weak: res?.weak ?? 0,
        unsupported: res?.unsupported ?? 0,
        failed: res?.review_failed ?? 0,
      }),
    )
    await reload()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.actionFailed'))
  } finally {
    reviewBatchLoading.value = false
  }
}

async function onDelete(row: KgRelation) {
  try {
    await api.deleteRelation(props.knowledgeId, row.id)
    message.success(t('kbMgmt.kg.deleted'))
    await reload()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.actionFailed'))
  }
}

watch(() => props.knowledgeId, reload, { immediate: true })
</script>

<style scoped>
.kg-triple-table__toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.kg-triple-table__spacer {
  flex: 1;
}
.kg-rel-link {
  color: var(--kg-text);
  cursor: pointer;
}
.kg-rel-link:hover {
  color: var(--kg-primary);
}
.kg-ent-cell {
  line-height: 1.45;
}
.kg-ent-cell .kg-muted {
  font-size: 11px;
}
.kg-rel-pred {
  margin-top: 2px;
  font-size: 11px;
}
.kg-weight {
  display: flex;
  align-items: center;
  gap: 6px;
}
.kg-weight__num {
  font-size: 11.5px;
  font-variant-numeric: tabular-nums;
}
.kg-rel-mentions {
  font-variant-numeric: tabular-nums;
}
/* 状态：与原型一致的小胶囊（已采纳绿 / 待评审黄 / 已驳回灰） */
.kg-status {
  display: inline-flex;
  align-items: center;
  height: 19px;
  padding: 0 6px;
  border: 1px solid var(--kg-border);
  border-radius: var(--kg-r-xs);
  background: var(--kg-subtle);
  color: var(--kg-text-2);
  font-size: 11px;
  line-height: 1;
}
/* LLM 二次复核徽标（绿=支撑 / 黄=存疑 / 红=不支撑 / 灰=复核失败） */
.kg-review-badge {
  display: inline-flex;
  align-items: center;
  height: 18px;
  margin-top: 4px;
  padding: 0 6px;
  border: 1px solid var(--kg-border);
  border-radius: var(--kg-r-xs);
  font-size: 11px;
  line-height: 1;
}
.kg-review-badge--supported {
  border-color: var(--kg-ok-border);
  background: var(--kg-ok-bg);
  color: var(--kg-ok-fg);
}
.kg-review-badge--weak {
  border-color: var(--kg-warn-border);
  background: var(--kg-warn-bg);
  color: var(--kg-warn-fg);
}
.kg-review-badge--unsupported {
  border-color: var(--kg-danger-border, #cf1322);
  background: var(--kg-danger-bg, #fff1f0);
  color: var(--kg-danger-fg, #cf1322);
}
.kg-review-badge--review_failed {
  color: var(--kg-text-3);
}
.kg-status--suggested {
  border-color: var(--kg-warn-border);
  background: var(--kg-warn-bg);
  color: var(--kg-warn-fg);
}
.kg-status--accepted {
  border-color: var(--kg-ok-border);
  background: var(--kg-ok-bg);
  color: var(--kg-ok-fg);
}
.kg-status--rejected {
  color: var(--kg-text-3);
}
/* 选中行（对应画布/检视面板当前关系） */
:deep(.ant-table-tbody > tr.kg-row--sel > td) {
  background: var(--kg-tint);
}
</style>
