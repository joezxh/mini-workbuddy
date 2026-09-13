<template>
  <StateWrapper :loading="loading" :error="error" :empty="!loading && !error && !sources.length" @retry="load">
    <div class="src-mgr">
      <div class="src-mgr__toolbar">
        <a-button type="primary" @click="openForm()">
          <PlusOutlined /> {{ t('kbMgmt.common.create') }}
        </a-button>
        <a-button @click="load"><ReloadOutlined /> {{ t('kbMgmt.common.refresh') }}</a-button>
      </div>

      <DataTable
        :columns="columns"
        :data-source="sources"
        :loading="loading"
        row-key="id"
        :page-visible="false"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="record.status === 'online' ? 'success' : 'default'">
              {{ record.status === 'online' ? t('kbMgmt.common.online') : t('kbMgmt.common.offline') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'has_password'">
            <a-tag v-if="record.has_password" color="blue">●</a-tag>
            <span v-else class="muted">—</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button size="small" @click="test(record)"><ThunderboltOutlined /> {{ t('kbMgmt.ds.testConn') }}</a-button>
            <a-button size="small" @click="openForm(record)">{{ t('kbMgmt.common.edit') }}</a-button>
            <a-popconfirm :title="t('kbMgmt.common.deleteConfirm')" @confirm="remove(record)">
              <a-button size="small" danger>{{ t('kbMgmt.common.delete') }}</a-button>
            </a-popconfirm>
          </template>
        </template>
      </DataTable>

      <a-modal v-model:open="formOpen" :title="form.id ? t('kbMgmt.common.edit') : t('kbMgmt.common.create')" @ok="save">
        <a-form :model="form" layout="vertical">
          <a-form-item :label="t('kbMgmt.common.name')" required><a-input v-model:value="form.name" /></a-form-item>
          <a-form-item :label="t('kbMgmt.common.type')" required>
            <a-select v-model:value="form.source_type">
              <a-select-option value="mysql">mysql</a-select-option>
              <a-select-option value="doris">doris</a-select-option>
              <a-select-option value="postgresql">postgresql</a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item :label="t('kbMgmt.ds.host')" required><a-input v-model:value="form.host" /></a-form-item>
          <a-form-item :label="t('kbMgmt.ds.port')" required><a-input-number v-model:value="form.port" :min="1" :max="65535" style="width:100%" /></a-form-item>
          <a-form-item :label="t('kbMgmt.ds.username')"><a-input v-model:value="form.username" /></a-form-item>
          <a-form-item :label="t('kbMgmt.ds.password')">
            <a-input-password v-model:value="form.password" :placeholder="t('kbMgmt.ds.passwordHint')" />
          </a-form-item>
          <a-form-item :label="t('kbMgmt.ds.defaultDb')"><a-input v-model:value="form.database" /></a-form-item>
          <a-form-item :label="t('kbMgmt.ds.charset')"><a-input v-model:value="form.charset" placeholder="utf8mb4" /></a-form-item>
        </a-form>
      </a-modal>
    </div>
  </StateWrapper>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined, ThunderboltOutlined } from '@ant-design/icons-vue'
import DataTable from '@/components/common/DataTable/index.vue'
import StateWrapper from '@/components/common/StateWrapper.vue'
import * as api from '@/api/dataops'

const { t } = useI18n()
const sources = ref<any[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const formOpen = ref(false)
const form = ref<any>({})

const columns = computed(() => [
  { title: t('kbMgmt.common.name'), dataIndex: 'name', key: 'name' },
  { title: t('kbMgmt.common.type'), dataIndex: 'source_type', key: 'source_type', width: 110 },
  { title: t('kbMgmt.ds.address'), key: 'addr', customRender: ({ record }: any) => `${record.host}:${record.port}` },
  { title: t('kbMgmt.ds.defaultDb'), dataIndex: 'database', key: 'database' },
  { title: t('kbMgmt.common.status'), key: 'status', width: 90 },
  { title: t('kbMgmt.ds.password'), key: 'has_password', width: 70 },
  { title: t('kbMgmt.common.actions'), key: 'action', width: 200 },
])

async function load() {
  loading.value = true
  error.value = null
  try {
    const r: any = await api.listSources()
    sources.value = r.data || r || []
  } catch (e: any) {
    error.value = e?.message || t('kbMgmt.common.error')
  } finally {
    loading.value = false
  }
}

function openForm(row?: any) {
  form.value = row ? { ...row, password: '' } : { source_type: 'mysql', port: 3306, charset: 'utf8mb4' }
  formOpen.value = true
}

async function save() {
  try {
    if (form.value.id) await api.updateSource(form.value.id, form.value)
    else await api.createSource(form.value)
    message.success(t('kbMgmt.ds.saveSuccess'))
    formOpen.value = false
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || t('kbMgmt.ds.saveFailed'))
  }
}

async function remove(row: any) {
  try {
    await api.deleteSource(row.id)
    message.success(t('kbMgmt.common.deleted'))
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || t('kbMgmt.common.deleteFailed'))
  }
}

async function test(row: any) {
  try {
    await api.testSource(row.id)
    message.success(t('kbMgmt.ds.testOk'))
  } catch (e: any) {
    message.warning(t('kbMgmt.ds.testNotImplemented'))
  }
}

onMounted(load)
</script>

<style scoped>
.src-mgr__toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
.muted { color: var(--fg-muted); }
</style>
