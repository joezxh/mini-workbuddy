<template>
  <div class="kb-coll-mgr">
    <a-space class="kb-coll-mgr__bar" wrap>
      <a-button type="primary" size="small" @click="openCreate">
        {{ t('kbMgmt.collCreate') }}
      </a-button>
      <a-button size="small" :loading="loading" @click="load">{{ t('common.refresh') }}</a-button>
      <span class="kb-coll-mgr__tip">{{ t('kbMgmt.collTip') }}</span>
    </a-space>

    <a-table
      size="small"
      class="kb-coll-mgr__table"
      :data-source="collections"
      :columns="columns"
      :pagination="{ pageSize: 10, size: 'small' }"
      :loading="loading"
      row-key="id"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'embed_fields'">
          <a-tag v-for="f in record.embed_fields" :key="f" color="blue">{{ f }}</a-tag>
          <span v-if="!record.embed_fields?.length" class="kb-coll-mgr__muted">—</span>
        </template>
        <template v-else-if="column.key === 'ref_files'">
          <a-popover v-if="docsOf(record.id).length" :title="t('kbMgmt.collRefFiles')">
            <template #content>
              <div class="kb-coll-mgr__doc-list">
                <a-tag v-for="d in docsOf(record.id)" :key="d.document_id">{{ d.name }}</a-tag>
              </div>
            </template>
            <a-button size="small" type="link">
              {{ docsOf(record.id).length }} {{ t('kbMgmt.collRefFiles') }}
            </a-button>
          </a-popover>
          <span v-else class="kb-coll-mgr__muted">{{ t('kbMgmt.collNoFiles') }}</span>
        </template>
        <template v-else-if="column.key === 'op'">
          <a-space size="small">
            <a-button size="small" @click="openEditFields(record)">{{ t('kbMgmt.collEditFields') }}</a-button>
            <a-button size="small" @click="openRename(record)">{{ t('kbMgmt.collRename') }}</a-button>
            <a-popconfirm :title="t('kbMgmt.collDeleteConfirm')" @confirm="confirmDelete(record)">
              <a-button size="small" danger>{{ t('common.delete') }}</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 新建 / 编辑字段：slug（仅新建）+ 字段定义编辑器 -->
    <a-modal
      v-model:open="editorOpen"
      :title="editingId ? t('kbMgmt.collEditFields') : t('kbMgmt.collCreate')"
      :confirm-loading="saving"
      :ok-button-props="{ disabled: !canSave }"
      @ok="submitSchema"
    >
      <a-alert
        v-if="!editingId"
        class="kb-coll-mgr__hint"
        type="info"
        :message="t('kbMgmt.collSlugHint')"
        show-icon
      />
      <a-form layout="vertical">
        <a-form-item v-if="!editingId" :label="t('kbMgmt.collSlug')">
          <a-input v-model:value="slug" :placeholder="t('kbMgmt.collSlugPlaceholder')" />
        </a-form-item>

        <a-form-item :label="t('kbMgmt.collFields')">
          <a-space direction="vertical" style="width: 100%" :size="8">
            <div v-for="(f, i) in fields" :key="i" class="kb-coll-mgr__field">
              <a-tooltip :title="t('kbMgmt.collFieldOrder')">
                <a-input-number
                  v-model:value="f.order"
                  :min="0"
                  :precision="0"
                  style="width: 72px"
                />
              </a-tooltip>
              <a-input
                v-model:value="f.name"
                :placeholder="t('kbMgmt.collFieldName')"
                style="width: 150px"
              />
              <a-select v-model:value="f.type" style="width: 110px" :options="typeOptions" />
              <a-tooltip :title="t('kbMgmt.collFieldEnabled')">
                <a-switch v-model:checked="f.enabled" size="small" />
              </a-tooltip>
              <a-tooltip :title="t('kbMgmt.collFieldEmbedding')">
                <a-switch v-model:checked="f.embedding" size="small" />
              </a-tooltip>
              <a-tooltip :title="t('kbMgmt.collFieldFilterable')">
                <a-switch v-model:checked="f.filterable" size="small" />
              </a-tooltip>
              <a-button size="small" danger @click="removeField(i)">{{ t('common.delete') }}</a-button>
            </div>
            <a-button size="small" @click="addField">{{ t('kbMgmt.collAddField') }}</a-button>
          </a-space>
          <div class="kb-coll-mgr__muted">{{ t('kbMgmt.collAtLeastOneEmbed') }}</div>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 重命名 -->
    <a-modal
      v-model:open="renameOpen"
      :title="t('kbMgmt.collRename')"
      :confirm-loading="saving"
      @ok="submitRename"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('kbMgmt.collSlug')">
          <a-input v-model:value="slug" :placeholder="t('kbMgmt.collSlugPlaceholder')" />
        </a-form-item>
        <a-alert
          class="kb-coll-mgr__hint"
          type="warning"
          :message="t('kbMgmt.collRenameHint')"
          show-icon
        />
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  createKnowledgeCollection,
  deleteKnowledgeCollection,
  listDocuments,
  listKnowledgeCollections,
  updateKnowledgeCollection,
  type KbCollectionItem,
  type KbSchemaField,
} from '@/api/kb'

const props = defineProps<{ knowledgeId: number }>()
const emit = defineEmits<{ changed: [] }>()
const { t } = useI18n()

const loading = ref(false)
const collections = ref<KbCollectionItem[]>([])
const editorOpen = ref(false)
const renameOpen = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const slug = ref('')
const fields = reactive<KbSchemaField[]>([])
// 按 collection_id 分组的引用文档（来自同知识库的文档列表）
const docGroups = ref<Record<number, any[]>>({})

function docsOf(id: number): any[] {
  return docGroups.value[id] || []
}

const typeOptions = [
  { label: 'string', value: 'string' },
  { label: 'number', value: 'number' },
  { label: 'boolean', value: 'boolean' },
]

const columns = [
  { title: t('kbMgmt.collName'), dataIndex: 'name', key: 'name' },
  { title: t('kbMgmt.collFieldCount'), dataIndex: 'field_count', key: 'field_count', width: 90 },
  { title: t('kbMgmt.collEmbedFields'), key: 'embed_fields', width: 220 },
  { title: t('kbMgmt.collRefFiles'), key: 'ref_files', width: 180 },
  { title: t('kbMgmt.common.actions'), key: 'op', width: 240 },
]

const canSave = computed(() => {
  const named = fields.filter((f) => (f.name || '').trim().length > 0)
  return named.length > 0 && named.some((f) => f.embedding)
})

async function load() {
  loading.value = true
  try {
    const [collRes, docRes] = await Promise.all([
      listKnowledgeCollections(props.knowledgeId),
      listDocuments(props.knowledgeId),
    ])
    collections.value = collRes?.items || []
    const groups: Record<number, any[]> = {}
    for (const d of (docRes || []) as any[]) {
      const cid = d.collection_id
      if (cid == null) continue
      ;(groups[cid] ||= []).push(d)
    }
    docGroups.value = groups
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.loadFailed'))
  } finally {
    loading.value = false
  }
}

function refresh() {
  emit('changed')
  load()
}

function addField() {
  fields.push({ name: '', type: 'string', enabled: true, embedding: false, filterable: false, order: fields.length })
}

function removeField(i: number) {
  fields.splice(i, 1)
}

function resetFields(list?: KbSchemaField[]) {
  const arr = (list || []).map((f, idx) => ({ ...f, order: f.order ?? idx }))
  arr.sort(
    (a, b) => (a.order ?? 0) - (b.order ?? 0) || (a.name || '').localeCompare(b.name || ''),
  )
  fields.splice(0, fields.length, ...arr)
}

function openCreate() {
  editingId.value = null
  slug.value = ''
  resetFields([{ name: '', type: 'string', enabled: true, embedding: true, filterable: false }])
  editorOpen.value = true
}

function openEditFields(item: KbCollectionItem) {
  editingId.value = item.id
  slug.value = ''
  resetFields(item.schema_config || [])
  editorOpen.value = true
}

function openRename(item: KbCollectionItem) {
  editingId.value = item.id
  // 取当前名除 kb_{kid} 前缀外的 slug（若有），便于微调
  const m = (item.name || '').match(/^kb_\d+_(.+)$/)
  slug.value = m ? m[1] : ''
  renameOpen.value = true
}

async function submitSchema() {
  if (!canSave.value) return
  saving.value = true
  try {
    const ordered = [...fields]
      .filter((f) => (f.name || '').trim().length > 0)
      .sort(
        (a, b) => (a.order ?? 0) - (b.order ?? 0) || (a.name || '').localeCompare(b.name || ''),
      )
    const schema_config = ordered.map((f) => ({
      name: f.name.trim(),
      type: f.type,
      enabled: !!f.enabled,
      embedding: !!f.embedding,
      filterable: !!f.filterable,
      order: f.order ?? 0,
    }))
    if (editingId.value) {
      await updateKnowledgeCollection(props.knowledgeId, editingId.value, { schema_config })
      message.success(t('kbMgmt.saved'))
    } else {
      await createKnowledgeCollection(props.knowledgeId, { slug: slug.value || undefined, schema_config })
      message.success(t('kbMgmt.collCreated'))
    }
    editorOpen.value = false
    refresh()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function submitRename() {
  saving.value = true
  try {
    await updateKnowledgeCollection(props.knowledgeId, editingId.value as number, { slug: slug.value })
    message.success(t('kbMgmt.saved'))
    renameOpen.value = false
    refresh()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function confirmDelete(item: KbCollectionItem) {
  saving.value = true
  try {
    await deleteKnowledgeCollection(props.knowledgeId, item.id)
    message.success(t('kbMgmt.common.deleted'))
    refresh()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.common.deleteFailed'))
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.kb-coll-mgr__bar {
  margin-bottom: 12px;
}
.kb-coll-mgr__tip {
  color: var(--fg-muted, #8f959e);
  font-size: 12px;
}
.kb-coll-mgr__field {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.kb-coll-mgr__muted {
  color: var(--fg-muted, #8f959e);
  font-size: 12px;
  margin-top: 4px;
}
.kb-coll-mgr__hint {
  margin-bottom: 12px;
}
.kb-coll-mgr__doc-list {
  max-width: 280px;
  max-height: 220px;
  overflow: auto;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
