<template>
  <div class="kg-entity-table">
    <a-space class="kg-entity-table__toolbar" wrap>
      <a-input
        v-model:value="query.keyword"
        :placeholder="t('kbMgmt.kg.searchPlaceholder')"
        allow-clear
        style="width: 220px"
        @pressEnter="reload"
      />
      <a-select
        v-model:value="query.type_code"
        :placeholder="t('kbMgmt.kg.filterType')"
        allow-clear
        style="width: 180px"
        @change="reload"
      >
        <a-select-option v-for="code in typeCodes" :key="code" :value="code">
          {{ code }}
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
        <a-select-option value="active">{{ t('kbMgmt.kg.statusActive') }}</a-select-option>
        <a-select-option value="deprecated">{{ t('kbMgmt.kg.statusDeprecated') }}</a-select-option>
      </a-select>
      <a-button @click="reload">{{ t('common.refresh') }}</a-button>
      <a-button type="primary" @click="openCreate">{{ t('kbMgmt.kg.addEntity') }}</a-button>
    </a-space>

    <a-table
      :columns="columns"
      :data-source="rows"
      :loading="loading"
      row-key="id"
      size="small"
      :pagination="false"
      :scroll="{ x: 900 }"
      class="kg-entity-table__table"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'type'">
          <a-tag v-if="record.type_code" color="blue">{{ record.type_code }}</a-tag>
          <span v-else class="kg-muted">{{ t('kbMgmt.kg.unclassified') }}</span>
        </template>
        <template v-else-if="column.key === 'aliases'">
          <a-tag v-for="a in record.aliases" :key="a" class="kg-tag">{{ a }}</a-tag>
          <span v-if="!record.aliases?.length" class="kg-muted">-</span>
        </template>
        <template v-else-if="column.key === 'properties'">
          <span v-if="!record.properties || !Object.keys(record.properties).length" class="kg-muted">-</span>
          <span v-else>{{ propertySummary(record) }}</span>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-space size="small">
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
            <a-popconfirm
              :title="t('kbMgmt.kg.confirmDeleteEntity')"
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
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import * as api from '@/api/kg'
import type { KgEntity, KgEntityStatus } from '@/api/kg'

const props = defineProps<{ knowledgeId: number }>()

const { t } = useI18n()

const rows = ref<KgEntity[]>([])
const loading = ref(false)
const saving = ref(false)
const modalOpen = ref(false)
const editing = ref<KgEntity | null>(null)
const knownTypes = ref<string[]>([])

const query = reactive<{ keyword?: string; type_code?: string; status?: string }>({})

const form = reactive({
  name: '',
  type_code: undefined as string | undefined,
  aliases: [] as string[],
})

const typeCodes = computed(() => knownTypes.value)
const typeCodeOptions = computed(() => knownTypes.value.map((c) => ({ value: c })))

const columns = computed(() => [
  { title: t('kbMgmt.kg.entityName'), dataIndex: 'name', key: 'name', width: 200 },
  { title: t('kbMgmt.kg.entityKey'), dataIndex: 'entity_key', key: 'entity_key', width: 220 },
  { title: t('kbMgmt.kg.entityType'), key: 'type', width: 150 },
  { title: t('kbMgmt.kg.aliases'), key: 'aliases', width: 180 },
  { title: t('kbMgmt.kg.properties'), key: 'properties', width: 220 },
  { title: t('kbMgmt.kg.mentionCount'), dataIndex: 'mention_count', key: 'mention_count', width: 100 },
  { title: t('kbMgmt.kg.status'), key: 'status', width: 110 },
  { title: t('kbMgmt.colActions'), key: 'actions', width: 220, fixed: 'right' },
])

function statusText(s: KgEntityStatus) {
  if (s === 'active') return t('kbMgmt.kg.statusActive')
  if (s === 'deprecated') return t('kbMgmt.kg.statusDeprecated')
  return t('kbMgmt.kg.statusSuggested')
}

function statusColor(s: KgEntityStatus) {
  if (s === 'active') return 'green'
  if (s === 'deprecated') return 'default'
  return 'orange'
}

function propertySummary(row: KgEntity) {
  const entries = Object.entries(row.properties || {})
  if (!entries.length) return ''
  const head = entries.slice(0, 2).map(([k, v]) => `${k}=${v}`).join(', ')
  return entries.length > 2 ? `${head} +${entries.length - 2}` : head
}

async function reload() {
  loading.value = true
  try {
    const res = await api.listEntities(props.knowledgeId, { ...query, limit: 500 })
    rows.value = res?.items || []
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

watch(() => props.knowledgeId, reload, { immediate: true })
</script>

<style scoped>
.kg-entity-table__toolbar {
  margin-bottom: 12px;
}
.kg-entity-table__table {
  margin-top: 4px;
}
.kg-tag {
  margin-right: 4px;
}
.kg-muted {
  color: #999;
}
</style>
