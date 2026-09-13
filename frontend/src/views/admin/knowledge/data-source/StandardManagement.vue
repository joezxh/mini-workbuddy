<template>
  <div class="std-mgr">
    <div class="std-mgr__toolbar">
      <a-button type="primary" @click="openForm()"><PlusOutlined /> {{ t('kbMgmt.common.create') }}</a-button>
      <a-button @click="seed"><DatabaseOutlined /> {{ t('kbMgmt.std.seed') }}</a-button>
      <a-button @click="load"><ReloadOutlined /> {{ t('kbMgmt.common.refresh') }}</a-button>
    </div>
    <DataTable :columns="columns" :data-source="standards" :loading="loading" row-key="id" :page-visible="false">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'aliases'">{{ (record.aliases || []).join(', ') || '—' }}</template>
        <template v-else-if="column.key === 'action'">
          <a-button size="small" @click="openForm(record)">{{ t('kbMgmt.common.edit') }}</a-button>
          <a-popconfirm :title="t('kbMgmt.common.deleteConfirm')" @confirm="remove(record)">
            <a-button size="small" danger>{{ t('kbMgmt.common.delete') }}</a-button>
          </a-popconfirm>
        </template>
      </template>
    </DataTable>

    <a-modal v-model:open="formOpen" :title="form.id ? t('kbMgmt.common.edit') : t('kbMgmt.common.create')" @ok="save">
      <a-form :model="form" layout="vertical">
        <a-form-item label="code" required><a-input v-model:value="form.code" /></a-form-item>
        <a-form-item :label="t('kbMgmt.common.name')" required><a-input v-model:value="form.name" /></a-form-item>
        <a-form-item :label="t('kbMgmt.std.semanticType')"><a-input v-model:value="form.semantic_type" /></a-form-item>
        <a-form-item :label="t('kbMgmt.std.dataTypeExpect')"><a-input v-model:value="form.data_type_expect" /></a-form-item>
        <a-form-item :label="t('kbMgmt.std.securityLevel')"><a-input v-model:value="form.security_level" /></a-form-item>
        <a-form-item :label="t('kbMgmt.meta.domain')"><a-input v-model:value="form.domain" /></a-form-item>
        <a-form-item :label="t('kbMgmt.std.aliases')"><a-input v-model:value="aliasesText" /></a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined, DatabaseOutlined } from '@ant-design/icons-vue'
import DataTable from '@/components/common/DataTable/index.vue'
import * as api from '@/api/dataops'

const { t } = useI18n()
const standards = ref<any[]>([])
const loading = ref(false)
const formOpen = ref(false)
const form = ref<any>({})
const aliasesText = ref('')

const columns = computed(() => [
  { title: 'code', dataIndex: 'code', key: 'code', width: 160 },
  { title: t('kbMgmt.common.name'), dataIndex: 'name', key: 'name' },
  { title: t('kbMgmt.std.semanticType'), dataIndex: 'semantic_type', key: 'semantic_type', width: 130 },
  { title: t('kbMgmt.std.dataTypeExpect'), dataIndex: 'data_type_expect', key: 'data_type_expect', width: 120 },
  { title: t('kbMgmt.std.securityLevel'), dataIndex: 'security_level', key: 'security_level', width: 100 },
  { title: t('kbMgmt.std.aliases'), key: 'aliases' },
  { title: t('kbMgmt.common.actions'), key: 'action', width: 140 },
])

async function load() {
  loading.value = true
  try {
    const r: any = await api.listStandards()
    standards.value = r.data || r || []
  } finally {
    loading.value = false
  }
}
function openForm(row?: any) {
  form.value = row ? { ...row } : {}
  aliasesText.value = row?.aliases ? row.aliases.join(',') : ''
  formOpen.value = true
}
async function save() {
  const payload = { ...form.value, aliases: aliasesText.value.split(',').map((s) => s.trim()).filter(Boolean) }
  try {
    if (form.value.id) await api.createStandard(payload)
    else await api.createStandard(payload)
    message.success(t('kbMgmt.std.saveSuccess'))
    formOpen.value = false
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.std.saveFailed'))
  }
}
async function remove(_row?: any) {
  message.info(t('kbMgmt.std.deleteNotImplemented'))
}
async function seed() {
  try {
    await api.seedStandards()
    message.success(t('kbMgmt.std.seeded'))
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.std.seedFailed'))
  }
}
onMounted(load)
</script>

<style scoped>
.std-mgr__toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
</style>
