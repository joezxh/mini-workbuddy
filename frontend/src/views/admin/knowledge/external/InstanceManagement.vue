<template>
  <div class="ext-inst">
    <div class="ext-inst__toolbar">
      <a-button type="primary" @click="openForm()"><PlusOutlined /> {{ t('knowledge.common.create') }}</a-button>
      <a-button @click="load"><ReloadOutlined /> {{ t('knowledge.common.refresh') }}</a-button>
    </div>
    <DataTable :columns="columns" :data-source="instances" :loading="loading" row-key="id" :page-visible="false">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'sync_enabled'">
          <a-switch :checked="record.sync_enabled" @change="(v: boolean) => toggleSync(record, v)" />
        </template>
        <template v-else-if="column.key === 'action'">
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
        <a-form-item label="类型">
          <a-select v-model:value="form.connector_type" @change="loadConfig">
            <a-select-option v-for="tp in types" :key="tp" :value="tp">{{ tp }}</a-select-option>
          </a-select>
        </a-form-item>
        <!-- 声明式表单：按后端 getCreateParamsConfig() 的 schema 动态渲染 -->
        <template v-for="f in configFields" :key="f.key">
          <a-form-item :label="f.label" v-if="f.type === 'password'">
            <a-input-password v-model:value="form[f.key]" :placeholder="f.placeholder" />
          </a-form-item>
          <a-form-item :label="f.label" v-else-if="f.type === 'number'">
            <a-input-number v-model:value="form[f.key]" :min="f.min" :max="f.max" style="width:100%" />
          </a-form-item>
          <a-form-item :label="f.label" v-else>
            <a-input v-model:value="form[f.key]" :placeholder="f.placeholder" />
          </a-form-item>
        </template>
        <a-form-item label="开启同步">
          <a-switch v-model:checked="form.sync_enabled" />
        </a-form-item>
        <a-form-item label="目标数据集" v-if="form.sync_enabled"><a-input v-model:value="form.kb_dataset" /></a-form-item>
        <a-form-item label="同步间隔(分)" v-if="form.sync_enabled"><a-input-number v-model:value="form.sync_interval_min" :min="1" style="width:100%" /></a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import DataTable from '@/components/common/DataTable/index.vue'
import * as api from '@/api/externalKb'

const { t } = useI18n()
const instances = ref<any[]>([])
const loading = ref(false)
const formOpen = ref(false)
const form = ref<any>({})
const types = ['notion', 'confluence', 'web', 's3']
const configFields = ref<any[]>([])

const columns = [
  { title: t('knowledge.common.name'), dataIndex: 'name', key: 'name' },
  { title: '类型', dataIndex: 'connector_type', key: 'connector_type', width: 120 },
  { title: '同步', key: 'sync_enabled', width: 80 },
  { title: '目标数据集', dataIndex: 'kb_dataset', key: 'kb_dataset' },
  { title: '最近同步', dataIndex: 'last_sync_at', key: 'last_sync_at', width: 160 },
  { title: t('knowledge.common.actions'), key: 'action', width: 150 },
]

async function load() {
  loading.value = true
  try {
    const r: any = await api.listInstances()
    instances.value = r.data || r || []
  } catch (e: any) {
    message.warning('外部知识库后端 router 未注册（/api/v1/connectors），列表为空')
  } finally {
    loading.value = false
  }
}
async function loadConfig(type: string) {
  try {
    const r: any = await api.getCreateParamsConfig(type)
    configFields.value = (r.data?.options || r.options || [])
  } catch {
    configFields.value = [{ key: 'token', label: 'Token', type: 'password', required: true }]
  }
}
function openForm(row?: any) {
  form.value = row ? { ...row } : { connector_type: 'notion', sync_enabled: false }
  formOpen.value = true
  loadConfig(form.value.connector_type)
}
async function save() {
  try {
    if (form.value.id) await api.updateInstance(form.value.id, form.value)
    else await api.createInstance(form.value)
    message.success('保存成功')
    formOpen.value = false
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '保存失败（需后端 router）')
  }
}
async function remove(row: any) {
  try {
    await api.deleteInstance(row.id)
    load()
  } catch (e: any) {
    message.error('删除失败（需后端 router）')
  }
}
async function toggleSync(row: any, v: boolean) {
  try {
    await api.setSync(row.id, v)
    message.success('已更新同步开关')
    load()
  } catch {
    message.warning('同步开关需后端 router')
  }
}
onMounted(load)
</script>

<style scoped>
.ext-inst__toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
</style>
