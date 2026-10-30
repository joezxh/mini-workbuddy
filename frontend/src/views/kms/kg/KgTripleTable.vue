<template>
  <div class="kg-triple-table">
    <a-space class="kg-triple-table__toolbar" wrap>
      <a-select
        v-model:value="query.relation_code"
        :placeholder="t('kbMgmt.kg.filterRelationType')"
        allow-clear
        style="width: 190px"
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
        style="width: 150px"
        @change="reload"
      >
        <a-select-option value="suggested">{{ t('kbMgmt.kg.statusSuggested') }}</a-select-option>
        <a-select-option value="accepted">{{ t('kbMgmt.kg.statusAccepted') }}</a-select-option>
        <a-select-option value="rejected">{{ t('kbMgmt.kg.statusRejected') }}</a-select-option>
      </a-select>
      <a-button @click="reload">{{ t('common.refresh') }}</a-button>
      <a-button type="primary" :disabled="!entities.length" @click="openCreate">
        {{ t('kbMgmt.kg.addRelation') }}
      </a-button>
    </a-space>

    <a-table
      :columns="columns"
      :data-source="rows"
      :loading="loading"
      row-key="id"
      size="small"
      :pagination="false"
      :scroll="{ x: 900 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'from'">
          <a-button type="link" size="small" @click="$emit('inspect-entity', record.from_entity_id)">
            {{ record.from_entity_name || `#${record.from_entity_id}` }}
          </a-button>
        </template>
        <template v-else-if="column.key === 'to'">
          <a-button type="link" size="small" @click="$emit('inspect-entity', record.to_entity_id)">
            {{ record.to_entity_name || `#${record.to_entity_id}` }}
          </a-button>
        </template>
        <template v-else-if="column.key === 'relation_code'">
          <a-tag v-if="record.relation_code" color="purple">{{ record.relation_code }}</a-tag>
          <span v-else class="kg-muted">{{ t('kbMgmt.kg.freePredicate') }}</span>
          <span v-if="record.predicate" class="kg-muted"> · {{ record.predicate }}</span>
        </template>
        <template v-else-if="column.key === 'weight'">
          <a-tag :color="weightColor(record.weight)">{{ weightText(record.weight) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-space size="small">
            <a-button
              v-if="record.status === 'suggested'"
              size="small"
              type="link"
              @click="onReview(record, 'accepted')"
            >
              {{ t('kbMgmt.kg.accept') }}
            </a-button>
            <a-popconfirm
              v-if="record.status === 'suggested'"
              :title="t('kbMgmt.kg.confirmRejectRelation')"
              @confirm="onReview(record, 'rejected')"
            >
              <a-button size="small" type="link" danger>{{ t('kbMgmt.kg.reject') }}</a-button>
            </a-popconfirm>
            <a-popconfirm
              :title="t('kbMgmt.kg.confirmDeleteRelation')"
              @confirm="onDelete(record)"
            >
              <a-button size="small" type="link" danger>{{ t('common.delete') }}</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalOpen"
      :title="t('kbMgmt.kg.addRelation')"
      :confirm-loading="saving"
      @ok="onSave"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('kbMgmt.kg.fromEntity')" required>
          <a-select
            v-model:value="form.from_entity_id"
            :options="entityOptions"
            show-search
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
            :placeholder="t('kbMgmt.kg.toEntityPlaceholder')"
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
import type { KgEntity, KgRelation, KgRelationStatus } from '@/api/kg'

const props = defineProps<{ knowledgeId: number }>()
defineEmits<{ (e: 'inspect-entity', entityId: number): void }>()

const { t } = useI18n()

const rows = ref<KgRelation[]>([])
const entities = ref<KgEntity[]>([])
const relationCodes = ref<string[]>([])
const loading = ref(false)
const saving = ref(false)
const modalOpen = ref(false)

const query = reactive<{ relation_code?: string; status?: string }>({})
const form = reactive({
  from_entity_id: undefined as number | undefined,
  to_entity_id: undefined as number | undefined,
  relation_code: undefined as string | undefined,
  predicate: '',
})

const entityOptions = computed(() =>
  entities.value.map((e) => ({ label: `${e.name}（${e.entity_key}）`, value: e.id })),
)
const relationCodeOptions = computed(() => relationCodes.value.map((c) => ({ value: c })))

const columns = computed(() => [
  { title: t('kbMgmt.kg.fromEntity'), key: 'from', width: 180 },
  { title: t('kbMgmt.kg.relationType'), key: 'relation_code', width: 200 },
  { title: t('kbMgmt.kg.toEntity'), key: 'to', width: 180 },
  { title: t('kbMgmt.kg.weight'), key: 'weight', width: 110 },
  { title: t('kbMgmt.kg.status'), key: 'status', width: 110 },
  { title: t('kbMgmt.colActions'), key: 'actions', width: 200, fixed: 'right' },
])

function statusText(s: KgRelationStatus) {
  if (s === 'accepted') return t('kbMgmt.kg.statusAccepted')
  if (s === 'rejected') return t('kbMgmt.kg.statusRejected')
  return t('kbMgmt.kg.statusSuggested')
}

function statusColor(s: KgRelationStatus) {
  if (s === 'accepted') return 'green'
  if (s === 'rejected') return 'red'
  return 'orange'
}

/** 置信度着色：<0.5 红 / 0.5–0.8 橙 / >0.8 绿 */
function weightColor(w: number | null) {
  if (w == null) return 'default'
  if (w < 0.5) return 'red'
  if (w <= 0.8) return 'orange'
  return 'green'
}

function weightText(w: number | null) {
  if (w == null) return '-'
  return w.toFixed(2)
}

async function reload() {
  loading.value = true
  try {
    const [relRes, entRes, stats] = await Promise.all([
      api.listRelations(props.knowledgeId, { ...query, limit: 500 }),
      api.listEntities(props.knowledgeId, { limit: 500 }),
      api.getGraphStats(props.knowledgeId),
    ])
    rows.value = relRes?.items || []
    entities.value = entRes?.items || []
    relationCodes.value = Object.keys(stats?.by_relation || {})
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.kg.loadFailed'))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.from_entity_id = undefined
  form.to_entity_id = undefined
  form.relation_code = undefined
  form.predicate = ''
  modalOpen.value = true
}

async function onSave() {
  if (!form.from_entity_id || !form.to_entity_id) {
    message.warning(t('kbMgmt.kg.relationEndpointsRequired'))
    return
  }
  saving.value = true
  try {
    await api.createRelation(props.knowledgeId, {
      from_entity_id: form.from_entity_id,
      to_entity_id: form.to_entity_id,
      relation_code: form.relation_code || undefined,
      predicate: form.predicate || undefined,
    })
    message.success(t('kbMgmt.kg.created'))
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
  margin-bottom: 12px;
}
.kg-muted {
  color: #999;
}
</style>
