<template>
  <StateWrapper :loading="loading" :error="error" :empty="!loading && !error && !sources.length" @retry="load">
    <div class="src-mgr">
      <div class="src-mgr__toolbar">
        <a-button type="primary" @click="openForm()">
          <PlusOutlined /> {{ t('knowledge.common.create') }}
        </a-button>
        <a-button @click="load"><ReloadOutlined /> {{ t('knowledge.common.refresh') }}</a-button>
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
              {{ record.status === 'online' ? t('knowledge.common.online') : t('knowledge.common.offline') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'has_password'">
            <a-tag v-if="record.has_password" color="blue">●</a-tag>
            <span v-else class="muted">—</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button size="small" @click="test(record)"><ThunderboltOutlined /> 探活</a-button>
            <a-button size="small" @click="openForm(record)">{{ t('knowledge.common.edit') }}</a-button>
            <a-popconfirm :title="t('knowledge.common.deleteConfirm')" @confirm="remove(record)">
              <a-button size="small" danger>{{ t('knowledge.common.delete') }}</a-button>
            </a-popconfirm>
          </template>
        </template>
      </DataTable>

      <a-modal v-model:open="formOpen" :title="form.id ? t('knowledge.common.edit') : t('knowledge.common.create')" @ok="save">
        <a-form :model="form" layout="vertical">
          <a-form-item label="名称" required><a-input v-model:value="form.name" /></a-form-item>
          <a-form-item label="类型" required>
            <a-select v-model:value="form.source_type">
              <a-select-option value="mysql">mysql</a-select-option>
              <a-select-option value="doris">doris</a-select-option>
              <a-select-option value="postgresql">postgresql</a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="主机" required><a-input v-model:value="form.host" /></a-form-item>
          <a-form-item label="端口" required><a-input-number v-model:value="form.port" :min="1" :max="65535" style="width:100%" /></a-form-item>
          <a-form-item label="用户名"><a-input v-model:value="form.username" /></a-form-item>
          <a-form-item label="密码">
            <a-input-password v-model:value="form.password" placeholder="留空=不修改" />
          </a-form-item>
          <a-form-item label="默认库"><a-input v-model:value="form.database" /></a-form-item>
          <a-form-item label="字符集"><a-input v-model:value="form.charset" placeholder="utf8mb4" /></a-form-item>
        </a-form>
      </a-modal>
    </div>
  </StateWrapper>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
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

const columns = [
  { title: t('knowledge.common.name'), dataIndex: 'name', key: 'name' },
  { title: '类型', dataIndex: 'source_type', key: 'source_type', width: 110 },
  { title: '地址', key: 'addr', customRender: ({ record }: any) => `${record.host}:${record.port}` },
  { title: '默认库', dataIndex: 'database', key: 'database' },
  { title: t('knowledge.common.status'), key: 'status', width: 90 },
  { title: '密码', key: 'has_password', width: 70 },
  { title: t('knowledge.common.actions'), key: 'action', width: 200 },
]

async function load() {
  loading.value = true
  error.value = null
  try {
    const r: any = await api.listSources()
    sources.value = r.data || r || []
  } catch (e: any) {
    error.value = e?.message || t('knowledge.common.error')
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
    message.success('保存成功')
    formOpen.value = false
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || '保存失败')
  }
}

async function remove(row: any) {
  try {
    await api.deleteSource(row.id)
    message.success('已删除')
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '删除失败')
  }
}

async function test(row: any) {
  try {
    await api.testSource(row.id)
    message.success('探活成功')
  } catch (e: any) {
    message.warning('探活端点未实现（后端 /sources/{id}/test 待补齐）')
  }
}

onMounted(load)
</script>

<style scoped>
.src-mgr__toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
.muted { color: var(--fg-muted); }
</style>
