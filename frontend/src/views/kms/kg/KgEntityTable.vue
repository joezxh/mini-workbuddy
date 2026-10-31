<template>
  <div class="kg-entity-table">
    <div class="kg-entity-table__toolbar">
      <div class="kg-entity-table__filters">
        <a-input
          v-model:value="query.keyword"
          :placeholder="t('kbMgmt.kg.entitySearchPh')"
          allow-clear
          style="width: 230px"
          @pressEnter="reload"
        />
        <a-select
          v-model:value="query.type_code"
          :placeholder="t('kbMgmt.kg.typeAll')"
          allow-clear
          style="width: 150px"
          @change="reload"
        >
          <a-select-option v-for="code in typeCodes" :key="code" :value="code">
            <span class="kg-dot-inline" :style="{ background: typeTone(code).color }" />
            {{ typeLabel(code) }}
          </a-select-option>
        </a-select>
        <a-select
          v-model:value="query.status"
          :placeholder="t('kbMgmt.kg.statusAll')"
          allow-clear
          style="width: 130px"
          @change="reload"
        >
          <a-select-option value="active">{{ t('kbMgmt.kg.statusActive') }}</a-select-option>
          <a-select-option value="suggested">{{ t('kbMgmt.kg.statusSuggested') }}</a-select-option>
          <a-select-option value="deprecated">{{ t('kbMgmt.kg.statusDeprecated') }}</a-select-option>
        </a-select>
        <a-checkbox v-model:checked="pendingOnly" @change="reload">
          {{ t('kbMgmt.kg.onlyPendingReview') }}
        </a-checkbox>
      </div>

      <div class="kg-entity-table__actions">
        <span class="kg-muted">{{ t('kbMgmt.kg.selectedCount', { count: selectedKeys.length }) }}</span>
        <a-button size="small" :disabled="!selectedKeys.length" @click="onBatchAccept">
          {{ t('kbMgmt.kg.batchAccept') }}
        </a-button>
        <a-button size="small" :disabled="!selectedKeys.length" @click="openBatchRetype">
          {{ t('kbMgmt.kg.batchRetype') }}
        </a-button>
        <a-popconfirm
          :title="t('kbMgmt.kg.confirmDeleteEntity')"
          :disabled="!selectedKeys.length"
          @confirm="onBatchDelete"
        >
          <a-button size="small" danger :disabled="!selectedKeys.length">
            {{ t('kbMgmt.kg.batchDelete') }}
          </a-button>
        </a-popconfirm>
        <a-button size="small" type="primary" @click="openCreate">
          <template #icon><PlusOutlined /></template>
          {{ t('kbMgmt.kg.createEntity') }}
        </a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data-source="rows"
      :loading="loading"
      row-key="id"
      size="small"
      :row-selection="rowSelection"
      :row-class-name="rowClassName"
      :pagination="pagination"
      :scroll="{ x: 1080 }"
      class="kg-entity-table__table"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <div class="kg-ent-name">{{ record.name }}</div>
          <div class="kg-ent-key">{{ record.entity_key }}</div>
        </template>
        <template v-else-if="column.key === 'type'">
          <span
            v-if="record.type_code"
            class="kg-type-tag"
            :style="typeTagStyle(record.type_code)"
          >{{ typeLabel(record.type_code) }}</span>
          <span v-else class="kg-muted">{{ t('kbMgmt.kg.unclassified') }}</span>
        </template>
        <template v-else-if="column.key === 'aliases'">
          <a-tag v-for="a in record.aliases" :key="a" class="kg-alias-tag">{{ a }}</a-tag>
          <span v-if="!record.aliases?.length" class="kg-muted">—</span>
        </template>
        <template v-else-if="column.key === 'properties'">
          <span v-if="!record.properties || !Object.keys(record.properties).length" class="kg-muted">—</span>
          <span v-else>{{ propertySummary(record.properties) }}</span>
        </template>
        <template v-else-if="column.key === 'mention_count'">
          {{ record.mention_count ?? 0 }}
        </template>
        <template v-else-if="column.key === 'status'">
          <span class="kg-status" :class="`kg-status--${record.status}`">{{ statusText(record.status) }}</span>
        </template>
        <template v-else-if="column.key === 'vector'">
          <span class="kg-vec" :class="{ 'kg-vec--on': record.has_vector }">
            {{ record.has_vector ? t('kbMgmt.kg.vectorIndexed') : t('kbMgmt.kg.vectorPending') }}
          </span>
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-button size="small" type="link" @click="emit('inspect-entity', record.id)">
            {{ t('kbMgmt.kg.actionInspect') }}
          </a-button>
          <a-button size="small" type="link" @click="openEdit(record)">
            {{ t('common.edit') }}
          </a-button>
          <a-button
            v-if="record.status === 'suggested'"
            size="small"
            type="link"
            @click="onAccept(record)"
          >
            {{ t('kbMgmt.kg.accept') }}
          </a-button>
          <a-button size="small" type="link" @click="emit('provenance', record.id)">
            {{ t('kbMgmt.kg.actionProvenance') }}
          </a-button>
          <a-popconfirm :title="t('kbMgmt.kg.confirmDeleteEntity')" @confirm="onDelete(record)">
            <a-button size="small" type="link" danger>{{ t('common.delete') }}</a-button>
          </a-popconfirm>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalOpen"
      :title="editing ? t('kbMgmt.kg.editEntity') : t('kbMgmt.kg.addEntity')"
      :confirm-loading="saving"
      @ok="onSave"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('kbMgmt.kg.entityName')" required>
          <a-input v-model:value="form.name" :placeholder="t('kbMgmt.kg.entityNamePlaceholder')" />
        </a-form-item>
        <a-form-item :label="t('kbMgmt.kg.entityType')">
          <a-auto-complete
            v-model:value="form.type_code"
            :options="typeCodeOptions"
            :placeholder="t('kbMgmt.kg.entityTypePlaceholder')"
          />
        </a-form-item>
        <a-form-item :label="t('kbMgmt.kg.aliases')">
          <a-select
            v-model:value="form.aliases"
            mode="tags"
            :placeholder="t('kbMgmt.kg.aliasesPlaceholder')"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="retypeOpen"
      :title="t('kbMgmt.kg.batchRetype')"
      :confirm-loading="saving"
      @ok="onBatchRetype"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('kbMgmt.kg.entityType')">
          <a-auto-complete
            v-model:value="retypeCode"
            :options="typeCodeOptions"
            :placeholder="t('kbMgmt.kg.entityTypePlaceholder')"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
/**
 * 实体表：搜索 / 类型 / 状态 / 仅看待评审 + 批量接受·改类型·删除 + 分页。
 *
 * 与原型 kg-knowledge-base-preview.html「实体」Tab 对齐：
 * 实体列两行（名称 + 归一名）、类型按语义色着色、含向量状态列。
 */
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import * as api from '@/api/kg'
import type { KgEntity, KgEntityStatus } from '@/api/kg'
import { propertySummary, typeLabel, typeTone } from '@/components/common/graph/graphTheme'

const props = defineProps<{ knowledgeId: number }>()
const emit = defineEmits<{
  (e: 'inspect-entity', id: number): void
  (e: 'provenance', id: number): void
}>()

const { t } = useI18n()

const rows = ref<KgEntity[]>([])
const loading = ref(false)
const saving = ref(false)
const modalOpen = ref(false)
const retypeOpen = ref(false)
const editing = ref<KgEntity | null>(null)
const knownTypes = ref<string[]>([])
const pendingOnly = ref(false)
const selectedKeys = ref<number[]>([])
const retypeCode = ref<string | undefined>(undefined)

const query = reactive<{ keyword?: string; type_code?: string; status?: string }>({})

const form = reactive({
  name: '',
  type_code: undefined as string | undefined,
  aliases: [] as string[],
})

const typeCodes = computed(() => knownTypes.value)
const typeCodeOptions = computed(() => knownTypes.value.map((c) => ({ value: c })))

const columns = computed(() => [
  { title: t('kbMgmt.kg.colEntity'), key: 'name', width: 240 },
  { title: t('kbMgmt.kg.colType'), key: 'type', width: 120 },
  { title: t('kbMgmt.kg.aliases'), key: 'aliases', width: 190 },
  { title: t('kbMgmt.kg.colPropsSummary'), key: 'properties', width: 220 },
  { title: t('kbMgmt.kg.colMentions'), key: 'mention_count', width: 80 },
  { title: t('kbMgmt.kg.status'), key: 'status', width: 100 },
  { title: t('kbMgmt.kg.colVector'), key: 'vector', width: 90 },
  { title: t('kbMgmt.kg.colActions'), key: 'actions', width: 240, fixed: 'right' as const },
])

const pagination = computed(() => ({
  pageSize: 10,
  showSizeChanger: false,
  hideOnSinglePage: false,
  showTotal: (total: number) => t('kbMgmt.kg.totalCount', { count: total }),
}))

const rowSelection = computed(() => ({
  selectedRowKeys: selectedKeys.value,
  columnWidth: 40,
  onChange: (keys: (string | number)[]) => {
    selectedKeys.value = keys.map((k) => Number(k))
  },
}))

function rowClassName(record: KgEntity) {
  return selectedKeys.value.includes(record.id) ? 'kg-row--on' : ''
}

function typeTagStyle(code: string) {
  const tone = typeTone(code)
  return {
    color: tone.fg,
    background: tone.bg,
    borderColor: tone.border,
  }
}

function statusText(s: KgEntityStatus) {
  if (s === 'active') return t('kbMgmt.kg.statusActive')
  if (s === 'deprecated') return t('kbMgmt.kg.statusDeprecated')
  return t('kbMgmt.kg.statusSuggested')
}

async function reload() {
  loading.value = true
  try {
    const params: api.KgEntityQuery = {
      ...query,
      status: pendingOnly.value ? 'suggested' : query.status,
      limit: 500,
    }
    const res = await api.listEntities(props.knowledgeId, params)
    rows.value = res?.items || []
    // 已选集合可能已不存在于新结果中
    const alive = new Set(rows.value.map((r) => r.id))
    selectedKeys.value = selectedKeys.value.filter((id) => alive.has(id))
    const stats = await api.getGraphStats(props.knowledgeId)
    knownTypes.value = Object.keys(stats?.by_type || {})
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.loadFailed'))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.name = ''
  form.type_code = undefined
  form.aliases = []
  modalOpen.value = true
}

function openEdit(row: KgEntity) {
  editing.value = row
  form.name = row.name
  form.type_code = row.type_code || undefined
  form.aliases = [...(row.aliases || [])]
  modalOpen.value = true
}

async function onSave() {
  if (!form.name?.trim()) {
    message.warning(t('kbMgmt.kg.entityNameRequired'))
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      type_code: form.type_code || undefined,
      aliases: form.aliases || [],
    }
    if (editing.value) {
      await api.updateEntity(props.knowledgeId, editing.value.id, payload)
    } else {
      await api.createEntity(props.knowledgeId, payload)
    }
    message.success(t('common.saved'))
    modalOpen.value = false
    await reload()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function onAccept(row: KgEntity) {
  try {
    await api.acceptEntity(props.knowledgeId, row.id)
    message.success(t('kbMgmt.kg.accepted'))
    await reload()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.actionFailed'))
  }
}

async function onDelete(row: KgEntity) {
  try {
    await api.deleteEntity(props.knowledgeId, row.id)
    message.success(t('kbMgmt.kg.deleted'))
    await reload()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.actionFailed'))
  }
}

/** 批量接受：仅对 suggested 行调 accept，逐个容错 */
async function onBatchAccept() {
  const targets = rows.value.filter(
    (r) => selectedKeys.value.includes(r.id) && r.status === 'suggested',
  )
  if (!targets.length) return
  const results = await Promise.allSettled(
    targets.map((r) => api.acceptEntity(props.knowledgeId, r.id)),
  )
  const ok = results.filter((r) => r.status === 'fulfilled').length
  if (ok) message.success(t('kbMgmt.kg.accepted'))
  if (ok < results.length) message.warning(t('kbMgmt.kg.actionFailed'))
  selectedKeys.value = []
  await reload()
}

function openBatchRetype() {
  retypeCode.value = undefined
  retypeOpen.value = true
}

/** 批量改类型：逐条 PUT type_code，null 表示清空类型 */
async function onBatchRetype() {
  const ids = [...selectedKeys.value]
  if (!ids.length) return
  saving.value = true
  try {
    const code = retypeCode.value?.trim() || undefined
    const results = await Promise.allSettled(
      ids.map((id) => api.updateEntity(props.knowledgeId, id, { type_code: code })),
    )
    const ok = results.filter((r) => r.status === 'fulfilled').length
    if (ok) message.success(t('common.saved'))
    if (ok < results.length) message.warning(t('kbMgmt.kg.saveFailed'))
    retypeOpen.value = false
    selectedKeys.value = []
    await reload()
  } finally {
    saving.value = false
  }
}

async function onBatchDelete() {
  const ids = [...selectedKeys.value]
  if (!ids.length) return
  const results = await Promise.allSettled(ids.map((id) => api.deleteEntity(props.knowledgeId, id)))
  const ok = results.filter((r) => r.status === 'fulfilled').length
  if (ok) message.success(t('kbMgmt.kg.deleted'))
  if (ok < results.length) message.warning(t('kbMgmt.kg.actionFailed'))
  selectedKeys.value = []
  await reload()
}

watch(() => props.knowledgeId, reload, { immediate: true })
</script>

<style scoped>
.kg-entity-table__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.kg-entity-table__filters,
.kg-entity-table__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.kg-entity-table__table {
  margin-top: 4px;
}
/* 实体列：名称 + 归一名（原型用行内代码样式，红字浅灰底） */
.kg-ent-name {
  font-size: 12.5px;
  color: var(--kg-text);
  line-height: 1.35;
}
.kg-ent-key {
  margin-top: 1px;
  padding: 0 3px;
  display: inline-block;
  border-radius: 3px;
  background: var(--kg-subtle);
  color: var(--kg-code-fg);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 10.5px;
  line-height: 15px;
}
.kg-type-tag {
  display: inline-block;
  padding: 0 7px;
  border: 1px solid transparent;
  border-radius: var(--kg-r-xs);
  font-size: 11px;
  line-height: 18px;
}
.kg-alias-tag {
  background: var(--kg-subtle);
  border-color: var(--kg-border);
  color: var(--kg-text-2);
}
.kg-status {
  display: inline-block;
  padding: 0 7px;
  border: 1px solid transparent;
  border-radius: var(--kg-r-xs);
  font-size: 11px;
  line-height: 18px;
}
.kg-status--active {
  border-color: var(--kg-ok-border);
  background: var(--kg-ok-bg);
  color: var(--kg-ok-fg);
}
.kg-status--suggested {
  border-color: var(--kg-warn-border);
  background: var(--kg-warn-bg);
  color: var(--kg-warn-fg);
}
.kg-status--deprecated {
  border-color: var(--kg-border);
  background: var(--kg-subtle);
  color: var(--kg-text-3);
}
.kg-vec {
  font-size: 11.5px;
  color: var(--kg-text-3);
}
.kg-vec--on {
  color: var(--kg-ok-fg);
}
.kg-dot-inline {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 6px;
  border-radius: 50%;
  vertical-align: 1px;
}
/* 选中行浅蓝底（原型默认选中实体时的高亮） */
:deep(.kg-row--on) > td {
  background: var(--kg-info-bg) !important;
}
</style>
