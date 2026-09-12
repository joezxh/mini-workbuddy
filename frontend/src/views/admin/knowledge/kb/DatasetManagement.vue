<template>
  <div class="kb-ds">
    <div class="kb-ds__toolbar">
      <a-button type="primary" @click="openForm()"><PlusOutlined /> {{ t('knowledge.common.create') }}</a-button>
      <a-button @click="load"><ReloadOutlined /> {{ t('knowledge.common.refresh') }}</a-button>
    </div>
    <DataTable :columns="columns" :data-source="datasets" :loading="loading" row-key="kb_id" :page-visible="false">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'action'">
          <a-button size="small" @click="rebuild(record)">重建索引</a-button>
          <a-popconfirm :title="t('knowledge.common.deleteConfirm')" @confirm="remove(record)">
            <a-button size="small" danger>{{ t('knowledge.common.delete') }}</a-button>
          </a-popconfirm>
        </template>
      </template>
    </DataTable>

    <a-modal v-model:open="formOpen" :title="t('knowledge.common.create')" @ok="save">
      <a-form :model="form" layout="vertical">
        <a-form-item label="名称" required><a-input v-model:value="form.name" /></a-form-item>
        <a-form-item label="Embedding 模型">
          <a-select v-model:value="form.embedding_model">
            <a-select-option v-for="m in embeddingModels" :key="m.id" :value="m.id">{{ m.name || m.id }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="切片器">
          <a-select v-model:value="form.chunker">
            <a-select-option v-for="c in chunkers" :key="c.key" :value="c.key">{{ c.label || c.key }}</a-select-option>
          </a-select>
        </a-form-item>
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
import * as api from '@/api/knowledgeBase'

const { t } = useI18n()
const datasets = ref<any[]>([])
const loading = ref(false)
const formOpen = ref(false)
const form = ref<any>({})
const embeddingModels = ref<any[]>([])
const chunkers = ref<any[]>([])

const columns = [
  { title: t('knowledge.common.name'), dataIndex: 'name', key: 'name' },
  { title: 'Embedding', dataIndex: 'embedding_model', key: 'embedding_model' },
  { title: '维度', dataIndex: 'dimension', key: 'dimension', width: 90 },
  { title: '切片器', dataIndex: 'chunker', key: 'chunker', width: 120 },
  { title: '文档数', dataIndex: 'doc_count', key: 'doc_count', width: 90 },
  { title: t('knowledge.common.actions'), key: 'action', width: 160 },
]

async function load() {
  loading.value = true
  try {
    const r: any = await api.listDatasets()
    datasets.value = r.data || r || []
  } finally {
    loading.value = false
  }
}
async function loadCaps() {
  try {
    const em: any = await api.getEmbeddingModels()
    embeddingModels.value = em.data || em || []
    const ck: any = await api.getChunkers()
    chunkers.value = ck.data || ck || []
  } catch {
    /* 能力发现端点未就绪时忽略 */
  }
}
function openForm() {
  form.value = {}
  formOpen.value = true
}
async function save() {
  try {
    await api.createDataset(form.value)
    message.success('创建成功')
    formOpen.value = false
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '创建失败')
  }
}
async function remove(row: any) {
  try {
    await api.deleteDataset(row.kb_id)
    message.success('已删除')
    load()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '删除失败')
  }
}
function rebuild(row: any) {
  message.info(`数据集 ${row.name} 重建索引：后端 RAG Service 提供重建入口（见设计文档 §8.1）`)
}
onMounted(async () => {
  await loadCaps()
  load()
})
</script>

<style scoped>
.kb-ds__toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
</style>
