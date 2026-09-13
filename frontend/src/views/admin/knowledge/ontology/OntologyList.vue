<template>
  <div class="onto-list">
    <div class="onto-list__toolbar">
      <a-button type="primary" @click="openForm()"><PlusOutlined /> {{ t('kbMgmt.common.create') }}</a-button>
      <a-button @click="load"><ReloadOutlined /> {{ t('kbMgmt.common.refresh') }}</a-button>
    </div>
    <DataTable :columns="columns" :data-source="list" :loading="loading" row-key="id" :page-visible="false">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'success' : 'default'">{{ record.status }}</a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button size="small" @click="doExport(record)">{{ t('kbMgmt.ont.exportTtl') }}</a-button>
          <a-upload
            :before-upload="(f: File) => doImport(record, f)"
            :show-upload-list="false"
            accept=".ttl"
          ><a-button size="small">{{ t('kbMgmt.ont.importTtl') }}</a-button></a-upload>
          <a-button size="small" @click="openForm(record)">{{ t('kbMgmt.common.edit') }}</a-button>
          <a-popconfirm :title="t('kbMgmt.common.deleteConfirm')" @confirm="remove(record)">
            <a-button size="small" danger>{{ t('kbMgmt.common.delete') }}</a-button>
          </a-popconfirm>
        </template>
      </template>
    </DataTable>

    <a-modal v-model:open="formOpen" :title="form.id ? t('kbMgmt.common.edit') : t('kbMgmt.common.create')" @ok="save">
      <a-form :model="form" layout="vertical">
        <a-form-item :label="t('kbMgmt.ont.code')" required><a-input v-model:value="form.code" /></a-form-item>
        <a-form-item :label="t('kbMgmt.common.name')" required><a-input v-model:value="form.name" /></a-form-item>
        <a-form-item :label="t('kbMgmt.ont.namespace')"><a-input v-model:value="form.namespace" /></a-form-item>
        <a-form-item :label="t('kbMgmt.ont.version')"><a-input v-model:value="form.version" /></a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import DataTable from '@/components/common/DataTable/index.vue'
import * as api from '@/api/ontology'

const { t } = useI18n()
const list = ref<any[]>([])
const loading = ref(false)
const formOpen = ref(false)
const form = ref<any>({})

const columns = computed(() => [
  { title: t('kbMgmt.ont.code'), dataIndex: 'code', key: 'code', width: 140 },
  { title: t('kbMgmt.common.name'), dataIndex: 'name', key: 'name' },
  { title: t('kbMgmt.ont.namespace'), dataIndex: 'namespace', key: 'namespace' },
  { title: t('kbMgmt.ont.version'), dataIndex: 'version', key: 'version', width: 90 },
  { title: t('kbMgmt.common.status'), key: 'status', width: 90 },
  { title: t('kbMgmt.common.actions'), key: 'action', width: 230 },
])

async function load() {
  loading.value = true
  try {
    const r: any = await api.listOntologies()
    list.value = r.data || r || []
  } catch (e: any) {
    message.warning(t('kbMgmt.ont.routerMissing'))
  } finally {
    loading.value = false
  }
}
function openForm(row?: any) {
  form.value = row ? { ...row } : {}
  formOpen.value = true
}
async function save() {
  try {
    if (form.value.id) await api.updateOntology(form.value.id, form.value)
    else await api.createOntology(form.value)
    message.success(t('kbMgmt.ont.saveSuccess'))
    formOpen.value = false
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.ont.saveFailed'))
  }
}
async function remove(row: any) {
  try {
    await api.deleteOntology(row.id)
    load()
  } catch {
    message.error(t('kbMgmt.ont.deleteFailed'))
  }
}
async function doExport(row: any) {
  try {
    const r: any = await api.exportTtl(row.id)
    const blob = r.data || r
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${row.code}.ttl`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    message.warning(t('kbMgmt.ont.exportRouterMissing'))
  }
}
async function doImport(row: any, file: File) {
  try {
    await api.importTtl(row.id, file)
    message.success(t('kbMgmt.ont.importSuccess'))
    load()
  } catch {
    message.error(t('kbMgmt.ont.importFailed'))
  }
  return false
}
onMounted(load)
</script>

<style scoped>
.onto-list__toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
</style>
