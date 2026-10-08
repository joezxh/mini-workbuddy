<template>
  <a-card :title="t('kbMgmt.tableRecords')" size="small">
    <a-space class="trl__bar" wrap>
      <a-select
        v-model:value="selectedDoc"
        :options="docOptions"
        style="min-width: 240px"
        :placeholder="t('kbMgmt.selectDocument')"
        @change="load"
      />
      <a-button :loading="loading" @click="load">{{ t('common.refresh') }}</a-button>
      <a-button type="primary" :disabled="!selectedDoc" @click="startCreate">{{ t('kbMgmt.addRow') }}</a-button>
    </a-space>

    <a-empty v-if="!rows.length && !loading" :description="t('kbMgmt.noRows')" />
    <a-table
      v-else
      size="small"
      :data-source="rows"
      :columns="columns"
      :pagination="{ pageSize: 10, size: 'small' }"
      :loading="loading"
      row-key="id"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'op'">
          <a-space size="small">
            <a-button size="small" @click="startEdit(record)">{{ t('common.edit') }}</a-button>
            <a-popconfirm :title="t('kbMgmt.confirmDeleteRow')" @confirm="remove(record)">
              <a-button size="small" danger>{{ t('common.delete') }}</a-button>
            </a-popconfirm>
          </a-space>
        </template>
        <template v-else-if="column.key.startsWith('m_')">
          {{ record.metadata?.[column.key.slice(2)] ?? '' }}
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="editorOpen"
      :title="editing ? t('kbMgmt.editRow') : t('kbMgmt.addRow')"
      @ok="submit"
      :confirm-loading="saving"
    >
      <a-alert
        class="trl__hint"
        type="info"
        :message="t('kbMgmt.embeddedColumnHint')"
        show-icon
      />
      <a-form layout="vertical">
        <a-form-item :label="t('kbMgmt.embeddedColumn')" required>
          <a-input v-model:value="form.content" />
        </a-form-item>
        <a-form-item v-for="f in metaFields" :key="f" :label="f">
          <a-input v-model:value="form.meta[f]" />
        </a-form-item>
        <a-form-item v-if="!metaFields.length" :label="t('kbMgmt.filterableField')">
          <a-input
            v-model:value="newField"
            :placeholder="t('kbMgmt.newFieldPlaceholder')"
            @press-enter="addField"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </a-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  createTableRecord,
  deleteSegment,
  listDocumentSegments,
  listDocuments,
  updateSegment,
  type KbSegment,
} from '@/api/kb'

const props = defineProps<{ knowledgeId: number; collection: string }>()
const { t } = useI18n()

const loading = ref(false)
const docs = ref<any[]>([])
const selectedDoc = ref<string | null>(null)
const rows = ref<KbSegment[]>([])

const editorOpen = ref(false)
const saving = ref(false)
const editing = ref<KbSegment | null>(null)
const newField = ref('')
const form = ref<{ content: string; meta: Record<string, string> }>({ content: '', meta: {} })

const docOptions = computed(() =>
  docs.value.map((d) => ({ label: `${d.name}（${d.segment_count}）`, value: d.document_id })),
)

/** 表格行：content 恒为被嵌入列，其余列是 metadata 里的动态键 */
const metaFields = computed(() => {
  const keys = new Set<string>()
  for (const r of rows.value) {
    for (const k of Object.keys(r.metadata || {})) {
      if (!['chunk_type', 'tenant_id', 'source', 'embed_field'].includes(k)) keys.add(k)
    }
  }
  return [...keys].sort()
})

const columns = computed(() => [
  { title: t('kbMgmt.embeddedColumn'), dataIndex: 'content', key: 'content' },
  ...metaFields.value.map((f) => ({ title: f, key: `m_${f}` })),
  { title: t('kbMgmt.common.actions'), key: 'op', width: 130 },
])

async function loadDocs() {
  const res: any = await listDocuments(props.knowledgeId)
  docs.value = res.items || res || []
  if (!selectedDoc.value && docs.value.length) selectedDoc.value = docs.value[0].document_id
}

async function load() {
  if (!selectedDoc.value) return
  loading.value = true
  try {
    const res: any = await listDocumentSegments(selectedDoc.value, {
      chunk_type: 'table_row',
      page_size: 500,
    })
    rows.value = res.items || []
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.loadFailed'))
  } finally {
    loading.value = false
  }
}

function addField() {
  const name = newField.value.trim()
  if (!name) return
  form.value.meta[name] = ''
  newField.value = ''
}

function startCreate() {
  editing.value = null
  form.value = { content: '', meta: Object.fromEntries(metaFields.value.map((f) => [f, ''])) }
  editorOpen.value = true
}

function startEdit(row: KbSegment) {
  editing.value = row
  form.value = {
    content: row.content || '',
    meta: Object.fromEntries(
      metaFields.value.map((f) => [f, String(row.metadata?.[f] ?? '')]),
    ),
  }
  editorOpen.value = true
}

async function submit() {
  if (!selectedDoc.value) return
  if (!form.value.content.trim()) {
    message.warning(t('kbMgmt.contentRequired'))
    return
  }
  saving.value = true
  try {
    const metadata = { ...form.value.meta, chunk_type: 'table_row' }
    if (editing.value) {
      await updateSegment(editing.value.id, { content: form.value.content, metadata })
    } else {
      await createTableRecord(props.collection, {
        document_id: selectedDoc.value,
        content: form.value.content,
        metadata,
      })
    }
    message.success(t('kbMgmt.saved'))
    editorOpen.value = false
    await load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function remove(row: KbSegment) {
  try {
    await deleteSegment(row.id)
    message.success(t('kbMgmt.common.deleted'))
    await load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.common.deleteFailed'))
  }
}

onMounted(async () => {
  await loadDocs()
  await load()
})
watch(() => props.knowledgeId, async () => {
  selectedDoc.value = null
  await loadDocs()
  await load()
})
</script>

<style scoped>
.trl__bar {
  margin-bottom: 12px;
}
.trl__hint {
  margin-bottom: 12px;
}
</style>
