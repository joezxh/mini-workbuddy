<template>
  <div>
    <a-button type="primary" @click="openCreate">{{ t('wikiMgmt.kb.create') }}</a-button>
    <a-table
      :columns="columns"
      :data-source="rows"
      :loading="loading"
      row-key="id"
      style="margin-top: 12px"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 1 ? 'green' : 'default'">
            {{ record.status === 1 ? t('wikiMgmt.enabled') : t('wikiMgmt.disabled') }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a @click="openEdit(record)">{{ t('common.edit') }}</a>
          <a-divider type="vertical" />
          <a-popconfirm :title="t('wikiMgmt.deleteConfirm')" @confirm="remove(record)">
            <a danger>{{ t('common.delete') }}</a>
          </a-popconfirm>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalOpen"
      :title="editing ? t('wikiMgmt.kb.edit') : t('wikiMgmt.kb.create')"
      @ok="save"
      :confirm-loading="saving"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('kbMgmt.common.name')" required>
          <a-input v-model:value="form.name" :placeholder="t('wikiMgmt.kb.namePlaceholder')" />
        </a-form-item>
        <a-form-item :label="t('skillHub.description')">
          <a-textarea v-model:value="form.description" :rows="3" :placeholder="t('skillHub.description')" />
        </a-form-item>
        <a-form-item :label="t('kbMgmt.common.status')">
          <a-radio-group v-model:value="form.status">
            <a-radio :value="1">{{ t('wikiMgmt.enabled') }}</a-radio>
            <a-radio :value="0">{{ t('wikiMgmt.disabled') }}</a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { listKnowledge, createKnowledge, updateKnowledge, deleteKnowledge } from '@/api/wiki.ts'

const { t } = useI18n()
const columns = computed(() => [
  { title: 'ID', dataIndex: 'id', key: 'id' },
  { title: t('kbMgmt.common.name'), dataIndex: 'name', key: 'name' },
  { title: t('skillHub.description'), dataIndex: 'description', key: 'description' },
  { title: t('kbMgmt.common.status'), key: 'status' },
  { title: t('kbMgmt.common.actions'), key: 'action' },
])
const rows = ref<any[]>([])
const loading = ref(false)
const modalOpen = ref(false)
const saving = ref(false)
const editing = ref<number | null>(null)
const form = ref({ name: '', description: '', status: 1 })

async function reload() {
  loading.value = true
  try {
    const res = await listKnowledge()
    rows.value = res.items || res || []
  } catch (e) {
    message.error(t('wikiMgmt.kb.loadFailed'))
  } finally {
    loading.value = false
  }
}
function openCreate() {
  editing.value = null
  form.value = { name: '', description: '', status: 1 }
  modalOpen.value = true
}
function openEdit(r: any) {
  editing.value = r.id
  form.value = { name: r.name, description: r.description || '', status: r.status }
  modalOpen.value = true
}
async function save() {
  if (!form.value.name.trim()) {
    message.warning(t('wikiMgmt.nameRequired'))
    return
  }
  saving.value = true
  try {
    if (editing.value) await updateKnowledge(editing.value, form.value)
    else await createKnowledge(form.value)
    message.success(t('wikiMgmt.saved'))
    modalOpen.value = false
    reload()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('wikiMgmt.saveFailed'))
  } finally {
    saving.value = false
  }
}
async function remove(r: any) {
  try {
    await deleteKnowledge(r.id)
    message.success(t('kbMgmt.common.deleted'))
    reload()
  } catch (e) {
    message.error(t('kbMgmt.common.deleteFailed'))
  }
}
onMounted(reload)
</script>
